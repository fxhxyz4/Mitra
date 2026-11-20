import hashlib
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, llm
from ..auth import is_assigned
from ..enums import EDITABLE_BY_EXECUTOR, SECTION_TITLES
from ..models import AiDraft, CorruptionRisk, Measure, MeasurePeriod, OrgUnit, Program, User
from ..schemas import intake as s
from ..schemas.ai import RewriteOut
from ..schemas.domain import AssignmentIn
from . import documents, templates as t
from .assistant import COMMON_PROMPT, Assistant, numbers, rank, top as top_n
from .mappers import resolve_period
from .rules import SIMILARITY_THRESHOLD, similarity, submit_hints, vague_result_facts

Pair = tuple[Measure, MeasurePeriod]

# Title similarity at which the measure is taken without asking the model.
SURE_MATCH = 0.9
# Below this the best candidate is not offered as the choice at all.
WEAK_MATCH = 0.5
RISK_MATCH = 0.8
TOP_N = 3

CHOOSE_MEASURE = COMMON_PROMPT + (
    " Дано фрагмент звіту виконавця і пронумерований список заходів. Визнач, якого заходу стосується звіт. "
    "choice — номер зі списку або 0, якщо жоден не підходить."
)
CHOOSE_OUTCOME = COMMON_PROMPT + (
    " Визнач стан виконання заходу за звітом: done — виконано повністю; not_done — не виконано або виконано "
    "частково; unknown — зі звіту не зрозуміло."
)
REWRITE = COMMON_PROMPT + (
    " Переформулюй опис результату виконання заходу для звіту: що саме зроблено, з числами та реквізитами "
    "підтвердних документів. Використовуй лише числа, дати й номери з наданого тексту. Не повторюй назву "
    "заходу. 2–4 речення."
)
CHOOSE_SECTION = COMMON_PROMPT + (
    " Визнач розділ антикорупційної програми, до якого належить захід: 1, 2 або 3 (назви розділів дано)."
)
CHOOSE_RISK = COMMON_PROMPT + (
    " Дано опис корупційного ризику з картки заходу і пронумерований список ризиків з реєстру. "
    "choice — номер ризику зі списку або 0, якщо жоден не відповідає."
)


class Choice(BaseModel):
    choice: int


class OutcomeChoice(BaseModel):
    outcome: Literal["done", "not_done", "unknown"]


class Rewrite(BaseModel):
    text: str


class SectionChoice(BaseModel):
    section: int


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _open_periods(db: Session, user: User, today: date, period: str | None) -> list[Pair]:
    out = []
    for m in db.scalars(select(Measure)):
        if not is_assigned(user, m):
            continue
        editable = [p for p in m.periods if p.status in EDITABLE_BY_EXECUTOR and period in (None, p.period)]
        if editable:
            current = resolve_period(m, today)
            out.append((m, current if current in editable else min(editable, key=lambda p: p.period)))
    return out


def _candidate(pair: Pair, score: float, reason: str) -> s.MeasureCandidate:
    m, p = pair
    return s.MeasureCandidate(measure_id=m.id, code=m.code, title=m.title, period=p.period, score=score, reason=reason)


async def choose_measure(
    ai: Assistant, fields: dict[str, str], pairs: list[Pair], warnings: list[str]
) -> tuple[list[s.MeasureCandidate], Pair | None, s.Source | None]:
    if code := t.measure_code(fields.get("code")):
        exact = next((pair for pair in pairs if pair[0].code == code), None)
        if exact:
            return [_candidate(exact, 1.0, "Номер заходу в документі")], exact, "document"
        warnings.append(f"Захід {code} не серед ваших заходів, що очікують звіту: підібрано за змістом.")
    scores = await rank(ai, fields["title"], [m.title for m, _ in pairs])
    order = top_n(scores, TOP_N)
    top = [(pairs[i], scores[i][0]) for i in order]
    candidates = [_candidate(pairs[i], scores[i][1], f"Схожість назви {scores[i][0]:.0%}") for i in order]
    best, best_sim = top[0]
    if best_sim >= SURE_MATCH:
        return candidates, best, "rule"
    answer = await ai.ask(CHOOSE_MEASURE, {
        "звіт": {"захід": fields["title"], "опис": fields["description"][:1500]},
        "заходи": [{"номер": n, "код": m.code, "назва": m.title} for n, ((m, _), _) in enumerate(top, 1)],
    }, Choice)
    if answer and 1 <= answer.choice <= len(top):
        return candidates, top[answer.choice - 1][0], "model"
    if answer and answer.choice == 0:
        warnings.append("Модель не знайшла відповідного заходу серед ваших: оберіть вручну.")
        return candidates, None, None
    if best_sim >= WEAK_MATCH:
        warnings.append("Захід підібрано лише за схожістю назви: перевірте вибір.")
        return candidates, best, "rule"
    warnings.append("Не вдалося визначити захід: оберіть його зі списку.")
    return candidates, None, None


