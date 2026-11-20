import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from ..enums import RiskLevel
from .common import CamelModel

AnswerSource = Literal["model", "rule"]
EntityType = Literal["risk", "indicator", "measure", "period", "flag", "signal", "evidence", "recommendation"]

PROPOSAL = "Пропозиція локальної моделі ШІ. Перевірте за джерелами: рішення ухвалює посадова особа."


class SourceRef(CamelModel):

    n: int
    type: EntityType
    id: uuid.UUID
    label: str
    target: uuid.UUID | None = None  # what a flag / signal link opens: its measure / its risk


class CoverageGap(CamelModel):
    rule_code: Literal["C1", "C2", "C3"]
    level: RiskLevel | None = None
    risk_id: uuid.UUID | None = None
    risk_code: str | None = None
    measure_id: uuid.UUID | None = None
    measure_code: str | None = None
    facts: dict[str, Any] = {}
    explanation: str


class RiskMeasureDraftIn(CamelModel):
    program_id: uuid.UUID


class RiskExplanation(CamelModel):
    risk_id: uuid.UUID
    text: str
    text_source: AnswerSource
    references: list[SourceRef] = []
    rule_text: str
    model: str
    model_used: bool
    disclaimer: str = PROPOSAL


class DigestHighlights(CamelModel):
    pri: float
    pri_before: float
    exec: float
    exec_before: float
    done: int
    overdue: int
    new_overdue: int
    new_flags: int
    open_flags: int
    risks_up: int
    risks_down: int


class WeeklyDigest(CamelModel):
    program_id: uuid.UUID
    since: date
    as_of: date
    text: str
    text_source: AnswerSource
    references: list[SourceRef] = []
    rule_text: str
    highlights: DigestHighlights
    model: str
    model_used: bool
    disclaimer: str = PROPOSAL


class EvidenceFinding(CamelModel):
    rule_code: str
    ok: bool
    text: str
    facts: dict[str, Any] = {}


class EvidenceQuote(CamelModel):
    evidence_id: uuid.UUID
    file_name: str
    quote: str


class EvidenceCheck(CamelModel):

    period_id: uuid.UUID
    findings: list[EvidenceFinding] = []
    unreadable: list[str] = []
    advice: str = ""
    advice_source: AnswerSource | None = None
    quotes: list[EvidenceQuote] = []
    model: str
    model_used: bool
    disclaimer: str = PROPOSAL


class AskIn(CamelModel):
    question: str = Field(min_length=3, max_length=500)


class AskAnswer(CamelModel):
    answer: str
    answer_source: AnswerSource
    references: list[SourceRef] = []
    model: str
    model_used: bool
    disclaimer: str = PROPOSAL


class AiChatIn(CamelModel):
    title: str | None = Field(None, min_length=1, max_length=120)


class AiChatRenameIn(CamelModel):
    title: str = Field(min_length=1, max_length=120)


class AiChatMessageOut(CamelModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    answer_source: AnswerSource | None = None
    references: list[SourceRef] = []
    model: str | None = None
    model_used: bool | None = None
    created_at: datetime


class AiChatSummary(CamelModel):
    id: uuid.UUID
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class AiChatOut(AiChatSummary):
    messages: list[AiChatMessageOut] = []
    disclaimer: str = PROPOSAL


class RewriteIn(CamelModel):
    text: str = Field(min_length=5, max_length=4000)


class RewriteOut(CamelModel):

    text: str | None = None
    note: str = ""
    model: str
    model_used: bool = False
