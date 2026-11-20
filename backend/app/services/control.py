from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import audit, halfyear
from ..config import settings
from ..config import today as config_today
from ..enums import FINAL_STATUSES, NAZK_STATE_IN_PROGRESS, STATUS_UA, Channel, FlagStatus, FlagType, MeasureStatus, ProgramStatus, RecStatus, RiskLevel, Role
from ..models import Measure, MeasurePeriod, Program, Recommendation, Reminder, RiskFlag, Section, User, local_date, utcnow
from ..schemas import domain as s
from . import measures as measure_svc
from . import notify, risk_model
from .rules import vague_result_facts

RULES: dict[FlagType, tuple[str, str]] = {
    FlagType.OVERDUE: ("R1", "Строк минув, а результат не подано і статус не «Виконано»"),
    FlagType.NO_EVIDENCE: ("E1", "«Виконано» (або подано як виконаний) без документа визначеної форми"),
    FlagType.FORMAL_CLOSURE: ("F1", "Захід розділу 2 виконано, а індикатор ризику пройшов менше 10 % шляху до цілі; "
                                    "до кінця лагу ефекту висновок попередній"),
    FlagType.WORSENING: ("F2", "Захід розділу 2 виконано, а ризик погіршився (RRS < 0)"),
    FlagType.AWAITING_EFFECT: ("F3", "Застаріле правило: лаг ефекту тепер лише робить висновок F1 попереднім"),
    FlagType.VAGUE_RESULT: ("R4", "Опис повторює назву заходу або не має числа чи посилання"),
    FlagType.TARGET_MISSED: ("R5", "«Виконано» або «Частково», строк настав, а індикатор виконання нижче цілі"),
    FlagType.REPEATED_DELAY: ("R6", "У підрозділу друге (і більше) порушення строку за період"),
    FlagType.REPEATED_POSTPONEMENT: ("R6a", "Строк заходу переносили два і більше разів"),
    FlagType.DATE_OUT_OF_PERIOD: ("R7a", "Фактична дата виконання пізніше за кінець звітного періоду"),
    FlagType.BACKDATED_EVIDENCE: ("R7b", "Усі підтвердні документи датовано пізніше за фактичну дату виконання"),
    FlagType.NO_EXPLANATION: ("R7c", "Стан «Не виконано», а пояснення причин немає (поле Порталу обовʼязкове)"),
    FlagType.PREMATURE_DESCRIPTION: ("R7e", "Строк не настав, а опис результату заповнено (на Порталі не заповнюється)"),
}
_F_TYPES = {"F1": FlagType.FORMAL_CLOSURE, "F2": FlagType.WORSENING}
HEAD_ONLY = {FlagType.FORMAL_CLOSURE, FlagType.WORSENING}
REPEATED_DELAY_THRESHOLD = 2
POSTPONEMENT_THRESHOLD = 2
REMIND_AT = time(9, 0)


@dataclass
class Hit:
    measure: Measure
    type: FlagType
    facts: dict
    explanation: str


def _load_measures(db: Session, program_id=None) -> list[Measure]:
    q = (
        select(Measure)
        .join(Measure.section)
        .join(Section.program)
        .where(Program.status == ProgramStatus.APPROVED)
        .options(
            selectinload(Measure.periods).selectinload(MeasurePeriod.evidence),
            selectinload(Measure.assignments),
            selectinload(Measure.flags),
            selectinload(Measure.indicator),
            selectinload(Measure.deadline_changes),
        )
    )
    if program_id:
        q = q.where(Section.program_id == program_id)
    return list(db.scalars(q))


def execution_fact(m: Measure, today: date) -> tuple[Decimal | None, Decimal | None]:
    """(ціль, останній факт) індикатора виконання заходу; індикатор ризику сюди не входить."""
    ind = m.indicator
    if ind is None or ind.risk_id is not None:
        return None, None
    values = [v for v in ind.values if v.measured_at <= today]
    return ind.target, (values[-1].value if values else None)


