import json
from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, llm
from ..enums import FLAG_UA, FlagStatus, MeasureStatus
from ..models import Measure, Program, RiskFlag, RiskSignal, User, local_date
from ..schemas import ai as a
from . import risk_model as rm
from .assistant import COMMON_PROMPT, Assistant, cited, only_known_numbers
from .risk_explain import Sources
from .scope import of as scope_of

DAYS = 7
NOISE = 0.1  # зміна RRS менше 0,1 — не рух
TOP = 4

DIGEST = COMMON_PROMPT + (
    " Дано пронумеровані джерела і зведення змін антикорупційної програми за тиждень за правилами. "
    "Напиши для керівника 3–5 речень: що покращилось, що погіршилось і що потребує рішення цього тижня. "
    "Після кожного твердження вказуй номер джерела в квадратних дужках, напр. [2]. "
    "Використовуй лише числа з джерел."
)


class Retelling(BaseModel):
    text: str


def _f(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _change(old: float, new: float) -> str:
    if _f(old) == _f(new):
        return f"не змінилась ({_f(new)})"
    return f"змінилась з {_f(old)} до {_f(new)}"


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def _measures(n: int) -> str:
    return _plural(n, "захід", "заходи", "заходів")


def _refs(numbers: list[int]) -> str:
    return f" [{', '.join(map(str, numbers))}]" if numbers else ""


def _codes(items: list[Measure]) -> str:
    codes = [m.code or m.title for m in items[:TOP]]
    rest = len(items) - len(codes)
    return ", ".join(codes) + (f" та ще {rest}" if rest > 0 else "")


def collect(db: Session, program: Program, today: date, see=None) -> tuple[Sources, str, a.DigestHighlights]:
    since = today - timedelta(days=DAYS)
    now = rm.program_metrics(db, program, today, see)
    before = rm.program_metrics(db, program, since, see)
    src = Sources()
    whose = "програми" if see is None or see.whole_program else "у вашій зоні відповідальності"
    parts = [f"За тиждень з {since:%d.%m} по {today:%d.%m} підтверджене зниження ризиків {whose} (PRI) "
             f"{_change(before.pri, now.pri)}, частка виконання заходів (EXEC) {_change(before.exec, now.exec)}."]

    past = {x.risk.id: x for x in before.assessments}
    moved = []
    for cur in now.assessments:
        if see is not None and not see.risk(cur.risk):
            continue
        old = past.get(cur.risk.id)
        if old and (cur.verdict != old.verdict or abs((cur.rrs or 0) - (old.rrs or 0)) >= NOISE):
            moved.append((cur, old))
    moved.sort(key=lambda p: abs((p[0].rrs or 0) - (p[1].rrs or 0)), reverse=True)
    up = [p for p in moved if (p[0].rrs or 0) < (p[1].rrs or 0)]  # ризик зріс: зниження стало меншим
    down = [p for p in moved if (p[0].rrs or 0) > (p[1].rrs or 0)]
    for cur, old in moved[:TOP]:
        n = src.add("risk", cur.risk.id, f"Ризик {cur.risk.code}", {
            "опис": cur.risk.description, "RRS тиждень тому": rm._r(old.rrs, 2), "RRS зараз": rm._r(cur.rrs, 2),
            "висновок тиждень тому": rm.VERDICTS[old.verdict][0], "висновок зараз": rm.VERDICTS[cur.verdict][0]})
        verdict = (f", висновок «{rm.VERDICTS[old.verdict][0]}» → «{rm.VERDICTS[cur.verdict][0]}»"
                   if cur.verdict != old.verdict else "")
        parts.append(f"Ризик {cur.risk.code}: зниження за індикатором (RRS) {_f(old.rrs or 0)} → "
                     f"{_f(cur.rrs or 0)}{verdict} [{n}].")
    if not moved:
        parts.append("Стан ризиків за індикаторами суттєво не змінився.")

    measures = [m for sec in program.sections for m in sec.measures if see is None or see.measure(m)]
    done: list[Measure] = []
    overdue: list[Measure] = []
    fresh_overdue: list[Measure] = []
    for m in measures:
        p = m.period_for(today)
        if p and p.status == MeasureStatus.DONE and p.actual_date and since < p.actual_date <= today:
            done.append(m)
        if m.is_overdue(today):
            overdue.append(m)
            if p and since < m.deadline_for(p) <= today:
                fresh_overdue.append(m)

    def cite(items: list[Measure], state: str) -> list[int]:
        return [src.add("measure", m.id, f"Захід {m.code}", {"назва": m.title, "стан": state}) for m in items[:TOP]]

    if done:
        parts.append(f"Виконано {_measures(len(done))}: {_codes(done)}{_refs(cite(done, 'виконано'))}.")
    else:
        parts.append("Жодного заходу за тиждень не виконано.")
    if fresh_overdue:
        parts.append(f"Строк минув цього тижня: {_measures(len(fresh_overdue))} — {_codes(fresh_overdue)}"
                     f"{_refs(cite(fresh_overdue, 'прострочено цього тижня'))}.")
    if overdue:
        parts.append(f"Усього прострочено {_measures(len(overdue))}.")

    window = lambda at: at is not None and since < local_date(at) <= today  # noqa: E731
    ids = [m.id for m in measures]
    open_flags = sorted(db.scalars(select(RiskFlag).where(RiskFlag.measure_id.in_(ids),
                                                          RiskFlag.status == FlagStatus.OPEN)),
                        key=lambda f: f.created_at, reverse=True)
    risk_ids = [x.risk.id for x in now.assessments if see is None or see.risk(x.risk)]
    open_signals = sorted(db.scalars(select(RiskSignal).where(RiskSignal.risk_id.in_(risk_ids),
                                                              RiskSignal.status == FlagStatus.OPEN)),
                          key=lambda s: s.created_at, reverse=True)
    new_flags = [f for f in open_flags if window(f.created_at)]
    new_signals = [s for s in open_signals if window(s.created_at)]
    fresh = len(new_flags) + len(new_signals)
    total = len(open_flags) + len(open_signals)
    by_measure = {m.id: m for m in measures}
    shown_flags = (new_flags if fresh < total else open_flags)[:2]
    shown_signals = (new_signals if fresh < total else open_signals)[: 2 if not shown_flags else 1]
    refs = [src.add("flag", f.id, f"Прапорець {f.rule_code} заходу {by_measure[f.measure_id].code}",
                    {"тип": FLAG_UA[f.type], "пояснення": f.explanation}, target=f.measure_id) for f in shown_flags]
    refs += [src.add("signal", s.id, f"Сигнал {s.rule_code}", {"тип": s.type.value, "пояснення": s.explanation},
                     target=s.risk_id)
             for s in shown_signals]
    if total == 0:
        parts.append("Відкритих прапорців і сигналів немає.")
    elif 0 < fresh < total:
        parts.append(f"Нових прапорців і сигналів за тиждень: {fresh}, усього відкритих {total}{_refs(refs)}.")
    else:
        parts.append(f"Відкритих прапорців і сигналів: {total}{_refs(refs)}.")

    highlights = a.DigestHighlights(
        pri=round(now.pri, 4), pri_before=round(before.pri, 4), exec=round(now.exec, 4),
        exec_before=round(before.exec, 4), done=len(done), overdue=len(overdue), new_overdue=len(fresh_overdue),
        new_flags=fresh if fresh < total else 0, open_flags=total, risks_up=len(up), risks_down=len(down))
    return src, " ".join(parts), highlights


async def digest(db: Session, user: User, program: Program, today: date) -> a.WeeklyDigest:
    src, rule_text, highlights = collect(db, program, today, scope_of(db, user))
    ai = Assistant(db)
    answer = None
    if src.refs:
        answer = await ai.ask(DIGEST, {"джерела": src.facts, "зведення за правилами": rule_text}, Retelling)
    text, text_source = rule_text, "rule"
    if answer:
        refs, valid = cited(answer.text, len(src.refs))
        grounding = json.dumps(src.facts, ensure_ascii=False, default=str) + rule_text
        if refs and valid and only_known_numbers(answer.text, grounding):
            text, text_source = answer.text.strip(), "model"
    numbers, _ = cited(text, len(src.refs))
    result = a.WeeklyDigest(
        program_id=program.id, since=today - timedelta(days=DAYS), as_of=today, text=text, text_source=text_source,
        references=src.only(numbers), rule_text=rule_text, highlights=highlights, model=llm.chat_model(),
        model_used=ai.used)
    audit.record(db, user, "program", program.id, "ai_digest", None, {
        "textSource": text_source, "references": numbers, "model": result.model, "modelUsed": ai.used})
    return result