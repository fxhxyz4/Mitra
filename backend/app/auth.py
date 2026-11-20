import hashlib
import hmac
import secrets
import time
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .enums import Role
from .models import Measure, User, as_utc, utcnow

DbDep = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False, description="Персональний токен користувача")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(user: User, token: str | None = None) -> str:
    if token is None:
        token = secrets.token_urlsafe(32)
        user.token_expires_at = utcnow() + timedelta(days=settings.token_days) if settings.token_days > 0 else None
    else:
        user.token_expires_at = None
    user.token_hash = hash_token(token)
    return token


def token_expired(user: User) -> bool:
    return user.token_expires_at is not None and as_utc(user.token_expires_at) <= utcnow()


def demo_token(name: str) -> str:
    if settings.demo_public_tokens:
        return f"demo-{name}"
    if settings.demo_token_secret:
        tag = hmac.new(settings.demo_token_secret.encode(), name.encode(), hashlib.sha256).hexdigest()[:12]
        return f"demo-{name}-{tag}"
    raise RuntimeError("Демо-дані увімкнено, але не задано DEMO_TOKEN_SECRET (або вимкніть DEMO_DATASET і SEED_DEMO_DATA)")


def hash_secret(password: str, salt: str | None = None, iterations: int = 600_000) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def check_admin_grant(password: str | None) -> None:
    stored = settings.admin_grant_hash
    if not stored:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Надання ролі ADMIN вимкнено: не задано ADMIN_GRANT_HASH")
    _, iterations, salt, _ = stored.split("$")
    if not password or not hmac.compare_digest(hash_secret(password, salt, int(iterations)), stored):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Невірний пароль підтвердження ролі адміністратора")


def user_by_token(db: Session, token: str) -> User | None:
    user = db.scalars(select(User).where(User.token_hash == hash_token(token))).first()
    return None if user is None or token_expired(user) else user


SESSION_PREFIX = "s1"
SESSION_HEADER = "X-Session-Token"  # renewed token for API clients that send it as Bearer
SESSION_COOKIE = "mitra_session"  # browser session: HttpOnly cookie, never readable by page scripts
CSRF_HEADER = "X-Requested-With"  # a cross-site form cannot set it; a cross-site fetch with it needs CORS approval
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def session_secret_problem() -> str | None:
    """SESSION_SECRET is a separate key: rotating it must not break QR checks of reports signed earlier."""
    if settings.session_secret or settings.demo_public_tokens:
        return None
    return ("Не задано SESSION_SECRET — ключ підпису сеансів. Згенеруйте: "
            "python -c \"import secrets;print(secrets.token_urlsafe(32))\"")


def _session_key() -> bytes:
    if settings.session_secret:
        return settings.session_secret.encode()
    if settings.demo_public_tokens:  # tests only
        return hmac.new(b"mitra-tests", b"mitra-session-v1", hashlib.sha256).digest()
    raise RuntimeError(session_secret_problem())


def set_session_cookie(response: Response, token: str, expires: int) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=max(0, expires - int(time.time())), path="/",
                        httponly=True, secure=settings.session_cookie_secure, samesite="strict")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=settings.session_cookie_secure,
                           samesite="strict")


def _session_sig(user: User, signed_in: int, expires: int) -> str:
    body = f"{SESSION_PREFIX}.{user.id}.{signed_in}.{expires}.{user.token_hash}"
    return hmac.new(_session_key(), body.encode(), hashlib.sha256).hexdigest()


def issue_session(user: User, signed_in: int | None = None) -> tuple[str, int]:
    now = int(time.time())
    signed_in = signed_in or now
    expires = min(now + settings.session_hours * 3600, signed_in + settings.session_max_days * 86400)
    if user.token_expires_at is not None:
        expires = min(expires, int(as_utc(user.token_expires_at).timestamp()))
    return f"{SESSION_PREFIX}.{user.id}.{signed_in}.{expires}.{_session_sig(user, signed_in, expires)}", expires


def user_by_session(db: Session, token: str) -> tuple[User, int, int] | None:
    try:
        prefix, user_id, signed_in, expires, sig = token.split(".")
        uid, signed_in_at, expires_at = uuid.UUID(user_id), int(signed_in), int(expires)
    except ValueError:
        return None
    if prefix != SESSION_PREFIX or expires_at <= time.time():
        return None
    user = db.get(User, uid)
    if user is None or user.token_hash is None or user.deleted_at is not None or token_expired(user):
        return None
    if not hmac.compare_digest(sig, _session_sig(user, signed_in_at, expires_at)):
        return None
    return user, signed_in_at, expires_at


def current_user(
    request: Request,
    db: DbDep,
    response: Response,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """Browser: session in the HttpOnly cookie. API clients and integrations: `Authorization: Bearer`."""
    via_cookie = not (creds and creds.credentials)
    token = request.cookies.get(SESSION_COOKIE) if via_cookie else creds.credentials
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Потрібно увійти", {"WWW-Authenticate": "Bearer"})
    if via_cookie and request.method not in SAFE_METHODS and not request.headers.get(CSRF_HEADER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Запит без заголовка {CSRF_HEADER} відхилено (захист від CSRF)")
    if token.startswith(f"{SESSION_PREFIX}."):
        found = user_by_session(db, token)
        if not found:
            if via_cookie:
                clear_session_cookie(response)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сеанс завершився, увійдіть знову",
                                {"WWW-Authenticate": "Bearer"})
        user, signed_in, expires = found
        if expires - time.time() < settings.session_hours * 1800:
            renewed, renewed_until = issue_session(user, signed_in)
            if via_cookie:
                set_session_cookie(response, renewed, renewed_until)
            else:
                response.headers[SESSION_HEADER] = renewed
        return user
    if via_cookie:  # the cookie only ever holds a session token
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сеанс завершився, увійдіть знову",
                            {"WWW-Authenticate": "Bearer"})
    user = user_by_token(db, token)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невірний або недійсний токен", {"WWW-Authenticate": "Bearer"})
    return user


UserDep = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    def dep(user: UserDep) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Для вашої ролі ця дія недоступна")
        return user

    return dep


def is_assigned(user: User, measure: Measure) -> bool:
    return any(
        a.user_id == user.id or (a.user_id is None and a.org_unit_id == user.org_unit_id)
        for a in measure.assignments
    )


def ensure_can_execute(user: User, measure: Measure) -> None:
    if user.role != Role.EXECUTOR or not is_assigned(user, measure):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Це може зробити лише призначений виконавець заходу")


Coordinator = Annotated[User, Depends(require_roles(Role.COORDINATOR))]
Head = Annotated[User, Depends(require_roles(Role.HEAD))]
Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]
Analyst = Annotated[User, Depends(require_roles(Role.ANALYST))]
Executor = Annotated[User, Depends(require_roles(Role.EXECUTOR))]
SubjectUser = Annotated[User, Depends(require_roles(Role.EXECUTOR, Role.COORDINATOR, Role.HEAD, Role.ANALYST))]
Staff = Annotated[User, Depends(require_roles(Role.COORDINATOR, Role.HEAD, Role.ANALYST))]
Overseer = Annotated[User, Depends(require_roles(Role.COORDINATOR, Role.HEAD, Role.ANALYST, Role.ADMIN))]
