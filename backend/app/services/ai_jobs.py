import asyncio
import concurrent.futures
import logging
import threading
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import AiJob, User, as_utc

log = logging.getLogger("app.ai_jobs")
KEEP = timedelta(days=1)
ACTIVE = ("queued", "running")

T = TypeVar("T")
Work = Callable[[Session, User], Awaitable[BaseModel]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stale_before() -> datetime:
    # a job still queued/running after this long belongs to a process that is gone
    return _now() - timedelta(seconds=2 * settings.llm_timeout + 60)


class Runner:
    """AI work runs here, off the server's event loop: own thread, own loop, own DB session per job.
    Job state lives in the ai_jobs table, so any worker process can answer GET /ai/jobs/{id}."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sem: asyncio.Semaphore | None = None
        self._futures: dict[uuid.UUID, concurrent.futures.Future] = {}
        self._results: dict[uuid.UUID, BaseModel] = {}

    def _start(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                ready = threading.Event()

                def main() -> None:
                    asyncio.set_event_loop(loop)
                    self._sem = asyncio.Semaphore(max(1, settings.ai_concurrency))
                    ready.set()
                    loop.run_forever()

                threading.Thread(target=main, name="ai-jobs", daemon=True).start()
                ready.wait()
                self._loop = loop
            return self._loop

    def call(self, coro: Coroutine[Any, Any, T], timeout: float) -> T:
        """Run a short coroutine (status, diagnostics) on the AI loop, outside the job queue."""
        return asyncio.run_coroutine_threadsafe(coro, self._start()).result(timeout)

    def submit(self, kind: str, key: str, user: User, work: Work) -> uuid.UUID:
        with SessionLocal() as db:
            db.execute(delete(AiJob).where(AiJob.finished_at < _now() - KEEP))
            same = db.scalars(select(AiJob).where(
                AiJob.kind == kind, AiJob.key == key, AiJob.user_id == user.id, AiJob.status.in_(ACTIVE),
                AiJob.created_at > _stale_before()).order_by(AiJob.created_at.desc())).first()
            if same is not None:
                db.commit()
                return same.id
            job = AiJob(kind=kind, key=key, user_id=user.id)
            db.add(job)
            db.commit()
            job_id = job.id
        self._futures[job_id] = asyncio.run_coroutine_threadsafe(self._run(job_id, work), self._start())
        return job_id

    def _set(self, job_id: uuid.UUID, **values: Any) -> None:
        with SessionLocal() as db:
            job = db.get(AiJob, job_id)
            for k, v in values.items():
                setattr(job, k, v)
            db.commit()

    async def _run(self, job_id: uuid.UUID, work: Work) -> None:
        assert self._sem is not None
        async with self._sem:
            self._set(job_id, status="running", started_at=_now())
            with SessionLocal() as db:
                try:
                    user = db.get(User, db.get(AiJob, job_id).user_id)
                    if user is None:
                        raise HTTPException(401, "Користувача не знайдено")
                    result = await work(db, user)
                    db.commit()
                except HTTPException as e:
                    db.rollback()
                    self._set(job_id, status="failed", finished_at=_now(),
                              error={"status": e.status_code, "detail": e.detail})
                    return
                except Exception:
                    db.rollback()
                    log.exception("AI job %s failed", job_id)
                    self._set(job_id, status="failed", finished_at=_now(),
                              error={"status": 500, "detail": "Внутрішня помилка під час роботи ШІ"})
                    return
            self._results[job_id] = result
            self._set(job_id, status="done", finished_at=_now(),
                      result=result.model_dump(mode="json", by_alias=True))

    def wait(self, job_id: uuid.UUID, timeout: float) -> bool:
        fut = self._futures.get(job_id)
        if fut is None:  # running in another worker process
            return False
        try:
            fut.result(timeout)
        except concurrent.futures.TimeoutError:
            return False
        self._futures.pop(job_id, None)
        return True

    def take_result(self, job_id: uuid.UUID) -> BaseModel | None:
        return self._results.pop(job_id, None)


runner = Runner()


def job_out(db: Session, job: AiJob) -> dict:
    status, error = job.status, job.error
    if status in ACTIVE and as_utc(job.created_at) < _stale_before():
        status, error = "failed", {"status": 504, "detail": "Задачу перервано: сервер перезапускався, повторіть запит"}
    out: dict = {"jobId": str(job.id), "kind": job.kind, "status": status}
    if status in ACTIVE:
        out["ahead"] = db.scalar(select(func.count()).select_from(AiJob).where(
            AiJob.status.in_(ACTIVE), AiJob.created_at < job.created_at, AiJob.created_at > _stale_before())) or 0
    if status == "done":
        out["result"] = job.result
    if status == "failed":
        out["error"] = error
    return out


def state(job_id: uuid.UUID) -> dict:
    with SessionLocal() as db:
        return job_out(db, db.get(AiJob, job_id))


def latest_job_id() -> uuid.UUID | None:
    with SessionLocal() as db:
        return db.scalar(select(AiJob.id).order_by(AiJob.created_at.desc()).limit(1))


def run(kind: str, key: str, user: User, work: Work) -> BaseModel | JSONResponse:
    """Quick answers (cache, rules, validation errors) come back at once; slow ones answer 202 with a job id."""
    job_id = runner.submit(kind, key, user, work)
    if not runner.wait(job_id, settings.ai_wait_seconds):
        return JSONResponse(state(job_id), status_code=202)
    out = state(job_id)
    if out["status"] == "failed":
        raise HTTPException(out["error"]["status"], out["error"]["detail"])
    return runner.take_result(job_id) or JSONResponse(out["result"])
