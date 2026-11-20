import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Awaitable
from typing import Annotated, TypeVar

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from .. import audit, llm
from ..auth import Admin, Coordinator, DbDep, Executor, Staff, SubjectUser, UserDep, ensure_can_execute
from ..config import settings, today
from ..enums import LEVEL_UA
from ..models import AiJob, CorruptionRisk, Measure, MeasurePeriod, Program, Recommendation, User, utcnow
from ..schemas import (
    AiChatIn,
    AiChatRenameIn,
    AiChatOut,
    AiChatSummary,
    AiStatus,
    AiSuggestion,
    AskAnswer,
    AskIn,
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    EvidenceCheck,
    MeasureDraft,
    ReportDraft,
    RiskExplanation,
    RiskMeasureDraftIn,
    RewriteIn,
    RewriteOut,
    WeeklyDigest,
)
from ..services import ai_chats, ai_jobs, coverage, data_chat, evidence_check, intake, risk_explain, scope, weekly_digest
from ..services.assistant import GUARD, ai_enabled, require_ai
from ..services.dashboards import resolve_program

router = APIRouter(prefix="/ai", tags=["ai"])

T = TypeVar("T")


async def call_llm(request: Awaitable[T]) -> T:
    try:
        return await request
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Мовна модель повернула помилку: {e.response.text[:300]}") from e
    except httpx.HTTPError as e:
        raise HTTPException(503, "Мовна модель недоступна") from e


STATUS_TIMEOUT = 5
STATUS_TTL = 30
_models_seen: tuple[object, float, list[str] | None] = (None, 0.0, None)


def _available_models() -> list[str] | None:
    global _models_seen
    source = (llm.client, llm.chat_model(), settings.llm_base_url, settings.ollama_url)
    seen_for, at, models = _models_seen
    if seen_for == source and time.monotonic() - at < STATUS_TTL:
        return models
    try:
        models = ai_jobs.runner.call(asyncio.wait_for(llm.list_models(), STATUS_TIMEOUT), STATUS_TIMEOUT + 1)
    except (httpx.HTTPError, TimeoutError):
        models = None
    _models_seen = (source, time.monotonic(), models)
    return models


@router.get("/status", response_model=AiStatus)
def status(db: DbDep, _: UserDep) -> AiStatus:
    enabled = ai_enabled(db)
    models = _available_models()
    if models is None:
        return AiStatus(
            enabled=enabled,
            reachable=False,
            ready=False,
            chatModel=llm.chat_model(),
            embedModel=settings.embed_model,
            models=[],
        )
    return AiStatus(
        enabled=enabled,
        reachable=True,
        ready=llm.has_model(models, llm.chat_model()),
        chatModel=llm.chat_model(),
        embedModel=settings.embed_model,
        models=models,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: DbDep, _: Admin) -> ChatResponse:
    """Діагностика моделі для адміністратора. Предметні ШІ-функції мають власні ендпоінти з перевірками."""
    require_ai(db)
    messages = [{"role": "system", "content": DIAGNOSTIC},
                *(m.model_dump() for m in body.messages if m.role != "system")]
    content = ai_jobs.runner.call(call_llm(llm.answer(messages)), 2 * settings.llm_timeout + 10)
    return ChatResponse(model=llm.chat_model(), content=content)


@router.delete("/cache")
def clear_cache(db: DbDep, admin: Admin) -> dict[str, int]:
    """Видаляє збережені відповіді моделі: наступні запити підуть до моделі заново."""
    removed = llm.clear_cache()
    audit.record(db, admin, "llm_cache", None, "clear", None, {"removed": removed})
    db.commit()
    return {"removed": removed}


@router.post("/embed", response_model=EmbedResponse)
def embed(body: EmbedRequest, db: DbDep, _: Admin) -> EmbedResponse:
    require_ai(db)
    vectors = ai_jobs.runner.call(call_llm(llm.embed(body.texts)), settings.llm_timeout + 10)
    return EmbedResponse(model=settings.embed_model, embeddings=vectors)


SUGGEST_SYSTEM = (
    "Ти — помічник уповноваженої особи з питань запобігання корупції в органі сектору безпеки і оборони. "
    "Тобі дають рекомендацію, сформовану за явним правилом, і факти, на яких вона ґрунтується. "
    "Запропонуй, як конкретизувати рекомендацію для управлінського рішення: чітке формулювання доручення "
    "та 2–4 практичні кроки. Спирайся ЛИШЕ на надані факти, не вигадуй дат, прізвищ, номерів документів. "
    "Не оцінюй людей і не рейтингуй підрозділи. Відповідай українською лише JSON-обʼєктом з полями "
    "text (формулювання доручення), steps (список кроків) і rationale (обґрунтування з посиланням на правило). "
) + GUARD
DIAGNOSTIC = (
    "Це діагностичний запит адміністратора до мовної моделі системи моніторингу антикорупційної програми. "
    "Відповідай коротко українською. Предметних даних у тебе немає. На прохання, не повʼязані з перевіркою "
    "роботи моделі чи з цією системою, ввічливо відмовляй. "
) + GUARD


