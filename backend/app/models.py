import hashlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import halfyear
from .config import settings
from .db import Base
from .enums import (
    FINAL_STATUSES,
    NAZK_STATE,
    NAZK_STATE_IN_PROGRESS,
    NAZK_STATE_NOT_DUE,
    Channel,
    Decision,
    FlagStatus,
    FlagType,
    InboxState,
    MeasureStatus,
    OutboxState,
    ProgramStatus,
    RecStatus,
    ReportType,
    KriDirection,
    RiskLevel,
    Role,
    SignalType,
)

JsonType = JSON().with_variant(JSONB(), "postgresql")
BigId = BigInteger().with_variant(Integer(), "sqlite")  # SQLite autoincrements only INTEGER PKs


def _enum(e: type) -> Enum:
    return Enum(e, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x])


def utcnow() -> datetime:
    now = datetime.now(timezone.utc)
    pinned = settings.demo_today
    if pinned and pinned < now.astimezone(settings.tz).date():
        return datetime.combine(pinned, now.timetz())
    return now


def as_utc(at: datetime) -> datetime:
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at.astimezone(timezone.utc)


def local_date(at: datetime) -> date:
    return as_utc(at).astimezone(settings.tz).date()


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class OrgUnit(Base):
    __tablename__ = "org_units"

    id: Mapped[uuid.UUID] = _uuid_pk()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("org_units.id"))
    name: Mapped[str] = mapped_column(Text)

    parent: Mapped["OrgUnit | None"] = relationship(remote_side="OrgUnit.id")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(_enum(Role))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    org_unit: Mapped[OrgUnit] = relationship()


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    org_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    title: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    has_restricted_info: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ProgramStatus] = mapped_column(_enum(ProgramStatus), default=ProgramStatus.DRAFT)

    org_unit: Mapped[OrgUnit] = relationship()
    sections: Mapped[list["Section"]] = relationship(
        back_populates="program", order_by="Section.number", cascade="all, delete-orphan"
    )

    @property
    def half_years(self) -> list[str]:
        return halfyear.between(self.period_start, self.period_end)


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("program_id", "number"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programs.id"))
    number: Mapped[int] = mapped_column(Integer)  # 1..3
    title: Mapped[str] = mapped_column(Text)

    program: Mapped[Program] = relationship(back_populates="sections")
    # "2.2" before "2.10": shorter codes first, then lexicographic
    measures: Mapped[list["Measure"]] = relationship(
        back_populates="section", order_by=lambda: (func.length(Measure.code), Measure.code)
    )

    def next_code(self) -> str:
        last = (int(n) for m in self.measures if (n := m.code.rsplit(".", 1)[-1]).isdigit())
        return f"{self.number}.{max(last, default=0) + 1}"


class CorruptionRisk(Base):
    __tablename__ = "corruption_risks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("programs.id"))
    description: Mapped[str] = mapped_column(Text)
    level: Mapped[RiskLevel] = mapped_column(_enum(RiskLevel))
    probability: Mapped[int | None] = mapped_column(Integer)
    impact: Mapped[int | None] = mapped_column(Integer)
    # Поля реєстру корупційних ризиків (Методологія НАЗК № 830/21; словник набору, таблиця `ryzyky`).
    process: Mapped[str] = mapped_column(Text, default="")  # «Функція, процес організації»
    content: Mapped[str] = mapped_column(Text, default="")  # «Зміст корупційного ризику»
    sources: Mapped[str] = mapped_column(Text, default="")  # «Джерело(а) корупційного ризику»
    existing_controls: Mapped[str] = mapped_column(Text, default="")  # «Існуючі заходи контролю»
    owner_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("org_units.id"))  # власник ризику

    owner_unit: Mapped["OrgUnit | None"] = relationship()
    indicators: Mapped[list["Indicator"]] = relationship(back_populates="risk")
    measures: Mapped[list["Measure"]] = relationship(back_populates="risk")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="risk", order_by="Incident.occurred_on")


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[uuid.UUID] = _uuid_pk()
    risk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("corruption_risks.id"))
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text, default="")
    baseline: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    target: Mapped[Decimal] = mapped_column(Numeric(14, 4))

    direction: Mapped[KriDirection | None] = mapped_column(_enum(KriDirection))  # порожньо — з бази й цілі
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal(1))  # w; нормується в межах ризику
    lag_months: Mapped[int] = mapped_column(Integer, default=6)  # лаг ефекту
    source: Mapped[str] = mapped_column(Text, default="")  # джерело даних
    independent: Mapped[bool] = mapped_column(Boolean, default=True)  # False — самозвіт: позитивний p × 0,5
    min_sample: Mapped[int | None] = mapped_column(Integer)  # мінімальне n
    noise_threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))  # δ вручну (в одиницях показника)
    target_date: Mapped[date | None] = mapped_column(Date)  # дедлайн цілі
    paired_with_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("indicators.id"))  # парний KRI
    baseline_frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    baseline_hash: Mapped[str | None] = mapped_column(String(64))

    risk: Mapped[CorruptionRisk | None] = relationship(back_populates="indicators")
    values: Mapped[list["IndicatorValue"]] = relationship(
        back_populates="indicator", order_by="IndicatorValue.measured_at"
    )
    paired_with: Mapped["Indicator | None"] = relationship(remote_side="Indicator.id")

    @property
    def lower_is_better(self) -> bool:
        if self.direction:
            return self.direction == KriDirection.LOWER
        return self.target < self.baseline

    def baseline_digest(self) -> str:
        raw = f"{Decimal(self.baseline).normalize()}|{Decimal(self.target).normalize()}|{self.lower_is_better}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def freeze_baseline(self, at: datetime) -> None:
        if self.baseline_hash is None:
            self.baseline_hash = self.baseline_digest()
            self.baseline_frozen_at = at

    @property
    def current(self) -> Decimal | None:
        return self.values[-1].value if self.values else None

    def is_improved(self, since: date | None = None) -> bool:
        vals = [v for v in self.values if since is None or v.measured_at >= since]
        if not vals:
            return False
        last = vals[-1].value
        return last < self.baseline if self.lower_is_better else last > self.baseline

    def is_target_reached(self) -> bool:
        cur = self.current
        if cur is None:
            return False
        return cur <= self.target if self.lower_is_better else cur >= self.target


