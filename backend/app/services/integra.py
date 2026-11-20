import uuid
from datetime import date, datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, halfyear
from ..config import settings
from ..enums import InboxState, MeasureStatus, OutboxState
from ..models import (
    IntegraInbox,
    Measure,
    MeasurePeriod,
    OutboxMessage,
    User,
    as_utc,
    local_date,
    utcnow,
)
from ..schemas import integra as s

TARGET = "integra"
WEBHOOK_PATH = "/integrations/theme2/measures/status"
MAX_ATTEMPTS = 20
MAX_BACKOFF = timedelta(hours=1)
EVIDENCE_LIMIT = 2000
RETRYABLE_4XX = {408, 425, 429}

PLANNED, IN_PROGRESS, DONE, CANCELLED = "planned", "in_progress", "done", "cancelled"
RANK = {PLANNED: 0, IN_PROGRESS: 1, DONE: 2}
ACTIVE = {
    MeasureStatus.IN_PROGRESS,
    MeasureStatus.ON_REVIEW,
    MeasureStatus.RETURNED,
    MeasureStatus.PARTIAL,
    MeasureStatus.NOT_DONE,
}
INBOX_FIELDS = ("title", "description", "component", "catalog_number", "owner", "due_date", "external_status")

transport: httpx.BaseTransport | None = None


def enabled() -> bool:
    return bool(settings.integra_url and settings.integra_api_key)


def receive(db: Session, data: s.IntegraMeasureIn) -> IntegraInbox:
    item = db.scalars(select(IntegraInbox).where(IntegraInbox.external_id == data.id)).first()
    old = audit.snapshot(item, *INBOX_FIELDS) if item else None
    if item is None:
        item = IntegraInbox(external_id=data.id)
        db.add(item)
    item.external_unit_id = data.unit_id
    item.title = data.title
    item.description = data.description or ""
    item.component = data.component
    item.catalog_number = data.catalog_number
    item.owner = data.owner or ""
    item.due_date = data.due_date
    item.external_status = data.status
    item.external_done_on = data.done_on
    item.payload = data.model_dump(mode="json")
    item.updated_at = utcnow()
    db.flush()
    new = audit.snapshot(item, *INBOX_FIELDS)
    if old != new:
        audit.record(db, None, "integra_inbox", item.id, "receive" if old is None else "update", old, new)
    if item.state == InboxState.LINKED and item.measure is not None:
        sync(db, item)
    return item


def _open(db: Session, item_id: uuid.UUID) -> IntegraInbox:
    item = db.get(IntegraInbox, item_id)
    if not item:
        raise HTTPException(404, "Вхідний захід не знайдено")
    return item


def link(db: Session, user: User, item_id: uuid.UUID, measure_id: uuid.UUID) -> IntegraInbox:
    item = _open(db, item_id)
    if item.state == InboxState.LINKED:
        raise HTTPException(409, "Захід уже повʼязано з заходом програми")
    measure = db.get(Measure, measure_id)
    if not measure:
        raise HTTPException(404, "Захід програми не знайдено")
    old = {"state": item.state, "measureId": None}
    item.state = InboxState.LINKED
    item.measure_id = measure.id
    item.measure = measure
    item.reject_reason = None
    item.decided_by = user.id
    item.decided_at = utcnow()
    db.flush()
    audit.record(db, user, "integra_inbox", item.id, "link", old,
                 {"state": item.state, "measureId": str(measure.id), "measureCode": measure.code})
    sync(db, item)
    return item


def reject(db: Session, user: User, item_id: uuid.UUID, reason: str) -> IntegraInbox:
    item = _open(db, item_id)
    if item.state != InboxState.NEW:
        raise HTTPException(409, "Відхилити можна лише новий вхідний захід")
    item.state = InboxState.REJECTED
    item.reject_reason = reason
    item.decided_by = user.id
    item.decided_at = utcnow()
    db.flush()
    audit.record(db, user, "integra_inbox", item.id, "reject", {"state": InboxState.NEW},
                 {"state": item.state, "reason": reason})
    return item


def _periods(item: IntegraInbox, m: Measure) -> list[MeasurePeriod]:
    if not m.is_permanent or item.decided_at is None:
        return list(m.periods)
    since = halfyear.of(local_date(item.decided_at))
    return [p for p in m.periods if p.period >= since]


def _done_period(periods: list[MeasurePeriod]) -> MeasurePeriod | None:
    done = [p for p in periods if p.status == MeasureStatus.DONE]
    return max(done, key=lambda p: (p.actual_date or date.min, p.period)) if done else None


def measure_status(periods: list[MeasurePeriod]) -> str:
    if _done_period(periods):
        return DONE
    if any(p.status in ACTIVE for p in periods):
        return IN_PROGRESS
    return PLANNED