class SuggestReply(BaseModel):
    text: str
    steps: list[str] = []
    rationale: str = ""


SUGGEST_FORMAT = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["text", "steps", "rationale"],
}


async def _suggest_recommendation(rec_id: uuid.UUID, db: DbDep, user: Staff) -> AiSuggestion:
    """Пропозиція локальної LLM до рекомендації. Рекомендація не змінюється: керівник може взяти текст"""
    require_ai(db)
    rec = db.get(Recommendation, rec_id)
    if not rec:
        raise HTTPException(404, "Рекомендацію не знайдено")
    scope.of(db, user).ensure_recommendation(rec)
    m = rec.measure
    basis = {k: v for k, v in rec.basis.items() if k not in ("aiSuggestions", "dedupKey")}
    context = {
        "рекомендація": rec.text,
        "захід": {"номер": m.code, "назва": m.title} if m else None,
        "корупційний ризик": {"код": m.risk.code, "опис": m.risk.description, "рівень": LEVEL_UA[m.risk.level]}
        if m and m.risk else None,
        "підстава": basis,
    }
    messages = [
        {"role": "system", "content": SUGGEST_SYSTEM},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
    ]
    parsed: SuggestReply | None = None
    for fmt in (SUGGEST_FORMAT, "json"):  # some servers end the JSON early despite the schema
        try:
            parsed = SuggestReply.model_validate_json(await call_llm(llm.answer(messages, fmt)))
            break
        except ValidationError:
            llm.forget(messages, fmt)
            continue
    text = parsed.text.strip() if parsed else ""
    if not parsed or not text:
        if parsed:
            llm.forget(messages, fmt)
        raise HTTPException(502, "Модель не дала коректної пропозиції")
    steps = [x.strip() for x in parsed.steps if x.strip()]
    rationale = parsed.rationale.strip()
    model = llm.chat_model()
    entry = {"model": model, "text": text, "steps": steps, "rationale": rationale,
             "at": utcnow().isoformat(), "requestedBy": str(user.id)}
    rec.basis = {**rec.basis, "aiSuggestions": [*rec.basis.get("aiSuggestions", []), entry]}
    audit.record(db, user, "recommendation", rec.id, "ai_suggest", None, {"model": model, "text": text})
    db.commit()
    return AiSuggestion(recommendation_id=rec.id, model=model, text=text, steps=steps,
                        rationale=rationale, basis=basis)


async def _rewrite(measure_id: uuid.UUID, body: RewriteIn, db: DbDep, user: Executor) -> RewriteOut:
    """Пропозиція чіткішого опису результату. Приймається, лише якщо не додає нових чисел і проходить правило R4;"""
    require_ai(db)
    m = db.get(Measure, measure_id)
    if not m:
        raise HTTPException(404, "Захід не знайдено")
    ensure_can_execute(user, m)
    result = await intake.rewrite(db, m, body.text)
    audit.record(db, user, "measure", m.id, "ai_rewrite", None,
                 {"accepted": result.text is not None, "model": result.model, "note": result.note})
    db.commit()
    return result


class Upload:
    def __init__(self, file: UploadFile) -> None:
        self.filename = file.filename or ""
        self.data = file.file.read(settings.ai_max_upload_mb * 1024 * 1024 + 1)
        if len(self.data) > settings.ai_max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"Файл більший за {settings.ai_max_upload_mb} МБ")

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


async def _intake_report(
    db: DbDep,
    user: Executor,
    file: "Upload",
    period: str | None = None,
) -> ReportDraft:
    """Звіт виконавця (зразок A) → чернетка форми «Внесення за один крок» для одного з власних заходів."""
    draft = await intake.report_draft(db, user, file.filename, file.data, period, today())
    db.commit()
    return draft


async def _intake_measure(
    db: DbDep,
    user: Coordinator,
    file: "Upload",
    program_id: uuid.UUID,
) -> MeasureDraft:
    """Картка заходу (зразок B) → чернетка форми створення заходу. Захід створює координатор через `POST /measures`."""
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(404, "Програму не знайдено")
    draft = await intake.measure_draft(db, user, program, file.filename, file.data)
    db.commit()
    return draft


