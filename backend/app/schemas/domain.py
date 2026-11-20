import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from .. import halfyear
from ..enums import (
    Channel,
    Decision,
    FlagStatus,
    FlagType,
    KriDirection,
    MeasureStatus,
    ProgramStatus,
    RecStatus,
    ReportType,
    RiskLevel,
    Role,
)
from .common import CamelModel, not_null


class OrgUnitIn(CamelModel):
    name: str
    parent_id: uuid.UUID | None = None


class OrgUnitOut(OrgUnitIn):
    id: uuid.UUID


class UserIn(CamelModel):
    display_name: str
    role: Role
    org_unit_id: uuid.UUID


class UserCreate(UserIn):
    admin_password: str | None = None  # секретний пароль — обовʼязковий, якщо role=ADMIN


class UserPatch(CamelModel):
    display_name: str | None = None
    role: Role | None = None
    org_unit_id: uuid.UUID | None = None
    admin_password: str | None = None  # секретний пароль — обовʼязковий при наданні чи знятті ролі ADMIN

    _not_null = not_null("display_name", "role", "org_unit_id")


class UserOut(UserIn):
    id: uuid.UUID


class UserWithToken(UserOut):
    token: str  # показується один раз
    token_expires_at: datetime | None = None


class LoginIn(CamelModel):
    token: str


class LoginOut(UserOut):
    session_token: str
    expires_at: int  # unix seconds


class UserRef(CamelModel):
    id: uuid.UUID
    display_name: str
    role: Role


class IndicatorValueIn(CamelModel):
    value: Decimal
    measured_at: date
    sample_size: int | None = Field(None, ge=1)  # n — обсяг вибірки (для порогу шуму δ)
    source_evidence_id: uuid.UUID | None = None


class IndicatorValueOut(IndicatorValueIn):
    id: uuid.UUID


class IndicatorIn(CamelModel):
    name: str
    unit: str = ""
    baseline: Decimal
    target: Decimal
    risk_id: uuid.UUID | None = None
    direction: KriDirection | None = None  # порожньо — з бази й цілі
    weight: Decimal = Field(Decimal(1), gt=0)
    lag_months: int = Field(6, ge=0, le=60)
    source: str = ""
    independent: bool = True
    min_sample: int | None = Field(None, ge=1)
    noise_threshold: Decimal | None = Field(None, ge=0)
    target_date: date | None = None
    paired_with_id: uuid.UUID | None = None


class IndicatorOut(IndicatorIn):
    id: uuid.UUID
    baseline_frozen_at: datetime | None = None
    current: Decimal | None = None
    is_improved: bool = False
    is_target_reached: bool = False
    values: list[IndicatorValueOut] = []


class RiskIn(CamelModel):
    code: str
    program_id: uuid.UUID | None = None  # порожньо — спільний реєстр, інакше ризик лише для цієї програми
    description: str
    level: RiskLevel | None = None  # порожньо — з балу x·y за Методологією НАЗК
    probability: int | None = Field(None, ge=1, le=4)  # імовірність x
    impact: int | None = Field(None, ge=1, le=4)  # наслідки y


class RiskKriIn(CamelModel):
    """Індикатор ризику (KRI) — у реєстрі разом з ризиком (словник: ryzyky.indykator_ryzyku …)."""
    name: str = Field(min_length=3)
    unit: str = ""
    direction: KriDirection | None = None
    baseline: Decimal
    target: Decimal
    target_date: date | None = None
    source: str = ""
    independent: bool = True


class RiskCreate(RiskIn):
    process: str = ""
    content: str = ""
    sources: str = ""
    existing_controls: str = ""
    owner_unit_id: uuid.UUID | None = None
    indicator: RiskKriIn | None = None


class RiskOut(RiskIn):
    id: uuid.UUID
    level: RiskLevel
    process: str = ""
    content: str = ""
    sources: str = ""
    existing_controls: str = ""
    owner_unit_id: uuid.UUID | None = None
    owner_unit_name: str | None = None
    measure_count: int = 0
    score: int | None = None  # x·y
    indicators: list[IndicatorOut] = []


class RiskRef(CamelModel):
    id: uuid.UUID
    code: str
    description: str
    level: RiskLevel


class ProgramIn(CamelModel):
    title: str
    org_unit_id: uuid.UUID
    period_start: date
    period_end: date
    has_restricted_info: bool = False


class ProgramOut(ProgramIn):
    id: uuid.UUID
    status: ProgramStatus


class SectionOut(CamelModel):
    id: uuid.UUID
    number: int
    title: str


class AssignmentIn(CamelModel):
    org_unit_id: uuid.UUID
    user_id: uuid.UUID | None = None
    is_responsible: bool = False


class AssignmentOut(AssignmentIn):
    org_unit_name: str
    user_name: str | None = None


