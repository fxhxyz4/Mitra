import io
import uuid
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import llm
from app.config import settings, today
from app.db import SessionLocal
from app import halfyear
from app.enums import Channel
from app.main import app
from app.models import Reminder, User
from app.services import notify

H = {name: {"Authorization": f"Bearer {tok}"} for name, tok in {
    "coord": "demo-coord", "head": "demo-head", "analyst": "demo-analyst", "admin": "demo-admin",
    "ex_fin": "demo-ex-fin", "ex_proc": "demo-ex-proc",
}.items()}
SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample-import.json"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c




def test_analytics_overview(client):
    assert client.get("/api/analytics/overview").status_code == 401
    assert client.get("/api/analytics/overview", headers=H["ex_fin"]).status_code == 403
    o = client.get("/api/analytics/overview?weeks=8", headers=H["analyst"]).json()
    k = o["kpis"]
    assert k["measuresTotal"] == 22 and k["overdue"] > 0 and k["risksTotal"] == 8
    assert 0 <= k["donePercent"] <= 100 and k["returnRatePercent"] > 0
    assert len(o["statusTrend"]) == 8 and len(o["flagTrend"]) == 8
    assert sum(o["statusTrend"][-1]["counts"].values()) == 22
    assert o["flagTrend"][-1]["open"] == k["openFlags"]
    assert [u["name"] for u in o["units"]] == sorted(u["name"] for u in o["units"])  # no ranking
    r1 = next(r for r in o["risks"] if r["code"] == "КР-01")
    ind = r1["indicators"][0]
    assert ind["values"] and 0 <= ind["progressPercent"] <= 100
    assert [s["number"] for s in o["sections"]] == [1, 2, 3]


