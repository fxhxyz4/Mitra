import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from ..enums import FlagStatus, KriDirection, MeasureStatus, RiskLevel, SignalType
from .common import CamelModel, not_null


class KriOut(CamelModel):
    indicator_id: uuid.UUID
    name: str
    unit: str
    direction: KriDirection
    weight: float  # w, нормована в межах ризику (Σ w = 1)
    lag_months: int
    source: str
    independent: bool
    baseline: float  # B — заморожена база
    target: float  # T
    target_date: date | None = None
    current: float | None = None  # C
    measured_at: date | None = None
    sample_size: int | None = None  # n
    min_sample: int | None = None
    delta: float  # поріг шуму δ
    change: float | None = None  # C − B
    noise: bool  # |C − B| < δ → p = 0
    raw: float | None = None
    p: float | None = None  # прогрес, [−1; 1]
    self_report_discount: bool  # позитивний p × 0,5 (самозвітні дані)
    expected: float | None = None  # очікуваний прогрес на дату (рівномірно до дедлайну цілі)
    state: str  # ON_TRACK / LAGGING / NO_CHANGE / WORSENING / NO_DATA
    state_label: str
    insufficient: list[str] = []
    paired_with: str | None = None
    baseline_frozen_at: datetime | None = None
    baseline_changed: bool = False


class MeasureStateOut(CamelModel):
    measure_id: uuid.UUID
    code: str
    title: str
    section: int
    status: MeasureStatus | None = None
    done: bool  # «Виконано» або подано як виконаний
    pending: bool  # подано, координатор ще не погодив
    completed_on: date | None = None


class HintOut(CamelModel):
    rule: str  # P1 / L+1 / L-1
    text: str
    suggested: int  # запропонована ймовірність
    inputs: dict[str, Any] = {}
    source: str = ""


class SignalOut(CamelModel):
    id: uuid.UUID | None = None  # None — розрахований, ще не збережений
    risk_id: uuid.UUID
    risk_code: str
    indicator_id: uuid.UUID | None = None
    indicator_name: str | None = None
    type: SignalType
    rule_code: str
    label: str
    color: str  # red / orange / yellow / gray
    facts: dict[str, Any] = {}
    explanation: str
    status: FlagStatus = FlagStatus.OPEN
    created_at: datetime | None = None


class IncidentIn(CamelModel):
    occurred_on: date
    confirmed: bool = True
    source: str = Field(min_length=2)  # ЄДРСР, Реєстр корупціонерів, висновок службового розслідування
    description: str = ""


class IncidentOut(IncidentIn):
    id: uuid.UUID
    risk_id: uuid.UUID
    created_at: datetime


class RiskAssessmentOut(CamelModel):
    risk_id: uuid.UUID
    code: str
    description: str
    level: RiskLevel  # рівень у реєстрі
    as_of: date
    ruleset_version: str
    probability0: int  # L₀
    impact0: int  # C₀
    inherent: int  # I = L₀·C₀
    inherent_level: RiskLevel
    kris: list[KriOut]
    rrs: float | None
    rrs_category: str
    expected: float | None = None  # очікуваний прогрес ризику на дату
    effect: str  # стан ризику за KRI
    effect_label: str
    measures: list[MeasureStateOut]
    done_count: int
    verdict: str  # WORKING / FORMAL / WORSE_DESPITE / EXTERNAL / STAGNANT / UNATTENDED / NO_DATA / NO_MEASURES
    verdict_label: str
    verdict_color: str
    preliminary: bool  # лаг ефекту виконаних заходів ще не минув — висновок попередній
    effect_due: date | None = None
    hints: list[HintOut]  # підстави для переоцінки ймовірності робочою групою
    signals: list[SignalOut]
    incidents: list[IncidentOut] = []


class RiskReassessIn(CamelModel):
    probability: int = Field(ge=1, le=4)  # L, за критеріями Методології НАЗК
    impact: int = Field(ge=1, le=4)  # C
    justification: str = Field(min_length=10)  # рішення робочої групи: підстави переоцінки


class RiskBrief(CamelModel):
    code: str
    rrs: float | None = None
    contribution_pp: float | None = None  # внесок у FCG, в.п.


class UncoveredRisk(CamelModel):
    """Ризик реєстру, щодо якого в програмі немає жодного заходу (правило C1); у PRI й EXEC не входить."""
    risk_id: uuid.UUID
    code: str
    description: str
    level: RiskLevel
    probability0: int
    impact0: int
    inherent: int


class RiskModelOverview(CamelModel):
    program_id: uuid.UUID
    as_of: date
    ruleset_version: str
    pri: float  # Σ I·RRS / Σ I
    exec: float  # Σ I·частка виконаних / Σ I
    fcg: float  # EXEC − PRI, в.п.
    fcg_color: str
    top_contributor: RiskBrief | None = None
    weakest_link: RiskBrief | None = None  # мінімальний RRS серед критичних (I ≥ 12)
    sub_index: float | None = None  # розділи 1 і 3: прогрес індикаторів виконання
    sub_index_count: int = 0
    scope_name: str | None = None  # показники лише за зоною відповідальності (керівник підрозділу)
    verdict_counts: dict[str, int] = {}
    risks_with_done: int = 0  # ризиків, де є виконані заходи
    risks_working: int = 0  # з них індикатор рухається до цілі
    uncovered: list[UncoveredRisk] = []
    risks: list[RiskAssessmentOut]


class IndicatorPatch(CamelModel):

    name: str | None = None
    baseline: Decimal | None = None
    target: Decimal | None = None
    direction: KriDirection | None = None
    weight: Decimal | None = Field(None, gt=0)
    lag_months: int | None = Field(None, ge=0, le=60)
    source: str | None = None
    independent: bool | None = None
    min_sample: int | None = Field(None, ge=1)
    noise_threshold: Decimal | None = Field(None, ge=0)
    target_date: date | None = None
    paired_with_id: uuid.UUID | None = None
    justification: str = Field(min_length=10)

    _not_null = not_null("name", "baseline", "target", "weight", "lag_months", "source", "independent")
