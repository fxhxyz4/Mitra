import json
import logging
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..auth import issue_token
from ..config import today as get_today
from ..enums import Channel, ProgramStatus, RiskLevel, Role
from ..models import CorruptionRisk, Indicator, IndicatorValue, Measure, OrgUnit, Program, Section, User, UserContact
from ..schemas import domain as s
from ..schemas.common import CamelModel
from . import measures as svc
from . import notify, risk_model

log = logging.getLogger("app")


class IOrgUnit(CamelModel):
    name: str
    parent: str | None = None


class IUser(CamelModel):
    display_name: str
    role: Role
    org_unit: str
    token: str | None = None  # якщо не задано — новому користувачу видається випадковий токен
    email: str | None = None


class IValue(CamelModel):
    value: Decimal
    measured_at: date


class IIndicator(CamelModel):
    name: str
    unit: str = ""
    baseline: Decimal
    target: Decimal
    values: list[IValue] = []


class IRisk(CamelModel):
    code: str
    description: str
    level: RiskLevel | None = None  # порожньо — з балу x·y
    probability: int | None = Field(None, ge=1, le=4)
    impact: int | None = Field(None, ge=1, le=4)
    process: str = ""  # поля реєстру ризиків (словник: ryzyky)
    content: str = ""
    sources: str = ""
    existing_controls: str = ""
    owner_unit: str | None = None  # назва підрозділу-власника
    indicators: list[IIndicator] = []


class IAssignment(CamelModel):
    org_unit: str
    user: str | None = None
    is_responsible: bool = False


class IMeasure(CamelModel):
    section: int = Field(ge=1, le=3)
    code: str
    title: str
    is_permanent: bool = False
    planned_deadline: date
    required_evidence: str = ""
    risk: str | None = None  # код ризику
    indicator: str | None = None  # індикатор виконання з паспорта
    indicator_unit: str = ""
    indicator_target: Decimal | None = None  # ціль, якщо індикатор кількісний
    assignments: list[IAssignment] = []


class IProgram(CamelModel):
    title: str
    org_unit: str
    period_start: date
    period_end: date
    has_restricted_info: bool = False
    approve: bool = True
    measures: list[IMeasure] = []


class ImportPayload(CamelModel):
    org_units: list[IOrgUnit] = []
    users: list[IUser] = []
    risks: list[IRisk] = []
    indicators: list[IIndicator] = []  # індикатори без привʼязки до ризику (напр. навчання)
    programs: list[IProgram] = []


class ImportResult(CamelModel):
    dry_run: bool
    created: dict[str, int]
    updated: dict[str, int]
    tokens: dict[str, str]  # displayName → виданий токен (лише для нових користувачів без заданого токена)
    warnings: list[str]


