import csv
import html
import io
import json
import uuid
from datetime import date
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, halfyear
from ..enums import (
    FLAG_UA,
    LEVEL_UA,
    NAZK_STATE_NOT_DUE,
    REC_STATUS_UA,
    SEVERITY_UA,
    STATUS_UA,
    FlagStatus,
    MeasureStatus,
    RecStatus,
    ReportType,
)
from ..models import AuditLogEntry, Measure, MeasurePeriod, Program, Recommendation, Report, ReportFile, User, utcnow
from ..schemas import domain as s
from . import analytics, exporters, integrity, storage


def _row(m: Measure, p: MeasurePeriod | None, period_end: date) -> s.NazkMeasureRow:
    executors = "; ".join(
        a.org_unit.name + (f" ({a.user.display_name})" if a.user else "") for a in m.assignments
    )
    ind = m.indicator
    base = dict(
        measure_id=m.id,
        code=m.code,
        title=m.title,
        executors=executors,
        planned_deadline=m.deadline_text
        or ("Постійно" if m.is_permanent else m.planned_deadline.strftime("%d.%m.%Y")),
        corruption_risk=f"{m.risk.code}. {m.risk.description}" if m.risk else None,
        # Індикатор виконання з паспорта; для кількісного — ціль і останній факт
        indicator=(
            f"{m.indicator_text or ind.name}: ціль {ind.target:g}, факт "
            f"{f'{ind.current:g}' if ind.current is not None else '—'} {ind.unit}".strip()
            if ind else (m.indicator_text or None)
        ),
    )
    if p is None:
        return s.NazkMeasureRow(**base, actual_deadline=None, state=NAZK_STATE_NOT_DUE, result_or_reason="")

    state = p.to_nazk_state(period_end)
    if state == NAZK_STATE_NOT_DUE:
        actual = None
    elif m.is_permanent:
        actual = period_end
    else:
        actual = p.actual_date
    if p.status in (MeasureStatus.DONE, MeasureStatus.PARTIAL):
        text = p.result_description or ""
    elif state == NAZK_STATE_NOT_DUE:
        text = ""
    else:
        text = p.non_execution_reason or ""
    return s.NazkMeasureRow(
        **base,
        actual_deadline=actual.strftime("%d.%m.%Y") if actual else None,
        state=state,
        result_or_reason=text,
    )


def build_nazk(program: Program, period: str, report_id) -> s.NazkReport:
    end = halfyear.end(period)
    sections = []
    for sec in program.sections:
        rows = []
        for m in sec.measures:
            p = next((x for x in m.periods if x.period == period), None)
            if p is None and not m.is_permanent:
                earlier = [x for x in m.periods if x.period <= period]
                p = earlier[-1] if earlier else None
            rows.append(_row(m, p, end))
        sections.append(s.NazkSection(number=sec.number, title=sec.title, measures=rows))
    return s.NazkReport(
        report_id=report_id,
        program_title=program.title,
        org_unit=program.org_unit.name,
        period=period,
        period_end=end,
        has_restricted_info=program.has_restricted_info,
        sections=sections,
    )


def to_csv(r: s.NazkReport) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Розділ", "№", "Захід", "Виконавці", "Строк", "Фактичний строк виконання", "Стан виконання",
                "Опис результату виконання заходу або пояснення причин невиконання", "Корупційний ризик", "Індикатор"])
    for sec in r.sections:
        for m in sec.measures:
            w.writerow([sec.number, m.code, m.title, m.executors, m.planned_deadline, m.actual_deadline or "",
                        m.state, m.result_or_reason, m.corruption_risk or "", m.indicator or ""])
    return "﻿" + buf.getvalue()


def _stamp_html(stamp: dict | None) -> str:
    if not stamp:
        return ""
    e = html.escape
    return (
        "<div class='stamp'>"
        f"<div class='qr'>{stamp['svg']}</div>"
        "<div><b>Перевірка справжності звіту</b><br>"
        "Відскануйте QR-код: справжній звіт показує «Підтверджено».<br>"
        f"SHA-256: <span class='mono'>{e(stamp['sha256'])}</span></div></div>"
    )