async def decide_outcome(ai: Assistant, fields: dict[str, str], warnings: list[str]) -> tuple[s.Outcome | None, s.Source | None]:
    if value := t.outcome(fields["outcome"]):
        return value, "rule"  # type: ignore[return-value]
    answer = await ai.ask(CHOOSE_OUTCOME, {"стан у документі": fields["outcome"], "опис": fields["description"]},
                          OutcomeChoice)
    if answer and answer.outcome != "unknown":
        return answer.outcome, "model"
    warnings.append(f"Стан «{fields['outcome']}» не є «виконано» чи «не виконано»: оберіть стан вручну.")
    return None, None


NOTHING_TO_FIX = "Опис уже конкретний: є число або реквізити документа і він не повторює назву заходу."
NO_GROUNDS = "У тексті немає чисел чи реквізитів документів, на які можна спертися: додайте їх самі."
REJECTED = "Модель не запропонувала формулювання, що проходить перевірку (без нових чисел, не повторює назву)."


async def improve(ai: Assistant, title: str, description: str, evidence: str = "") -> tuple[str | None, str]:
    source = f"{description}\n{evidence}"
    if not vague_result_facts(title, description):
        return None, NOTHING_TO_FIX
    grounds = vague_result_facts(title, source)
    if grounds and not (grounds["hasNumber"] or grounds["hasReference"]):
        return None, NO_GROUNDS
    answer = await ai.ask(REWRITE, {"назва заходу": title, "опис": description, "підтвердні документи": evidence},
                          Rewrite)
    text = answer.text.strip() if answer else ""
    if not text or not numbers(text) <= numbers(f"{source}\n{title}") or vague_result_facts(title, text):
        return None, REJECTED
    return text, ""


async def rewrite(db: Session, m: Measure, text: str) -> RewriteOut:
    ai = Assistant(db)
    evidence = "; ".join(e.file_name for p in m.periods for e in p.evidence)
    better, note = await improve(ai, m.title, text.strip(), evidence)
    return RewriteOut(text=better, note=note, model=llm.chat_model(), model_used=ai.used)


async def report_draft(
    db: Session, user: User, file_name: str, data: bytes, period: str | None, today: date
) -> s.ReportDraft:
    fields = t.extract(t.REPORT, await run_in_threadpool(documents.read, file_name, data))
    ai = Assistant(db)
    warnings: list[str] = []
    doc_period = period or t.half_year(fields["period"])
    if not doc_period:
        warnings.append(f"Звітний період «{fields['period']}» не розпізнано.")
    pairs = _open_periods(db, user, today, doc_period)
    if not pairs and doc_period:
        warnings.append(f"У періоді {doc_period} немає ваших заходів, що очікують звіту: показано інші періоди.")
        pairs = _open_periods(db, user, today, None)
    if not pairs:
        raise HTTPException(409, "Немає ваших заходів, що очікують звіту")

    candidates, chosen, measure_source = await choose_measure(ai, fields, pairs, warnings)
    outcome, outcome_source = await decide_outcome(ai, fields, warnings)
    text, text_source = fields["description"], "document"
    hints: list[str] = []
    draft_key = None
    sha = file_sha256(data)
    if chosen:
        m, p = chosen
        if outcome == "done":
            better, _ = await improve(ai, m.title, fields["description"], fields.get("evidence", ""))
            if better:
                text, text_source = better, "model"
        hints = submit_hints(m.title, text if outcome == "done" else None, m.required_evidence, len(p.evidence) + 1)
        draft_key = uuid.uuid4().hex
        db.add(AiDraft(key=draft_key, user_id=user.id, measure_id=m.id, period=p.period, outcome=outcome,
                       text=text, text_source=text_source, file_sha256=sha))
    draft = s.ReportDraft(
        measure_id=chosen[0].id if chosen else None, period=chosen[1].period if chosen else doc_period,
        measure_source=measure_source, candidates=candidates, outcome=outcome, outcome_source=outcome_source,
        text=text, text_source=text_source, document_text=fields["description"], hints=hints, warnings=warnings,
        file_name=file_name, file_sha256=sha, draft_key=draft_key, model=llm.chat_model(), model_used=ai.used,
    )
    audit.record(db, user, "measure", draft.measure_id, "ai_intake_report", None, {
        "fileName": file_name, "sha256": sha, "period": draft.period, "measureSource": measure_source,
        "outcome": outcome, "outcomeSource": outcome_source, "textSource": text_source, "draftKey": draft_key,
        "model": draft.model, "modelUsed": ai.used, "warnings": warnings,
    })
    return draft


