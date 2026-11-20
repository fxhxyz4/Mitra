import json
import re
from datetime import date

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import audit, halfyear, llm
from ..models import Evidence, MeasurePeriod, User
from ..schemas import ai as a
from . import documents, storage
from .assistant import COMMON_PROMPT, Assistant, numbers, only_known_numbers
from .dataset import EVIDENCE_LABEL, INDICATOR_LABEL
from .templates import normalize

ADVISE = COMMON_PROMPT + (
    " Дано захід, опис результату від виконавця, результати перевірок за правилами і текст підтвердних "
    "документів. Напиши координатору 2–3 речення: чи підтверджують документи опис і що уточнити у виконавця. "
    "Рішення не ухвалюй. quotes — до 3 дослівних цитат з документів (file — номер документа)."
)
# Day-month-year dates in documents; «від 02.10.2026» etc.
_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b")
GRACE_DAYS = 92
STEM = 5
MAX_CHARS = 4000


class Quote(BaseModel):
    file: int
    quote: str


class Advice(BaseModel):
    advice: str
    quotes: list[Quote] = []


def required_types(text: str) -> list[str]:
    evidence = text.split(INDICATOR_LABEL)[0].replace(EVIDENCE_LABEL, "").strip().rstrip(".")
    return [t.strip() for t in re.split(r"[,;]", evidence) if t.strip()]


def _has_type(doc_type: str, haystack: str) -> bool:
    words = [w[:STEM] for w in normalize(doc_type).split() if len(w) > 2]
    return bool(words) and all(w in haystack for w in words)


def _read(e: Evidence) -> str | None:
    if not storage.verify(e.object_key, e.sha256):
        return None
    try:
        return documents.read(e.file_name, storage.get_object(e.object_key)).text
    except HTTPException:
        return None


def findings(p: MeasurePeriod, texts: dict[Evidence, str]) -> list[a.EvidenceFinding]:
    m = p.measure
    corpus = normalize(" ".join([*texts.values(), *(e.file_name for e in p.evidence),
                                 *(e.doc_type for e in p.evidence)]))
    out = []
    required = required_types(m.evidence_form or m.required_evidence)
    if required:
        missing = [t for t in required if not _has_type(t, corpus)]
        out.append(a.EvidenceFinding(
            rule_code="V1", ok=not missing, facts={"required": required, "missing": missing},
            text="Усі потрібні типи документів знайдено." if not missing
            else f"Не знайдено документів: {', '.join(missing)}."))
    description = p.result_description or ""
    claimed = {n for n in numbers(description) if len(n.replace(".", "")) >= 2}
    if claimed and texts:
        found = numbers(" ".join(texts.values()))
        absent = sorted(claimed - found)
        out.append(a.EvidenceFinding(
            rule_code="V2", ok=not absent, facts={"claimed": sorted(claimed), "absent": absent},
            text="Числа з опису результату є в документах." if not absent
            else f"Числа з опису, яких немає в документах: {', '.join(absent)}."))
    start, end = halfyear.start(p.period), halfyear.end(p.period)
    outside = []
    for text in texts.values():
        for d, mth, y in _DATE.findall(text):
            try:
                day = date(int(y), int(mth), int(d))
            except ValueError:
                continue
            if day < start or (day - end).days > GRACE_DAYS:
                outside.append(day.isoformat())
    if texts:
        out.append(a.EvidenceFinding(
            rule_code="V3", ok=not outside, facts={"period": p.period, "outside": sorted(set(outside))},
            text=f"Дати в документах відповідають періоду {p.period}." if not outside
            else f"Дати поза періодом {p.period}: {', '.join(sorted(set(outside)))}."))
    return out


async def check(db: Session, user: User, p: MeasurePeriod) -> a.EvidenceCheck:
    texts: dict[Evidence, str] = {}
    unreadable = []
    for e in p.evidence:
        if (text := await run_in_threadpool(_read, e)) is None:
            unreadable.append(e.file_name)
        else:
            texts[e] = text
    result = a.EvidenceCheck(period_id=p.id, findings=findings(p, texts), unreadable=unreadable,
                             model=llm.chat_model(), model_used=False)
    ai = Assistant(db)
    files = list(texts.items())
    if files:
        context = {
            "захід": {"номер": p.measure.code, "назва": p.measure.title},
            "опис результату": p.result_description or p.non_execution_reason or "",
            "перевірки": [f.text for f in result.findings],
            "документи": [{"номер": i, "файл": e.file_name, "текст": t[:MAX_CHARS]} for i, (e, t) in enumerate(files, 1)],
        }
        answer = await ai.ask(ADVISE, context, Advice)
        if answer and only_known_numbers(answer.advice, json.dumps(context, ensure_ascii=False)):
            result.advice, result.advice_source = answer.advice.strip(), "model"
            result.quotes = [
                a.EvidenceQuote(evidence_id=files[q.file - 1][0].id, file_name=files[q.file - 1][0].file_name,
                                quote=q.quote.strip())
                for q in answer.quotes
                if 1 <= q.file <= len(files) and q.quote.strip()
                and " ".join(q.quote.split()) in " ".join(files[q.file - 1][1].split())
            ]
    if not result.advice:
        failed = [f.text for f in result.findings if not f.ok]
        result.advice = " ".join(failed) if failed else "Правила розбіжностей не виявили."
        result.advice_source = "rule"
    result.model_used = ai.used
    audit.record(db, user, "measure_period", p.id, "ai_evidence_check", None, {
        "findings": {f.rule_code: f.ok for f in result.findings}, "unreadable": unreadable,
        "adviceSource": result.advice_source, "quotes": len(result.quotes), "model": result.model,
        "modelUsed": ai.used})
    return result
