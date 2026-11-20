import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import OutboxMessage, utcnow
from app.services import integra

KEY = "test-integra-key"
URL = "http://integra.test/api/v1"
COORD = {"Authorization": "Bearer demo-coord"}
ADMIN = {"Authorization": "Bearer demo-admin"}
EXEC = {"Authorization": "Bearer demo-ex-fin"}
SEND = {"X-Integration-Key": KEY, "X-Topic": "measure.upsert"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "integra_url", URL)
    monkeypatch.setattr(settings, "integra_api_key", KEY)
    monkeypatch.setattr(integra, "transport", None)


@pytest.fixture
def integra_server(monkeypatch):
    calls: list[httpx.Request] = []
    replies: list[httpx.Response] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return replies.pop(0) if replies else httpx.Response(200, json={"status": "ok"})

    monkeypatch.setattr(integra, "transport", httpx.MockTransport(handle))
    return calls, replies


def their_measure(**over) -> dict:
    body = {
        "id": str(uuid.uuid4()),
        "unit_id": str(uuid.uuid4()),
        "title": "Провести навчання щодо конфлікту інтересів",
        "description": "Рекомендація за компонентом «Культура»",
        "component": "culture",
        "catalog_number": "3.2",
        "owner": "Начальник відділу кадрів",
        "due_date": "2026-12-31",
        "status": "planned",
        "done_on": None,
        "source": "integrity-dashboard",
    }
    return body | over


def own_measure(client, code: str) -> dict:
    me = client.post("/api/auth/login", json={"token": "demo-ex-fin"}).json()
    program = client.get("/api/programs", headers=COORD).json()[0]
    passport = client.get(f"/api/programs/{program['id']}/passport", headers=COORD).json()
    section = next(x for x in passport["sections"] if x["number"] == 3)
    r = client.post("/api/measures", headers=COORD, json={
        "sectionId": section["id"], "code": code, "title": "Навчання з питань конфлікту інтересів",
        "plannedDeadline": "2026-12-31",
        "assignments": [{"orgUnitId": me["orgUnitId"], "userId": me["id"], "isResponsible": True}],
    })
    assert r.status_code == 201, r.text
    client.post(f"/api/measures/{r.json()['id']}/progress", headers=EXEC, json={"text": "Розпочато підготовку"})
    return r.json()


def outbox(client) -> list[dict]:
    return client.get("/api/integrations/integra/outbox", headers=COORD).json()


def test_inbound_needs_key(client, monkeypatch):
    path = "/api/integrations/integra/measures"
    assert client.post(path, json=their_measure()).status_code == 401
    assert client.post(path, json=their_measure(), headers={"X-Integration-Key": "wrong"}).status_code == 401
    assert client.post(path, json=their_measure(), headers={**SEND, "X-Topic": "other"}).status_code == 422
    monkeypatch.setattr(settings, "integra_api_key", "")
    assert client.post(path, json=their_measure(), headers=SEND).status_code == 503


def test_upsert_is_idempotent_and_reject(client):
    body = their_measure()
    first = client.post("/api/integrations/integra/measures", json=body, headers=SEND)
    assert first.status_code == 200, first.text
    again = client.post("/api/integrations/integra/measures", json=body | {"title": "Оновлена назва", "extra": 1},
                        headers=SEND)
    assert again.json()["id"] == first.json()["id"]

    inbox = client.get("/api/integrations/integra/inbox?state=NEW", headers=COORD).json()
    item = next(i for i in inbox if i["externalId"] == body["id"])
    assert item["title"] == "Оновлена назва" and item["owner"] == "Начальник відділу кадрів"
    assert client.get("/api/integrations/integra/inbox", headers=EXEC).status_code == 403

    r = client.post(f"/api/integrations/integra/inbox/{item['id']}/reject", headers=COORD,
                    json={"comment": "Не стосується програми"})
    assert r.status_code == 200 and r.json()["state"] == "REJECTED"
    assert client.post(f"/api/integrations/integra/inbox/{item['id']}/reject", headers=COORD,
                       json={"comment": "ще раз"}).status_code == 409


