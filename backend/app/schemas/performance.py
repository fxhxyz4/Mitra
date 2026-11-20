import uuid
from datetime import date as Date
from datetime import datetime
from typing import Literal

from ..enums import MeasureStatus, Role
from .common import CamelModel


class Verdict(CamelModel):

    level: Literal["good", "attention", "behind"]
    title: str
    text: str


class SummarySection(CamelModel):
    number: int
    title: str
    total: int
    done: int
    overdue: int
    percent: float


class SummaryDeadline(CamelModel):
    measure_id: uuid.UUID
    code: str
    title: str
    deadline: Date
    days_left: int
    unit: str | None


class AnalyticsSummary(CamelModel):
    program_id: uuid.UUID
    program_title: str
    period: str
    as_of: Date
    total: int
    done: int
    in_work: int  # заплановано, в роботі, повернено
    on_review: int
    overdue: int
    not_done: int
    due: int  # заходи, строк яких уже настав
    done_percent: float
    on_time_percent: float
    risks_total: int
    risks_reduced: int
    verdict: Verdict
    sections: list[SummarySection]
    upcoming: list[SummaryDeadline]  # найближчі 30 днів, до 5 заходів
    upcoming_total: int
    attention: list[str]  # що потребує уваги, звичайною мовою
    scope: str | None = None  # підрозділ керівника; None — уся програма


class Counters(CamelModel):

    tasks: int = 0
    done: int = 0
    on_time: int = 0  # виконано не пізніше строку
    late_done: int = 0  # виконано із запізненням
    not_done: int = 0
    partial: int = 0
    overdue: int = 0  # строк минув, результат не погоджено
    in_work: int = 0
    on_review: int = 0
    submissions: int = 0  # подань на перевірку
    returns: int = 0  # повернень на доопрацювання
    decisions: int = 0  # рішень координатора (погоджено + повернено)
    first_pass: int = 0  # завдань, погоджених без жодного повернення
    evidence: int = 0  # завантажених підтвердних матеріалів
    open_flags: int = 0
    delay_days_total: int = 0
    delayed: int = 0  # завдань із запізненням (виконані пізно + прострочені)
    done_percent: float = 0.0
    on_time_percent: float = 0.0  # вчасно / усі виконані
    return_rate: float = 0.0  # повернення / рішення
    first_pass_percent: float = 0.0  # без повернень / завершені через погодження
    avg_delay_days: float | None = None


class UnitPerformance(Counters):
    org_unit_id: uuid.UUID | None  # None — заходи без відповідального підрозділу (окрема знахідка для аудиту)
    name: str
    people: int


class PersonPerformance(Counters):
    user_id: uuid.UUID
    name: str
    role: Role
    org_unit_id: uuid.UUID
    org_unit: str
    active: bool
    last_activity: datetime | None


class ReviewerPerformance(CamelModel):
    user_id: uuid.UUID
    name: str
    reviews: int
    approved: int
    returned: int
    return_rate: float
    avg_review_days: float | None


class TaskRow(CamelModel):

    measure_id: uuid.UUID
    period_id: uuid.UUID
    code: str
    title: str
    section: int
    period: str
    status: MeasureStatus
    deadline: Date
    actual_date: Date | None
    delay_days: int | None  # > 0 — на скільки днів пізніше строку (або скільки вже прострочено)
    on_time: bool | None
    overdue: bool
    org_unit_id: uuid.UUID | None
    org_unit: str | None
    executors: list[str]
    executor_ids: list[uuid.UUID]
    submissions: int
    returns: int
    evidence: int
    open_flags: list[str]
    risk_code: str | None
    last_activity: datetime | None


class TaskEvent(CamelModel):

    kind: Literal["submitted", "approved", "returned"]
    at: datetime
    measure_id: uuid.UUID
    code: str
    title: str
    period: str
    org_unit_id: uuid.UUID | None
    org_unit: str | None
    actor_id: uuid.UUID | None
    actor: str | None
    executor_id: uuid.UUID | None  # хто подавав результат, якого стосується подія
    executor: str | None
    comment: str
    round: int | None = None  # котре повернення цього завдання
    resolved: bool | None = None  # для повернення: результат згодом погоджено


class PerformanceReport(CamelModel):
    program_id: uuid.UUID
    program_title: str
    as_of: Date
    period: str | None  # None — усі півріччя до сьогодні
    periods: list[str]
    org_unit_id: uuid.UUID | None
    user_id: uuid.UUID | None
    scope: str | None = None  # підрозділ керівника; None — уся програма
    totals: Counters
    units: list[UnitPerformance]
    people: list[PersonPerformance]
    reviewers: list[ReviewerPerformance]
    tasks: list[TaskRow]
    events: list[TaskEvent]


class PeerStats(CamelModel):

    name: str
    org_unit: str
    shared_measures: int  # спільних заходів з тим, хто дивиться (для себе — усіх власних)
    tasks: int
    done: int
    overdue: int
    returns: int
    done_percent: float | None
    on_time_percent: float | None
    return_rate: float | None
    first_pass_percent: float | None
    avg_delay_days: float | None


class PeerReport(CamelModel):
    program_title: str
    as_of: Date
    shared_measures: int  # власних заходів, які виконуються спільно з колегами
    me: PeerStats
    average: PeerStats | None  # None, якщо колег менше PEER_MIN_GROUP
    colleagues: int
    min_group: int
