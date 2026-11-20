import pytest
from fastapi.testclient import TestClient

from app import auth
from app.config import settings
from app.main import app

ADMIN = {"Authorization": "Bearer demo-admin"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_no_builtin_secrets_by_default():
    fields = type(settings).model_fields
    assert fields["admin_grant_hash"].default == ""
    assert fields["demo_token_secret"].default == ""
    assert fields["demo_public_tokens"].default is False
    assert fields["demo_login"].default is False


def test_demo_tokens_come_from_the_secret(monkeypatch):
    monkeypatch.setattr(settings, "demo_public_tokens", False)
    monkeypatch.setattr(settings, "demo_token_secret", "")
    with pytest.raises(RuntimeError, match="DEMO_TOKEN_SECRET"):
        auth.demo_token("coord")
    monkeypatch.setattr(settings, "demo_token_secret", "one")
    a = auth.demo_token("coord")
    monkeypatch.setattr(settings, "demo_token_secret", "two")
    b = auth.demo_token("coord")
    assert a.startswith("demo-coord-") and b.startswith("demo-coord-") and a != b


def test_test_only_public_tokens_win_over_a_local_secret(monkeypatch):
    monkeypatch.setattr(settings, "demo_token_secret", "from-local-env")
    monkeypatch.setattr(settings, "demo_public_tokens", True)
    assert auth.demo_token("coord") == "demo-coord"


def test_demo_accounts_listed_only_when_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_login", False)
    assert client.get("/api/auth/demo-accounts").json() == []
    monkeypatch.setattr(settings, "demo_login", True)
    accounts = client.get("/api/auth/demo-accounts").json()
    assert {a["role"] for a in accounts} == {"COORDINATOR", "HEAD", "ANALYST", "ADMIN", "EXECUTOR"}
    coord = next(a for a in accounts if a["role"] == "COORDINATOR")
    assert client.post("/api/auth/login", json={"token": coord["token"]}).status_code == 200


def test_granting_admin_is_off_without_a_configured_hash(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_grant_hash", "")
    unit = client.get("/api/admin/org-units", headers=ADMIN).json()[0]["id"]
    r = client.post("/api/admin/users", headers=ADMIN, json={
        "displayName": "Новий адмін", "role": "ADMIN", "orgUnitId": unit, "adminPassword": "anything"})
    assert r.status_code == 403 and "ADMIN_GRANT_HASH" in r.text