def to_print_html(r: s.NazkReport, stamp: dict | None = None) -> str:
    e = html.escape
    parts = [
        "<!doctype html><html lang='uk'><head><meta charset='utf-8'>",
        f"<title>Звіт {e(r.period)}</title>",
        "<style>body{font:12pt 'Times New Roman',serif;margin:2cm}h1,h2{text-align:center}"
        "table{width:100%;border-collapse:collapse;margin-bottom:1em}td,th{border:1px solid #000;padding:4px;"
        "vertical-align:top}th{background:#eee}@media print{.np{display:none}}"
        ".stamp{display:flex;gap:12px;align-items:center;margin-top:2em;padding:8px;border:1px solid #000;"
        "font-size:9pt;page-break-inside:avoid}.qr svg{display:block}.mono{font-family:monospace;word-break:break-all}"
        "</style></head><body>",
        f"<h1>Звіт про виконання антикорупційної програми</h1><h2>{e(r.program_title)}</h2>",
        f"<p>Орган: {e(r.org_unit)}<br>Звітний період: {e(r.period)} (по {r.period_end:%d.%m.%Y})</p>",
    ]
    if r.has_restricted_info:
        parts.append("<p><b>Програма містить інформацію з обмеженим доступом — звіт подається у паперовому вигляді.</b></p>")
    for sec in r.sections:
        parts.append(f"<h3>Розділ {sec.number}. {e(sec.title)}</h3><table><tr><th>№</th><th>Захід</th>"
                     "<th>Фактичний строк виконання</th><th>Стан виконання</th>"
                     "<th>Опис результату виконання заходу або пояснення причин невиконання</th></tr>")
        for m in sec.measures:
            parts.append(f"<tr><td>{e(m.code)}</td><td>{e(m.title)}</td><td>{e(m.actual_deadline or '')}</td>"
                         f"<td>{e(m.state)}</td><td>{e(m.result_or_reason)}</td></tr>")
        parts.append("</table>")
    parts.append("<p style='margin-top:3em'>Уповноважена особа ____________________ &nbsp; Дата ____________</p>")
    parts.append(_stamp_html(stamp))
    parts.append("</body></html>")
    return "".join(parts)


INFO, WARNING, CRITICAL = "INFO", "WARNING", "CRITICAL"
OVERDUE_CRITICAL_SHARE = 25  # % прострочених заходів, з якого висновок критичний
RETURN_RATE_WARNING = 30  # % повернень, з якого якість внесення вважається проблемою
REVIEW_DAYS_WARNING = 10  # днів на перевірку, з якого координатор — вузьке місце
UNIT_OVERDUE_WARNING = 2  # прострочених заходів у підрозділі (як правило R6)


