import uuid

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response
from sqlalchemy import delete, select

from .. import audit
from ..auth import (Admin, DbDep, UserDep, check_admin_grant, clear_session_cookie, demo_token, issue_session,
                    issue_token, require_roles, set_session_cookie, user_by_token)
from ..enums import (
    SECTION_TITLES,
    Channel,
    Decision,
    FlagStatus,
    FlagType,
    MeasureStatus,
    ProgramStatus,
    RecStatus,
    ReportType,
    RiskLevel,
    Role,
)
from ..models import MeasureAssignment, OrgUnit, Reminder, User, UserContact, utcnow
from ..schemas import domain as s
from ..config import settings
from ..schemas import AiSettings, AiSettingsIn
from ..services import assistant, importer, notify
from ..services.control import RULES

router = APIRouter(tags=["Admin"])

USER_FIELDS = ("display_name", "role", "org_unit_id")


@router.get("/admin/users", response_model=list[s.UserOut])
def list_users(db: DbDep, _: Admin):
    return db.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.display_name)).all()


def _get_user(db, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if not u or u.deleted_at:
        raise HTTPException(404, "Користувача не знайдено")
    return u


@router.post("/admin/users", response_model=s.UserWithToken, status_code=201)
def create_user(data: s.UserCreate, db: DbDep, admin: Admin):
    """Створює користувача і повертає його токен (показується лише один раз)."""
    if data.role == Role.ADMIN:
        check_admin_grant(data.admin_password)
    u = User(**data.model_dump(exclude={"admin_password"}))
    token = issue_token(u)
    db.add(u)
    db.flush()
    audit.record(db, admin, "user", u.id, "create", None, audit.snapshot(u, *USER_FIELDS))
    db.commit()
    return s.UserWithToken(**s.UserOut.model_validate(u).model_dump(), token=token,
                           token_expires_at=u.token_expires_at)


@router.post("/admin/users/{user_id}/token", response_model=s.UserWithToken)
def reissue_token(
    user_id: uuid.UUID, db: DbDep, admin: Admin,
    admin_password: Annotated[str | None, Header(alias="X-Admin-Password")] = None,
):
    """Видає новий токен; попередній одразу перестає діяти."""
    u = _get_user(db, user_id)
    if u.role == Role.ADMIN and u.id != admin.id:
        check_admin_grant(admin_password)
    token = issue_token(u)
    audit.record(db, admin, "user", u.id, "reissue_token", None, None)
    db.commit()
    return s.UserWithToken(**s.UserOut.model_validate(u).model_dump(), token=token,
                           token_expires_at=u.token_expires_at)


@router.patch("/admin/users/{user_id}", response_model=s.UserOut)
def patch_user(user_id: uuid.UUID, data: s.UserPatch, db: DbDep, admin: Admin):
    u = _get_user(db, user_id)
    changes = data.model_dump(exclude_unset=True, exclude={"admin_password"})
    if u.id == admin.id and changes.get("role", Role.ADMIN) != Role.ADMIN:
        raise HTTPException(409, "Не можна зняти роль адміністратора із себе")
    if "role" in changes and (changes["role"] == Role.ADMIN) != (u.role == Role.ADMIN):
        check_admin_grant(data.admin_password)
    old = audit.snapshot(u, *USER_FIELDS)
    for k, v in changes.items():
        setattr(u, k, v)
    db.flush()
    audit.record(db, admin, "user", u.id, "update", old, audit.snapshot(u, *USER_FIELDS))
    db.commit()
    return u


@router.delete("/admin/users/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID, db: DbDep, admin: Admin,
    admin_password: Annotated[str | None, Header(alias="X-Admin-Password")] = None,
):
    """Видаляє обліковий запис: токен перестає діяти, користувач зникає зі списків і розсилок."""
    u = _get_user(db, user_id)
    if u.id == admin.id:
        raise HTTPException(409, "Не можна видалити власний обліковий запис")
    if u.role == Role.ADMIN:
        check_admin_grant(admin_password)
    old = audit.snapshot(u, *USER_FIELDS)
    for a in db.scalars(select(MeasureAssignment).where(MeasureAssignment.user_id == u.id)):
        a.user_id = None
    db.execute(delete(UserContact).where(UserContact.user_id == u.id))
    db.execute(delete(Reminder).where(Reminder.user_id == u.id, Reminder.sent.is_(False)))
    u.token_hash = None
    u.deleted_at = utcnow()
    db.flush()
    audit.record(db, admin, "user", u.id, "delete", old, None)
    db.commit()
    return Response(status_code=204)


@router.get("/admin/org-units", response_model=list[s.OrgUnitOut])
def list_units(db: DbDep, _: UserDep):
    return db.scalars(select(OrgUnit).order_by(OrgUnit.name)).all()


@router.post("/admin/org-units", response_model=s.OrgUnitOut, status_code=201)
def create_unit(data: s.OrgUnitIn, db: DbDep, admin: Admin):
    ou = OrgUnit(**data.model_dump())
    db.add(ou)
    db.flush()
    audit.record(db, admin, "org_unit", ou.id, "create", None, data.model_dump())
    db.commit()
    return ou


@router.get("/admin/settings/ai", response_model=AiSettings)
def ai_settings(db: DbDep, _: Admin) -> AiSettings:
    return AiSettings(enabled=assistant.ai_enabled(db), available=settings.ai_enabled)


@router.put("/admin/settings/ai", response_model=AiSettings)
def set_ai_settings(data: AiSettingsIn, db: DbDep, admin: Admin) -> AiSettings:
    """Вимкнений ШІ: `/ai/*` з моделлю → 503, внесення документом працює лише за правилами зразка."""
    if data.enabled and not settings.ai_enabled:
        raise HTTPException(409, "ШІ вимкнено в налаштуваннях середовища (AI_ENABLED=false)")
    assistant.set_ai_enabled(db, admin, data.enabled)
    db.commit()
    return AiSettings(enabled=assistant.ai_enabled(db), available=settings.ai_enabled)


@router.get("/admin/dictionaries")
def dictionaries(_: UserDep) -> dict:
    """Довідники для фронтенду: enum-и, назви розділів, правила Risk Flags."""
    enum_map = lambda e: [m.value for m in e]  # noqa: E731
    return {
        "measureStatus": enum_map(MeasureStatus),
        "flagType": enum_map(FlagType),
        "flagStatus": enum_map(FlagStatus),
        "recStatus": enum_map(RecStatus),
        "decision": enum_map(Decision),
        "channel": enum_map(Channel),
        "reportType": enum_map(ReportType),
        "role": enum_map(Role),
        "riskLevel": enum_map(RiskLevel),
        "programStatus": enum_map(ProgramStatus),
        "sections": [{"number": n, "title": t} for n, t in SECTION_TITLES.items()],
        "flagRules": [{"type": t.value, "ruleCode": c, "description": d} for t, (c, d) in RULES.items()],
    }


@router.post("/auth/login", response_model=s.LoginOut, tags=["Auth"])
def login(data: s.LoginIn, db: DbDep, response: Response):
    """Обмінює персональний токен на сеанс з обмеженим строком дії.
    Браузер отримує сеанс у cookie HttpOnly (скрипти сторінки його не бачать) і далі нічого не зберігає сам.
    Скрипти й інтеграції можуть узяти `sessionToken` і слати `Authorization: Bearer <sessionToken>`;
    оновлений токен тоді приходить у заголовку `X-Session-Token`."""
    u = user_by_token(db, data.token)
    if not u or u.deleted_at is not None:
        raise HTTPException(401, "Невірний або недійсний токен")
    token, expires = issue_session(u)
    set_session_cookie(response, token, expires)
    return s.LoginOut(**s.UserOut.model_validate(u).model_dump(), session_token=token, expires_at=expires)


@router.post("/auth/logout", status_code=204, tags=["Auth"])
def logout(response: Response) -> Response:
    """Вихід: прибирає cookie сеансу. Працює і з уже простроченим сеансом."""
    clear_session_cookie(response)
    response.status_code = 204
    return response


DEMO_NAMES = ("coord", "head", "head-sector", "analyst", "admin", "ex-proc", "ex-hr", "ex-fin", "ex-com", "ex-log",
              "ex-legal", "ex-it", "ex-aud", *(f"ex-p{i:02d}" for i in range(1, 31)))


@router.get("/auth/demo-accounts", response_model=list[s.UserWithToken], tags=["Auth"])
def demo_accounts(db: DbDep):
    """Демо-акаунти для кнопок входу. Лише якщо явно ввімкнено DEMO_LOGIN; токени — від DEMO_TOKEN_SECRET."""
    if not settings.demo_login:
        return []
    out = []
    for name in DEMO_NAMES:
        token = demo_token(name)
        if (u := user_by_token(db, token)) is not None and u.deleted_at is None:
            out.append(s.UserWithToken(**s.UserOut.model_validate(u).model_dump(), token=token))
    return out


@router.get("/auth/me", response_model=s.UserOut, tags=["Auth"])
def me(user: UserDep):
    return user


def _contacts(db, user_id: uuid.UUID) -> list[UserContact]:
    return list(db.scalars(select(UserContact).where(UserContact.user_id == user_id).order_by(UserContact.channel)))


def _set_contacts(db, actor: User, target: User, items: list[s.ContactIn]) -> list[UserContact]:
    if len({c.channel for c in items}) != len(items):
        raise HTTPException(422, "Один контакт на канал")
    for c in items:
        if err := notify.validate_address(c.channel, c.address.strip()):
            raise HTTPException(422, f"{c.channel}: {err}")
    old = {c.channel.value: c.address for c in _contacts(db, target.id)}
    for c in _contacts(db, target.id):
        db.delete(c)
    db.flush()
    for c in items:
        db.add(UserContact(user_id=target.id, channel=c.channel, address=c.address.strip()))
    db.flush()
    audit.record(db, actor, "user", target.id, "contacts", old, {c.channel.value: c.address for c in items})
    db.commit()
    return _contacts(db, target.id)


@router.get("/auth/me/contacts", response_model=list[s.ContactOut], tags=["Auth"])
def my_contacts(db: DbDep, user: UserDep):
    """Куди, крім застосунку, надсилати нагадування: e-mail (EMAIL)."""
    return _contacts(db, user.id)


@router.put("/auth/me/contacts", response_model=list[s.ContactOut], tags=["Auth"])
def set_my_contacts(data: list[s.ContactIn], db: DbDep, user: UserDep):
    return _set_contacts(db, user, user, data)


@router.put("/admin/users/{user_id}/contacts", response_model=list[s.ContactOut])
def set_user_contacts(user_id: uuid.UUID, data: list[s.ContactIn], db: DbDep, admin: Admin):
    u = _get_user(db, user_id)
    return _set_contacts(db, admin, u, data)


@router.post("/admin/import", response_model=importer.ImportResult)
def import_data(
    data: importer.ImportPayload, db: DbDep, user: UserDep,
    dry_run: Annotated[bool, Query(alias="dryRun")] = False,
):
    """Імпорт набору даних (підрозділи, користувачі, ризики, індикатори, програми із заходами)."""
    require_roles(Role.ADMIN, Role.COORDINATOR)(user)
    accounts = bool(data.org_units or data.users)
    program_data = bool(data.risks or data.indicators or data.programs)
    if user.role == Role.ADMIN and program_data:
        raise HTTPException(403, "Програми, ризики й індикатори імпортує координатор")
    if user.role == Role.COORDINATOR and accounts:
        raise HTTPException(403, "Підрозділи й користувачів імпортує адміністратор")
    return importer.run_import(db, data, user, dry_run=dry_run)