class MeasureIn(CamelModel):
    section_id: uuid.UUID
    code: str = ""
    title: str
    is_permanent: bool = False
    planned_deadline: date
    risk_id: uuid.UUID | None = None
    # «Індикатор виконання» з паспорта (НАЗК): назва; ціль і одиниця — якщо він кількісний
    indicator_text: str = ""
    indicator_unit: str = ""
    indicator_target: Decimal | None = None
    required_evidence: str = ""
    assignments: list[AssignmentIn] = []


class MeasurePatch(CamelModel):
    code: str | None = None
    title: str | None = None
    is_permanent: bool | None = None
    planned_deadline: date | None = None
    risk_id: uuid.UUID | None = None
    indicator_text: str | None = None
    indicator_unit: str | None = None
    indicator_target: Decimal | None = None
    required_evidence: str | None = None
    assignments: list[AssignmentIn] | None = None

    _not_null = not_null("code", "title", "is_permanent", "planned_deadline", "indicator_text", "indicator_unit",
                         "required_evidence")


class MeasurePeriodOut(CamelModel):
    id: uuid.UUID
    period: str
    status: MeasureStatus
    actual_date: date | None = None
    result_description: str | None = None
    non_execution_reason: str | None = None


class FlagBrief(CamelModel):
    id: uuid.UUID
    type: FlagType
    explanation: str
    status: FlagStatus


class MeasureListItem(CamelModel):

    id: uuid.UUID
    code: str
    title: str
    section_number: int
    is_permanent: bool
    planned_deadline: date
    deadline: date  # effective deadline of the current period
    period: str | None
    status: MeasureStatus | None
    is_overdue: bool
    days_left: int
    risk: RiskRef | None = None
    responsible_unit: str | None = None
    responsible_user: str | None = None
    open_flags: list[FlagBrief] = []
    evidence_count: int = 0


class EvidenceOut(CamelModel):
    id: uuid.UUID
    period: str
    file_name: str
    content_type: str
    size: int
    object_key: str
    sha256: str
    version: int
    uploaded_at: datetime
    uploaded_by: uuid.UUID | None = None
    doc_type: str = ""  # тип документа: наказ, протокол, акт…
    document_date: date | None = None  # дата самого документа


class ProgressUpdateOut(CamelModel):
    id: uuid.UUID
    status_from: MeasureStatus
    status_to: MeasureStatus
    text: str
    created_at: datetime
    author: UserRef | None = None


class ApprovalOut(CamelModel):
    id: uuid.UUID
    decision: Decision
    comment: str
    created_at: datetime
    reviewer: UserRef | None = None


class MeasureDetail(MeasureListItem):
    section_title: str
    program_id: uuid.UUID
    required_evidence: str
    indicator_text: str = ""  # індикатор виконання з паспорта
    indicator: IndicatorOut | None = None  # кількісний індикатор виконання заходу: ціль і факти
    internal_deadline: date | None = None  # внутрішній строк після перенесень (строк у програмі не змінюється)
    deadline_changes: list["DeadlineChangeOut"] = []
    assignments: list[AssignmentOut] = []
    periods: list[MeasurePeriodOut] = []
    current_period: MeasurePeriodOut | None = None
    updates: list[ProgressUpdateOut] = []
    approvals: list[ApprovalOut] = []
    evidence: list[EvidenceOut] = []
    flags: list["RiskFlagOut"] = []
    allowed_actions: list[str] = []


class DeadlineChangeIn(CamelModel):
    new_deadline: date
    reason: str = Field(min_length=10)


class DeadlineChangeOut(CamelModel):
    id: uuid.UUID
    decided_on: date
    old_deadline: date
    new_deadline: date
    reason: str
    decided_by_name: str | None = None
    created_at: datetime


class SubmitResult(CamelModel):
    measure: MeasureDetail
    hints: list[str] = []  # підказки «додай показник або документ»


class ReturnIn(CamelModel):
    comment: str = Field(min_length=3)
    period: str | None = None


class ApproveIn(CamelModel):
    comment: str = ""
    period: str | None = None
    indicator_value: IndicatorValueIn | None = None


class ProgressIn(CamelModel):

    text: str
    period: str | None = None


class SectionPassport(SectionOut):
    measures: list[MeasureListItem]


class ProgramPassport(ProgramOut):
    org_unit_name: str
    sections: list[SectionPassport]
    totals: dict[str, int]


class RiskFlagOut(CamelModel):
    id: uuid.UUID
    measure_id: uuid.UUID
    measure_code: str = ""
    measure_title: str = ""
    type: FlagType
    rule_code: str
    facts: dict[str, Any]
    explanation: str
    status: FlagStatus
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_comment: str | None = None


class ResolveIn(CamelModel):
    comment: str = Field(min_length=3)