def conclusions(o) -> list[s.Conclusion]:
    k = o.kpis
    out = [s.Conclusion(
        rule="I1", severity=INFO,
        text=f"Виконано {k.done} з {k.measures_total} заходів ({k.done_percent}%), "
             f"на перевірці — {k.on_review}, повернено на доопрацювання — {k.returned}, не виконано — {k.not_done}.",
        facts={"done": k.done, "total": k.measures_total, "donePercent": k.done_percent},
    )]
    if k.overdue:
        share = round(100 * k.overdue / k.measures_total, 1) if k.measures_total else 0
        out.append(s.Conclusion(
            rule="I2", severity=CRITICAL if share >= OVERDUE_CRITICAL_SHARE else WARNING,
            text=f"Прострочено {k.overdue} заходів ({share}% програми).",
            facts={"overdue": k.overdue, "sharePercent": share, "criticalFrom": OVERDUE_CRITICAL_SHARE},
        ))
    formal = [r.code for r in o.risks
              if r.formal_closures or (r.measures_total and r.measures_done == r.measures_total and not r.reduced)]
    not_reduced = [r.code for r in o.risks if not r.reduced]
    out.append(s.Conclusion(
        rule="I3", severity=CRITICAL if formal else (WARNING if not_reduced else INFO),
        text=f"За індикаторами зменшено {k.risks_reduced} з {k.risks_total} корупційних ризиків."
             + (f" Ризики без підтвердженого зменшення: {', '.join(not_reduced)}." if not_reduced else "")
             + (f" Ознаки формального закриття (заходи виконано, індикатор не змінився): {', '.join(formal)}."
                if formal else ""),
        facts={"reduced": k.risks_reduced, "total": k.risks_total, "notReduced": not_reduced, "formalClosure": formal},
    ))
    if k.done and k.evidence_coverage_percent < 100:
        out.append(s.Conclusion(
            rule="I4", severity=WARNING,
            text=f"Підтвердні матеріали є лише для {k.evidence_coverage_percent}% виконаних заходів.",
            facts={"evidenceCoveragePercent": k.evidence_coverage_percent},
        ))
    if k.return_rate_percent >= RETURN_RATE_WARNING:
        out.append(s.Conclusion(
            rule="I5", severity=WARNING,
            text=f"Координатор повертає {k.return_rate_percent}% поданих результатів — "
                 "виконавцям потрібні чіткіші вимоги до опису результату та документів.",
            facts={"returnRatePercent": k.return_rate_percent, "threshold": RETURN_RATE_WARNING},
        ))
    if k.avg_review_days is not None and k.avg_review_days > REVIEW_DAYS_WARNING:
        out.append(s.Conclusion(
            rule="I6", severity=WARNING,
            text=f"Середній час перевірки результатів — {k.avg_review_days} дн.",
            facts={"avgReviewDays": k.avg_review_days, "threshold": REVIEW_DAYS_WARNING},
        ))
    units = [u.name for u in o.units if u.overdue >= UNIT_OVERDUE_WARNING]
    if units:
        out.append(s.Conclusion(
            rule="I7", severity=WARNING,
            text=f"Системне порушення строків (≥{UNIT_OVERDUE_WARNING} прострочених заходів): {', '.join(units)}.",
            facts={"units": units, "threshold": UNIT_OVERDUE_WARNING},
        ))
    return out


def build_internal(db: Session, program: Program, period: str, today: date) -> s.InternalMemo:
    as_of = min(today, halfyear.end(period))
    o = analytics.overview(db, program, as_of)
    ms = [m for sec in program.sections for m in sec.measures]
    problems = []
    for m in ms:
        open_flags = [f for f in m.flags if f.status == FlagStatus.OPEN]
        if open_flags:
            p = m.period_for(as_of)
            resp = m.responsible
            problems.append(s.ProblemMeasure(
                code=m.code, title=m.title, status=p.status if p else None,
                responsible_unit=resp.org_unit.name if resp else None,
                flags=[f"{f.rule_code} «{FLAG_UA[f.type]}»: {f.explanation}" for f in open_flags],
            ))
    mids = {m.id for m in ms}
    recs = [r for r in db.scalars(select(Recommendation).where(
        Recommendation.status.in_([RecStatus.PROPOSED, RecStatus.ACCEPTED]))) if r.measure_id in mids]
    recs.sort(key=lambda r: (r.basis.get("priority", 9), r.created_at))
    users = {u.id: u.display_name for u in db.scalars(select(User))}
    return s.InternalMemo(
        program_title=program.title, period=period, as_of=as_of,
        kpis=o.kpis.model_dump(by_alias=True),
        conclusions=conclusions(o),
        risks=[{"code": r.code, "description": r.description, "level": r.level.value, "reduced": r.reduced,
                "formalClosures": r.formal_closures,
                "indicators": [{"name": i.name, "baseline": str(i.baseline), "target": str(i.target),
                                "current": str(i.current) if i.current is not None else None,
                                "progressPercent": i.progress_percent} for i in r.indicators]}
               for r in o.risks],
        units=[u.model_dump(mode="json", by_alias=True) for u in o.units],
        problem_measures=problems,
        recommendations=[s.MemoRecommendation(
            text=r.text, status=r.status, priority=r.basis.get("priority"), rule=r.basis.get("rule"),
            responsible=users.get(r.responsible_id), due_date=r.due_date,
        ) for r in recs],
    )


_SEVERITY = {INFO: "", WARNING: "Увага: ", CRITICAL: "Критично: "}
NAZK_HEADER = ["№", "Захід", "Виконавці", "Строк", "Фактичний строк виконання", "Стан виконання",
               "Опис результату виконання заходу або пояснення причин невиконання"]