class IndicatorValue(Base):
    __tablename__ = "indicator_values"

    id: Mapped[uuid.UUID] = _uuid_pk()
    indicator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("indicators.id"))
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    measured_at: Mapped[date] = mapped_column(Date)
    sample_size: Mapped[int | None] = mapped_column(Integer)  # n — обсяг вибірки
    source_evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence_files.id"))

    indicator: Mapped[Indicator] = relationship(back_populates="values")


class Measure(Base):
    __tablename__ = "measures"

    id: Mapped[uuid.UUID] = _uuid_pk()
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"))
    risk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("corruption_risks.id"))
    indicator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("indicators.id"))
    code: Mapped[str] = mapped_column(String(32), default="")  # номер заходу в програмі, напр. «2.3»
    title: Mapped[str] = mapped_column(Text)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False)
    planned_deadline: Mapped[date] = mapped_column(Date)
    # Строк дослівно, як у програмі («IV квартал 2026», «Щокварталу»); порожньо — з дати.
    deadline_text: Mapped[str] = mapped_column(Text, default="")
    required_evidence: Mapped[str] = mapped_column(Text, default="")
    # Документ «визначеної форми» (типи через кому: «наказ, протокол»); порожньо — будь-який документ.
    evidence_form: Mapped[str] = mapped_column(Text, default="")
    # Застаріле: внесок заходу vⱼ більше не використовується моделлю ризику.
    contribution: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    # «Індикатор виконання» заходу з програми (НАЗК; словник: zakhody.indykator_vykonannia). Якщо він кількісний,
    # ціль і факти — у власному `indicator` заходу (не індикатор ризику: той належить ризику).
    indicator_text: Mapped[str] = mapped_column(Text, default="")

    section: Mapped[Section] = relationship(back_populates="measures")
    risk: Mapped[CorruptionRisk | None] = relationship(back_populates="measures")
    indicator: Mapped[Indicator | None] = relationship()
    periods: Mapped[list["MeasurePeriod"]] = relationship(
        back_populates="measure", order_by="MeasurePeriod.period", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["MeasureAssignment"]] = relationship(
        back_populates="measure", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="measure", cascade="all, delete-orphan")
    flags: Mapped[list["RiskFlag"]] = relationship(back_populates="measure", cascade="all, delete-orphan")
    deadline_changes: Mapped[list["DeadlineChange"]] = relationship(
        back_populates="measure", order_by="DeadlineChange.created_at", cascade="all, delete-orphan"
    )

    @property
    def internal_deadline(self) -> date:
        """Внутрішній строк після перенесень; строк у затвердженій програмі (planned_deadline) не змінюється."""
        return self.deadline_changes[-1].new_deadline if self.deadline_changes else self.planned_deadline

    def period_for(self, on: date) -> "MeasurePeriod | None":
        if not self.periods:
            return None
        want = halfyear.of(on)
        for p in self.periods:
            if p.period == want:
                return p
        return self.periods[0] if want < self.periods[0].period else self.periods[-1]

    def deadline_for(self, period: "MeasurePeriod") -> date:
        return halfyear.end(period.period) if self.is_permanent else self.planned_deadline

    def is_overdue(self, on: date) -> bool:
        p = self.period_for(on)
        return p is not None and p.status not in FINAL_STATUSES and self.deadline_for(p) < on

    @property
    def responsible(self) -> "MeasureAssignment | None":
        return next((a for a in self.assignments if a.is_responsible), None)