def test_link_and_report_done_with_evidence(client, integra_server):
    calls, _ = integra_server
    m = own_measure(client, "3.91")
    body = their_measure()
    item_id = client.post("/api/integrations/integra/measures", json=body, headers=SEND).json()["id"]

    r = client.post(f"/api/integrations/integra/inbox/{item_id}/link", headers=COORD, json={"measureId": m["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "LINKED" and r.json()["measureCode"] == m["code"]
    assert client.post(f"/api/integrations/integra/inbox/{item_id}/link", headers=COORD,
                       json={"measureId": m["id"]}).status_code == 409

    r = client.post(
        f"/api/measures/{m['id']}/submit", headers=EXEC,
        data={"resultDescription": "Проведено навчання для 42 працівників, протокол № 7 від 10.11.2026",
              "documentTypes": "протокол", "documentDates": "2026-11-10"},
        files=[("files", ("протокол.pdf", b"%PDF integra", "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    sha = r.json()["measure"]["evidence"][0]["sha256"]
    r = client.post(f"/api/measures/{m['id']}/approve", headers=COORD, json={"comment": "Ок"})
    assert r.status_code == 200 and r.json()["status"] == "DONE", r.text

    mine = [o for o in outbox(client) if o["inboxId"] == item_id]
    assert [o["status"] for o in mine if o["state"] == "PENDING"] == ["done"]
    assert all(o["state"] == "SUPERSEDED" for o in mine if o["status"] != "done")

    r = client.post("/api/integrations/integra/outbox/flush", headers=COORD)
    assert r.status_code == 200 and r.json()["sent"] >= 1 and r.json()["pending"] == 0

    sent = [json.loads(c.content) for c in calls if json.loads(c.content).get("measure_id") == body["id"]]
    assert len(sent) == 1
    payload = sent[0]
    assert set(payload) <= {"measure_id", "external_id", "status", "done_on", "evidence"}
    assert payload["status"] == "done" and payload["done_on"]
    assert sha in payload["evidence"] and "протокол № 7" in payload["evidence"]
    assert len(payload["evidence"]) <= 2000
    req = next(c for c in calls if json.loads(c.content).get("measure_id") == body["id"])
    assert str(req.url) == URL + "/integrations/theme2/measures/status"
    assert req.headers["X-Integration-Key"] == KEY

    client.post("/api/integrations/integra/measures", json=body | {"status": "done"}, headers=SEND)
    assert not [o for o in outbox(client) if o["inboxId"] == item_id and o["state"] == "PENDING"]


def test_failures_retry_and_stop(client, integra_server):
    _, replies = integra_server
    m = own_measure(client, "3.92")
    item_id = client.post("/api/integrations/integra/measures", json=their_measure(), headers=SEND).json()["id"]
    client.post(f"/api/integrations/integra/inbox/{item_id}/link", headers=COORD, json={"measureId": m["id"]})
    pending = [o for o in outbox(client) if o["inboxId"] == item_id and o["state"] == "PENDING"]
    assert pending and pending[0]["status"] == "in_progress"

    replies.append(httpx.Response(503, text="busy"))
    client.post("/api/integrations/integra/outbox/flush", headers=ADMIN)
    msg = next(o for o in outbox(client) if o["id"] == pending[0]["id"])
    assert msg["state"] == "PENDING" and msg["attempts"] == 1 and "503" in msg["lastError"]
    assert msg["nextAttemptAt"] > msg["createdAt"]

    with SessionLocal() as db:
        row = db.get(OutboxMessage, uuid.UUID(msg["id"]))
        row.next_attempt_at = utcnow()
        db.commit()
    replies.append(httpx.Response(409, json={"detail": "bad transition"}))
    client.post("/api/integrations/integra/outbox/flush", headers=ADMIN)
    msg = next(o for o in outbox(client) if o["id"] == msg["id"])
    assert msg["state"] == "FAILED" and "409" in msg["lastError"]

    assert client.post(f"/api/integrations/integra/outbox/{msg['id']}/retry", headers=EXEC).status_code == 403
    r = client.post(f"/api/integrations/integra/outbox/{msg['id']}/retry", headers=COORD)
    assert r.status_code == 200 and r.json()["sent"] == 1

    status = client.get("/api/integrations/integra/status", headers=COORD).json()
    assert status["enabled"] and status["inbox"]["LINKED"] >= 1 and status["outbox"]["FAILED"] == 0


def test_permanent_measure_counts_only_periods_since_link():
    from datetime import datetime, timezone

    from app.enums import MeasureStatus as St
    from app.models import IntegraInbox, Measure, MeasurePeriod

    def measure(permanent: bool) -> Measure:
        m = Measure(code="1.1", title="Канали повідомлень", is_permanent=permanent)
        m.periods = [MeasurePeriod(period="2026-H1", status=St.DONE), MeasurePeriod(period="2026-H2", status=St.PLANNED)]
        return m

    item = IntegraInbox(external_id="x", decided_at=datetime(2026, 11, 19, tzinfo=timezone.utc))
    assert integra.measure_status(integra._periods(item, measure(permanent=True))) == "planned"
    assert integra.measure_status(integra._periods(item, measure(permanent=False))) == "done"
    m = measure(permanent=True)
    m.periods[1].status = St.ON_REVIEW
    assert integra.measure_status(integra._periods(item, m)) == "in_progress"