def _camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w.title() for w in rest)


def _kpi_rows(kpis: dict) -> list[list]:
    return [["Показник", "Значення"]] + [[label, kpis.get(_camel(f))] for f, label in analytics.KPI_LABELS.items()]


Writer = exporters.Docx | exporters.Pdf


def _stamp(d: Writer, stamp: dict | None) -> None:
    if not stamp:
        return
    d.heading("Перевірка справжності звіту", 2)
    d.image(stamp["png"], width_cm=3.5)
    d.para("Відскануйте QR-код: справжній звіт показує «Підтверджено».")
    d.para(f"SHA-256: {stamp['sha256']}")


def nazk_doc(r: s.NazkReport, stamp: dict | None = None, d: Writer | None = None) -> bytes:
    d = d or exporters.Docx()
    d.heading("Звіт про виконання антикорупційної програми", 0)
    d.para(r.program_title, bold=True)
    d.para(f"Орган: {r.org_unit}. Звітний період: {r.period} (по {r.period_end:%d.%m.%Y}).")
    if r.has_restricted_info:
        d.para("Програма містить інформацію з обмеженим доступом — звіт подається у паперовому вигляді.", bold=True)
    for sec in r.sections:
        d.heading(f"Розділ {sec.number}. {sec.title}", 2)
        d.table([NAZK_HEADER] + [[m.code, m.title, m.executors, m.planned_deadline, m.actual_deadline or "",
                                  m.state, m.result_or_reason] for m in sec.measures])
    d.para("Уповноважена особа ____________________   Дата ____________")
    _stamp(d, stamp)
    return d.bytes()


def memo_doc(m: s.InternalMemo, stamp: dict | None = None, d: Writer | None = None) -> bytes:
    d = d or exporters.Docx()
    d.heading("Аналітична довідка про стан виконання антикорупційної програми", 0)
    d.para(m.program_title, bold=True)
    d.para(f"Звітний період: {m.period}. Дані станом на {m.as_of:%d.%m.%Y}. Для внутрішнього використання.")
    d.heading("1. Висновки", 1)
    d.bullets(f"{_SEVERITY.get(c.severity, '')}{c.text} [правило {c.rule}]" for c in m.conclusions)
    d.heading("2. Основні показники", 1)
    d.table(_kpi_rows(m.kpis))
    d.heading("3. Стан корупційних ризиків", 1)
    d.table([["Ризик", "Рівень", "Індикатор", "Базове", "Ціль", "Поточне", "Зменшено"]]
            + [[f"{r['code']}. {r['description']}", LEVEL_UA.get(r["level"], r["level"]), i["name"], i["baseline"], i["target"],
                i["current"] or "—", "так" if r["reduced"] else "ні"]
               for r in m.risks for i in r["indicators"]])
    d.heading("4. Виконання за підрозділами (за абеткою, без рейтингування)", 1)
    d.table([["Підрозділ", "Заходів", "Виконано", "Прострочено", "Повернень", "Risk Flags", "Вчасно, %"]]
            + [[u["name"], u["total"], u["done"], u["overdue"], u["returned"], u["openFlags"], u["onTimePercent"]]
               for u in m.units])
    d.heading("5. Проблемні заходи", 1)
    if m.problem_measures:
        d.table([["№", "Захід", "Стан", "Відповідальний", "Risk Flags"]]
                + [[p.code, p.title, STATUS_UA[p.status] if p.status else "", p.responsible_unit or "", "\n".join(p.flags)]
                   for p in m.problem_measures])
    else:
        d.para("Відкритих Risk Flags немає.")
    d.heading("6. Рекомендації (за явними правилами; рішення ухвалює керівник)", 1)
    if m.recommendations:
        d.table([["Пріоритет", "Рекомендація", "Підстава", "Статус", "Відповідальний", "Строк"]]
                + [[r.priority, r.text, r.rule or "", REC_STATUS_UA[r.status], r.responsible or "",
                    r.due_date.strftime("%d.%m.%Y") if r.due_date else ""] for r in m.recommendations])
    else:
        d.para("Рекомендацій немає.")
    _stamp(d, stamp)
    return d.bytes()


