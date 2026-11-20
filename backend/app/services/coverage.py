from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, halfyear, llm
from ..enums import LEVEL_UA, RiskLevel
from ..models import CorruptionRisk, Program, User
from ..schemas import ai as a, intake as s
from .assistant import COMMON_PROMPT, Assistant, only_known_numbers
from .rules import SIMILARITY_THRESHOLD, similarity
from .scope import Scope

RISK_SECTION = 2
EXAMPLES = 3
MIN_TITLE_WORDS = 4
LEVEL_ORDER = {RiskLevel.CRITICAL: 0, RiskLevel.HIGH: 1, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 3}

DRAFT_MEASURE = COMMON_PROMPT + (
    " title — захід впливу на останній ризик у стилі прикладів: речення з дієсловом в інфінітиві, 6–25 слів, "
    "без дат і номерів; захід має усувати причину ризику, а не лише навчати чи роз'яснювати. "
    "required_evidence — підтвердні документи, що засвідчать виконання."
)


class MeasureProposal(BaseModel):
    title: str
    required_evidence: str


def _acceptable(title: str, context: str) -> bool:
    return len(title.split()) >= MIN_TITLE_WORDS and only_known_numbers(title, context)


def gaps(db: Session, program: Program, see: "Scope | None" = None) -> list[a.CoverageGap]:
    every = [m for sec in program.sections for m in sec.measures]
    covered = {m.risk_id for m in every if m.risk_id}
    measures = every if see is None else see.measures(every)
    out: list[a.CoverageGap] = []
    for r in db.scalars(select(CorruptionRisk)) if see is None or see.whole_program else ():
        if r.id not in covered:
            out.append(a.CoverageGap(
                rule_code="C1", level=r.level, risk_id=r.id, risk_code=r.code,
                facts={"level": r.level.value, "measures": 0},
                explanation=f"Ризик {r.code} ({LEVEL_UA[r.level]} рівень) є в реєстрі, але програма не містить жодного "
                            f"заходу щодо нього."))
    for m in measures:
        if m.section.number == RISK_SECTION and m.risk_id is None:
            out.append(a.CoverageGap(
                rule_code="C2", measure_id=m.id, measure_code=m.code, facts={"section": RISK_SECTION},
                explanation=f"Захід {m.code} розділу {RISK_SECTION} не повʼязаний з корупційним ризиком."))
        elif m.risk is not None and not m.risk.indicators:
            out.append(a.CoverageGap(
                rule_code="C3", level=m.risk.level, risk_id=m.risk.id, risk_code=m.risk.code,
                measure_id=m.id, measure_code=m.code, facts={"indicators": 0},
                explanation=f"Для заходу {m.code} немає індикатора: зменшення ризику {m.risk.code} "
                            f"неможливо оцінити."))
    return sorted(out, key=lambda g: (g.rule_code, LEVEL_ORDER.get(g.level, 9) if g.level else 9, g.risk_code or "",
                                      g.measure_code or ""))


def _deadline(program: Program, today: date) -> date:
    current_end = halfyear.end(halfyear.of(today))
    upcoming = halfyear.end(halfyear.of(current_end + timedelta(days=1)))
    return min(max(upcoming, program.period_start), program.period_end)


async def measure_draft(db: Session, user: User, program: Program, risk: CorruptionRisk, today: date) -> s.MeasureDraft:
    section = next(sec for sec in program.sections if sec.number == RISK_SECTION)
    deadline = _deadline(program, today)
    v = s.MeasureDraftValues(section_id=section.id, code=section.next_code(), risk_id=risk.id, planned_deadline=deadline)
    fields = {
        "section": s.DraftField(value=RISK_SECTION, source="rule"),
        "code": s.DraftField(value=v.code, source="rule"),
        "risk": s.DraftField(value=f"{risk.code} {risk.description}", source="rule"),
        "plannedDeadline": s.DraftField(value=deadline.isoformat(), source="rule"),
    }
    warnings = ["Строк запропоновано за правилом (кінець наступного півріччя): уточніть його.",
                "Оберіть відповідальний підрозділ.",
                "Вкажіть індикатор виконання заходу (і ціль, якщо він кількісний)."]
    if not risk.indicators:
        warnings.append(f"У ризику {risk.code} немає індикатора ризику: додайте його в реєстрі, інакше ефект не оцінити.")

    examples = [(m.risk.description, m.title) for m in section.measures if m.risk][:EXAMPLES]
    prompt = "\n\n".join([
        "Приклади:\n" + "\n".join(f"Ризик: {r}\nЗахід: {t}" for r, t in examples),
        f"Ризик: {risk.description}\n" + "".join(f"Індикатор: {i.name}\n" for i in risk.indicators) + "Захід:",
    ])
    ai = Assistant(db)
    proposal = await ai.ask(DRAFT_MEASURE, prompt, MeasureProposal)
    existing = [m for sec in program.sections for m in sec.measures]
    similar: list[s.SimilarMeasure] = []
    if proposal and _acceptable(proposal.title, prompt):
        v.title = proposal.title.strip()
        v.required_evidence = proposal.required_evidence.strip()
        fields["title"] = s.DraftField(value=v.title, source="model")
        fields["requiredEvidence"] = s.DraftField(value=v.required_evidence, source="model")
        similar = [s.SimilarMeasure(measure_id=m.id, code=m.code, title=m.title, score=round(sc, 2))
                   for m in existing if (sc := similarity(v.title, m.title)) >= SIMILARITY_THRESHOLD]
        warnings += [f"Схожий захід уже є: {x.code} ({x.score:.0%})." for x in similar]
    else:
        warnings.append("Модель не запропонувала придатної назви: сформулюйте захід самостійно.")

    draft = s.MeasureDraft(measure=v, fields=fields, warnings=warnings, similar=similar, file_name="",
                           model=llm.chat_model(), model_used=ai.used)
    audit.record(db, user, "corruption_risk", risk.id, "ai_measure_draft", None, {
        "programId": str(program.id), "fields": {k: f.source for k, f in fields.items()},
        "title": v.title, "model": draft.model, "modelUsed": ai.used,
    })
    return draft
