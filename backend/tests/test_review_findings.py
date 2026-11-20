import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone, UTC

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import llm
from app.auth import issue_session
from app.config import settings
from app.db import SessionLocal
from app.main import app, seconds_until
from app.models import Evidence, LlmAnswer, Program, User, local_date
from app.services import leases, storage

H = {k: {"Authorization": f"Bearer demo-{k}"} for k in ("coord", "admin", "ex-fin", "head")}
META = {"documentTypes": "акт", "documentDates": "2026-11-02"}  # тип і дата документа на кожен файл


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def program(client: TestClient) -> dict:
    p = next(p for p in client.get("/api/programs", headers=H["coord"]).json() if p["status"] == "APPROVED")
    return client.get(f"/api/programs/{p['id']}/passport", headers=H["coord"]).json()


def _measure(client: TestClient, program: dict, code: str, **extra) -> dict:
    unit = client.get("/api/auth/me", headers=H["ex-fin"]).json()["orgUnitId"]
    section = next(s for s in program["sections"] if s["number"] == 2)
    r = client.post("/api/measures", headers=H["coord"], json={
        "sectionId": section["id"], "code": code, "title": f"Перевірити договори {code}",
        "plannedDeadline": "2026-12-31", "assignments": [{"orgUnitId": unit, "isResponsible": True}], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_login_gives_an_expiring_session_token(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"token": "demo-ex-fin"}).json()
    session = r["sessionToken"]
    assert session.startswith("s1.") and r["expiresAt"] <= time.time() + settings.session_hours * 3600 + 5
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {session}"}).status_code == 200

    forged = session[:-4] + ("0000" if not session.endswith("0000") else "1111")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401

    with SessionLocal() as db:
        user = db.get(User, uuid.UUID(r["id"]))
        expired, _ = issue_session(user, signed_in=int(time.time()) - settings.session_max_days * 86400 - 10)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_session_is_renewed_near_expiry_and_dies_with_the_personal_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit = client.get("/api/auth/me", headers=H["ex-fin"]).json()["orgUnitId"]
    made = client.post("/api/admin/users", headers=H["admin"],
                       json={"displayName": "Тимчасовий виконавець", "role": "EXECUTOR", "orgUnitId": unit}).json()
    session = client.post("/api/auth/login", json={"token": made["token"]}).json()["sessionToken"]
    bearer = {"Authorization": f"Bearer {session}"}
    assert "X-Session-Token" not in client.get("/api/auth/me", headers=bearer).headers

    monkeypatch.setattr(settings, "session_hours", 100)
    renewed = client.get("/api/auth/me", headers=bearer).headers["X-Session-Token"]
    assert renewed != session
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {renewed}"}).status_code == 200

    assert client.post(f"/api/admin/users/{made['id']}/token", headers=H["admin"]).status_code == 200
    assert client.get("/api/auth/me", headers=bearer).status_code == 401


def test_browser_session_lives_in_an_httponly_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import SESSION_COOKIE
    from app.main import app

    monkeypatch.setattr(settings, "session_cookie_secure", False)  # the test client speaks plain http
    with TestClient(app) as browser:
        r = browser.post("/api/auth/login", json={"token": "demo-ex-fin"})
        cookie = r.headers["set-cookie"]
        assert f"{SESSION_COOKIE}=s1." in cookie and "HttpOnly" in cookie and "samesite=strict" in cookie.lower()
        assert browser.get("/api/auth/me").json()["id"] == r.json()["id"]  # no Authorization header at all

        # a write through the cookie needs X-Requested-With: a cross-site form cannot send it
        chat = browser.post("/api/ai/chats", json={})
        assert chat.status_code == 403 and "CSRF" in chat.json()["detail"]
        assert browser.post("/api/ai/chats", json={}, headers={"X-Requested-With": "mitra"}).status_code != 403

        browser.cookies.set(SESSION_COOKIE, "demo-ex-fin")  # the cookie never accepts a personal token
        assert browser.get("/api/auth/me").status_code == 401

        browser.post("/api/auth/login", json={"token": "demo-ex-fin"})
        out = browser.post("/api/auth/logout", headers={"X-Requested-With": "mitra"})
        assert out.status_code == 204 and f'{SESSION_COOKIE}=""' in out.headers["set-cookie"]
        assert browser.get("/api/auth/me").status_code == 401


def test_server_refuses_to_start_without_a_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import _session_key, session_secret_problem

    monkeypatch.setattr(settings, "demo_public_tokens", False)
    monkeypatch.setattr(settings, "session_secret", "")
    assert "SESSION_SECRET" in (session_secret_problem() or "")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        _session_key()
    monkeypatch.setattr(settings, "session_secret", "x" * 32)
    assert session_secret_problem() is None


def test_evidence_type_comes_from_the_allow_list(client: TestClient, program: dict) -> None:
    m = _measure(client, program, "2.81")
    url = f"/api/measures/{m['id']}/evidence"
    meta = {"documentTypes": "акт", "documentDates": "2026-03-01"}
    bad = client.post(url, headers=H["ex-fin"], data=meta, files=[("files", ("payload.html", b"<script>", "text/html"))])
    assert bad.status_code == 415
    ok = client.post(url, headers=H["ex-fin"], data=meta, files=[("files", ("akt.pdf", b"%PDF-1.4", "text/html"))])
    assert ok.status_code == 201, ok.text
    assert ok.json()[0]["docType"] == "акт" and ok.json()[0]["documentDate"] == "2026-03-01"
    dl = client.get(f"{url}/{ok.json()[0]['id']}/download", headers=H["ex-fin"])
    assert dl.headers["content-type"] == "application/pdf" and dl.headers["x-content-type-options"] == "nosniff"


def test_result_and_reason_are_exclusive_and_done_takes_no_more_files(client: TestClient, program: dict) -> None:
    m = _measure(client, program, "2.82")
    both = client.post(f"/api/measures/{m['id']}/submit", headers=H["ex-fin"],
                       data={"resultDescription": "Перевірено 14 договорів", "nonExecutionReason": "Не встигли"})
    assert both.status_code == 422
    r = client.post(f"/api/measures/{m['id']}/submit", headers=H["ex-fin"],
                    data={"resultDescription": "Перевірено 14 договорів, акт № 5 від 10.11.2026",
                          "nonExecutionReason": "  ", "documentTypes": "акт", "documentDates": "2026-11-10"},
                    files=[("files", ("akt.pdf", b"%PDF akt", "application/pdf"))])
    assert r.status_code == 200, r.text
    assert r.json()["measure"]["currentPeriod"]["nonExecutionReason"] is None
    done = client.post(f"/api/measures/{m['id']}/approve", headers=H["coord"], json={"comment": "Ок"})
    assert done.status_code == 200 and done.json()["status"] == "DONE"
    late = client.post(f"/api/measures/{m['id']}/evidence", headers=H["ex-fin"],
                       data={"documentTypes": "додаток", "documentDates": "2026-11-10"},
                       files=[("files", ("dodatok.pdf", b"%PDF late", "application/pdf"))])
    assert late.status_code == 409


def test_approved_program_freezes_the_measure_passport(client: TestClient, program: dict) -> None:
    m = _measure(client, program, "2.83")
    url = f"/api/measures/{m['id']}"
    assert client.patch(url, headers=H["coord"], json={"title": "Інша назва"}).status_code == 409
    assert client.patch(url, headers=H["coord"], json={"plannedDeadline": "2026-10-01"}).status_code == 409
    other = client.get("/api/admin/org-units", headers=H["coord"]).json()[1]["id"]
    same = client.patch(url, headers=H["coord"], json={
        "title": m["title"], "code": m["code"], "assignments": [{"orgUnitId": other, "isResponsible": True}]})
    assert same.status_code == 200, same.text


def test_file_is_removed_when_the_transaction_rolls_back(client: TestClient) -> None:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        key, _ = storage.put_object(db, "test", "a.txt", b"rolled back")
        assert (settings.storage_dir / key).exists()
        db.rollback()
    assert not (settings.storage_dir / key).exists()
    with SessionLocal() as db:
        key, _ = storage.put_object(db, "test", "b.txt", b"kept")
        db.commit()
    assert (settings.storage_dir / key).exists()


def test_dates_follow_the_configured_timezone() -> None:
    late_evening_utc = datetime(2026, 11, 20, 23, 30, tzinfo=UTC)
    assert local_date(late_evening_utc) == date(2026, 11, 21)
    assert 0 < seconds_until(datetime.now(settings.tz).time()) <= 86400


def test_lease_lets_one_process_run_a_job() -> None:
    ttl = timedelta(minutes=5)
    assert leases.claim("test-job", ttl, holder="a")
    assert not leases.claim("test-job", ttl, holder="b")
    assert leases.claim("test-job", ttl, holder="a")
    assert not leases.claim("test-job", ttl, holder="a", renew=False)


def test_bad_model_answers_are_not_kept() -> None:
    messages = [{"role": "user", "content": "test-cache"}]
    key = llm.request_key(messages, "json")
    llm._store(key, "{not json")
    assert llm._stored(key, "json") is None
    with SessionLocal() as db:
        assert db.get(LlmAnswer, key) is None
        db.add(LlmAnswer(key=key, model="m", content=json.dumps({"a": 1}),
                         created_at=datetime.now(UTC) - timedelta(days=settings.llm_cache_days + 1)))
        db.commit()
    assert llm._stored(key, "json") is None
    llm._store(key, json.dumps({"a": 2}))
    assert llm._stored(key, "json") == json.dumps({"a": 2})
    llm.forget(messages, "json")
    assert llm._stored(key, "json") is None


def test_personal_token_expires(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    unit = client.get("/api/auth/me", headers=H["ex-fin"]).json()["orgUnitId"]
    made = client.post("/api/admin/users", headers=H["admin"],
                       json={"displayName": "Виконавець зі строком", "role": "EXECUTOR", "orgUnitId": unit}).json()
    assert made["tokenExpiresAt"] is not None
    login = client.post("/api/auth/login", json={"token": made["token"]}).json()
    expires_at = datetime.fromisoformat(made["tokenExpiresAt"]).timestamp()
    assert login["expiresAt"] <= expires_at
    with SessionLocal() as db:
        db.get(User, uuid.UUID(made["id"])).token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/auth/login", json={"token": made["token"]}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {made['token']}"}).status_code == 401
    session = {"Authorization": f"Bearer {login['sessionToken']}"}
    assert client.get("/api/auth/me", headers=session).status_code == 401
    assert client.get("/api/auth/me", headers=H["coord"]).status_code == 200