def draft_usage(db: Session, user: User, m: Measure, key: str, text: str, outcome: s.Outcome) -> dict[str, Any]:
    draft = db.get(AiDraft, key)
    if not draft or draft.user_id != user.id:
        raise HTTPException(422, "Чернетку з документа не знайдено: завантажте документ ще раз")
    return {
        "aiDraftKey": key,
        "aiDraftTextSource": draft.text_source,
        "aiDraftEdited": t.normalize(text) != t.normalize(draft.text) or outcome != draft.outcome,
        "aiDraftMeasureChanged": draft.measure_id != m.id,
    }


def _field(value: str | int | bool | None, source: s.Source, document_value: str = "") -> s.DraftField:
    return s.DraftField(value=value, source=source, document_value=document_value)


async def _section(ai: Assistant, f: dict[str, str], code: str | None) -> tuple[int | None, s.Source | None]:
    raw = f.get("section", "")
    if n := t.section_number(raw):
        return n, "rule"
    if code:
        return int(code.split(".")[0]), "rule"
    if raw:
        n, sim = max(((n, similarity(raw, title)) for n, title in SECTION_TITLES.items()), key=lambda x: x[1])
        if sim >= SIMILARITY_THRESHOLD:
            return n, "rule"
    if f.get("risk"):
        return 2, "rule"  # заходи з усунення корупційних ризиків
    answer = await ai.ask(CHOOSE_SECTION, {"розділи": SECTION_TITLES, "захід": f["title"],
                                           "індикатор": f["indicator"]}, SectionChoice)
    if answer and answer.section in SECTION_TITLES:
        return answer.section, "model"
    return None, None


async def _risk(
    ai: Assistant, text: str, risks: list[CorruptionRisk]
) -> tuple[CorruptionRisk | None, s.Source | None]:
    norm = t.normalize(text)
    for r in risks:
        if re.search(rf"(?<![\w]){re.escape(t.normalize(r.code))}(?![\w])", norm):
            return r, "rule"
    if not risks:
        return None, None
    scores = await rank(ai, text, [r.description for r in risks])
    top = top_n(scores, TOP_N)
    if scores[top[0]][0] >= RISK_MATCH:
        return risks[top[0]], "rule"
    answer = await ai.ask(CHOOSE_RISK, {
        "ризик у картці": text,
        "реєстр": [{"номер": n, "код": risks[i].code, "опис": risks[i].description} for n, i in enumerate(top, 1)],
    }, Choice)
    if answer and 1 <= answer.choice <= len(top):
        return risks[top[answer.choice - 1]], "model"
    return None, None


