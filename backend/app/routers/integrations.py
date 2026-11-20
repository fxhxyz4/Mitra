import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select

from ..auth import Coordinator, DbDep, require_roles
from ..config import settings
from ..enums import InboxState, OutboxState, Role
from ..models import IntegraInbox, OutboxMessage, User
from ..schemas import integra as s
from ..schemas.domain import RejectIn
from ..services import integra as svc

router = APIRouter(prefix="/integrations/integra", tags=["Integrations"])
Operator = Annotated[User, Depends(require_roles(Role.COORDINATOR, Role.ADMIN))]


def _check_key(key: str | None) -> None:
    expected = settings.integra_api_key
    if not expected:
        raise HTTPException(503, "Інтеграцію з Integra не налаштовано (INTEGRA_API_KEY)")
    if not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "Невірний ключ інтеграції")


def _inbox_out(item: IntegraInbox) -> s.InboxOut:
    return s.InboxOut(
        id=item.id,
        external_id=item.external_id,
        title=item.title,
        description=item.description,
        component=item.component,
        catalog_number=item.catalog_number,
        owner=item.owner,
        due_date=item.due_date,
        external_status=item.external_status,
        state=item.state,
        measure_id=item.measure_id,
        measure_code=item.measure.code if item.measure else None,
        measure_title=item.measure.title if item.measure else None,
        reported_status=item.reported_status,
        reject_reason=item.reject_reason,
        decided_by=item.decider.display_name if item.decider else None,
        decided_at=item.decided_at,
        received_at=item.received_at,
        updated_at=item.updated_at,
    )


@router.post("/measures", response_model=s.IntegraAck)
def receive(
    data: s.IntegraMeasureIn,
    db: DbDep,
    x_integration_key: Annotated[str | None, Header()] = None,
    x_topic: Annotated[str | None, Header()] = None,
):
    """Вхідна точка для Integra: прийнята керівником рекомендація як захід (`measure.upsert`).
    Повторне надсилання з тим самим `id` оновлює запис. Відповідь `id` Integra зберігає як свій `external_id`."""
    _check_key(x_integration_key)
    if x_topic and x_topic != "measure.upsert":
        raise HTTPException(422, f"Невідома тема повідомлення: {x_topic}")
    item = svc.receive(db, data)
    db.commit()
    return s.IntegraAck(id=item.id, state=item.state)


@router.get("/status", response_model=s.IntegraStatus)
def status(db: DbDep, _: Operator):
    inbox = dict(db.execute(select(IntegraInbox.state, func.count()).group_by(IntegraInbox.state)).all())
    outbox = dict(db.execute(
        select(OutboxMessage.state, func.count()).where(OutboxMessage.target == svc.TARGET).group_by(OutboxMessage.state)
    ).all())
    return s.IntegraStatus(
        enabled=svc.enabled(),
        target_url=settings.integra_url,
        inbox={st.value: inbox.get(st, 0) for st in InboxState},
        outbox={st.value: outbox.get(st, 0) for st in OutboxState},
    )


@router.get("/inbox", response_model=list[s.InboxOut])
def inbox(db: DbDep, _: Operator, state: InboxState | None = None):
    q = select(IntegraInbox).order_by(IntegraInbox.received_at.desc())
    if state:
        q = q.where(IntegraInbox.state == state)
    return [_inbox_out(i) for i in db.scalars(q)]


@router.post("/inbox/{item_id}/link", response_model=s.InboxOut)
def link(item_id: uuid.UUID, data: s.LinkIn, db: DbDep, user: Coordinator):
    """Повʼязати вхідний захід із наявним заходом програми. Новий захід не створюється."""
    item = svc.link(db, user, item_id, data.measure_id)
    db.commit()
    return _inbox_out(item)


@router.post("/inbox/{item_id}/reject", response_model=s.InboxOut)
def reject(item_id: uuid.UUID, data: RejectIn, db: DbDep, user: Coordinator):
    item = svc.reject(db, user, item_id, data.comment)
    db.commit()
    return _inbox_out(item)


@router.get("/outbox", response_model=list[s.OutboxOut])
def outbox(db: DbDep, _: Operator, limit: int = 50):
    rows = db.scalars(
        select(OutboxMessage).where(OutboxMessage.target == svc.TARGET)
        .order_by(OutboxMessage.created_at.desc()).limit(min(max(limit, 1), 200))
    )
    return [
        s.OutboxOut(
            id=m.id,
            inbox_id=m.inbox_id,
            title=m.inbox.title if m.inbox else None,
            status=m.payload.get("status"),
            state=m.state,
            attempts=m.attempts,
            last_error=m.last_error,
            created_at=m.created_at,
            next_attempt_at=m.next_attempt_at,
            sent_at=m.sent_at,
        )
        for m in rows
    ]


@router.post("/outbox/flush", response_model=s.DeliveryResult)
def flush(db: DbDep, _: Operator):
    if not svc.enabled():
        raise HTTPException(409, "Інтеграцію з Integra не налаштовано (INTEGRA_URL, INTEGRA_API_KEY)")
    result = svc.deliver(db)
    db.commit()
    return result


@router.post("/outbox/{msg_id}/retry", response_model=s.DeliveryResult)
def retry(msg_id: uuid.UUID, db: DbDep, user: Operator):
    svc.retry(db, user, msg_id)
    result = svc.deliver(db)
    db.commit()
    return result