def test_risk_bound_to_a_program_is_not_usable_elsewhere(client: TestClient, program: dict) -> None:
    section = next(s for s in program["sections"] if s["number"] == 2)
    own = client.post("/api/risks", headers=H["coord"], json={
        "code": "R-OWN-1", "description": "Ризик цієї програми", "level": "LOW", "programId": program["id"]})
    assert own.status_code == 201 and own.json()["programId"] == program["id"]
    with SessionLocal() as db:
        other = Program(org_unit_id=uuid.UUID(client.get("/api/auth/me", headers=H["coord"]).json()["orgUnitId"]),
                        title="Інша програма", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31))
        db.add(other)
        db.commit()
        other_id = str(other.id)
    foreign = client.post("/api/risks", headers=H["coord"], json={
        "code": "R-OTHER-1", "description": "Ризик іншої програми", "level": "LOW", "programId": other_id})
    assert foreign.status_code == 201
    body = {"sectionId": section["id"], "code": "2.85", "title": "Захід з ризиком іншої програми",
            "plannedDeadline": "2026-12-31", "riskId": foreign.json()["id"]}
    r = client.post("/api/measures", headers=H["coord"], json=body)
    assert r.status_code == 422 and "іншій програмі" in r.text
    body["riskId"] = own.json()["id"]
    assert client.post("/api/measures", headers=H["coord"], json=body).status_code == 201


