import hashlib
import os
import stat
import time
import uuid
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.orm import Session, SessionTransaction

from ..config import settings

_PENDING = "storage_pending"


EVIDENCE_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".rtf": "application/rtf",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".p7s": "application/pkcs7-signature",
    ".asice": "application/vnd.etsi.asic-e+zip",
}


def evidence_type(file_name: str) -> str | None:
    return EVIDENCE_TYPES.get(Path(file_name).suffix.lower())


def _path(key: str) -> Path:
    p = (settings.storage_dir / key).resolve()
    if settings.storage_dir.resolve() not in p.parents:
        raise ValueError("Invalid object key")
    return p


def put_object(db: Session, prefix: str, file_name: str, data: bytes) -> tuple[str, str]:
    """Stores bytes, returns (object_key, sha256). The file is removed again if `db` does not commit."""
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(file_name).suffix[:16]
    key = f"{prefix}/{uuid.uuid4().hex}{suffix}"
    path = _path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    db.info.setdefault(_PENDING, []).append(key)
    with open(path, "xb") as f:
        f.write(data)
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    return key, digest


def delete_object(key: str) -> None:
    path = _path(key)
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        path.unlink()
    except FileNotFoundError:
        return


@event.listens_for(Session, "after_commit")
def _keep_written(db: Session) -> None:
    db.info.pop(_PENDING, None)


@event.listens_for(Session, "after_transaction_end")
def _drop_uncommitted(db: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is None:
        for key in db.info.pop(_PENDING, []):
            delete_object(key)


def sweep_orphans(db: Session, older_than_seconds: int = 3600) -> int:
    from ..models import Evidence, Report, ReportFile

    root = settings.storage_dir.resolve()
    if not root.exists():
        return 0
    known = set(db.scalars(select(Evidence.object_key)))
    known |= set(db.scalars(select(Report.file_key).where(Report.file_key.is_not(None))))
    known |= set(db.scalars(select(ReportFile.file_key)))
    cutoff = time.time() - older_than_seconds
    removed = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.stat().st_mtime > cutoff:
            continue
        key = path.relative_to(root).as_posix()
        if key not in known:
            delete_object(key)
            removed += 1
    return removed


def get_object(key: str) -> bytes:
    return _path(key).read_bytes()


def verify(key: str, sha256: str) -> bool:
    try:
        return hashlib.sha256(get_object(key)).hexdigest() == sha256
    except FileNotFoundError:
        return False
