import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from .. import audit
from ..auth import Admin, DbDep
from ..models import AuditLogEntry
from ..schemas import domain as s
from ..services.mappers import user_ref

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


def entry_out(e: AuditLogEntry) -> s.AuditEntryOut:
    return s.AuditEntryOut(
        id=e.id, user=user_ref(e.user), entity=e.entity, entity_id=e.entity_id, action=e.action,
        old_value=e.old_value, new_value=e.new_value, at=e.at, prev_hash=e.prev_hash, hash=e.hash,
    )


@router.get("", response_model=list[s.AuditEntryOut])
def list_entries(
    db: DbDep,
    _: Admin,
    entity: str | None = None,
    entity_id: Annotated[uuid.UUID | None, Query(alias="entityId")] = None,
    user_id: Annotated[uuid.UUID | None, Query(alias="userId")] = None,
    limit: Annotated[int, Query(le=1000)] = 200,
):
    """Журнал дій читає лише адміністратор."""
    q = select(AuditLogEntry)
    if entity:
        q = q.where(AuditLogEntry.entity == entity)
    if entity_id:
        q = q.where(AuditLogEntry.entity_id == entity_id)
    if user_id:
        q = q.where(AuditLogEntry.user_id == user_id)
    return [entry_out(e) for e in db.scalars(q.order_by(AuditLogEntry.id.desc()).limit(limit))]


@router.get("/verify", response_model=s.AuditVerifyOut)
def verify(db: DbDep, _: Admin):
    """Перевірка цілісності ланцюжка хешів журналу."""
    ok, n, broken = audit.verify_chain(db)
    return s.AuditVerifyOut(ok=ok, checked=n, first_broken_id=broken)
