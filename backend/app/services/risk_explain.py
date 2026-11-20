import json
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, llm
from ..enums import FLAG_UA, LEVEL_UA, STATUS_UA, FlagStatus
from ..models import CorruptionRisk, RiskSignal, User
from ..schemas import ai as a
from . import risk_model as rm
from .assistant import COMMON_PROMPT, Assistant, cited, only_known_numbers
from .mappers import resolve_period
from .scope import of as scope_of

EXPLAIN = COMMON_PROMPT + (
    " Дано пронумеровані джерела і пояснення стану корупційного ризику за правилами. Перекажи пояснення "
    "простою мовою для керівника, 3–5 речень: чи зменшується ризик, чому, що потребує уваги. Після кожного "
    "твердження вказуй номер джерела в квадратних дужках, напр. [2]. Використовуй лише числа з джерел."
)


class Retelling(BaseModel):
    text: str


def _n(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


class Sources:
    def __init__(self) -> None:
        self.refs: list[a.SourceRef] = []
        self.facts: list[dict[str, Any]] = []

    def add(self, type_: a.EntityType, id_: Any, label: str, facts: dict[str, Any], target: Any = None) -> int:
        n = len(self.refs) + 1
        self.refs.append(a.SourceRef(n=n, type=type_, id=id_, label=label, target=target))
        self.facts.append({"n": n, "що": label, **facts})
        return n

    def only(self, numbers: list[int]) -> list[a.SourceRef]:
        return [r for r in self.refs if r.n in numbers]


def collect(db: Session, risk: CorruptionRisk, today: date, see=None) -> tuple[Sources, str]:
    asm = rm.assess(risk, today)
    measures = [x for x in asm.measures if see is None or see.measure(x.measure)]
    src = Sources()
    r = src.add("risk", risk.id, f"Ризик {risk.code}", {
        "опис": risk.description, "рівень": LEVEL_UA[risk.level], "імовірність": asm.probability0,
        "наслідки": asm.impact0, "бал": asm.inherent})
    parts = [f"Ризик {risk.code} «{risk.description}» має {LEVEL_UA[risk.level]} рівень, початковий бал "
             f"{asm.probability0}×{asm.impact0} = {asm.inherent} [{r}]."]

    kri_refs = []
    for k in asm.kris:
        n = src.add("indicator", k.indicator.id, f"Індикатор «{k.indicator.name}»", {
            "база": k.baseline, "ціль": k.target, "поточне": _n(k.current),
            "дата виміру": k.measured_at.isoformat() if k.measured_at else None, "прогрес p": _n(k.p),
            "очікуваний прогрес": _n(k.expected), "стан": rm.EFFECT_UA[k.state]})
        kri_refs.append(n)
        if k.current is None:
            parts.append(f"Для індикатора «{k.indicator.name}» ще немає вимірювань [{n}].")
        else:
            expected = f", очікувано на цю дату {_n(k.expected)}" if k.expected is not None else ""
            parts.append(f"Індикатор «{k.indicator.name}»: база {k.baseline:g}, ціль {k.target:g}, поточне "
                         f"{k.current:g}, прогрес {_n(k.p)}{expected} — {rm.EFFECT_UA[k.state]} [{n}].")

    measure_refs = []
    for x in measures:
        p = resolve_period(x.measure, today)
        status = STATUS_UA[p.status] if p else "—"
        measure_refs.append(src.add("measure", x.measure.id, f"Захід {x.measure.code}", {
            "назва": x.measure.title, "стан": status, "виконано": x.done}))
    done = sum(1 for x in measures if x.done)
    refs = ", ".join(map(str, measure_refs + kri_refs))
    if measure_refs:
        parts.append(f"Виконано {done} з {len(measure_refs)} заходів, стан індикатора — "
                     f"{rm.EFFECT_UA[asm.effect]}. Висновок: {rm.VERDICTS[asm.verdict][0]}"
                     + (" (попередній: лаг ефекту ще не минув)" if asm.preliminary else "") + f" [{refs}].")
    else:
        parts.append("Затверджених заходів щодо ризику немає.")

    signals = db.scalars(select(RiskSignal).where(RiskSignal.risk_id == risk.id,
                                                  RiskSignal.status == FlagStatus.OPEN))
    for sig in signals:
        n = src.add("signal", sig.id, f"Сигнал {sig.rule_code}", {"тип": sig.type.value, "пояснення": sig.explanation},
                    target=risk.id)
        parts.append(f"{sig.explanation.rstrip('.')} [{n}].")
    for x in measures:
        m = x.measure
        for f in m.flags:
            if f.status == FlagStatus.OPEN:
                n = src.add("flag", f.id, f"Прапорець {f.rule_code} заходу {m.code}",
                            {"тип": FLAG_UA[f.type], "пояснення": f.explanation}, target=m.id)
                parts.append(f"Захід {m.code}: {f.explanation.rstrip('.')} [{n}].")
    return src, " ".join(parts)


async def explain(db: Session, user: User, risk: CorruptionRisk, today: date) -> a.RiskExplanation:
    src, rule_text = collect(db, risk, today, scope_of(db, user))
    ai = Assistant(db)
    answer = await ai.ask(EXPLAIN, {"джерела": src.facts, "пояснення за правилами": rule_text}, Retelling)
    text, text_source = rule_text, "rule"
    if answer:
        refs, valid = cited(answer.text, len(src.refs))
        grounding = json.dumps(src.facts, ensure_ascii=False, default=str) + rule_text
        if refs and valid and only_known_numbers(answer.text, grounding):
            text, text_source = answer.text.strip(), "model"
    numbers, _ = cited(text, len(src.refs))
    result = a.RiskExplanation(risk_id=risk.id, text=text, text_source=text_source, references=src.only(numbers),
                               rule_text=rule_text, model=llm.chat_model(), model_used=ai.used)
    audit.record(db, user, "corruption_risk", risk.id, "ai_explain", None, {
        "textSource": text_source, "references": numbers, "model": result.model, "modelUsed": ai.used})
    return result