def test_sweep_removes_only_old_unreferenced_files(client: TestClient) -> None:
    with SessionLocal() as db:
        kept_key = db.scalars(select(Evidence.object_key).limit(1)).one()
    orphan = settings.storage_dir / "orphans" / "lost.pdf"
    fresh = settings.storage_dir / "orphans" / "fresh.pdf"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"lost")
    fresh.write_bytes(b"in flight")
    old = time.time() - 7200
    os.utime(orphan, (old, old))
    os.utime(settings.storage_dir / kept_key, (old, old))
    with SessionLocal() as db:
        assert storage.sweep_orphans(db) >= 1
    assert not orphan.exists() and fresh.exists() and (settings.storage_dir / kept_key).exists()


# Модель даних за словником набору (datasets/zavdannia-2/dictionary.md): індикатор виконання заходу ≠ індикатор
# ризику; документ має тип і дату; перенесення строку — внутрішнє рішення координатора; реєстр ризиків з KRI.


def test_execution_indicator_is_the_measure_own_and_its_fact_is_required(client: TestClient, program: dict) -> None:
    risk = next(r for r in client.get("/api/risks", headers=H["coord"]).json() if r["indicators"])
    m = _measure(client, program, "2.91", isPermanent=True, riskId=risk["id"],
                 indicatorText="Частка перевірених договорів", indicatorUnit="%", indicatorTarget=100)
    assert m["indicatorText"] == "Частка перевірених договорів"
    assert float(m["indicator"]["target"]) == 100 and m["indicator"]["riskId"] is None  # не індикатор ризику
    assert m["indicator"]["id"] not in {i["id"] for i in risk["indicators"]}

    url = f"/api/measures/{m['id']}/submit"
    text = {"resultDescription": "Перевірено 80 % договорів, акт № 4 від 02.11.2026"}
    file = [("files", ("akt.pdf", b"%PDF akt", "application/pdf"))]
    no_fact = client.post(url, headers=H["ex-fin"], data={**text, **META}, files=file)
    assert no_fact.status_code == 422 and "фактичне значення" in no_fact.json()["detail"]
    no_meta = client.post(url, headers=H["ex-fin"], data={**text, "indicatorValue": "80"}, files=file)
    assert no_meta.status_code == 422 and "тип документа і дату" in no_meta.json()["detail"]
    future = client.post(url, headers=H["ex-fin"], files=file,
                         data={**text, "indicatorValue": "80", "documentTypes": "акт", "documentDates": "2099-01-01"})
    assert future.status_code == 422

    ok = client.post(url, headers=H["ex-fin"], data={**text, **META, "indicatorValue": "80"}, files=file)
    assert ok.status_code == 200, ok.text
    detail = ok.json()["measure"]
    assert float(detail["indicator"]["current"]) == 80
    assert detail["evidence"][0]["docType"] == "акт" and detail["evidence"][0]["documentDate"] == "2026-11-02"

    assert client.post(f"/api/measures/{m['id']}/approve", headers=H["coord"], json={"comment": "Ок"}).status_code == 200
    missed = [f for f in client.get("/api/flags?type=TARGET_MISSED", headers=H["coord"]).json()
              if f["measureCode"] == "2.91"]
    assert missed and missed[0]["ruleCode"] == "R5" and missed[0]["facts"]["fact"] == 80


