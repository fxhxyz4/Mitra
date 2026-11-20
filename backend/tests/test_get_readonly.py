import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.main import app

ROLES = ("coord", "head", "analyst", "admin", "ex-fin")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_get_endpoints_never_write(client):
    from app.services import ai_jobs

    H = lambda r: {"Authorization": f"Bearer demo-{r}"}  # noqa: E731
    coord = H("coord")
    program = client.get("/api/programs", headers=coord).json()[0]["id"]
    report = client.post("/api/reports/generate", headers=coord,
                         json={"programId": program, "period": "2026-H1", "type": "NAZK"}).json()["id"]
    with_evidence = next(
        (m["id"], ev[0]["id"]) for m in client.get("/api/measures", headers=coord).json()
        if (ev := client.get(f"/api/measures/{m['id']}/evidence", headers=coord).json())
    )
    risk = client.get("/api/risks", headers=coord).json()[0]["id"]
    assert client.post(f"/api/ai/risks/{risk}/explain", headers=coord).status_code == 200
    ids = {
        "program_id": program,
        "measure_id": with_evidence[0],
        "evidence_id": with_evidence[1],
        "risk_id": risk,
        "indicator_id": client.get("/api/indicators", headers=coord).json()[0]["id"],
        "org_unit_id": client.get("/api/admin/org-units", headers=coord).json()[0]["id"],
        "report_id": report,
        "job_id": str(ai_jobs.latest_job_id()),
        "chat_id": client.post("/api/ai/chats", headers=coord, json={}).json()["id"],
    }

    writes: list[str] = []
    current = {"url": ""}

    def spy(session, _ctx):
        if session.new or session.dirty or session.deleted:
            writes.append(current["url"])

    event.listen(Session, "after_flush", spy)
    try:
        for path, ops in app.openapi()["paths"].items():
            if "get" not in ops:
                continue
            params = re.findall(r"{(\w+)}", path)
            assert all(p in ids for p in params), f"give the test an id for {path}"
            url = path
            for p in params:
                url = url.replace("{" + p + "}", ids[p])
            for role in ROLES:
                current["url"] = f"GET {url} as {role}"
                client.get(url, headers=H(role))
    finally:
        event.remove(Session, "after_flush", spy)
    assert not writes, sorted(set(writes))


def test_get_handlers_have_no_write_calls():
    """Static guard for branches a request did not reach."""
    import ast
    from pathlib import Path

    bad = []
    for f in sorted(Path(__file__).parents[1].joinpath("app", "routers").glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for node in ast.parse(src).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "get" for d in node.decorator_list
            ):
                for call in ast.walk(node):
                    name = getattr(getattr(call, "func", None), "attr", None) if isinstance(call, ast.Call) else None
                    if name in ("commit", "add", "flush", "delete", "record", "sign", "merge"):
                        bad.append(f"{f.name}:{node.name} calls {name}()")
    assert not bad, bad


def test_unsigned_report_is_signed_only_by_post(client):
    from app.db import SessionLocal
    from app.models import Report
    from app.services import integrity

    coord = {"Authorization": "Bearer demo-coord"}
    program = client.get("/api/programs", headers=coord).json()[0]["id"]
    rid = client.post("/api/reports/generate", headers=coord,
                      json={"programId": program, "period": "2026-H1", "type": "NAZK"}).json()["id"]
    with SessionLocal() as db:
        r = db.get(Report, __import__("uuid").UUID(rid))
        r.data = {k: v for k, v in r.data.items() if k != integrity.KEY}
        db.commit()

    writes = []
    spy = lambda s, _c: writes.append(1) if (s.new or s.dirty) else None  # noqa: E731
    event.listen(Session, "after_flush", spy)
    try:
        assert client.get(f"/api/reports/{rid}/integrity", headers=coord).status_code == 409
        assert client.get(f"/api/reports/{rid}/export?format=docx", headers=coord).status_code == 409
    finally:
        event.remove(Session, "after_flush", spy)
    assert not writes
    assert client.post(f"/api/reports/{rid}/sign", headers=coord).status_code == 200
    assert client.get(f"/api/reports/{rid}/integrity", headers=coord).status_code == 200
