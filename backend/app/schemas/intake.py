import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from .common import CamelModel
from .domain import AssignmentIn

Source = Literal["document", "rule", "model"]
Outcome = Literal["done", "not_done"]

DISCLAIMER = "Чернетка з документа. Перевірте кожне поле: рішення і відправлення — за вами."


class MeasureCandidate(CamelModel):
    measure_id: uuid.UUID
    code: str
    title: str
    period: str
    score: float
    reason: str


class ReportDraft(CamelModel):

    measure_id: uuid.UUID | None = None
    period: str | None = None
    measure_source: Source | None = None
    candidates: list[MeasureCandidate] = []
    outcome: Outcome | None = None
    outcome_source: Source | None = None
    text: str = ""
    text_source: Source = "document"
    document_text: str = ""
    hints: list[str] = []
    warnings: list[str] = []
    file_name: str
    file_sha256: str
    draft_key: str | None = None
    model: str
    model_used: bool
    disclaimer: str = DISCLAIMER


class DraftField(CamelModel):
    value: str | int | bool | None = None
    source: Source
    document_value: str = ""


class SimilarMeasure(CamelModel):
    measure_id: uuid.UUID
    code: str
    title: str
    score: float


class MeasureDraftValues(CamelModel):

    section_id: uuid.UUID | None = None
    code: str = ""
    title: str = ""
    is_permanent: bool = False
    planned_deadline: date | None = None
    risk_id: uuid.UUID | None = None
    indicator_text: str = ""  # індикатор виконання заходу
    indicator_unit: str = ""
    indicator_target: Decimal | None = None
    required_evidence: str = ""
    assignments: list[AssignmentIn] = []


class MeasureDraft(CamelModel):

    measure: MeasureDraftValues
    fields: dict[str, DraftField] = {}
    warnings: list[str] = []
    similar: list[SimilarMeasure] = []
    file_name: str
    model: str
    model_used: bool
    disclaimer: str = DISCLAIMER
