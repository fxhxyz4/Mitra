import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


DEMO_TOKENS = {
    "Координатор програми": "demo-coord",
    "Керівник органу": "demo-head",
    "Аналітик": "demo-analyst",
    "Адміністратор системи": "demo-admin",
    "Виконавець — закупівлі": "demo-ex-proc",
    "Виконавець — персонал": "demo-ex-hr",
    "Виконавець — фінанси": "demo-ex-fin",
    "Виконавець — комунікації": "demo-ex-com",
}


@pytest.fixture(scope="module")
def users(client):
    """displayName → user id, resolved by logging in with each demo token."""
    out = {}
    for name, token in DEMO_TOKENS.items():
        r = client.post("/api/auth/login", json={"token": token})
        assert r.status_code == 200 and r.json()["displayName"] == name
        out[name] = r.json()["id"]
    return out


def as_(users, name):
    return {"Authorization": f"Bearer {DEMO_TOKENS[name]}"}


def test_passport_and_flags(client, users):
    programs = client.get("/api/programs", headers=as_(users, "Координатор програми")).json()
    assert len(programs) == 1 and programs[0]["status"] == "APPROVED"
    pp = client.get(f"/api/programs/{programs[0]['id']}/passport", headers=as_(users, "Координатор програми")).json()
    assert [s["number"] for s in pp["sections"]] == [1, 2, 3]
    assert pp["totals"]["measures"] == 22

    flags = client.get("/api/flags", headers=as_(users, "Координатор програми")).json()
    types = {f["type"] for f in flags}
    assert {"OVERDUE", "NO_EVIDENCE", "FORMAL_CLOSURE", "VAGUE_RESULT", "REPEATED_DELAY"} <= types
    # R5: індикатор виконання заходу нижче цілі (навчання: 180 з 300 осіб)
    missed = [f for f in flags if f["type"] == "TARGET_MISSED"]
    assert missed and all(f["ruleCode"] == "R5" and f["facts"]["fact"] < f["facts"]["target"] for f in missed)
    assert all(f["explanation"] and f["ruleCode"] for f in flags)


