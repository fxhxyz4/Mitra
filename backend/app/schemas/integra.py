import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from ..enums import InboxState, OutboxState
from .common import CamelModel


class IntegraMeasureIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=128)
    unit_id: str | None = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default="", max_length=20000)
    component: str | None = Field(default=None, max_length=64)
    catalog_number: str | None = Field(default=None, max_length=64)
    owner: str | None = Field(default=None, max_length=500)
    due_date: date | None = None
    status: str | None = Field(default=None, max_length=32)
    done_on: date | None = None
    source: str | None = Field(default=None, max_length=128)


class IntegraAck(BaseModel):
    id: uuid.UUID
    state: InboxState


class LinkIn(CamelModel):
    measure_id: uuid.UUID


class InboxOut(CamelModel):
    id: uuid.UUID
    external_id: str
    title: str
    description: str
    component: str | None
    catalog_number: str | None
    owner: str
    due_date: date | None
    external_status: str | None
    state: InboxState
    measure_id: uuid.UUID | None
    measure_code: str | None
    measure_title: str | None
    reported_status: str | None
    reject_reason: str | None
    decided_by: str | None
    decided_at: datetime | None
    received_at: datetime
    updated_at: datetime


class OutboxOut(CamelModel):
    id: uuid.UUID
    inbox_id: uuid.UUID | None
    title: str | None
    status: str | None
    state: OutboxState
    attempts: int
    last_error: str | None
    created_at: datetime
    next_attempt_at: datetime
    sent_at: datetime | None


class IntegraStatus(CamelModel):
    enabled: bool
    target_url: str
    inbox: dict[str, int]
    outbox: dict[str, int]


class DeliveryResult(CamelModel):
    sent: int
    failed: int
    pending: int
