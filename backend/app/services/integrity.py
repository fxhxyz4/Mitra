import base64
import hashlib
import hmac
import io
import json
import logging
import secrets
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import segno
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLogEntry, Report
from . import storage

log = logging.getLogger("app")

KEY = "_integrity"
DOMAIN = "mitra-report-v1"
# v2: the stored report file and every issued copy also carry a keyed signature of their sha256, so whoever can
# write to the database (audit log included: its hash chain has no key) cannot bless a swapped file.
DOMAIN_V2 = "mitra-report-v2"
FILE_DOMAIN = "mitra-report-file-v1"
VERSION = 2
MAIN_FILE = "report"


def _legacy_key_file():
    return settings.storage_dir.parent / ".report-secret"


def report_secret_problem() -> str | None:
    """REPORT_SECRET is required: a lost key turns every printed QR code invalid."""
    if settings.report_secret or settings.demo_public_tokens or _legacy_key_file().exists():
        return None
    return ("Не задано REPORT_SECRET — ключ підпису звітів (QR-коди). Згенеруйте: "
            "python -c \"import secrets;print(secrets.token_urlsafe(48))\"")


@lru_cache(maxsize=1)
def _secret() -> bytes:
    if settings.report_secret:
        return settings.report_secret.encode()
    path = _legacy_key_file()
    if path.exists():  # deployments made before REPORT_SECRET became required: keep their printed QR codes valid
        log.warning("REPORT_SECRET is not set: using the signing key from %s. Move it into REPORT_SECRET.", path)
        return path.read_bytes().strip()
    if not settings.demo_public_tokens:  # tests only may run without a configured key
        raise RuntimeError(report_secret_problem())
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48).encode()
    path.write_bytes(key)
    return key


def _mac(msg: str) -> str:
    raw = hmac.new(_secret(), msg.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def content_hash(data: dict[str, Any]) -> str:
    body = {k: v for k, v in (data or {}).items() if k != KEY}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _signed_on(report: Report) -> str:
    at = report.generated_at
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(timezone.utc).date().isoformat()


def _signature(report_id: str, sha: str, signed_on: str, version: int = 1) -> str:
    # The version is inside the signed message: lowering it in the database breaks the signature printed in the QR.
    return _mac(f"{DOMAIN_V2 if version >= 2 else DOMAIN}|{report_id}|{sha}|{signed_on}")


def _version(info: dict) -> int:
    return int(info.get("version", 1))


def sign(report: Report) -> dict[str, str]:
    sha = content_hash(report.data)
    info = {"sha256": sha, "signature": _signature(str(report.id), sha, _signed_on(report), VERSION),
            "signedOn": _signed_on(report), "algorithm": "HMAC-SHA256", "version": VERSION}
    report.data = {**(report.data or {}), KEY: info}
    return info


def file_signature(report_id: object, fmt: str, sha: str) -> str:
    """Keyed signature of a stored file's sha256; kept in the audit log next to the hash."""
    return _mac(f"{FILE_DOMAIN}|{report_id}|{fmt}|{sha.lower()}")


def self_consistent(report: Report) -> bool:
    """The report's own signature matches its stored hash and version (catches a downgraded version)."""
    info = (report.data or {}).get(KEY)
    if not info:
        return False
    expected = _signature(str(report.id), info["sha256"], info["signedOn"], _version(info))
    return hmac.compare_digest(info["signature"], expected)


def file_signed(report: Report, fmt: str, sha: str, sig: str | None) -> bool:
    """v2 reports: the file hash must carry a valid keyed signature. v1 reports predate file signatures."""
    if _version((report.data or {}).get(KEY) or {}) < 2:
        return True
    return bool(sig) and hmac.compare_digest(sig, file_signature(report.id, fmt, sha))


def signature_of(report: Report) -> dict[str, str]:
    info = (report.data or {}).get(KEY)
    if not info:
        raise HTTPException(409, "Звіт не підписано: підпишіть його (POST /reports/{id}/sign) або сформуйте заново")
    return info


def recorded_file(db: Session, report: Report) -> tuple[str | None, str | None]:
    # The file hash lives in the hash-chained audit log, not in report.data: whoever can edit the report row
    # must not be able to bless a swapped file.
    entry = db.scalars(
        select(AuditLogEntry)
        .where(AuditLogEntry.entity == "report", AuditLogEntry.entity_id == report.id,
               AuditLogEntry.action == "generate")
        .order_by(AuditLogEntry.id)
    ).first()
    value = (entry.new_value or {}) if entry else {}
    return value.get("sha256"), value.get("fileSignature")


def verify(report: Report | None, sha: str, sig: str, file_sha: str | None = None,
           file_sig: str | None = None) -> tuple[bool, str]:
    if report is None:
        return False, "Звіт з таким ідентифікатором не знайдено"
    info = (report.data or {}).get(KEY)
    if not info:
        return False, "Звіт не має цифрового підпису"
    expected = _signature(str(report.id), info["sha256"], info["signedOn"], _version(info))
    if not (hmac.compare_digest(sha, info["sha256"]) and hmac.compare_digest(sig, expected)):
        return False, "Підпис або хеш з QR-коду не відповідають звіту"
    if not hmac.compare_digest(content_hash(report.data), info["sha256"]):
        return False, "Вміст звіту змінено після підписання"
    if report.file_key and not (file_sha and file_signed(report, MAIN_FILE, file_sha, file_sig)
                                and storage.verify(report.file_key, file_sha)):
        return False, "Файл звіту змінено або пошкоджено після підписання"
    return True, "Підпис дійсний"


def verify_url(report: Report) -> str:
    info = signature_of(report)
    query = urlencode({"id": str(report.id), "h": info["sha256"], "sig": info["signature"]})
    return f"{settings.site_url.rstrip('/')}/verify?{query}"


def qr_svg(url: str, scale: int = 3) -> str:
    qr = segno.make(url, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", xmldecl=False, svgns=True, nl=False, scale=scale, border=2)
    width, height = qr.symbol_size(scale=scale, border=2)
    return buf.getvalue().decode().replace("<svg ", f'<svg viewBox="0 0 {width} {height}" ', 1)


def qr_png(url: str, scale: int = 6) -> bytes:
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


def signed_at(report: Report) -> datetime:
    at = report.generated_at
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)