class RecommendationOut(CamelModel):
    id: uuid.UUID
    flag_id: uuid.UUID | None
    measure_id: uuid.UUID | None
    measure_title: str | None = None
    text: str
    basis: dict[str, Any]
    responsible_id: uuid.UUID | None
    due_date: date | None
    status: RecStatus
    created_at: datetime


class AcceptIn(CamelModel):
    responsible_id: uuid.UUID
    due_date: date
    # Остаточне формулювання (напр. відредаговане керівником). Порожнє — текст правила.
    text: str | None = Field(default=None, min_length=10)


class RejectIn(CamelModel):
    comment: str = Field(min_length=3)


class DeliveryOut(CamelModel):
    channel: Channel
    address: str
    status: str
    error: str | None = None
    at: datetime


class ReminderOut(CamelModel):
    id: uuid.UUID
    measure_id: uuid.UUID
    measure_title: str
    send_at: datetime
    channel: Channel
    text: str
    sent: bool
    deliveries: list[DeliveryOut] = []


class ContactIn(CamelModel):
    channel: Channel
    address: str = Field(min_length=1, max_length=320)


class ContactOut(ContactIn):
    id: uuid.UUID


class AuditEntryOut(CamelModel):
    id: int
    user: UserRef | None
    entity: str
    entity_id: uuid.UUID | None
    action: str
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    at: datetime
    prev_hash: str
    hash: str


class AuditVerifyOut(CamelModel):
    ok: bool
    checked: int
    first_broken_id: int | None


class JobResult(CamelModel):
    flags_opened: int
    flags_auto_resolved: int
    recommendations_created: int
    reminders_created: int
    periods_started: int
    notifications_sent: int = 0
    signals_opened: int = 0  # сигнали ризику (T1, D1, B1, P1, S1, X1, G1)
    signals_auto_resolved: int = 0


class ReportIn(CamelModel):
    program_id: uuid.UUID
    period: str
    type: ReportType = ReportType.NAZK

    @field_validator("period")
    @classmethod
    def _period(cls, v: str) -> str:
        halfyear.parse(v)
        return v


class ReportOut(CamelModel):
    id: uuid.UUID
    program_id: uuid.UUID
    period: str
    type: ReportType
    file_key: str | None
    generated_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str = ""


class ReportRevokeIn(CamelModel):
    reason: str = Field(min_length=5, max_length=1000)


class ReportIntegrity(CamelModel):
    report_id: uuid.UUID
    sha256: str
    signature: str
    signed_on: date
    algorithm: str
    verify_url: str
    qr_svg: str


class ReportVerification(CamelModel):

    valid: bool
    reason: str
    report_id: uuid.UUID | None = None
    period: str | None = None
    type: ReportType | None = None
    program_title: str | None = None
    org_unit: str | None = None
    generated_at: datetime | None = None
    generated_by: str | None = None
    sha256: str | None = None
    # A newer edition of the same report (program, period, type): the signature stays valid, the reader is warned.
    superseded_by: uuid.UUID | None = None
    superseded_at: datetime | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


class ReportCopyCheck(CamelModel):
    match: bool
    reason: str
    report_id: uuid.UUID | None = None
    format: str | None = None
    issued_at: datetime | None = None
    period: str | None = None
    type: ReportType | None = None
    program_title: str | None = None


class NazkMeasureRow(CamelModel):

    measure_id: uuid.UUID
    code: str
    title: str
    executors: str
    planned_deadline: str
    actual_deadline: str | None  # «Фактичний строк виконання»
    state: str  # «Стан виконання»
    result_or_reason: str  # «Опис результату виконання заходу або пояснення причин невиконання»
    corruption_risk: str | None = None
    indicator: str | None = None


class NazkSection(CamelModel):
    number: int
    title: str
    measures: list[NazkMeasureRow]


class NazkReport(CamelModel):
    report_id: uuid.UUID
    program_title: str
    org_unit: str
    period: str
    period_end: date
    has_restricted_info: bool
    sections: list[NazkSection]


class Conclusion(CamelModel):

    rule: str
    severity: str  # INFO / WARNING / CRITICAL
    text: str
    facts: dict[str, Any] = {}


class ProblemMeasure(CamelModel):
    code: str
    title: str
    status: MeasureStatus | None
    responsible_unit: str | None
    flags: list[str]  # пояснення відкритих Risk Flags


class MemoRecommendation(CamelModel):
    text: str
    status: RecStatus
    priority: int | None
    rule: str | None
    responsible: str | None = None
    due_date: date | None = None


class InternalMemo(CamelModel):

    program_title: str
    period: str
    as_of: date
    kpis: dict[str, Any]
    conclusions: list[Conclusion]
    risks: list[dict[str, Any]]
    units: list[dict[str, Any]]
    problem_measures: list[ProblemMeasure]
    recommendations: list[MemoRecommendation]


MeasureDetail.model_rebuild()