def test_analytics_export(client):
    from openpyxl import load_workbook

    assert client.get("/api/analytics/export?format=xlsx", headers=H["head"]).status_code == 403
    r = client.get("/api/analytics/export?format=xlsx", headers=H["analyst"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxml")
    wb = load_workbook(io.BytesIO(r.content))
    assert {"Показники", "Розділи", "Підрозділи", "Ризики", "Динаміка статусів"} <= set(wb.sheetnames)
    assert wb["Показники"]["A2"].value == "Заходів у програмі" and wb["Показники"]["B2"].value == 22

    csv = client.get("/api/analytics/export?format=csv", headers=H["analyst"]).text
    assert "# Показники" in csv and "# Підрозділи" in csv
    js = client.get("/api/analytics/export?format=json", headers=H["analyst"]).json()
    assert js["kpis"]["measuresTotal"] == 22




def _program_id(client):
    return client.get("/api/programs", headers=H["coord"]).json()[0]["id"]


def test_internal_memo_and_exports(client):
    from docx import Document
    from openpyxl import load_workbook

    pid, period = _program_id(client), halfyear.of(today())
    body = {"programId": pid, "period": period, "type": "INTERNAL"}
    assert client.post("/api/reports/generate", headers=H["analyst"], json=body).status_code == 403
    rep = client.post("/api/reports/generate", headers=H["coord"], json=body).json()
    assert rep["fileKey"].endswith(".docx")
    memo = client.get(f"/api/reports/{rep['id']}/internal", headers=H["analyst"]).json()
    rules = {c["rule"] for c in memo["conclusions"]}
    assert {"I1", "I2", "I3"} <= rules
    i3 = next(c for c in memo["conclusions"] if c["rule"] == "I3")
    assert i3["severity"] == "CRITICAL" and i3["facts"]["formalClosure"]  # demo 2.2: formal closure
    assert memo["problemMeasures"] and memo["recommendations"]

    doc = Document(io.BytesIO(client.get(f"/api/reports/{rep['id']}/export?format=docx", headers=H["analyst"]).content))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Аналітична довідка" in text and "[правило I1]" in text
    wb = load_workbook(io.BytesIO(client.get(f"/api/reports/{rep['id']}/export?format=xlsx", headers=H["analyst"]).content))
    assert {"Звіт НАЗК", "Висновки", "Рекомендації"} <= set(wb.sheetnames)

    nazk = client.post("/api/reports/generate", headers=H["coord"], json={"programId": pid, "period": period}).json()
    assert client.get(f"/api/reports/{nazk['id']}/internal", headers=H["coord"]).status_code == 404
    doc = Document(io.BytesIO(client.get(f"/api/reports/{nazk['id']}/export", headers=H["coord"]).content))
    assert len(doc.tables) == 3  # one table per NAZK section
    wb = load_workbook(io.BytesIO(client.get(f"/api/reports/{nazk['id']}/export?format=xlsx", headers=H["coord"]).content))
    assert wb.sheetnames == ["Звіт НАЗК"] and wb["Звіт НАЗК"].max_row == 23




def test_contacts_and_delivery(client, monkeypatch):
    bad = client.put("/api/auth/me/contacts", headers=H["ex_proc"], json=[{"channel": "EMAIL", "address": "nope"}])
    assert bad.status_code == 422
    r = client.put("/api/auth/me/contacts", headers=H["ex_proc"], json=[
        {"channel": "EMAIL", "address": "proc@example.org"}])
    assert r.status_code == 200 and len(r.json()) == 1
    assert len(client.get("/api/auth/me/contacts", headers=H["ex_proc"]).json()) == 1
    assert client.put("/api/auth/me/contacts", headers=H["ex_proc"],
                      json=[{"channel": "MESSENGER", "address": "123456"}]).status_code == 422

    sent: list = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setitem(notify.SENDERS, Channel.EMAIL, lambda addr, rem: sent.append((addr, rem.text)))

    with SessionLocal() as db:
        user = db.query(User).filter_by(display_name="Виконавець — закупівлі").one()
        measure_id = uuid.UUID(client.get("/api/measures?mine=true", headers=H["ex_proc"]).json()[0]["id"])
        now = datetime.now(timezone.utc)
        db.add(Reminder(measure_id=measure_id, user_id=user.id, send_at=now - timedelta(hours=1), text="Тест нагадування"))
        db.add(Reminder(measure_id=measure_id, user_id=user.id, send_at=now - timedelta(days=5), text="Старе нагадування"))
        db.commit()
        assert notify.dispatch(db) == 1
        assert notify.dispatch(db) == 0  # no duplicates
        db.commit()
    assert sent == [("proc@example.org", "Тест нагадування")]

    rems = client.get("/api/reminders", headers=H["ex_proc"]).json()
    fresh = next(x for x in rems if x["text"] == "Тест нагадування")
    assert fresh["sent"] and [(d["channel"], d["status"]) for d in fresh["deliveries"]] == [("EMAIL", "SENT")]
    old = next(x for x in rems if x["text"] == "Старе нагадування")
    assert old["deliveries"][0]["status"] == "SKIPPED"

    # admin can manage contacts; an empty list switches external delivery off
    users = client.get("/api/admin/users", headers=H["admin"]).json()
    uid = next(u["id"] for u in users if u["displayName"] == "Виконавець — закупівлі")
    assert client.put(f"/api/admin/users/{uid}/contacts", headers=H["admin"], json=[]).json() == []




def _ollama(monkeypatch, handler):
    monkeypatch.setattr(llm, "client", httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler)))