def _check_measure(m: Measure, today: date) -> list[Hit]:
    p = m.period_for(today)
    if p is None or p.status == MeasureStatus.DRAFT:
        return []
    hits: list[Hit] = []
    deadline = m.deadline_for(p)
    base = {"period": p.period, "status": p.status.value, "deadline": deadline.isoformat()}

    # R1 OVERDUE — a result submitted as done and awaiting approval is not the executor's delay
    if deadline < today and p.status != MeasureStatus.DONE and not risk_model.is_submitted(p):
        days = (today - deadline).days
        hits.append(Hit(m, FlagType.OVERDUE, {**base, "daysOverdue": days},
                        f"Строк {deadline:%d.%m.%Y} минув {days} дн. тому, статус — «{STATUS_UA[p.status]}»."))

    closed = p if p.status in FINAL_STATUSES else risk_model.closed_period(m, today)
    # Заявлене виконання: погоджене «Виконано» / «Частково» або подане на перевірку з описом результату.
    claimed = p if risk_model.is_submitted(p) else (
        closed if closed is not None and closed.status in (MeasureStatus.DONE, MeasureStatus.PARTIAL) else None)
    if claimed is not None:
        pending = risk_model.is_submitted(claimed)
        cbase = {**base, "period": claimed.period, "status": claimed.status.value, "pendingApproval": pending}
        said = "подано як виконаний" if pending else "позначено виконаним"
        # E1 NO_EVIDENCE
        if not risk_model.has_document(m, claimed):
            form = (m.evidence_form or "").strip()
            hits.append(Hit(m, FlagType.NO_EVIDENCE, {**cbase, "evidenceCount": len(claimed.evidence), "form": form},
                            f"Захід {said}, але немає документа визначеної форми"
                            + (f" ({form})." if form else " — не завантажено жодного підтвердного документа.")))
        # F1 / F2 — formal closure (the risk model)
        f = risk_model.formal_closure_hit(m, claimed, today)
        if f:
            code, facts, text = f
            hits.append(Hit(m, _F_TYPES[code], {**cbase, **facts}, text))
        # R5 TARGET_MISSED — the measure's own execution indicator is below target once the deadline has come
        target, fact = execution_fact(m, today)
        if target is not None and fact is not None and fact < target and (
                m.is_permanent or m.deadline_for(claimed) <= today):
            unit = (m.indicator.unit or "").strip()
            hits.append(Hit(m, FlagType.TARGET_MISSED,
                            {**cbase, "fact": float(fact), "target": float(target), "unit": unit},
                            f"Індикатор виконання {fact:g} при цілі {target:g} {unit}".rstrip()
                            + f", а захід {said}."))
        # R7a DATE_OUT_OF_PERIOD
        period_end = halfyear.end(claimed.period)
        if claimed.actual_date and claimed.actual_date > period_end:
            hits.append(Hit(m, FlagType.DATE_OUT_OF_PERIOD,
                            {**cbase, "actualDate": claimed.actual_date.isoformat(), "periodEnd": period_end.isoformat()},
                            f"Фактична дата виконання {claimed.actual_date:%d.%m.%Y} пізніше за кінець звітного "
                            f"періоду {period_end:%d.%m.%Y}."))
        # R7b BACKDATED_EVIDENCE — only for measures with a date
        docs = claimed.evidence
        if (not m.is_permanent and claimed.actual_date and docs
                and all(e.document_date and e.document_date > claimed.actual_date for e in docs)):
            first = min(e.document_date for e in docs)
            hits.append(Hit(m, FlagType.BACKDATED_EVIDENCE,
                            {**cbase, "actualDate": claimed.actual_date.isoformat(),
                             "earliestDocument": first.isoformat(), "documents": len(docs)},
                            f"Найраніший підтвердний документ датовано {first:%d.%m.%Y}, пізніше за фактичну дату "
                            f"виконання {claimed.actual_date:%d.%m.%Y}: на дату закриття підтвердження не було."))

    # R7c NO_EXPLANATION — «Не виконано» on the Portal and no reason given
    if (p.to_nazk_state(today) == NAZK_STATE_IN_PROGRESS
            and p.status not in (MeasureStatus.DONE, MeasureStatus.PARTIAL, MeasureStatus.ON_REVIEW)
            and not (p.non_execution_reason or "").strip() and not (p.result_description or "").strip()):
        hits.append(Hit(m, FlagType.NO_EXPLANATION, base,
                        "Стан на Порталі «Не виконано», а пояснення причин невиконання немає "
                        "(поле обовʼязкове на Порталі)."))
    # R7e PREMATURE_DESCRIPTION — the deadline has not come, yet a result is filled in
    if (p.status in (MeasureStatus.PLANNED, MeasureStatus.IN_PROGRESS) and deadline > today
            and (p.result_description or "").strip()):
        hits.append(Hit(m, FlagType.PREMATURE_DESCRIPTION, base,
                        f"Строк {deadline:%d.%m.%Y} не настав, а опис результату заповнено: на Порталі для стану "
                        f"«Строк виконання заходу не настав» опис не заповнюється."))
    # R6a REPEATED_POSTPONEMENT — internal deadline-change decisions (the programme deadline itself never moves)
    postponements = len(m.deadline_changes)
    if postponements >= POSTPONEMENT_THRESHOLD:
        hits.append(Hit(m, FlagType.REPEATED_POSTPONEMENT,
                        {**base, "postponements": postponements, "threshold": POSTPONEMENT_THRESHOLD},
                        f"Строк заходу переносили {postponements} рази: "
                        + "; ".join(f"{c.old_deadline:%d.%m.%Y} → {c.new_deadline:%d.%m.%Y} ({c.reason})"
                                    for c in m.deadline_changes) + "."))

    # R4 VAGUE_RESULT
    vf = vague_result_facts(m.title, p.result_description)
    if vf:
        why = []
        if vf["similarityToTitle"] >= vf["threshold"]:
            why.append(f"схожість з назвою заходу {int(vf['similarityToTitle'] * 100)}%")
        if not (vf["hasNumber"] or vf["hasReference"]):
            why.append("немає числа чи посилання на документ")
        hits.append(Hit(m, FlagType.VAGUE_RESULT, {**base, **vf}, "Неінформативний опис результату: " + ", ".join(why) + "."))

    return hits