def test_only_the_coordinator_postpones_and_the_programme_deadline_stays(client: TestClient, program: dict) -> None:
    m = _measure(client, program, "2.92")
    url = f"/api/measures/{m['id']}/deadline-changes"
    body = {"newDeadline": "2026-12-15", "reason": "Постачальник переніс строк поставки"}
    assert client.post(url, headers=H["head"], json=body).status_code == 403
    assert client.post(url, headers=H["ex-fin"], json=body).status_code == 403
    assert client.post(url, headers=H["coord"], json={**body, "reason": "коротко"}).status_code == 422
    assert client.post(url, headers=H["coord"], json={**body, "newDeadline": "2031-01-01"}).status_code == 422

    once = client.post(url, headers=H["coord"], json=body)
    assert once.status_code == 201, once.text
    d = once.json()
    assert d["plannedDeadline"] == "2026-12-31" and d["internalDeadline"] == "2026-12-15"  # програма не змінюється
    assert [(c["oldDeadline"], c["newDeadline"]) for c in d["deadlineChanges"]] == [("2026-12-31", "2026-12-15")]
    assert client.post(url, headers=H["coord"], json=body).status_code == 422  # той самий строк

    twice = client.post(url, headers=H["coord"], json={**body, "newDeadline": "2026-12-20",
                                                       "reason": "Постачальник повторно переніс строк"}).json()
    assert len(twice["deadlineChanges"]) == 2
    flags = [f for f in twice["flags"] if f["type"] == "REPEATED_POSTPONEMENT"]
    assert flags and flags[0]["ruleCode"] == "R6a" and flags[0]["facts"]["postponements"] == 2

    permanent = _measure(client, program, "2.93", isPermanent=True)
    assert client.post(f"/api/measures/{permanent['id']}/deadline-changes", headers=H["coord"],
                       json=body).status_code == 422