def _indicator_target(text: str) -> tuple[Decimal, str] | None:
    """Ціль кількісного індикатора з тексту — лише явні відсотки («не менше 95 %», «100 відсотків»):
    інші числа в назві («у строк до 10 робочих днів») ціллю не є. Решту координатор вносить сам."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|відсот)", text)
    return (Decimal(m.group(1).replace(",", ".")), "%") if m else None


async def measure_draft(db: Session, user: User, program: Program, file_name: str, data: bytes) -> s.MeasureDraft:
    f = t.extract(t.MEASURE_CARD, await run_in_threadpool(documents.read, file_name, data))
    ai = Assistant(db)
    warnings: list[str] = []
    v = s.MeasureDraftValues(title=f["title"], required_evidence=f.get("evidence", ""))
    fields = {"title": _field(f["title"], "document", f["title"])}
    if v.required_evidence:
        fields["requiredEvidence"] = _field(v.required_evidence, "document", v.required_evidence)

    number, number_source = await _section(ai, f, t.measure_code(f.get("code")))
    code = t.measure_code(f.get("code"), number)
    section = next((sec for sec in program.sections if sec.number == number), None)
    if section:
        v.section_id = section.id
        fields["section"] = _field(number, number_source or "rule", f.get("section", ""))
        taken = {m.code for m in section.measures}
        if code and code.split(".")[0] != str(number):
            warnings.append(f"Номер {code} не відповідає розділу {number}.")
        if not code:
            code = section.next_code()
            fields["code"] = _field(code, "rule")
        else:
            fields["code"] = _field(code, "document" if code == f.get("code") else "rule", f.get("code", ""))
        if code in taken:
            warnings.append(f"Номер {code} уже зайнятий у розділі {number}.")
        v.code = code
    else:
        warnings.append("Розділ програми не визначено: оберіть його.")

    planned, permanent = t.deadline(f["deadline"], program.period_end)
    v.is_permanent = permanent
    if planned:
        v.planned_deadline = planned
        fields["plannedDeadline"] = _field(planned.isoformat(), "rule", f["deadline"])
        fields["isPermanent"] = _field(permanent, "rule", f["deadline"])
        if not program.period_start <= planned <= program.period_end:
            warnings.append(f"Строк {planned:%d.%m.%Y} поза періодом програми.")
    else:
        warnings.append(f"Строк «{f['deadline']}» не розпізнано: вкажіть дату.")

    units = list(db.scalars(select(OrgUnit)))
    matched: list[OrgUnit] = []
    for part in t.unit_parts(f["responsible"]):
        exact = [u for u in units if t.normalize(u.name) == t.normalize(part)]
        partial = [u for u in units if t.unit_score(part, u.name) == 1.0]
        best = exact[0] if exact else max(units, key=lambda u: t.unit_score(part, u.name), default=None)
        if not exact and len(partial) > 1:
            warnings.append(f"Підрозділ «{part}» неоднозначний ({len(partial)} збіги): оберіть його.")
        elif best and t.unit_score(part, best.name) >= t.UNIT_MATCH_THRESHOLD:
            if best not in matched:
                matched.append(best)
        else:
            warnings.append(f"Підрозділ «{part}» не знайдено.")
    v.assignments = [AssignmentIn(org_unit_id=u.id, is_responsible=i == 0) for i, u in enumerate(matched)]
    if matched:
        fields["assignments"] = _field("; ".join(u.name for u in matched), "rule", f["responsible"])

    risk = None
    if f.get("risk"):
        risk, risk_source = await _risk(ai, f["risk"], list(db.scalars(select(CorruptionRisk))))
        if risk:
            v.risk_id = risk.id
            fields["risk"] = _field(f"{risk.code} {risk.description}", risk_source or "rule", f["risk"])
        else:
            warnings.append(f"Ризик «{f['risk']}» не знайдено в реєстрі: додайте його або оберіть наявний.")
    if number == 2 and not risk:
        warnings.append("Для заходу розділу 2 потрібен корупційний ризик.")

    # Індикатор виконання заходу — з документа як є; індикатор ризику належить ризику, а не заходу.
    if f.get("indicator"):
        v.indicator_text = f["indicator"].strip()
        fields["indicator"] = _field(v.indicator_text, "document", f["indicator"])
        target = _indicator_target(v.indicator_text)
        if target is not None:
            v.indicator_target, v.indicator_unit = target
    else:
        warnings.append("У документі немає індикатора виконання заходу: вкажіть його.")

    existing = [m for sec in program.sections for m in sec.measures]
    similar = sorted(
        (s.SimilarMeasure(measure_id=m.id, code=m.code, title=m.title, score=round(similarity(v.title, m.title), 2))
         for m in existing),
        key=lambda x: -x.score,
    )
    similar = [x for x in similar if x.score >= SIMILARITY_THRESHOLD][:TOP_N]
    warnings += [f"Схожий захід уже є: {x.code} ({x.score:.0%})." for x in similar]

    draft = s.MeasureDraft(measure=v, fields=fields, warnings=warnings, similar=similar, file_name=file_name,
                           model=llm.chat_model(), model_used=ai.used)
    audit.record(db, user, "program", program.id, "ai_intake_measure", None, {
        "fileName": file_name, "sha256": file_sha256(data),
        "fields": {k: x.source for k, x in fields.items()}, "warnings": warnings,
        "model": draft.model, "modelUsed": ai.used,
    })
    return draft
