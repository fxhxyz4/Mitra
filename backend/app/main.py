import asyncio
import logging
from contextlib import asynccontextmanager
import time as clock
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import llm
from . import models  # noqa: F401  (register tables)
from .auth import session_secret_problem
from .services import integrity
from .config import settings
from .db import Base, SessionLocal, add_missing_columns, engine
from .models import User
from .routers import (
    admin,
    ai,
    analytics,
    audit,
    dashboard,
    flags,
    health,
    integrations,
    measures,
    programs,
    recommendations,
    reports,
    risk_model,
    risks,
)
from .services import control, dataset, importer, integra, leases, notify, seed, storage

log = logging.getLogger("app")
DAILY_AT = time(6, 0)
DAILY_LEASE = timedelta(hours=20)


def _run_daily():
    with SessionLocal() as db:
        result = control.run_daily(db)
        if removed := storage.sweep_orphans(db):
            log.info("removed %d orphaned files from storage", removed)
        return result


def _dispatch() -> None:
    with SessionLocal() as db:
        notify.dispatch(db)
        db.commit()


def _deliver_integra() -> None:
    with SessionLocal() as db:
        integra.deliver(db)
        db.commit()


async def _lead(name: str, ttl: timedelta, renew: bool = True) -> bool:
    try:
        return await asyncio.to_thread(leases.claim, name, ttl, renew=renew)
    except Exception:
        log.exception("lease %s unavailable", name)
        return False


async def _integra_loop() -> None:
    while True:
        await asyncio.sleep(settings.integra_interval_seconds)
        if not integra.enabled() or not await _lead("integra", timedelta(seconds=3 * settings.integra_interval_seconds)):
            continue
        try:
            await asyncio.to_thread(_deliver_integra)
        except Exception:
            log.exception("integra delivery failed")


def seconds_until(at: time) -> float:
    now = datetime.now(settings.tz)
    day = now.date() if now.timetz().replace(tzinfo=None) < at else now.date() + timedelta(days=1)
    return max(0.0, datetime.combine(day, at, tzinfo=settings.tz).timestamp() - clock.time())


async def _daily_scheduler() -> None:
    while True:
        await asyncio.sleep(seconds_until(DAILY_AT))
        if not await _lead("daily", DAILY_LEASE, renew=False):
            continue
        try:
            log.info("daily job: %s", await asyncio.to_thread(_run_daily))
        except Exception:
            log.exception("daily job failed")


async def _notify_loop() -> None:
    while True:
        await asyncio.sleep(settings.notify_interval_minutes * 60)
        if not await _lead("notify", timedelta(minutes=3 * settings.notify_interval_minutes)):
            continue
        try:
            await asyncio.to_thread(_dispatch)
        except Exception:
            log.exception("reminder dispatch failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    for problem in (session_secret_problem(), integrity.report_secret_problem()):
        if problem:
            raise RuntimeError(problem)
    if (site := urlsplit(settings.site_url)).scheme != "https" and site.hostname not in ("localhost", "127.0.0.1"):
        log.warning("SITE_URL is %s: QR codes on reports lead there, and checking a downloaded copy needs https "
                    "(browsers hash files only in a secure context).", settings.site_url)
    # Prototype: schema is created from the ORM models. For production use Alembic migrations.
    Base.metadata.create_all(engine)
    add_missing_columns()
    with SessionLocal() as db:
        ds_file = settings.dataset_file or dataset.DEFAULT_FILE
        uses_dataset = settings.demo_dataset and not settings.import_file and ds_file.exists()
        fresh_or_dataset = dataset.is_loaded(db, ds_file) or db.scalar(select(User.id).limit(1)) is None
        if settings.demo_today is None and uses_dataset and fresh_or_dataset:
            settings.demo_today = dataset.cut_date(ds_file)
        if settings.import_file and importer.import_file_if_empty(db, settings.import_file):
            log.info("data imported from %s", settings.import_file)
        elif settings.demo_dataset and dataset.load(db, ds_file):
            log.info("organisers' dataset loaded from %s", ds_file)
        elif settings.seed_demo_data and seed.seed(db):
            log.info("demo data seeded")
        elif leases.claim("daily-startup", timedelta(minutes=5), renew=False):
            control.run_daily(db)
        if settings.demo_login:
            log.warning("DEMO_LOGIN is on: the login page lists demo accounts with their tokens. "
                        "For real data start with DEMO_DATASET=false, SEED_DEMO_DATA=false and DEMO_LOGIN=false.")
    tasks = [
        asyncio.create_task(_daily_scheduler()),
        asyncio.create_task(_notify_loop()),
        asyncio.create_task(_integra_loop()),
    ]
    yield
    for t in tasks:
        t.cancel()
    await llm.aclose()


app = FastAPI(
    title=settings.app_name,
    description="Mitra — API. Браузер: сеанс у cookie HttpOnly після `POST /api/auth/login` "
    "(запити, що змінюють дані, — із заголовком `X-Requested-With`). "
    "Скрипти й інтеграції: `Authorization: Bearer <token>` (кнопка Authorize у Swagger).",
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Token"],
)

for r in (health, analytics, ai, programs, measures, risks, risk_model, flags, dashboard, recommendations, reports,
          audit, admin, integrations):
    app.include_router(r.router, prefix=settings.api_prefix)