def report_xlsx(r: s.NazkReport, memo: s.InternalMemo | None = None) -> bytes:
    sheets: dict[str, list[list]] = {
        "Звіт НАЗК": [["Розділ"] + NAZK_HEADER + ["Корупційний ризик", "Індикатор"]]
        + [[sec.number, m.code, m.title, m.executors, m.planned_deadline, m.actual_deadline or "", m.state,
            m.result_or_reason, m.corruption_risk or "", m.indicator or ""] for sec in r.sections for m in sec.measures],
    }
    if memo:
        sheets["Висновки"] = [["Правило", "Рівень", "Висновок"]] + [[c.rule, SEVERITY_UA.get(c.severity, c.severity), c.text] for c in memo.conclusions]
        sheets["Показники"] = _kpi_rows(memo.kpis)
        sheets["Рекомендації"] = [["Пріоритет", "Рекомендація", "Підстава", "Статус", "Відповідальний", "Строк"]] + [
            [x.priority, x.text, x.rule, REC_STATUS_UA[x.status], x.responsible, x.due_date.isoformat() if x.due_date else None]
            for x in memo.recommendations]
    return exporters.to_xlsx(sheets)


def memo_of(rep: Report) -> s.InternalMemo | None:
    raw = (rep.data or {}).get("internal")
    return s.InternalMemo.model_validate(raw) if raw else None


def generate(db: Session, user: User, program: Program, period: str, rtype: ReportType, today: date) -> Report:
    rep = Report(program_id=program.id, period=period, type=rtype, generated_by=user.id)
    db.add(rep)
    db.flush()
    data = build_nazk(program, period, rep.id)
    rep.data = json.loads(data.model_dump_json(by_alias=True))
    memo = None
    if rtype == ReportType.INTERNAL:
        memo = build_internal(db, program, period, today)
        rep.data = {**rep.data, "internal": json.loads(memo.model_dump_json(by_alias=True))}
    signature = integrity.sign(rep)
    if rtype == ReportType.PRINT:
        content, ext = to_print_html(data, stamp(rep, "svg")).encode(), ".html"
    elif memo:
        content, ext = memo_doc(memo, stamp(rep, "png")), ".docx"
    else:
        content, ext = json.dumps(rep.data, ensure_ascii=False, indent=2).encode(), ".json"
    rep.file_key, sha = storage.put_object(db, f"reports/{program.id}", f"report{ext}", content)
    audit.record(db, user, "report", rep.id, "generate", None,
                 {"programId": str(program.id), "period": period, "type": rtype.value, "sha256": sha,
                  "fileSignature": integrity.file_signature(rep.id, integrity.MAIN_FILE, sha),
                  "contentSha256": signature["sha256"], "signature": signature["signature"]})
    issue_copies(db, user, rep)
    return rep


CopyFormat = Literal["pdf", "docx", "xlsx", "csv", "json", "html"]
COPY_FORMATS: tuple[CopyFormat, ...] = ("pdf", "docx", "xlsx", "csv", "json", "html")
MEDIA_TYPES: dict[CopyFormat, str] = {
    "pdf": exporters.PDF_TYPE, "docx": exporters.DOCX_TYPE, "xlsx": exporters.XLSX_TYPE,
    "csv": "text/csv; charset=utf-8", "json": "application/json", "html": "text/html; charset=utf-8",
}


def render(rep: Report, fmt: CopyFormat) -> bytes:
    data = s.NazkReport.model_validate(rep.data)
    memo = memo_of(rep)
    if fmt == "csv":
        return to_csv(data).encode()
    if fmt == "json":
        return data.model_dump_json(by_alias=True).encode()
    if fmt == "html":
        return to_print_html(data, stamp(rep, "svg")).encode()
    if fmt == "xlsx":
        return report_xlsx(data, memo)
    writer = exporters.Pdf() if fmt == "pdf" else exporters.Docx()
    return memo_doc(memo, stamp(rep, "png"), writer) if memo else nazk_doc(data, stamp(rep, "png"), writer)