def _get_risk(db: DbDep, risk_id: uuid.UUID) -> CorruptionRisk:
    risk = db.get(CorruptionRisk, risk_id)
    if not risk:
        raise HTTPException(404, "Ризик не знайдено")
    return risk


async def _risk_measure_draft(risk_id: uuid.UUID, body: RiskMeasureDraftIn, db: DbDep, user: Coordinator) -> MeasureDraft:
    """Чернетка заходу для ризику без заходів (правило C1): назву пропонує модель, решту полів — правила."""
    require_ai(db)
    program = db.get(Program, body.program_id)
    if not program:
        raise HTTPException(404, "Програму не знайдено")
    draft = await coverage.measure_draft(db, user, program, _get_risk(db, risk_id), today())
    db.commit()
    return draft


async def _explain_risk(risk_id: uuid.UUID, db: DbDep, user: Staff) -> RiskExplanation:
    """Пояснення стану ризику з посиланнями [n] на ризик, індикатори, заходи, сигнали і прапорці."""
    risk = _get_risk(db, risk_id)
    scope.of(db, user).ensure_risk(risk)
    result = await risk_explain.explain(db, user, risk, today())
    db.commit()
    return result


async def _weekly(db: DbDep, user: Staff, program_id: uuid.UUID | None = None) -> WeeklyDigest:
    result = await weekly_digest.digest(db, user, resolve_program(db, program_id), today())
    db.commit()
    return result


async def _check_evidence(period_id: uuid.UUID, db: DbDep, user: Staff) -> EvidenceCheck:
    """Порада координатору перед погодженням: правила V1–V3 і, якщо ШІ увімкнено, коментар з цитатами."""
    period = db.get(MeasurePeriod, period_id)
    if not period:
        raise HTTPException(404, "Звітний період не знайдено")
    scope.of(db, user).ensure_measure(period.measure)
    result = await evidence_check.check(db, user, period)
    db.commit()
    return result


async def _ask(body: AskIn, db: DbDep, user: SubjectUser) -> AskAnswer:
    """Питання по даних програми в межах прав ролі; відповідь з посиланнями на записи."""
    result = await data_chat.ask(db, user, body.question, today())
    db.commit()
    return result


# Endpoints: the work above runs in the AI queue (services/ai_jobs.py), off the server's event loop.
# A fast answer (cache, rules, validation error) returns as before; a slow one answers 202 with a job id.
JOB = {202: {"description": "Задачу поставлено в чергу: `GET /ai/jobs/{jobId}`"}}


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


@router.get("/jobs/{job_id}")
def job_status(job_id: uuid.UUID, db: DbDep, user: UserDep) -> dict:
    """Стан ШІ-задачі: queued / running (ahead — скільки задач попереду) / done (result) / failed (error)."""
    job = db.get(AiJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "Задачу не знайдено або вона застаріла")
    return ai_jobs.job_out(db, job)


@router.post("/recommendations/{rec_id}/suggest", response_model=AiSuggestion, responses=JOB)
def suggest_recommendation(rec_id: uuid.UUID, user: Staff):
    """Пропозиція локальної LLM до рекомендації. Рекомендація не змінюється: керівник може взяти текст."""
    async def work(db: Session, u: User) -> AiSuggestion:
        return await _suggest_recommendation(rec_id, db, u)
    return ai_jobs.run("suggest", str(rec_id), user, work)


@router.post("/measures/{measure_id}/rewrite", response_model=RewriteOut, responses=JOB)
def rewrite(measure_id: uuid.UUID, body: RewriteIn, user: Executor):
    """Пропозиція чіткішого опису результату (без нових чисел, з правилом R4)."""
    async def work(db: Session, u: User) -> RewriteOut:
        return await _rewrite(measure_id, body, db, u)
    return ai_jobs.run("rewrite", _digest(measure_id, body.text), user, work)


@router.post("/intake/report", response_model=ReportDraft, responses=JOB)
def intake_report(user: Executor, file: Annotated[UploadFile, File()], period: Annotated[str | None, Form()] = None):
    """Звіт виконавця (зразок A) → чернетка форми «Внесення за один крок» для одного з власних заходів."""
    upload = Upload(file)

    async def work(db: Session, u: User) -> ReportDraft:
        return await _intake_report(db, u, upload, period)
    return ai_jobs.run("intake_report", _digest(upload.sha, period), user, work)


@router.post("/intake/measure", response_model=MeasureDraft, responses=JOB)
def intake_measure(
    user: Coordinator, file: Annotated[UploadFile, File()], program_id: Annotated[uuid.UUID, Form(alias="programId")]
):
    """Картка заходу (зразок B) → чернетка форми створення заходу. Захід створює координатор через `POST /measures`."""
    upload = Upload(file)

    async def work(db: Session, u: User) -> MeasureDraft:
        return await _intake_measure(db, u, upload, program_id)
    return ai_jobs.run("intake_measure", _digest(upload.sha, program_id), user, work)


