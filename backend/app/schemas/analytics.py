import uuid
from datetime import date as Date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..enums import RiskLevel
from .common import CamelModel


class Kpis(CamelModel):
    measures_total: int
    done: int
    not_done: int
    overdue: int
    on_review: int
    returned: int
    done_percent: float
    on_time_percent: float  # «Виконано» не пізніше строку / усі «Виконано»
    evidence_coverage_percent: float  # «Виконано» з підтвердними матеріалами / усі «Виконано»
    return_rate_percent: float  # повернення / усі рішення координатора
    avg_review_days: float | None  # від «На перевірці» до рішення координатора
    risks_total: int
    risks_reduced: int
    open_flags: int
    recommendations_proposed: int
    recommendations_accepted: int


class StatusPoint(CamelModel):
    date: Date
    counts: dict[str, int]


class FlagPoint(CamelModel):
    date: Date
    opened: int
    resolved: int
    open: int


class IndicatorPoint(CamelModel):
    date: Date
    value: Decimal


class IndicatorSeries(CamelModel):
    id: uuid.UUID
    name: str
    unit: str
    baseline: Decimal
    target: Decimal
    current: Decimal | None
    progress_percent: float | None  # шлях від базового до цільового значення, 0..100
    is_improved: bool
    is_target_reached: bool
    values: list[IndicatorPoint]


class RiskDynamics(CamelModel):
    id: uuid.UUID
    code: str
    description: str
    level: RiskLevel
    measures_total: int
    measures_done: int
    reduced: bool  # усі індикатори ризику покращились відносно базового значення
    formal_closures: int  # відкриті FORMAL_CLOSURE: заходи виконано, а ризик не змінився
    indicators: list[IndicatorSeries]


class SectionStats(CamelModel):
    number: int
    title: str
    total: int
    done: int
    overdue: int
    open_flags: int
    done_percent: float


class UnitStats(CamelModel):

    org_unit_id: uuid.UUID
    name: str
    total: int
    done: int
    overdue: int
    returned: int
    open_flags: int
    on_time_percent: float


class AnalyticsOverview(CamelModel):
    program_id: uuid.UUID
    program_title: str
    as_of: Date
    period: str
    kpis: Kpis
    status_trend: list[StatusPoint]  # стан заходів на кінець кожного тижня
    flag_trend: list[FlagPoint]  # відкриті / зняті Risk Flags по тижнях
    risks: list[RiskDynamics]  # динаміка корупційних ризиків за індикаторами
    sections: list[SectionStats]
    units: list[UnitStats]
    flags_by_type: dict[str, int]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    model: str
    content: str


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class EmbedResponse(BaseModel):
    model: str
    embeddings: list[list[float]]


class AiStatus(BaseModel):
    enabled: bool = True
    reachable: bool
    ready: bool
    chatModel: str
    embedModel: str
    models: list[str]


class AiSettings(CamelModel):
    enabled: bool
    available: bool = True  # False: вимкнено в середовищі (AI_ENABLED=false), адміністратор не може ввімкнути


class AiSettingsIn(CamelModel):
    enabled: bool


class AiSuggestion(CamelModel):

    recommendation_id: uuid.UUID
    model: str
    text: str
    steps: list[str] = []
    rationale: str = ""
    disclaimer: str = "Пропозиція згенерована локальною моделлю ШІ. Рішення ухвалює посадова особа."
    basis: dict[str, Any] = {}


class Health(BaseModel):
    status: Literal["ok"] = "ok"