def issue_copies(db: Session, user: User, rep: Report) -> None:
    # Exports are frozen once: every download is byte-identical, so an uploaded copy can be matched by sha256.
    have = set(db.scalars(select(ReportFile.format).where(ReportFile.report_id == rep.id)))
    hashes: dict[str, str] = {}
    for fmt in COPY_FORMATS:
        if fmt in have:
            continue
        key, sha = storage.put_object(db, f"reports/{rep.program_id}/copies", f"copy.{fmt}", render(rep, fmt))
        db.add(ReportFile(report_id=rep.id, format=fmt, file_key=key, sha256=sha))
        hashes[fmt] = sha
    if hashes:
        signatures = {fmt: integrity.file_signature(rep.id, fmt, sha) for fmt, sha in hashes.items()}
        audit.record(db, user, "report", rep.id, "issue_copies", None, {"copies": hashes, "signatures": signatures})


def copy_of(db: Session, rep: Report, fmt: CopyFormat) -> bytes:
    f = db.scalar(select(ReportFile).where(ReportFile.report_id == rep.id, ReportFile.format == fmt))
    if f is None:
        return render(rep, fmt)
    integrity.signature_of(rep)
    if not storage.verify(f.file_key, f.sha256):
        raise HTTPException(409, "Збережену копію звіту змінено або пошкоджено")
    return storage.get_object(f.file_key)


def stamp(rep: Report, kind: str) -> dict:
    url = integrity.verify_url(rep)
    out = {"url": url, "sha256": integrity.signature_of(rep)["sha256"]}
    out["svg" if kind == "svg" else "png"] = integrity.qr_svg(url) if kind == "svg" else integrity.qr_png(url)
    return out


def newer_edition(db: Session, rep: Report) -> Report | None:
    """The latest non-revoked report of the same program, period and type generated after this one."""
    return db.scalars(
        select(Report)
        .where(Report.program_id == rep.program_id, Report.period == rep.period, Report.type == rep.type,
               Report.generated_at > rep.generated_at, Report.revoked_at.is_(None))
        .order_by(Report.generated_at.desc())
    ).first()


def revoke(db: Session, user: User, rep: Report, reason: str) -> Report:
    if rep.revoked_at is not None:
        raise HTTPException(409, "Звіт уже відкликано")
    rep.revoked_at, rep.revoked_by, rep.revoke_reason = utcnow(), user.id, reason.strip()
    audit.record(db, user, "report", rep.id, "revoke", None, {"reason": rep.revoke_reason})
    return rep


def check_copy(db: Session, sha256: str, report_id: str) -> s.ReportCopyCheck:
    # Hashes come from the hash-chained audit log, so a swapped stored copy cannot vouch for itself.
    sha = sha256.strip().lower()
    q = select(AuditLogEntry).where(AuditLogEntry.entity == "report", AuditLogEntry.action == "issue_copies")
    if report_id:
        try:
            q = q.where(AuditLogEntry.entity_id == uuid.UUID(report_id))
        except ValueError:
            return s.ReportCopyCheck(match=False, reason="Звіт з таким ідентифікатором не знайдено")
    for entry in db.scalars(q.order_by(AuditLogEntry.id)):
        value = entry.new_value or {}
        fmt = next((f for f, h in value.get("copies", {}).items() if h == sha), None)
        rep = db.get(Report, entry.entity_id) if fmt else None
        # A hash counts only if the key vouches for it: an edited audit row (even with a rebuilt chain) does not.
        if rep and integrity.self_consistent(rep) and integrity.file_signed(rep, fmt, sha,
                                                                            value.get("signatures", {}).get(fmt)):
            data = s.NazkReport.model_validate(rep.data)
            reason = "Файл збігається з копією, виданою системою"
            if rep.revoked_at is not None:
                reason += f", але звіт відкликано {rep.revoked_at:%d.%m.%Y}: {rep.revoke_reason}"
            elif newer := newer_edition(db, rep):
                reason += f", але існує новіша редакція звіту від {newer.generated_at:%d.%m.%Y}"
            return s.ReportCopyCheck(
                match=True, reason=reason, report_id=rep.id, format=fmt,
                issued_at=entry.at, period=rep.period, type=rep.type, program_title=data.program_title,
            )
    return s.ReportCopyCheck(
        match=False,
        reason="Файл не збігається з жодною копією, виданою системою" + (" для цього звіту" if report_id else ""),
    )
