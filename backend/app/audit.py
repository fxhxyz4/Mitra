import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session, SessionTransaction

from .models import AuditLogEntry, User, utcnow

GENESIS = "0" * 64
_CHAIN_LOCK_KEY = 0x6D697472  # pg_advisory_xact_lock key for the audit chain
_HELD = "audit_chain_lock"


def _lock_chain(db: Session) -> None:
    if db.info.get(_HELD):
        return
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_KEY})
    else:
        db.execute(text("UPDATE audit_log SET id = id WHERE 0"))
    db.info[_HELD] = True


@event.listens_for(Session, "after_transaction_end")
def _release_chain(db: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is None:
        db.info.pop(_HELD, None)


def _default(o: Any) -> Any:
    if isinstance(o, (uuid.UUID, Decimal)):
        return str(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, Enum):
        return o.value
    raise TypeError(type(o))


def jsonable(d: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if d is None else json.loads(json.dumps(d, default=_default))


def snapshot(obj: Any, *fields: str) -> dict[str, Any]:
    return jsonable({f: getattr(obj, f) for f in fields})  # type: ignore[return-value]


def _utc(at: datetime) -> datetime:
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at.astimezone(timezone.utc)


def _digest(e: AuditLogEntry) -> str:
    payload = json.dumps(
        {
            "prev": e.prev_hash,
            "user": str(e.user_id) if e.user_id else None,
            "entity": e.entity,
            "entityId": str(e.entity_id) if e.entity_id else None,
            "action": e.action,
            "old": e.old_value,
            "new": e.new_value,
            "at": _utc(e.at).replace(tzinfo=None).isoformat(timespec="microseconds"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def record(
    db: Session,
    user: User | None,
    entity: str,
    entity_id: uuid.UUID | None,
    action: str,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> AuditLogEntry:
    _lock_chain(db)
    last = db.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(1)).first()
    e = AuditLogEntry(
        user_id=user.id if user else None,
        entity=entity,
        entity_id=entity_id,
        action=action,
        old_value=jsonable(old),
        new_value=jsonable(new),
        at=_utc(at or utcnow()),
        prev_hash=last.hash if last else GENESIS,
    )
    e.hash = _digest(e)
    db.add(e)
    db.flush()
    return e


def verify_chain(db: Session) -> tuple[bool, int, int | None]:
    """Returns (ok, checked_count, first_broken_id)."""
    prev = GENESIS
    n = 0
    for e in db.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id)):
        n += 1
        if e.prev_hash != prev or _digest(e) != e.hash:
            return False, n, e.id
        prev = e.hash
    return True, n, None