def _check_repeated(ms: list[Measure], overdue_hits: list[Hit], today: date) -> list[Hit]:
    hy = halfyear.of(today)
    by_unit: dict = defaultdict(list)
    for h in overdue_hits:
        resp = h.measure.responsible
        if resp and h.facts["period"] <= hy:
            by_unit[(resp.org_unit_id, resp.org_unit.name)].append(h.measure)
    out = []
    for (unit_id, unit_name), items in by_unit.items():
        if len(items) >= REPEATED_DELAY_THRESHOLD:
            codes = sorted(x.code or x.title[:30] for x in items)
            for m in items:
                out.append(Hit(m, FlagType.REPEATED_DELAY,
                               {"orgUnitId": str(unit_id), "orgUnit": unit_name, "overdueCount": len(items),
                                "threshold": REPEATED_DELAY_THRESHOLD, "measures": codes},
                               f"Підрозділ «{unit_name}» має {len(items)} прострочених заходів: {', '.join(codes)}."))
    return out


def evaluate(db: Session, today: date, program_id=None) -> tuple[int, int]:
    ms = _load_measures(db, program_id)
    hits: list[Hit] = []
    for m in ms:
        hits += _check_measure(m, today)
    hits += _check_repeated(ms, [h for h in hits if h.type == FlagType.OVERDUE], today)

    want = {(h.measure.id, h.type): h for h in hits}
    opened = resolved = 0
    for m in ms:
        open_flags = {f.type: f for f in m.flags if f.status == FlagStatus.OPEN}
        for t, f in open_flags.items():
            h = want.get((m.id, t))
            if h:
                f.facts, f.explanation = h.facts, h.explanation
            elif t not in HEAD_ONLY:
                f.status = FlagStatus.RESOLVED
                f.resolved_at = utcnow()
                f.resolution_comment = "Автоматично: умова правила більше не виконується"
                audit.record(db, None, "risk_flag", f.id, "auto_resolve", {"status": "OPEN"}, {"status": "RESOLVED"})
                resolved += 1
        for (mid, t), h in want.items():
            if mid == m.id and t not in open_flags:
                if t in HEAD_ONLY and any(
                    f.type == t and f.status == FlagStatus.RESOLVED and f.facts.get("period") == h.facts.get("period")
                    for f in m.flags
                ):
                    continue
                f = RiskFlag(measure=m, type=t, rule_code=RULES[t][0], facts=h.facts, explanation=h.explanation)
                db.add(f)
                db.flush()
                audit.record(db, None, "risk_flag", f.id, "open", None,
                             {"type": t.value, "ruleCode": f.rule_code, "measureId": str(m.id)})
                opened += 1
    db.flush()
    return opened, resolved


def resolve_flag(db: Session, user: User, flag: RiskFlag, comment: str) -> RiskFlag:
    if flag.status != FlagStatus.OPEN:
        raise HTTPException(409, "Прапорець уже знято")
    if flag.type in HEAD_ONLY and user.role != Role.HEAD:
        raise HTTPException(403, "Цей прапорець знімає лише керівник")
    if user.role not in (Role.HEAD, Role.COORDINATOR):
        raise HTTPException(403, "Знімати прапорці може лише координатор або керівник")
    flag.status = FlagStatus.RESOLVED
    flag.resolved_at = utcnow()
    flag.resolved_by = user.id
    flag.resolution_comment = comment
    audit.record(db, user, "risk_flag", flag.id, "resolve", {"status": "OPEN"}, {"status": "RESOLVED", "comment": comment})
    return flag