@router.post("/risks/{risk_id}/measure-draft", response_model=MeasureDraft, responses=JOB)
def risk_measure_draft(risk_id: uuid.UUID, body: RiskMeasureDraftIn, user: Coordinator):
    """Чернетка заходу для ризику без заходів (правило C1): назву пропонує модель, решту полів — правила."""
    async def work(db: Session, u: User) -> MeasureDraft:
        return await _risk_measure_draft(risk_id, body, db, u)
    return ai_jobs.run("measure_draft", _digest(risk_id, body.program_id), user, work)


@router.post("/risks/{risk_id}/explain", response_model=RiskExplanation, responses=JOB)
def explain_risk(risk_id: uuid.UUID, user: Staff):
    """Пояснення стану ризику з посиланнями [n] на ризик, індикатори, заходи, сигнали і прапорці."""
    async def work(db: Session, u: User) -> RiskExplanation:
        return await _explain_risk(risk_id, db, u)
    return ai_jobs.run("explain", str(risk_id), user, work)


@router.post("/digest/weekly", response_model=WeeklyDigest, responses=JOB)
def weekly(user: Staff, program_id: uuid.UUID | None = None):
    """Тижневий дайджест керівнику з посиланнями на джерела."""
    async def work(db: Session, u: User) -> WeeklyDigest:
        return await _weekly(db, u, program_id)
    return ai_jobs.run("digest", str(program_id), user, work)


@router.post("/periods/{period_id}/evidence-check", response_model=EvidenceCheck, responses=JOB)
def check_evidence(period_id: uuid.UUID, user: Staff):
    """Порада координатору перед погодженням: правила V1–V3 і, якщо ШІ увімкнено, коментар з цитатами."""
    async def work(db: Session, u: User) -> EvidenceCheck:
        return await _check_evidence(period_id, db, u)
    return ai_jobs.run("evidence", str(period_id), user, work)


@router.post("/ask", response_model=AskAnswer, responses=JOB)
def ask(body: AskIn, user: SubjectUser):
    """Питання по даних програми в межах прав ролі; відповідь з посиланнями на записи."""
    async def work(db: Session, u: User) -> AskAnswer:
        return await _ask(body, db, u)
    return ai_jobs.run("ask", _digest(body.question), user, work)


@router.get("/chats", response_model=list[AiChatSummary])
def list_chats(db: DbDep, user: SubjectUser) -> list[AiChatSummary]:
    """Власні розмови з асистентом, найсвіжіші першими."""
    return [ai_chats.summary(c) for c in ai_chats.of_user(db, user)]


@router.post("/chats", response_model=AiChatOut, status_code=201)
def create_chat(body: AiChatIn, db: DbDep, user: SubjectUser) -> AiChatOut:
    chat = ai_chats.create(db, user, body.title)
    db.commit()
    return ai_chats.out(chat)


@router.get("/chats/{chat_id}", response_model=AiChatOut)
def get_chat(chat_id: uuid.UUID, db: DbDep, user: SubjectUser) -> AiChatOut:
    return ai_chats.out(ai_chats.owned(db, user, chat_id))


@router.patch("/chats/{chat_id}", response_model=AiChatOut)
def rename_chat(chat_id: uuid.UUID, body: AiChatRenameIn, db: DbDep, user: SubjectUser) -> AiChatOut:
    chat = ai_chats.owned(db, user, chat_id)
    ai_chats.rename(db, user, chat, body.title)
    db.commit()
    return ai_chats.out(chat)


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: uuid.UUID, db: DbDep, user: SubjectUser) -> Response:
    """Розмова зникає зі списку; питання і відповіді лишаються в журналі дій."""
    ai_chats.delete(db, user, ai_chats.owned(db, user, chat_id))
    db.commit()
    return Response(status_code=204)


@router.post("/chats/{chat_id}/messages", response_model=AiChatOut, responses=JOB)
def send_message(chat_id: uuid.UUID, body: AskIn, user: SubjectUser):
    """Питання в розмові: попередні репліки допомагають зрозуміти уточнення, факти — лише з поточних записів."""
    async def work(db: Session, u: User) -> AiChatOut:
        chat = ai_chats.owned(db, u, chat_id)
        await ai_chats.send(db, u, chat, body.question, today())
        db.commit()
        return ai_chats.out(chat)
    return ai_jobs.run("chat", _digest(chat_id, body.question), user, work)