def test_full_cycle(client, users):
    ex = as_(users, "Виконавець — персонал")
    coord = as_(users, "Координатор програми")
    mine = client.get("/api/measures?mine=true", headers=ex).json()
    m = next(x for x in mine if x["code"] == "2.5")

    # vague text without evidence → blocked with hints
    r = client.post(f"/api/measures/{m['id']}/submit", headers=ex, data={"resultDescription": "Оприлюднено"})
    assert r.status_code == 422

    r = client.post(
        f"/api/measures/{m['id']}/submit", headers=ex,
        data={"resultDescription": "Оприлюднено 12 рішень у реєстрі https://example.org/registry",
              "documentTypes": "рішення", "documentDates": "2026-06-15"},
        files=[("files", ("рішення.pdf", b"%PDF demo", "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["measure"]["status"] == "ON_REVIEW"
    assert body["measure"]["evidence"][0]["sha256"]

    # executor cannot edit while on review
    assert client.post(f"/api/measures/{m['id']}/submit", headers=ex, data={"resultDescription": "x 1"}).status_code == 409

    queue = client.get("/api/dashboard/coordinator", headers=coord).json()["reviewQueue"]
    assert any(q["id"] == m["id"] for q in queue)

    r = client.post(f"/api/measures/{m['id']}/approve", headers=coord,
                    json={"comment": "Ок", "indicatorValue": {"value": 55, "measuredAt": "2026-01-01"}})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "DONE"

    # evidence download keeps integrity, no DELETE route
    ev = r.json()["evidence"][0]
    dl = client.get(f"/api/measures/{m['id']}/evidence/{ev['id']}/download", headers=ex)
    assert dl.status_code == 200 and dl.content == b"%PDF demo"
    assert client.delete(f"/api/measures/{m['id']}/evidence/{ev['id']}", headers=ex).status_code in (404, 405)

    assert client.get(f"/api/measures/{m['id']}/history", headers=coord).status_code == 403
    hist = client.get(f"/api/measures/{m['id']}/history", headers=as_(users, "Адміністратор системи")).json()
    assert any(h["action"] == "submit" for h in hist)


def test_formal_closure_only_head(client, users):
    coord, head = as_(users, "Координатор програми"), as_(users, "Керівник органу")
    f = next(x for x in client.get("/api/flags?type=FORMAL_CLOSURE", headers=coord).json())
    assert client.post(f"/api/flags/{f['id']}/resolve", headers=coord, json={"comment": "знято"}).status_code == 403
    assert client.post(f"/api/flags/{f['id']}/resolve", headers=head, json={"comment": "перевірено"}).status_code == 200


def test_recommendations_and_dashboards(client, users):
    head = as_(users, "Керівник органу")
    ex = client.get("/api/dashboard/executive", headers=head).json()
    assert ex["overall"]["total"] == 22 and ex["units"] and ex["risks"]
    assert [u["name"] for u in ex["units"]] == sorted(u["name"] for u in ex["units"])
    rec = ex["recommendations"][0]
    assert rec["basis"]["rule"] and rec["basis"]["facts"]
    r = client.post(f"/api/recommendations/{rec['id']}/accept", headers=head,
                    json={"responsibleId": users["Координатор програми"], "dueDate": "2026-12-20"})
    assert r.status_code == 200 and r.json()["status"] == "ACCEPTED"

    exd = client.get("/api/dashboard/executor", headers=as_(users, "Виконавець — фінанси")).json()
    assert exd["overdue"] and exd["returned"]


def test_reports_and_audit(client, users):
    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    from app.config import today
    from app import halfyear

    period = halfyear.of(today())
    rep = client.post("/api/reports/generate", headers=coord, json={"programId": pid, "period": period}).json()
    nazk = client.get(f"/api/reports/{rep['id']}/nazk", headers=coord).json()
    assert len(nazk["sections"]) == 3
    row = nazk["sections"][0]["measures"][0]
    assert {"actualDeadline", "state", "resultOrReason"} <= row.keys()
    assert client.get(f"/api/reports/{rep['id']}/nazk?format=csv", headers=coord).status_code == 200
    assert "<table>" in client.get(f"/api/reports/{rep['id']}/print", headers=coord).text

    assert client.get("/api/audit/verify", headers=coord).status_code == 403
    v = client.get("/api/audit/verify", headers=as_(users, "Адміністратор системи")).json()
    assert v["ok"] and v["checked"] > 50


def test_rbac(client, users):
    ex = as_(users, "Виконавець — закупівлі")
    assert client.post("/api/programs", headers=ex, json={}).status_code in (403, 422)
    assert client.get("/api/admin/users", headers=ex).status_code == 403
    other = [m for m in client.get("/api/measures", headers=as_(users, "Координатор програми")).json()
             if m["responsibleUnit"] == "Управління персоналу"][0]
    assert client.get(f"/api/measures/{other['id']}", headers=ex).status_code == 403


def test_auth(client, users):
    assert client.get("/api/programs").status_code == 401
    assert client.get("/api/programs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"token": "wrong"}).status_code == 401
    assert client.get("/api/auth/me", headers=as_(users, "Аналітик")).json()["role"] == "ANALYST"

    admin = as_(users, "Адміністратор системи")
    unit = client.get("/api/admin/org-units", headers=admin).json()[0]["id"]
    new = client.post("/api/admin/users", headers=admin,
                      json={"displayName": "Новий виконавець", "role": "EXECUTOR", "orgUnitId": unit}).json()
    tok = {"Authorization": f"Bearer {new['token']}"}
    assert client.get("/api/auth/me", headers=tok).json()["id"] == new["id"]
    again = client.post(f"/api/admin/users/{new['id']}/token", headers=admin).json()
    assert client.get("/api/auth/me", headers=tok).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {again['token']}"}).status_code == 200
    assert "token" not in client.get("/api/admin/users", headers=admin).json()[0]


def test_admin_deletes_user(client, users):
    admin = as_(users, "Адміністратор системи")
    me = client.get("/api/auth/me", headers=admin).json()
    unit = client.get("/api/admin/org-units", headers=admin).json()[0]["id"]
    new = client.post("/api/admin/users", headers=admin,
                      json={"displayName": "Тимчасовий", "role": "EXECUTOR", "orgUnitId": unit}).json()
    tok = {"Authorization": f"Bearer {new['token']}"}
    url = f"/api/admin/users/{new['id']}"

    assert client.delete(url, headers=as_(users, "Координатор програми")).status_code == 403
    assert client.delete(f"/api/admin/users/{me['id']}", headers=admin).status_code == 409  # not yourself
    assert client.delete(url, headers=admin).status_code == 204
    assert client.get("/api/auth/me", headers=tok).status_code == 401  # token no longer works
    assert new["id"] not in {u["id"] for u in client.get("/api/admin/users", headers=admin).json()}
    assert client.delete(url, headers=admin).status_code == 404
    assert client.post(f"{url}/token", headers=admin).status_code == 404  # cannot be revived by a new token
    log = client.get(f"/api/audit?entityId={new['id']}", headers=admin).json()
    assert log[0]["action"] == "delete" and client.get("/api/audit/verify", headers=admin).json()["ok"]


def test_admin_keeps_own_role(client, users):
    admin = as_(users, "Адміністратор системи")
    me = client.get("/api/auth/me", headers=admin).json()
    url = f"/api/admin/users/{me['id']}"
    assert client.patch(url, headers=admin, json={"role": "COORDINATOR"}).status_code == 409
    assert client.get("/api/auth/me", headers=admin).json()["role"] == "ADMIN"
    assert client.patch(url, headers=admin, json={"role": "ADMIN", "displayName": me["displayName"]}).status_code == 200


def test_admin_grant_requires_secret(client, users, monkeypatch):
    from app import auth

    monkeypatch.setattr(settings, "admin_grant_hash", auth.hash_secret("test-secret", iterations=1000))
    admin = as_(users, "Адміністратор системи")
    unit = client.get("/api/admin/org-units", headers=admin).json()[0]["id"]
    body = {"displayName": "Другий адмін", "role": "ADMIN", "orgUnitId": unit}
    assert client.post("/api/admin/users", headers=admin, json=body).status_code == 403
    assert client.post("/api/admin/users", headers=admin, json={**body, "adminPassword": "wrong"}).status_code == 403
    new = client.post("/api/admin/users", headers=admin, json={**body, "adminPassword": "test-secret"})
    assert new.status_code == 201 and new.json()["role"] == "ADMIN"

    ex = client.post("/api/admin/users", headers=admin,
                     json={"displayName": "Майбутній адмін", "role": "EXECUTOR", "orgUnitId": unit}).json()
    url = f"/api/admin/users/{ex['id']}"
    assert client.patch(url, headers=admin, json={"role": "ADMIN"}).status_code == 403
    assert client.patch(url, headers=admin, json={"role": "ADMIN", "adminPassword": "nope"}).status_code == 403
    assert client.patch(url, headers=admin, json={"role": "COORDINATOR"}).status_code == 200  # other roles — no secret
    r = client.patch(url, headers=admin, json={"role": "ADMIN", "adminPassword": "test-secret"})
    assert r.status_code == 200 and r.json()["role"] == "ADMIN"
    log = client.get(f"/api/audit?entityId={ex['id']}", headers=admin).json()
    assert "test-secret" not in str(log)  # the secret never lands in the audit log

    unit_name = client.get("/api/admin/org-units", headers=admin).json()[0]["name"]
    imp = {"users": [{"displayName": "Імпортований адмін", "role": "ADMIN", "orgUnit": unit_name}]}
    r = client.post("/api/admin/import", headers=admin, json=imp)
    assert r.status_code == 422

    # another admin's token: only with the secret, otherwise one admin could sign in as another
    token_url = f"/api/admin/users/{new.json()['id']}/token"
    assert client.post(token_url, headers=admin).status_code == 403
    assert client.post(token_url, headers={**admin, "X-Admin-Password": "test-secret"}).status_code == 200
    # import must not demote or re-token an existing admin either
    demote = {"users": [{"displayName": "Другий адмін", "role": "ANALYST", "orgUnit": unit_name, "token": "x" * 20}]}
    assert client.post("/api/admin/import", headers=admin, json=demote).status_code == 422


def test_admin_revoke_requires_secret(client, users, monkeypatch):
    from app import auth

    monkeypatch.setattr(settings, "admin_grant_hash", auth.hash_secret("test-secret", iterations=1000))
    admin = as_(users, "Адміністратор системи")
    unit = client.get("/api/admin/org-units", headers=admin).json()[0]["id"]
    body = {"role": "ADMIN", "orgUnitId": unit, "adminPassword": "test-secret"}
    other = client.post("/api/admin/users", headers=admin, json={**body, "displayName": "Адмін на зняття"}).json()
    url = f"/api/admin/users/{other['id']}"
    assert client.patch(url, headers=admin, json={"role": "ANALYST"}).status_code == 403
    assert client.patch(url, headers=admin, json={"role": "ANALYST", "adminPassword": "nope"}).status_code == 403
    assert client.patch(url, headers=admin, json={"displayName": "Адмін (перейменований)"}).status_code == 200
    r = client.patch(url, headers=admin, json={"role": "ANALYST", "adminPassword": "test-secret"})
    assert r.status_code == 200 and r.json()["role"] == "ANALYST"

    gone = client.post("/api/admin/users", headers=admin, json={**body, "displayName": "Адмін на видалення"}).json()
    url = f"/api/admin/users/{gone['id']}"
    assert client.delete(url, headers=admin).status_code == 403
    assert client.delete(url, headers={**admin, "X-Admin-Password": "nope"}).status_code == 403
    assert client.delete(url, headers={**admin, "X-Admin-Password": "test-secret"}).status_code == 204


def _docx_text(data: bytes) -> str:
    import io

    from docx import Document

    doc = Document(io.BytesIO(data))
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    return "\n".join([p.text for p in doc.paragraphs] + cells)


def _pdf_text(data: bytes) -> str:
    import io

    from pypdf import PdfReader

    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


def test_report_signature_and_public_verify(client, users):
    import uuid
    from urllib.parse import parse_qs, urlparse

    from app import halfyear
    from app.config import today
    from app.db import SessionLocal
    from app.models import Report

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    rep = client.post("/api/reports/generate", headers=coord,
                      json={"programId": pid, "period": halfyear.of(today()), "type": "PRINT"}).json()
    info = client.get(f"/api/reports/{rep['id']}/integrity", headers=coord).json()
    assert info["qrSvg"].startswith("<svg") and len(info["sha256"]) == 64
    # Shown as <img src="data:...">: without the SVG namespace a browser renders a broken image.
    assert 'xmlns="http://www.w3.org/2000/svg"' in info["qrSvg"] and "viewBox=" in info["qrSvg"]
    q = parse_qs(urlparse(info["verifyUrl"]).query)
    assert q["id"] == [rep["id"]] and q["h"] == [info["sha256"]] and q["sig"] == [info["signature"]]
    printed = client.get(f"/api/reports/{rep['id']}/print", headers=coord).text
    assert "<svg" in printed and "/verify?" not in printed and info["sha256"] in printed
    docx = client.get(f"/api/reports/{rep['id']}/export?format=docx", headers=coord)
    assert docx.status_code == 200 and "/verify?" not in _docx_text(docx.content)
    pdf = client.get(f"/api/reports/{rep['id']}/export?format=pdf", headers=coord)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    text = _pdf_text(pdf.content)
    assert "Звіт про виконання антикорупційної програми" in text and info["sha256"] in text and "/verify?" not in text

    ok = client.get(f"/api/reports/{rep['id']}/verify", params={"h": info["sha256"], "sig": info["signature"]}).json()
    assert ok["valid"] and ok["generatedBy"] == "Координатор програми" and ok["programTitle"]

    bad_sig = client.get(f"/api/reports/{rep['id']}/verify", params={"h": info["sha256"], "sig": "x" * 43}).json()
    assert not bad_sig["valid"] and bad_sig["programTitle"] is None
    assert not client.get("/api/reports/not-a-uuid/verify", params={"h": "a", "sig": "b"}).json()["valid"]

    with SessionLocal() as db:
        r = db.get(Report, uuid.UUID(rep["id"]))
        r.data = {**r.data, "orgUnit": "Підроблений орган"}
        db.commit()
    tampered = client.get(f"/api/reports/{rep['id']}/verify", params={"h": info["sha256"], "sig": info["signature"]}).json()
    assert not tampered["valid"] and "змінено" in tampered["reason"]


def test_public_verify_detects_swapped_report_file(client, users):
    import os
    import stat
    import uuid

    from app import halfyear
    from app.config import settings, today
    from app.db import SessionLocal
    from app.models import Report

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    rep = client.post("/api/reports/generate", headers=coord,
                      json={"programId": pid, "period": halfyear.of(today()), "type": "PRINT"}).json()
    info = client.get(f"/api/reports/{rep['id']}/integrity", headers=coord).json()
    params = {"h": info["sha256"], "sig": info["signature"]}
    assert client.get(f"/api/reports/{rep['id']}/verify", params=params).json()["valid"]

    with SessionLocal() as db:
        path = settings.storage_dir / db.get(Report, uuid.UUID(rep["id"])).file_key
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    path.write_bytes(path.read_bytes().replace("Виконано".encode(), "Підмінено".encode(), 1) + b" ")
    swapped = client.get(f"/api/reports/{rep['id']}/verify", params=params).json()
    assert not swapped["valid"] and "Файл звіту змінено" in swapped["reason"] and swapped["sha256"] is None

    path.unlink()
    assert not client.get(f"/api/reports/{rep['id']}/verify", params=params).json()["valid"]


def test_downloaded_copy_matches_original_by_hash(client, users):
    import hashlib

    from app import halfyear
    from app.config import today

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    gen = lambda t: client.post("/api/reports/generate", headers=coord,  # noqa: E731
                                json={"programId": pid, "period": halfyear.of(today()), "type": t}).json()["id"]
    rid, other = gen("NAZK"), gen("INTERNAL")
    urls = {"pdf": f"/api/reports/{rid}/export?format=pdf", "docx": f"/api/reports/{rid}/export?format=docx",
            "xlsx": f"/api/reports/{rid}/export?format=xlsx", "csv": f"/api/reports/{rid}/nazk?format=csv",
            "json": f"/api/reports/{rid}/nazk?format=json", "html": f"/api/reports/{rid}/print"}
    check = lambda sha, **kw: client.get("/api/reports/copies/check", params={"sha256": sha, **kw}).json()  # noqa: E731

    for fmt, url in urls.items():
        first, second = client.get(url, headers=coord).content, client.get(url, headers=coord).content
        assert first == second, fmt
        ok = check(hashlib.sha256(first).hexdigest().upper(), id=rid)
        assert ok["match"] and ok["format"] == fmt and ok["reportId"] == rid and ok["programTitle"], fmt

    pdf = client.get(urls["pdf"], headers=coord).content
    assert not check(hashlib.sha256(pdf + b" ").hexdigest())["match"]
    assert not check(hashlib.sha256(pdf).hexdigest(), id=other)["match"]
    assert not check(hashlib.sha256(pdf).hexdigest(), id="not-a-uuid")["match"]
    assert check(hashlib.sha256(pdf).hexdigest())["reportId"] == rid
    assert client.get(f"/api/reports/{rid}/nazk", headers=coord).json()["programTitle"]


def test_legacy_report_gets_copies_on_sign_and_swapped_copy_is_refused(client, users):
    import hashlib
    import os
    import stat
    import uuid

    from sqlalchemy import delete, select

    from app import halfyear
    from app.config import settings, today
    from app.db import SessionLocal
    from app.models import ReportFile

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    rid = client.post("/api/reports/generate", headers=coord,
                      json={"programId": pid, "period": halfyear.of(today()), "type": "NAZK"}).json()["id"]
    with SessionLocal() as db:
        db.execute(delete(ReportFile).where(ReportFile.report_id == uuid.UUID(rid)))
        db.commit()
    url = f"/api/reports/{rid}/export?format=xlsx"
    check = lambda: client.get("/api/reports/copies/check",  # noqa: E731
                               params={"sha256": hashlib.sha256(client.get(url, headers=coord).content).hexdigest()}).json()
    assert client.get(url, headers=coord).status_code == 200

    assert client.post(f"/api/reports/{rid}/sign", headers=coord).status_code == 200
    assert check()["match"]

    with SessionLocal() as db:
        assert len(db.scalars(select(ReportFile).where(ReportFile.report_id == uuid.UUID(rid))).all()) == 6
        key = db.scalar(select(ReportFile.file_key).where(ReportFile.report_id == uuid.UUID(rid), ReportFile.format == "xlsx"))
    path = settings.storage_dir / key
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    path.write_bytes(path.read_bytes() + b" ")
    assert client.get(url, headers=coord).status_code == 409


def _rebuild_audit_chain(db) -> None:
    """What an attacker with database write access does after editing a row: re-hash the whole chain."""
    from sqlalchemy import select

    from app import audit
    from app.models import AuditLogEntry

    prev = audit.GENESIS
    for e in db.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id)):
        e.prev_hash = prev
        e.hash = audit._digest(e)
        prev = e.hash
    db.flush()
    assert audit.verify_chain(db)[0]


def test_file_hashes_are_signed_so_a_rewritten_audit_log_cannot_bless_a_swapped_file(client, users):
    import hashlib
    import os
    import stat
    import uuid

    from sqlalchemy import select

    from app import halfyear
    from app.config import today
    from app.db import SessionLocal
    from app.models import AuditLogEntry, Report, ReportFile

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    rid = client.post("/api/reports/generate", headers=coord,
                      json={"programId": pid, "period": halfyear.of(today()), "type": "PRINT"}).json()["id"]
    info = client.get(f"/api/reports/{rid}/integrity", headers=coord).json()
    params = {"h": info["sha256"], "sig": info["signature"]}
    assert client.get(f"/api/reports/{rid}/verify", params=params).json()["valid"]
    xlsx = client.get(f"/api/reports/{rid}/export?format=xlsx", headers=coord).content
    copy_check = lambda data: client.get("/api/reports/copies/check",  # noqa: E731
                                         params={"sha256": hashlib.sha256(data).hexdigest(), "id": rid}).json()
    assert copy_check(xlsx)["match"]

    def rewrite(action: str, change) -> None:
        with SessionLocal() as db:
            e = db.scalars(select(AuditLogEntry).where(AuditLogEntry.entity_id == uuid.UUID(rid),
                                                       AuditLogEntry.action == action)).first()
            e.new_value = change(dict(e.new_value))
            _rebuild_audit_chain(db)
            db.commit()

    # 1. The stored report file is swapped and its hash in the audit log rewritten to match.
    with SessionLocal() as db:
        path = settings.storage_dir / db.get(Report, uuid.UUID(rid)).file_key
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    forged = path.read_bytes().replace("Виконано".encode(), "Підмінено".encode(), 1)
    path.write_bytes(forged)
    rewrite("generate", lambda v: {**v, "sha256": hashlib.sha256(forged).hexdigest()})
    swapped = client.get(f"/api/reports/{rid}/verify", params=params).json()
    assert not swapped["valid"] and "Файл звіту змінено" in swapped["reason"]

    # 2. A forged copy is registered in the audit log: with the old signature, without one, or after a downgrade.
    fake = xlsx + b" "
    fake_sha = hashlib.sha256(fake).hexdigest()
    rewrite("issue_copies", lambda v: {**v, "copies": {**v["copies"], "xlsx": fake_sha}})
    assert not copy_check(fake)["match"]
    rewrite("issue_copies", lambda v: {"copies": v["copies"]})
    assert not copy_check(fake)["match"]
    with SessionLocal() as db:
        r = db.get(Report, uuid.UUID(rid))
        r.data = {**r.data, "_integrity": {**r.data["_integrity"], "version": 1}}
        db.commit()
    assert not copy_check(fake)["match"]
    assert not client.get(f"/api/reports/{rid}/verify", params=params).json()["valid"]
    with SessionLocal() as db:
        assert db.scalar(select(ReportFile.sha256).where(ReportFile.report_id == uuid.UUID(rid),
                                                         ReportFile.format == "xlsx")) == hashlib.sha256(xlsx).hexdigest()


def test_reports_signed_before_file_signatures_still_verify(client, users):
    import hashlib
    import uuid

    from sqlalchemy import select

    from app import halfyear
    from app.config import today
    from app.db import SessionLocal
    from app.models import AuditLogEntry, Report
    from app.services import integrity

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    rid = client.post("/api/reports/generate", headers=coord,
                      json={"programId": pid, "period": halfyear.of(today()), "type": "NAZK"}).json()["id"]
    xlsx = client.get(f"/api/reports/{rid}/export?format=xlsx", headers=coord).content
    with SessionLocal() as db:  # what a v1 report looks like: v1 signature, no file signatures anywhere
        r = db.get(Report, uuid.UUID(rid))
        info = {k: v for k, v in r.data["_integrity"].items() if k != "version"}
        info["signature"] = integrity._signature(rid, info["sha256"], info["signedOn"])
        r.data = {**r.data, "_integrity": info}
        for e in db.scalars(select(AuditLogEntry).where(AuditLogEntry.entity_id == r.id)):
            e.new_value = {k: v for k, v in (e.new_value or {}).items() if k not in ("fileSignature", "signatures")}
        _rebuild_audit_chain(db)
        db.commit()
    ok = client.get(f"/api/reports/{rid}/verify", params={"h": info["sha256"], "sig": info["signature"]}).json()
    assert ok["valid"]
    assert client.get("/api/reports/copies/check",
                      params={"sha256": hashlib.sha256(xlsx).hexdigest(), "id": rid}).json()["match"]


def test_server_needs_a_report_secret(monkeypatch, tmp_path):
    from app.services import integrity

    monkeypatch.setattr(settings, "demo_public_tokens", False)
    monkeypatch.setattr(settings, "report_secret", "")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "evidence")
    assert "REPORT_SECRET" in (integrity.report_secret_problem() or "")
    (tmp_path / ".report-secret").write_text("old-volume-key")  # an older deployment keeps its printed QR codes
    assert integrity.report_secret_problem() is None


def test_verify_warns_about_a_newer_edition_and_shows_a_revoked_report(client, users):
    import hashlib

    from app import halfyear
    from app.config import today

    coord = as_(users, "Координатор програми")
    pid = client.get("/api/programs", headers=coord).json()[0]["id"]
    gen = lambda: client.post("/api/reports/generate", headers=coord,  # noqa: E731
                              json={"programId": pid, "period": halfyear.of(today()), "type": "PRINT"}).json()["id"]
    first, second = gen(), gen()

    def check(rid: str) -> dict:
        info = client.get(f"/api/reports/{rid}/integrity", headers=coord).json()
        return client.get(f"/api/reports/{rid}/verify", params={"h": info["sha256"], "sig": info["signature"]}).json()

    old = check(first)
    assert old["valid"] and old["supersededBy"] == second and old["supersededAt"]
    assert check(second)["supersededBy"] is None

    url = f"/api/reports/{second}/revoke"
    assert client.post(url, headers=as_(users, "Керівник органу"), json={"reason": "Помилка в розділі 2"}).status_code == 403
    assert client.post(url, headers=coord, json={"reason": "ні"}).status_code == 422
    revoked = client.post(url, headers=coord, json={"reason": "Помилка в розділі 2"}).json()
    assert revoked["revokedAt"] and revoked["revokeReason"] == "Помилка в розділі 2"
    assert client.post(url, headers=coord, json={"reason": "Помилка в розділі 2"}).status_code == 409

    gone = check(second)
    assert not gone["valid"] and "відкликано" in gone["reason"] and "Помилка в розділі 2" in gone["reason"]
    assert gone["revokedAt"] and gone["programTitle"]  # the reader still sees which report was withdrawn
    assert check(first)["supersededBy"] is None  # a revoked edition does not replace the earlier one

    xlsx = client.get(f"/api/reports/{second}/export?format=xlsx", headers=coord).content
    copy = client.get("/api/reports/copies/check", params={"sha256": hashlib.sha256(xlsx).hexdigest(), "id": second}).json()
    assert copy["match"] and "відкликано" in copy["reason"]
