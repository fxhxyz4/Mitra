import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from ..auth import Coordinator, DbDep, require_roles
from .. import audit
from ..config import today
from ..enums import ReportType, Role
from ..models import Program, Report, User
from ..schemas import domain as s
from ..services import integrity
from ..services import reports as svc

router = APIRouter(prefix="/reports", tags=["Reporting"])

ReportUser = Depends(require_roles(Role.COORDINATOR, Role.ANALYST))


def _get(db, report_id: uuid.UUID) -> Report:
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Звіт не знайдено")
    return r


@router.get("", response_model=list[s.ReportOut], dependencies=[ReportUser])
def list_reports(db: DbDep):
    return db.scalars(select(Report).order_by(Report.generated_at.desc())).all()


@router.post("/generate", response_model=s.ReportOut, status_code=201)
def generate(data: s.ReportIn, db: DbDep, user: Coordinator):
    program = db.get(Program, data.program_id)
    if not program:
        raise HTTPException(404, "Програму не знайдено")
    r = svc.generate(db, user, program, data.period, data.type, today())
    db.commit()
    return r


@router.get("/{report_id}/nazk", response_model=s.NazkReport, dependencies=[ReportUser])
def nazk(report_id: uuid.UUID, db: DbDep, format: Literal["json", "csv"] = "json"):
    """Дані у структурі полів Порталу доброчесності НАЗК (знімок на момент генерації)."""
    r = _get(db, report_id)
    headers = {"Content-Disposition": f'attachment; filename="nazk-{r.period}.csv"'} if format == "csv" else None
    return Response(svc.copy_of(db, r, format), media_type=svc.MEDIA_TYPES[format], headers=headers)


@router.get("/{report_id}/print", response_class=HTMLResponse, dependencies=[ReportUser])
def print_form(report_id: uuid.UUID, db: DbDep):
    """Друкована форма (для програм з інформацією з обмеженим доступом — подання на папері) з QR перевірки."""
    return HTMLResponse(svc.copy_of(db, _get(db, report_id), "html"))


@router.get("/{report_id}/integrity", response_model=s.ReportIntegrity, dependencies=[ReportUser])
def report_integrity(report_id: uuid.UUID, db: DbDep):
    """Хеш, підпис і QR-посилання для перевірки справжності звіту."""
    r = _get(db, report_id)
    info = integrity.signature_of(r)
    url = integrity.verify_url(r)
    return s.ReportIntegrity(report_id=r.id, sha256=info["sha256"], signature=info["signature"],
                             signed_on=info["signedOn"], algorithm=info["algorithm"], verify_url=url,
                             qr_svg=integrity.qr_svg(url, scale=4))


@router.post("/{report_id}/sign", response_model=s.ReportOut)
def sign(report_id: uuid.UUID, db: DbDep, user: Coordinator):
    """Підписати звіт, сформований до появи підписів, і зафіксувати його копії. Уже підписаний звіт не змінюється."""
    r = _get(db, report_id)
    if not (r.data or {}).get(integrity.KEY):
        info = integrity.sign(r)
        audit.record(db, user, "report", r.id, "sign", None, {"contentSha256": info["sha256"]})
    svc.issue_copies(db, user, r)
    db.commit()
    return r


@router.get("/copies/check", response_model=s.ReportCopyCheck)
def check_copy(db: DbDep, sha256: str, id: str = ""):
    """Публічна перевірка завантаженої копії: sha256 рахує браузер, сам файл на сервер не надсилається."""
    return svc.check_copy(db, sha256, id)


@router.get("/{report_id}/verify", response_model=s.ReportVerification)
def verify(report_id: str, db: DbDep, h: str = "", sig: str = ""):
    """Публічна перевірка справжності звіту за QR-кодом (без авторизації)."""
    try:
        r = db.get(Report, uuid.UUID(report_id))
    except ValueError:
        r = None
    ok, reason = integrity.verify(r, h, sig, *(integrity.recorded_file(db, r) if r else (None, None)))
    if not ok:
        return s.ReportVerification(valid=False, reason=reason)
    data = s.NazkReport.model_validate(r.data)
    author = db.get(User, r.generated_by) if r.generated_by else None
    out = s.ReportVerification(
        valid=True, reason=reason, report_id=r.id, period=r.period, type=r.type, program_title=data.program_title,
        org_unit=data.org_unit, generated_at=integrity.signed_at(r), generated_by=author.display_name if author else None,
        sha256=r.data[integrity.KEY]["sha256"],
    )
    if r.revoked_at is not None:  # genuine, but withdrawn: shown with its details so the reader knows which one
        out.valid, out.revoked_at, out.revoke_reason = False, r.revoked_at, r.revoke_reason
        out.reason = f"Звіт відкликано {r.revoked_at:%d.%m.%Y}: {r.revoke_reason}"
    elif newer := svc.newer_edition(db, r):
        out.superseded_by, out.superseded_at = newer.id, integrity.signed_at(newer)
    return out


@router.post("/{report_id}/revoke", response_model=s.ReportOut)
def revoke(report_id: uuid.UUID, data: s.ReportRevokeIn, db: DbDep, user: Coordinator):
    """Відкликати звіт (наприклад, сформований з помилкою). Підпис лишається, а перевірка за QR показує відкликання."""
    r = svc.revoke(db, user, _get(db, report_id), data.reason)
    db.commit()
    return r


@router.get("/{report_id}/internal", response_model=s.InternalMemo, dependencies=[ReportUser])
def internal(report_id: uuid.UUID, db: DbDep):
    """Аналітична довідка (тип INTERNAL): висновки за правилами I1–I7, показники, ризики, рекомендації."""
    memo = svc.memo_of(_get(db, report_id))
    if not memo:
        raise HTTPException(404, "Звіт не має аналітичної довідки: сформуйте звіт типу «Аналітична довідка»")
    return memo


@router.get("/{report_id}/export", dependencies=[ReportUser])
def export(report_id: uuid.UUID, db: DbDep, format: Literal["docx", "pdf", "xlsx"] = "docx"):
    """Експорт звіту: DOCX чи PDF (форма НАЗК або аналітична довідка для INTERNAL) або XLSX (таблиці)."""
    r = _get(db, report_id)
    name = f"{'memo' if r.type == ReportType.INTERNAL else 'nazk'}-{r.period}"
    return Response(svc.copy_of(db, r, format), media_type=svc.MEDIA_TYPES[format],
                    headers={"Content-Disposition": f'attachment; filename="{name}.{format}"'})