_REC_TEXT = {
    FlagType.OVERDUE: "Заслухати відповідального виконавця ({unit}) щодо причин порушення строку заходу {code} "
    "та встановити новий контрольний строк.",
    FlagType.NO_EVIDENCE: "Доручити {unit} завантажити підтвердні матеріали виконання заходу {code}; "
    "до їх надходження не враховувати захід як виконаний у звітності.",
    FlagType.FORMAL_CLOSURE: "Перевірити фактичний вплив заходу {code} на корупційний ризик {risk}: "
    "отримати актуальне значення індикатора або переглянути захід.",
    FlagType.VAGUE_RESULT: "Повернути опис результату заходу {code} на доопрацювання з вимогою зазначити "
    "вимірюваний показник і реквізити підтвердного документа.",
    FlagType.WORSENING: "Терміново переглянути захід {code}: попри виконання ризик {risk} погіршився; "
    "розглянути додатковий або інший захід.",
    FlagType.REPEATED_DELAY: "Розглянути на нараді системне порушення строків підрозділом {unit} "
    "та визначити заходи з посилення контролю.",
    FlagType.TARGET_MISSED: "Зʼясувати в {unit}, чому індикатор виконання заходу {code} не досяг цілі, "
    "і вирішити, чи зараховувати захід як виконаний.",
    FlagType.REPEATED_POSTPONEMENT: "Заслухати {unit} щодо повторних перенесень строку заходу {code}; "
    "наступне перенесення — лише з рішення керівника.",
    FlagType.BACKDATED_EVIDENCE: "Перевірити підтвердні документи заходу {code}: на дату виконання їх ще не було; "
    "уточнити фактичну дату виконання.",
    FlagType.NO_EXPLANATION: "Доручити {unit} внести пояснення причин невиконання заходу {code} — поле обовʼязкове "
    "на Порталі.",
    FlagType.DATE_OUT_OF_PERIOD: "Уточнити фактичну дату виконання заходу {code}: вона поза звітним періодом.",
}
_LEVEL_PRIORITY = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3, None: 3}
_TYPE_PRIORITY = {FlagType.WORSENING: 0, FlagType.FORMAL_CLOSURE: 0, FlagType.REPEATED_DELAY: 1}


def generate_recommendations(db: Session) -> int:
    existing = set()
    for r in db.scalars(select(Recommendation).where(Recommendation.status != RecStatus.DONE)):
        if r.status != RecStatus.REJECTED or (r.flag is not None and r.flag.status == FlagStatus.OPEN):
            existing.add(r.basis.get("dedupKey"))
    n = 0
    for f in db.scalars(select(RiskFlag).where(RiskFlag.status == FlagStatus.OPEN)):
        m = f.measure
        resp = m.responsible
        unit = resp.org_unit.name if resp else "—"
        key = f"{f.type}:{f.facts.get('orgUnitId')}" if f.type == FlagType.REPEATED_DELAY else f"{f.type}:{m.id}"
        if key in existing or f.type not in _REC_TEXT:  # F3 «очікування ефекту» — без рекомендації
            continue
        level = m.risk.level if m.risk else None
        priority = _LEVEL_PRIORITY[level] + _TYPE_PRIORITY.get(f.type, 2)
        text = _REC_TEXT[f.type].format(unit=unit, code=m.code or m.title, risk=m.risk.code if m.risk else "—")
        rec = Recommendation(
            flag_id=f.id,
            measure_id=m.id,
            text=text,
            basis={
                "dedupKey": key,
                "rule": f.rule_code,
                "ruleDescription": RULES[f.type][1],
                "flagType": f.type.value,
                "explanation": f.explanation,
                "facts": f.facts,
                "riskLevel": level.value if level else None,
                "priority": priority,
                "source": "rules",
            },
        )
        db.add(rec)
        db.flush()
        audit.record(db, None, "recommendation", rec.id, "propose", None, {"text": text, "flagId": str(f.id)})
        existing.add(key)
        n += 1
    return n