class MeasureAssignment(Base):
    __tablename__ = "measure_assignments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measures.id"))
    org_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    is_responsible: Mapped[bool] = mapped_column(Boolean, default=False)

    measure: Mapped[Measure] = relationship(back_populates="assignments")
    org_unit: Mapped[OrgUnit] = relationship()
    user: Mapped[User | None] = relationship()


class MeasurePeriod(Base):
    __tablename__ = "measure_periods"
    __table_args__ = (UniqueConstraint("measure_id", "period"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measures.id"))
    period: Mapped[str] = mapped_column(String(7))  # HalfYear
    status: Mapped[MeasureStatus] = mapped_column(_enum(MeasureStatus), default=MeasureStatus.DRAFT)
    actual_date: Mapped[date | None] = mapped_column(Date)
    result_description: Mapped[str | None] = mapped_column(Text)
    non_execution_reason: Mapped[str | None] = mapped_column(Text)

    measure: Mapped[Measure] = relationship(back_populates="periods")
    updates: Mapped[list["ProgressUpdate"]] = relationship(
        back_populates="measure_period", order_by="ProgressUpdate.created_at"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="measure_period", order_by="Evidence.uploaded_at"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="measure_period", order_by="Approval.created_at"
    )

    def to_nazk_state(self, report_end: date) -> str:
        if self.status in NAZK_STATE:
            return NAZK_STATE[self.status]
        deadline = self.measure.deadline_for(self)
        if deadline > report_end:
            return NAZK_STATE_NOT_DUE
        return NAZK_STATE_IN_PROGRESS


class ProgressUpdate(Base):
    __tablename__ = "progress_updates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure_periods.id"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status_from: Mapped[MeasureStatus] = mapped_column(_enum(MeasureStatus))
    status_to: Mapped[MeasureStatus] = mapped_column(_enum(MeasureStatus))
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    measure_period: Mapped[MeasurePeriod] = relationship(back_populates="updates")
    author: Mapped[User | None] = relationship()


class Evidence(Base):
    __tablename__ = "evidence_files"

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure_periods.id"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    file_name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text, default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    doc_type: Mapped[str] = mapped_column(Text, default="")  # наказ, протокол, акт…
    document_date: Mapped[date | None] = mapped_column(Date)  # дата самого документа (не завантаження)
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    measure_period: Mapped[MeasurePeriod] = relationship(back_populates="evidence")


class DeadlineChange(Base):
    """Внутрішнє рішення координатора про перенесення строку (словник: `perenesennia_strokiv`).
    Строк у затвердженій програмі не змінюється."""

    __tablename__ = "deadline_changes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measures.id"))
    decided_on: Mapped[date] = mapped_column(Date)  # дата рішення
    old_deadline: Mapped[date] = mapped_column(Date)
    new_deadline: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))  # хто погодив
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    measure: Mapped[Measure] = relationship(back_populates="deadline_changes")
    author: Mapped["User | None"] = relationship()


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measure_periods.id"))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[Decision] = mapped_column(_enum(Decision))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    measure_period: Mapped[MeasurePeriod] = relationship(back_populates="approvals")
    reviewer: Mapped[User | None] = relationship()


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("measure_id", "user_id", "send_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measures.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[Channel] = mapped_column(_enum(Channel), default=Channel.IN_APP)
    text: Mapped[str] = mapped_column(Text, default="")
    sent: Mapped[bool] = mapped_column(Boolean, default=False)

    measure: Mapped[Measure] = relationship(back_populates="reminders")
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="reminder", cascade="all, delete-orphan", order_by="NotificationDelivery.at"
    )