def test_risk_register_entry_with_working_group_scores_and_kri(client: TestClient) -> None:
    owner = client.get("/api/admin/org-units", headers=H["coord"]).json()[0]
    body = {"code": "КР-R1", "description": "Завищення обсягів ремонтних робіт", "probability": 3, "impact": 3,
            "process": "Капітальне будівництво", "content": "Підписання актів на невиконані роботи",
            "sources": "Відсутність звірки з дефектними відомостями", "existingControls": "Комісія приймання",
            "ownerUnitId": owner["id"],
            "indicator": {"name": "Частка актів, звірених з дефектними відомостями", "unit": "%", "baseline": 10,
                          "target": 80, "targetDate": "2026-12-31", "source": "акти приймання"}}
    assert client.post("/api/risks", headers=H["head"], json=body).status_code == 403
    flat = client.post("/api/risks", headers=H["coord"],
                       json={**body, "code": "КР-R2", "indicator": {**body["indicator"], "target": 10}})
    assert flat.status_code == 422  # ціль KRI дорівнює базі
    r = client.post("/api/risks", headers=H["coord"], json=body)
    assert r.status_code == 201, r.text
    risk = r.json()
    assert risk["level"] == "HIGH" and risk["score"] == 9  # рівень — з балу 3·3
    assert risk["process"] == "Капітальне будівництво" and risk["ownerUnitName"] == owner["name"]
    assert [i["name"] for i in risk["indicators"]] == ["Частка актів, звірених з дефектними відомостями"]
    assert risk["measureCount"] == 0
    assert client.post("/api/risks", headers=H["coord"], json=body).status_code == 409  # код унікальний


def test_late_approval_keeps_the_executor_submission_date(client: TestClient, program: dict,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """Затримка перевірки — не запізнення виконавця: фактичний строк = дата подання, R7a не спрацьовує."""
    from app.routers import measures as routes

    m = _measure(client, program, "2.94")
    r = client.post(f"/api/measures/{m['id']}/submit", headers=H["ex-fin"],
                    files=[("files", ("akt.pdf", b"%PDF", "application/pdf"))],
                    data={"resultDescription": "Перевірено 12 договорів, акт № 9 від 02.11.2026", **META})
    assert r.status_code == 200, r.text
    submitted = r.json()["measure"]["updates"][-1]["createdAt"][:10]

    monkeypatch.setattr(routes, "today", lambda: date(2027, 1, 12))  # координатор погоджує вже в наступному півріччі
    done = client.post(f"/api/measures/{m['id']}/approve", headers=H["coord"], json={"comment": "Ок"})
    assert done.status_code == 200, done.text
    period = next(p for p in done.json()["periods"] if p["status"] == "DONE")
    assert period["actualDate"] == submitted  # не 12.01.2027
    assert not [f for f in done.json()["flags"] if f["type"] == "DATE_OUT_OF_PERIOD"]