class _Importer:
    def __init__(self, db: Session, actor: User | None):
        self.db, self.actor = db, actor
        self.created: dict[str, int] = {}
        self.updated: dict[str, int] = {}
        self.tokens: dict[str, str] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def _count(self, kind: str, created: bool) -> None:
        d = self.created if created else self.updated
        d[kind] = d.get(kind, 0) + 1

    def _one(self, model, **by):
        return self.db.scalars(select(model).filter_by(**by)).first()

    def unit(self, name: str | None) -> OrgUnit | None:
        if name is None:
            return None
        u = self._one(OrgUnit, name=name)
        if not u:
            self.errors.append(f"Підрозділ «{name}» не знайдено")
        return u

    def user(self, name: str) -> User | None:
        u = self._one(User, display_name=name, deleted_at=None)
        if not u:
            self.errors.append(f"Користувача «{name}» не знайдено")
        return u


    def org_units(self, items: list[IOrgUnit]) -> None:
        for it in items:
            parent = self.unit(it.parent)
            ou = self._one(OrgUnit, name=it.name)
            if ou:
                ou.parent_id = parent.id if parent else ou.parent_id
                self._count("orgUnits", False)
            else:
                ou = OrgUnit(name=it.name, parent_id=parent.id if parent else None)
                self.db.add(ou)
                self.db.flush()
                audit.record(self.db, self.actor, "org_unit", ou.id, "import", None, {"name": it.name})
                self._count("orgUnits", True)

    def users(self, items: list[IUser]) -> None:
        for it in items:
            ou = self.unit(it.org_unit)
            if not ou:
                continue
            u = self._one(User, display_name=it.display_name, deleted_at=None)
            new = u is None
            if self.actor is not None and Role.ADMIN in (it.role, None if new else u.role):
                self.errors.append(f"{it.display_name}: облікові записи адміністраторів імпортом не змінюються")
                continue
            if new:
                u = User(display_name=it.display_name, role=it.role, org_unit_id=ou.id)
                token = issue_token(u, it.token)
                if not it.token:
                    self.tokens[it.display_name] = token
                self.db.add(u)
            else:
                u.role, u.org_unit_id = it.role, ou.id
                if it.token:
                    issue_token(u, it.token)
            self.db.flush()
            if it.email:
                if err := notify.validate_address(Channel.EMAIL, it.email):
                    self.warnings.append(f"{it.display_name}: {err} ({it.email}) — контакт пропущено")
                elif c := self._one(UserContact, user_id=u.id, channel=Channel.EMAIL):
                    c.address = it.email
                else:
                    self.db.add(UserContact(user_id=u.id, channel=Channel.EMAIL, address=it.email))
            audit.record(self.db, self.actor, "user", u.id, "import", None,
                         {"displayName": u.display_name, "role": u.role.value})
            self._count("users", new)

    def indicator(self, it: IIndicator, risk: CorruptionRisk | None) -> None:
        problem = risk_model.kri_problem(it.baseline, it.target, None)
        if problem:
            self.errors.append(f"Індикатор «{it.name}»: {problem}")
            return
        ind = self._one(Indicator, name=it.name)
        new = ind is None
        if new:
            ind = Indicator(name=it.name)
            self.db.add(ind)
        old = None if new else audit.snapshot(ind, "unit", "baseline", "target", "risk_id")
        ind.unit, ind.baseline, ind.target = it.unit, it.baseline, it.target
        if risk:
            ind.risk = risk
        self.db.flush()
        now = audit.snapshot(ind, "unit", "baseline", "target", "risk_id")
        if new or now != old:
            audit.record(self.db, self.actor, "indicator", ind.id, "import", old, now)
        have = {v.measured_at for v in ind.values}
        for v in it.values:
            if v.measured_at not in have:
                iv = IndicatorValue(indicator=ind, value=v.value, measured_at=v.measured_at)
                self.db.add(iv)
                self.db.flush()
                audit.record(self.db, self.actor, "indicator_value", iv.id, "import", None,
                             audit.snapshot(iv, "indicator_id", "value", "measured_at"))
                self._count("indicatorValues", True)
        self._count("indicators", new)

    def risks(self, items: list[IRisk]) -> None:
        for it in items:
            r = self._one(CorruptionRisk, code=it.code)
            new = r is None
            if new:
                r = CorruptionRisk(code=it.code)
                self.db.add(r)
            problem = risk_model.level_problem(it.level, it.probability, it.impact)
            if problem:
                self.errors.append(f"Ризик {it.code}: {problem}")
                continue
            r.description = it.description
            r.process, r.content, r.sources, r.existing_controls = it.process, it.content, it.sources, it.existing_controls
            if it.owner_unit:
                owner = self.unit(it.owner_unit)
                r.owner_unit_id = owner.id if owner else None
            if it.probability is not None:
                r.probability, r.impact = it.probability, it.impact
            elif r.probability and r.impact and RiskLevel.from_score(r.probability * r.impact) != it.level:
                self.errors.append(f"Ризик {it.code}: рівень «{it.level.value}» суперечить збереженому балу "
                                   f"{r.probability}·{r.impact}; передайте probability та impact")
                continue
            r.level = it.level or RiskLevel.from_score(r.probability * r.impact)
            self.db.flush()
            audit.record(self.db, self.actor, "corruption_risk", r.id, "import", None,
                         {"code": r.code, "level": r.level.value, "probability": r.probability, "impact": r.impact})
            self._count("risks", new)
            for ind in it.indicators:
                self.indicator(ind, r)

    def program(self, it: IProgram, today: date) -> None:
        ou = self.unit(it.org_unit)
        if not ou:
            return
        p = self._one(Program, title=it.title)
        new = p is None
        if new:
            p = svc.create_program(self.db, self.actor, s.ProgramIn(
                title=it.title, org_unit_id=ou.id, period_start=it.period_start, period_end=it.period_end,
                has_restricted_info=it.has_restricted_info))
        elif (p.period_start, p.period_end) != (it.period_start, it.period_end):
            self.warnings.append(f"«{it.title}»: період існуючої програми не змінюється під час імпорту")
        self._count("programs", new)
        sections = {x.number: x for x in p.sections}
        for mi in it.measures:
            self.measure(p, sections[mi.section], mi)
        if it.approve and p.status == ProgramStatus.DRAFT:
            svc.approve_program(self.db, self.actor, p, today)

    def measure(self, program: Program, section: Section, it: IMeasure) -> None:
        risk = self._one(CorruptionRisk, code=it.risk) if it.risk else None
        if it.risk and not risk:
            self.errors.append(f"Захід {it.code}: ризик «{it.risk}» не знайдено")
        assignments = []
        for a in it.assignments:
            ou = self.unit(a.org_unit)
            u = self.user(a.user) if a.user else None
            if ou:
                assignments.append(s.AssignmentIn(org_unit_id=ou.id, user_id=u.id if u else None,
                                                  is_responsible=a.is_responsible))
        if not program.period_start <= it.planned_deadline <= program.period_end:
            self.warnings.append(f"Захід {it.code}: строк {it.planned_deadline} поза періодом програми")
        if self.errors:
            return
        fields = dict(code=it.code, title=it.title, is_permanent=it.is_permanent, planned_deadline=it.planned_deadline,
                      risk_id=risk.id if risk else None, indicator_text=it.indicator or "",
                      indicator_unit=it.indicator_unit, indicator_target=it.indicator_target,
                      required_evidence=it.required_evidence)
        existing = self.db.scalars(select(Measure).join(Measure.section).where(
            Section.program_id == program.id, Measure.code == it.code)).first()
        if existing:
            if existing.section_id != section.id:
                self.warnings.append(f"Захід {it.code}: розділ існуючого заходу не змінюється")
            svc.patch_measure(self.db, self.actor, existing, s.MeasurePatch(**fields, assignments=assignments))
        else:
            svc.create_measure(self.db, self.actor, s.MeasureIn(section_id=section.id, **fields,
                                                                assignments=assignments))
        self._count("measures", existing is None)