def evidence_text(m: Measure, p: MeasurePeriod) -> str:
    head = f"Mitra: захід {m.code} «{m.title}» виконано, результат погоджено координатором."
    docs = "\n".join(f"• {e.file_name} — sha256:{e.sha256}" for e in p.evidence)
    tail = f"\nДокументи (SHA-256):\n{docs}" if docs else "\nДокументи не додавались."
    result = (p.result_description or "").strip()
    room = EVIDENCE_LIMIT - len(head) - len(tail) - len("\nРезультат: ")
    if room < 20:
        return (head + tail)[:EVIDENCE_LIMIT]
    if len(result) > room:
        result = result[: room - 1] + "…"
    return f"{head}\nРезультат: {result}{tail}"


def _payload(item: IntegraInbox, m: Measure, periods: list[MeasurePeriod], status: str) -> dict:
    try:
        ref = {"measure_id": str(uuid.UUID(item.external_id))}
    except ValueError:
        ref = {"external_id": str(item.id)}
    body: dict = {**ref, "status": status}
    if status == DONE:
        p = _done_period(periods)
        real = datetime.now(settings.tz).date()  # Integra lives in real time, Mitra may pin DEMO_TODAY
        body["done_on"] = (real if settings.demo_today else p.actual_date or real).isoformat()
        body["evidence"] = evidence_text(m, p)
    return body


def sync(db: Session, item: IntegraInbox) -> OutboxMessage | None:
    if item.state != InboxState.LINKED or item.measure is None or item.external_status == CANCELLED:
        return None
    periods = _periods(item, item.measure)
    status = measure_status(periods)
    floor = max(RANK.get(item.external_status or "", -1), RANK.get(item.reported_status or "", -1))
    if RANK[status] <= floor:
        return None
    for old in db.scalars(select(OutboxMessage).where(
        OutboxMessage.inbox_id == item.id, OutboxMessage.state == OutboxState.PENDING
    )):
        old.state = OutboxState.SUPERSEDED
    msg = OutboxMessage(target=TARGET, inbox_id=item.id, payload=_payload(item, item.measure, periods, status))
    db.add(msg)
    item.reported_status = status
    db.flush()
    return msg


def on_measure_changed(db: Session, m: Measure) -> None:
    for item in db.scalars(select(IntegraInbox).where(
        IntegraInbox.measure_id == m.id, IntegraInbox.state == InboxState.LINKED
    )):
        sync(db, item)


def _backoff(attempts: int) -> timedelta:
    return min(timedelta(seconds=30 * 2 ** (attempts - 1)), MAX_BACKOFF)


def _fail(msg: OutboxMessage, error: str, retry: bool) -> None:
    msg.last_error = error[:500]
    if retry and msg.attempts < MAX_ATTEMPTS:
        msg.next_attempt_at = utcnow() + _backoff(msg.attempts)
    else:
        msg.state = OutboxState.FAILED


def deliver(db: Session, limit: int = 100) -> dict[str, int]:
    sent = failed = 0
    if not enabled():
        return {"sent": 0, "failed": 0, "pending": pending_count(db)}
    now = utcnow()
    due = [
        m for m in db.scalars(select(OutboxMessage).where(
            OutboxMessage.target == TARGET, OutboxMessage.state == OutboxState.PENDING
        ).order_by(OutboxMessage.created_at))
        if as_utc(m.next_attempt_at) <= now
    ][:limit]
    url = settings.integra_url.rstrip("/") + WEBHOOK_PATH
    headers = {"X-Integration-Key": settings.integra_api_key}
    with httpx.Client(timeout=settings.integra_timeout, transport=transport) as client:
        for msg in due:
            msg.attempts += 1
            try:
                res = client.post(url, json=msg.payload, headers=headers)
            except httpx.HTTPError as e:
                _fail(msg, f"{type(e).__name__}: {e}", retry=True)
                failed += 1
                continue
            if res.is_success:
                msg.state = OutboxState.SENT
                msg.sent_at = utcnow()
                msg.last_error = None
                sent += 1
                continue
            retry = res.status_code >= 500 or res.status_code in RETRYABLE_4XX
            _fail(msg, f"HTTP {res.status_code}: {res.text[:400]}", retry)
            failed += 1
    db.flush()
    return {"sent": sent, "failed": failed, "pending": pending_count(db)}


def retry(db: Session, user: User, msg_id: uuid.UUID) -> OutboxMessage:
    msg = db.get(OutboxMessage, msg_id)
    if not msg or msg.target != TARGET:
        raise HTTPException(404, "Повідомлення не знайдено")
    if msg.state != OutboxState.FAILED:
        raise HTTPException(409, "Повторити можна лише невдале відправлення")
    msg.state = OutboxState.PENDING
    msg.attempts = 0
    msg.next_attempt_at = utcnow()
    db.flush()
    audit.record(db, user, "outbox", msg.id, "retry", {"state": OutboxState.FAILED}, {"state": msg.state})
    return msg


def pending_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(OutboxMessage).where(
        OutboxMessage.target == TARGET, OutboxMessage.state == OutboxState.PENDING
    )) or 0