def decide_recommendation(db: Session, user: User, rec: Recommendation, accept: bool, data) -> Recommendation:
    if rec.status != RecStatus.PROPOSED:
        raise HTTPException(409, "Рішення щодо цієї рекомендації вже ухвалено")
    old = {"status": rec.status.value}
    rec.decided_by = user.id
    rec.decided_at = utcnow()
    if accept:
        responsible = db.get(User, data.responsible_id)
        if not responsible or responsible.deleted_at:
            raise HTTPException(422, "Відповідального не знайдено")
        rec.status = RecStatus.ACCEPTED
        rec.responsible_id = data.responsible_id
        rec.due_date = data.due_date
        new = {"status": "ACCEPTED", "responsibleId": str(data.responsible_id), "dueDate": data.due_date.isoformat()}
        if data.text and data.text.strip() != rec.text:
            rec.basis = {**rec.basis, "originalText": rec.text}
            old["text"], new["text"] = rec.text, data.text.strip()
            rec.text = data.text.strip()
    else:
        rec.status = RecStatus.REJECTED
        rec.basis = {**rec.basis, "rejectionComment": data.comment}
        new = {"status": "REJECTED", "comment": data.comment}
    audit.record(db, user, "recommendation", rec.id, "accept" if accept else "reject", old, new)
    return rec


def complete_recommendation(db: Session, user: User, rec: Recommendation, comment: str) -> Recommendation:
    if rec.status != RecStatus.ACCEPTED:
        raise HTTPException(409, "Позначити виконаною можна лише прийняту рекомендацію")
    if user.role != Role.HEAD and user.id != rec.responsible_id:
        raise HTTPException(403, "Закрити рекомендацію може відповідальний або керівник")
    rec.status = RecStatus.DONE
    rec.basis = {**rec.basis, "completionComment": comment, "completedBy": str(user.id),
                 "completedAt": utcnow().isoformat()}
    audit.record(db, user, "recommendation", rec.id, "complete", {"status": "ACCEPTED"},
                 {"status": "DONE", "comment": comment})
    return rec


def _recipients(db: Session, m: Measure) -> list[User]:
    out: dict = {}
    for a in m.assignments:
        if a.user:
            out[a.user.id] = a.user
        else:
            for u in db.scalars(select(User).where(
                User.org_unit_id == a.org_unit_id, User.role == Role.EXECUTOR, User.deleted_at.is_(None)
            )):
                out[u.id] = u
    return list(out.values())


def generate_reminders(db: Session, today: date) -> int:
    n = 0
    now = utcnow()
    have = {(r.measure_id, r.user_id, local_date(r.send_at)) for r in db.scalars(select(Reminder))}
    for m in _load_measures(db):
        p = m.period_for(today)
        if not p or p.status in FINAL_STATUSES or p.status == MeasureStatus.ON_REVIEW:
            continue
        # Нагадування — за внутрішнім строком після перенесень; прострочення (R1) — за строком у програмі
        deadline = m.deadline_for(p) if m.is_permanent else m.internal_deadline
        if deadline < today:
            continue
        for days in settings.reminder_day_list:
            on = deadline - timedelta(days=days)
            send_at = datetime.combine(on, REMIND_AT, tzinfo=settings.tz).astimezone(timezone.utc)
            if on > today + timedelta(days=max(settings.reminder_day_list)):
                continue
            for u in _recipients(db, m):
                if (m.id, u.id, on) in have:
                    continue
                db.add(Reminder(
                    measure=m, user_id=u.id, send_at=send_at, channel=Channel.IN_APP,
                    text=f"До строку заходу {m.code} «{m.title}» залишилось {days} дн. ({deadline:%d.%m.%Y}).",
                    sent=send_at <= now,
                ))
                have.add((m.id, u.id, on))
                n += 1
    db.flush()
    return n


def run_daily(db: Session, today: date | None = None) -> s.JobResult:
    today = today or config_today()
    started = measure_svc.start_due_periods(db, today)
    measure_svc.close_ended_periods(db, today)
    opened, resolved = evaluate(db, today)
    s_opened, s_resolved = risk_model.evaluate_signals(db, today)
    recs = generate_recommendations(db)
    reminders = generate_reminders(db, today)
    sent = notify.dispatch(db)
    db.commit()
    return s.JobResult(
        flags_opened=opened,
        flags_auto_resolved=resolved,
        recommendations_created=recs,
        reminders_created=reminders,
        periods_started=started,
        notifications_sent=sent,
        signals_opened=s_opened,
        signals_auto_resolved=s_resolved,
    )


def after_change(db: Session, m: Measure, today: date) -> None:
    db.flush()
    evaluate(db, today, m.section.program_id)
    if m.risk is not None:
        risk_model.evaluate_signals(db, today, [m.risk])
    generate_recommendations(db)