def run_import(db: Session, payload: ImportPayload, actor: User | None, dry_run: bool = False,
               today: date | None = None) -> ImportResult:
    from . import control

    today = today or get_today()
    imp = _Importer(db, actor)
    try:
        imp.org_units(payload.org_units)
        imp.users(payload.users)
        imp.risks(payload.risks)
        for ind in payload.indicators:
            imp.indicator(ind, None)
        if not imp.errors:
            for prog in payload.programs:
                imp.program(prog, today)
        if imp.errors:
            raise HTTPException(422, {"message": "Імпорт не вдався, нічого не збережено", "errors": imp.errors})
        result = ImportResult(dry_run=dry_run, created=imp.created, updated=imp.updated, tokens=imp.tokens,
                              warnings=imp.warnings)
        if dry_run:
            db.rollback()
            return result
        db.flush()
        audit.record(db, actor, "import", None, "import", None,
                     {"created": imp.created, "updated": imp.updated})
        db.commit()
    except Exception:
        db.rollback()
        raise
    control.run_daily(db, today)
    return result


def load(path: Path) -> ImportPayload:
    try:
        return ImportPayload.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Cannot read import file {path}: {e}") from e


def import_file_if_empty(db: Session, path: Path) -> bool:
    if db.scalars(select(User).limit(1)).first():
        return False
    res = run_import(db, load(path), None)
    # Accounts without a token in the file get a random one. Nobody could sign in without it, so it is shown once
    # here; later an administrator reissues tokens in the UI. Tokens are never taken from a file someone else saw.
    if res.tokens:
        lines = "\n".join(f"  {name}: {token}" for name, token in res.tokens.items())
        log.warning("Import from %s issued sign-in tokens (shown once, hand them over and clear this log):\n%s",
                    path, lines)
    return True


def main(argv: list[str]) -> int:
    from ..db import Base, SessionLocal, engine
    from .. import models  # noqa: F401

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        try:
            res = run_import(db, load(Path(argv[0])), None, dry_run="--dry-run" in argv)
        except HTTPException as e:
            print(json.dumps(e.detail, ensure_ascii=False, indent=2))
            return 1
    print(res.model_dump_json(by_alias=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
