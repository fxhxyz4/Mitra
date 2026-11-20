import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

HEAD = {"Authorization": "Bearer demo-head"}
COORD = {"Authorization": "Bearer demo-coord"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def slow_model(model):
    gate = threading.Event()

    def handler(_req: httpx.Request) -> httpx.Response:
        gate.wait(10)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "{}"}})

    model(handler)
    yield gate
    gate.set()


def test_slow_ai_answers_202_and_the_job_delivers(client, slow_model, monkeypatch):
    monkeypatch.setattr(settings, "ai_wait_seconds", 0.3)
    risk = client.get("/api/risks", headers=HEAD).json()[0]["id"]

    first = client.post(f"/api/ai/risks/{risk}/explain", headers=HEAD)
    assert first.status_code == 202, first.text
    job = first.json()
    assert job["status"] in ("queued", "running")

    again = client.post(f"/api/ai/risks/{risk}/explain", headers=HEAD).json()
    assert again["jobId"] == job["jobId"]  # same request while running → same job

    t = time.monotonic()
    assert client.get("/api/measures", headers=HEAD).status_code == 200
    assert time.monotonic() - t < 2  # the server keeps serving while the model thinks

    assert client.get(f"/api/ai/jobs/{job['jobId']}", headers=COORD).status_code == 404  # not your job

    slow_model.set()
    for _ in range(100):
        state = client.get(f"/api/ai/jobs/{job['jobId']}", headers=HEAD).json()
        if state["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert state["status"] == "done", state
    assert state["result"]["riskId"] == risk and state["result"]["text"]


def test_validation_errors_still_come_back_directly(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_wait_seconds", 5)
    r = client.post("/api/ai/risks/00000000-0000-0000-0000-000000000000/explain", headers=HEAD)
    assert r.status_code == 404


def test_job_state_lives_in_the_database(client, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.models import AiJob
    from app.services import ai_jobs

    risk = client.get("/api/risks", headers=HEAD).json()[0]["id"]
    assert client.post(f"/api/ai/risks/{risk}/explain", headers=HEAD).status_code == 200
    job_id = ai_jobs.latest_job_id()
    ai_jobs.runner._futures.clear()
    ai_jobs.runner._results.clear()  # as if another worker process answers the poll
    done = client.get(f"/api/ai/jobs/{job_id}", headers=HEAD).json()
    assert done["status"] == "done" and done["result"]["riskId"] == risk

    with SessionLocal() as db:
        me = db.get(AiJob, job_id).user_id
        stale = AiJob(kind="explain", key="stale", user_id=me, status="running",
                      created_at=datetime.now(timezone.utc) - timedelta(seconds=3 * settings.llm_timeout))
        db.add(stale)
        db.commit()
        stale_id = stale.id
    gone = client.get(f"/api/ai/jobs/{stale_id}", headers=HEAD).json()
    assert gone["status"] == "failed" and gone["error"]["status"] == 504


def test_status_and_diagnostics_are_plain_endpoints():
    import inspect

    from app.routers import ai

    for name in ("status", "chat", "embed", "explain_risk", "weekly", "ask", "job_status"):
        assert not inspect.iscoroutinefunction(getattr(ai, name)), name
