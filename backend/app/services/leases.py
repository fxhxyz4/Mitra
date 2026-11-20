import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError

from ..db import SessionLocal
from ..models import JobLease

HOLDER = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def claim(name: str, ttl: timedelta, holder: str = HOLDER, renew: bool = True) -> bool:
    now = datetime.now(timezone.utc)
    free = or_(JobLease.holder == holder, JobLease.expires_at < now) if renew else JobLease.expires_at < now
    with SessionLocal() as db:
        taken = db.execute(
            update(JobLease).where(JobLease.name == name, free).values(holder=holder, expires_at=now + ttl)
        ).rowcount
        if not taken:
            db.add(JobLease(name=name, holder=holder, expires_at=now + ttl))
        try:
            db.commit()
        except IntegrityError:
            return False
    return True