def test_ai_suggestion_is_only_a_proposal(client, monkeypatch):
    seen = {}

    def fake(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        content = json.dumps({"text": "Доручити підрозділу надати пояснення щодо строку до наради.",
                              "steps": ["Заслухати виконавця", "Встановити новий строк"], "rationale": "R1"},
                             ensure_ascii=False)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    _ollama(monkeypatch, fake)
    rec = client.get("/api/recommendations?status=PROPOSED", headers=H["head"]).json()[0]
    r = client.post(f"/api/ai/recommendations/{rec['id']}/suggest", headers=H["head"])
    assert r.status_code == 200, r.text
    sug = r.json()
    assert sug["steps"] and sug["disclaimer"] and sug["basis"]["rule"]
    assert seen["body"]["format"]["required"] == ["text", "steps", "rationale"]

    after = next(x for x in client.get("/api/recommendations", headers=H["head"]).json() if x["id"] == rec["id"])
    assert after["text"] == rec["text"] and after["status"] == "PROPOSED"  # nothing decided by the model
    assert after["basis"]["aiSuggestions"][0]["text"] == sug["text"]

    users = client.get("/api/admin/users", headers=H["admin"]).json()
    coord = next(u["id"] for u in users if u["role"] == "COORDINATOR")
    acc = client.post(f"/api/recommendations/{rec['id']}/accept", headers=H["head"],
                      json={"responsibleId": coord, "dueDate": "2026-12-20", "text": sug["text"]}).json()
    assert acc["text"] == sug["text"] and acc["basis"]["originalText"] == rec["text"]

    assert client.post(f"/api/ai/recommendations/{rec['id']}/suggest", headers=H["ex_fin"]).status_code == 403

    def down(request):
        raise httpx.ConnectError("down", request=request)

    _ollama(monkeypatch, down)
    assert client.post(f"/api/ai/recommendations/{rec['id']}/suggest", headers=H["head"]).status_code == 503


def test_ai_suggestion_retries_broken_json(client, monkeypatch):
    formats = []

    def fake(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        formats.append(body["format"])
        content = '{"text": "Обірвана відповідь", "steps": ["Крок"]' if isinstance(body["format"], dict) \
            else '{"text": "Доручити підрозділу надати пояснення.", "steps": ["Заслухати виконавця"]}'
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    _ollama(monkeypatch, fake)
    rec = client.get("/api/recommendations?status=PROPOSED", headers=H["head"]).json()[-1]
    r = client.post(f"/api/ai/recommendations/{rec['id']}/suggest", headers=H["head"])
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "Доручити підрозділу надати пояснення." and r.json()["steps"] == ["Заслухати виконавця"]
    assert formats[-1] == "json"

    _ollama(monkeypatch, lambda request: httpx.Response(200, json={"message": {"role": "assistant", "content": "{"}}))
    other = client.get("/api/recommendations?status=PROPOSED", headers=H["head"]).json()[0]
    assert client.post(f"/api/ai/recommendations/{other['id']}/suggest", headers=H["head"]).status_code == 502




def test_import(client):
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    accounts = {k: payload[k] for k in ("orgUnits", "users")}
    program_data = {k: payload[k] for k in ("risks", "indicators", "programs")}
    n_programs = len(client.get("/api/programs", headers=H["coord"]).json())
    # accounts — administrator, program data — coordinator
    assert client.post("/api/admin/import", headers=H["coord"], json=payload).status_code == 403
    assert client.post("/api/admin/import", headers=H["admin"], json=payload).status_code == 403
    assert client.post("/api/admin/import", headers=H["admin"], json=program_data).status_code == 403
    assert client.post("/api/admin/import", headers=H["head"], json=accounts).status_code == 403

    names = lambda: {u["displayName"] for u in client.get("/api/admin/users", headers=H["admin"]).json()}  # noqa: E731
    dry = client.post("/api/admin/import?dryRun=true", headers=H["admin"], json=accounts).json()
    assert dry["dryRun"] and dry["created"]["users"] == 4
    assert "Уповноважена особа (приклад)" not in names()  # nothing saved

    res = client.post("/api/admin/import", headers=H["admin"], json=accounts).json()
    assert res["created"] == {"orgUnits": 4, "users": 4}
    # the sample sets no tokens: every account gets a random one, shown once in the result
    assert set(res["tokens"]) == {u["displayName"] for u in accounts["users"]}
    assert all(len(t) >= 32 for t in res["tokens"].values())

    dry = client.post("/api/admin/import?dryRun=true", headers=H["coord"], json=program_data).json()
    assert dry["dryRun"] and dry["created"]["measures"] == 4
    assert len(client.get("/api/programs", headers=H["coord"]).json()) == n_programs  # nothing saved

    bad = json.loads(json.dumps(program_data))
    bad["programs"][0]["measures"][1]["risk"] = "НЕМАЄ"
    r = client.post("/api/admin/import", headers=H["coord"], json=bad)
    assert r.status_code == 422 and "НЕМАЄ" in json.dumps(r.json(), ensure_ascii=False)
    assert len(client.get("/api/programs", headers=H["coord"]).json()) == n_programs  # rolled back

    out = client.post("/api/admin/import", headers=H["coord"], json=program_data).json()
    assert out["created"] == {"risks": 2, "indicators": 3, "indicatorValues": 3, "programs": 1, "measures": 4}
    programs = client.get("/api/programs", headers=H["coord"]).json()
    imported = next(p for p in programs if p["title"].startswith("Антикорупційна програма (приклад"))
    assert imported["status"] == "APPROVED" and len(programs) == n_programs + 1

    coord = {"Authorization": f"Bearer {res['tokens']['Уповноважена особа (приклад)']}"}
    pp = client.get(f"/api/programs/{imported['id']}/passport", headers=coord).json()
    assert pp["totals"]["measures"] == 4
    ex = {"Authorization": f"Bearer {res['tokens']['Виконавець — кадри (приклад)']}"}
    assert client.get("/api/measures?mine=true", headers=ex).json()

    again = client.post("/api/admin/import", headers=H["coord"], json=program_data).json()
    assert "measures" not in again["created"] and again["updated"]["measures"] == 4
    assert len(client.get("/api/programs", headers=H["coord"]).json()) == n_programs + 1




def test_role_matrix(client):
    pid = _program_id(client)
    get = lambda url, who: client.get(url, headers=H[who]).status_code  # noqa: E731
    # admin: accounts and settings only, no program/flags/reports/dashboards
    assert client.post("/api/programs", headers=H["admin"], json={}).status_code == 403
    assert client.post("/api/flags/evaluate", headers=H["admin"]).status_code == 403
    assert client.post("/api/reports/generate", headers=H["admin"], json={"programId": pid}).status_code == 403
    for url in ("/api/flags", "/api/reports", "/api/recommendations",
                "/api/dashboard/coordinator", "/api/dashboard/executive", "/api/analytics/overview"):
        assert get(url, "admin") == 403, url
    assert get("/api/audit", "admin") == 200
    assert get("/api/admin/users", "coord") == 403
    # panels: coordinator — own panel, head — executive, analyst — all (read)
    assert get("/api/dashboard/executive", "coord") == 403
    assert get("/api/dashboard/executive", "head") == 200
    for url in ("/api/dashboard/coordinator", "/api/dashboard/executive", "/api/analytics/overview", "/api/reports"):
        assert get(url, "analyst") == 200, url
    assert get("/api/reports", "head") == 403
    # Risk Flags: everyone except admin; executor — only own
    for who in ("coord", "head", "analyst", "ex_fin"):
        assert get("/api/flags", who) == 200
    # action journal: administrator only
    for who in ("coord", "head", "analyst", "ex_fin"):
        assert get("/api/audit", who) == 403, who
        assert get("/api/audit/verify", who) == 403, who
    assert get("/api/audit/verify", "admin") == 200


def test_startup_import_shows_the_issued_tokens_once(caplog):
    """IMPORT_FILE on a fresh database: the sample sets no tokens, so the random ones must reach someone."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import models  # noqa: F401  (register tables)
    from app.auth import user_by_token
    from app.db import Base
    from app.services.importer import import_file_if_empty

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as db, caplog.at_level("WARNING", logger="app"):
        assert import_file_if_empty(db, SAMPLE)
        db.commit()
        shown = [r.getMessage() for r in caplog.records if "issued sign-in tokens" in r.getMessage()]
        assert len(shown) == 1
        users = json.loads(SAMPLE.read_text(encoding="utf-8"))["users"]
        lines = dict(line.strip().rsplit(": ", 1) for line in shown[0].splitlines()[1:])
        assert set(lines) == {u["displayName"] for u in users}
        assert user_by_token(db, lines["Уповноважена особа (приклад)"]).role.value == "COORDINATOR"
        assert not import_file_if_empty(db, SAMPLE)  # a database with users is never imported into again