class UserContact(Base):

    __tablename__ = "user_contacts"
    __table_args__ = (UniqueConstraint("user_id", "channel"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    address: Mapped[str] = mapped_column(Text)


class NotificationDelivery(Base):

    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("reminder_id", "channel"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    reminder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reminders.id"))
    channel: Mapped[Channel] = mapped_column(_enum(Channel))
    address: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))  # SENT / FAILED / SKIPPED
    error: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reminder: Mapped[Reminder] = relationship(back_populates="deliveries")


class Incident(Base):

    __tablename__ = "risk_incidents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corruption_risks.id"))
    occurred_on: Mapped[date] = mapped_column(Date)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(Text, default="")  # ЄДРСР, Реєстр корупціонерів, службове розслідування
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    risk: Mapped[CorruptionRisk] = relationship(back_populates="incidents")


class RiskSignal(Base):

    __tablename__ = "risk_signals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corruption_risks.id"))
    indicator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("indicators.id"))
    type: Mapped[SignalType] = mapped_column(_enum(SignalType))
    rule_code: Mapped[str] = mapped_column(Text)
    facts: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[FlagStatus] = mapped_column(_enum(FlagStatus), default=FlagStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    risk: Mapped[CorruptionRisk] = relationship()
    indicator: Mapped[Indicator | None] = relationship()


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[uuid.UUID] = _uuid_pk()
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measures.id"))
    type: Mapped[FlagType] = mapped_column(_enum(FlagType))
    rule_code: Mapped[str] = mapped_column(Text)
    facts: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[FlagStatus] = mapped_column(_enum(FlagStatus), default=FlagStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolution_comment: Mapped[str | None] = mapped_column(Text)

    measure: Mapped[Measure] = relationship(back_populates="flags")

    def explain(self) -> str:
        return self.explanation


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    flag_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("risk_flags.id"))
    measure_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("measures.id"))
    text: Mapped[str] = mapped_column(Text)
    basis: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[RecStatus] = mapped_column(_enum(RecStatus), default=RecStatus.PROPOSED)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    flag: Mapped[RiskFlag | None] = relationship()
    measure: Mapped[Measure | None] = relationship()


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    entity: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(Text)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

    user: Mapped[User | None] = relationship()


class LlmAnswer(Base):

    __tablename__ = "llm_answers"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SystemSetting(Base):

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JsonType)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AiDraft(Base):

    __tablename__ = "ai_drafts"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    measure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measures.id"))
    period: Mapped[str] = mapped_column(String(7))
    outcome: Mapped[str | None] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    text_source: Mapped[str] = mapped_column(String(16))
    file_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programs.id"))
    period: Mapped[str] = mapped_column(String(7))
    type: Mapped[ReportType] = mapped_column(_enum(ReportType))
    file_key: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # Revocation lives outside `data`: the signed content never changes, the public check reports the revocation.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revoke_reason: Mapped[str] = mapped_column(Text, default="")

    program: Mapped[Program] = relationship()


class ReportFile(Base):
    __tablename__ = "report_files"
    __table_args__ = (UniqueConstraint("report_id", "format"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"))
    format: Mapped[str] = mapped_column(String(8))
    file_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegraInbox(Base):
    __tablename__ = "integra_inbox"

    id: Mapped[uuid.UUID] = _uuid_pk()
    external_id: Mapped[str] = mapped_column(String(128), unique=True)
    external_unit_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    component: Mapped[str | None] = mapped_column(Text)
    catalog_number: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date)
    external_status: Mapped[str | None] = mapped_column(String(32))
    external_done_on: Mapped[date | None] = mapped_column(Date)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    state: Mapped[InboxState] = mapped_column(_enum(InboxState), default=InboxState.NEW)
    measure_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("measures.id"))
    reported_status: Mapped[str | None] = mapped_column(String(32))
    reject_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    measure: Mapped[Measure | None] = relationship()
    decider: Mapped[User | None] = relationship()


class OutboxMessage(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = _uuid_pk()
    target: Mapped[str] = mapped_column(String(32))
    inbox_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("integra_inbox.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    state: Mapped[OutboxState] = mapped_column(_enum(OutboxState), default=OutboxState.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    inbox: Mapped[IntegraInbox | None] = relationship()


class AiJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(32))
    key: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued / running / done / failed
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiChat(Base):
    __tablename__ = "ai_chats"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["AiChatMessage"]] = relationship(
        back_populates="chat", order_by="AiChatMessage.id", cascade="all, delete-orphan")


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_chats.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    answer_source: Mapped[str | None] = mapped_column(String(16))
    references: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    model: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chat: Mapped[AiChat] = relationship(back_populates="messages")


class JobLease(Base):
    __tablename__ = "job_leases"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    holder: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
