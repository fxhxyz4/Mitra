import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

H = {k: {"Authorization": f"Bearer demo-{k}"} for k in ("coord", "head", "analyst", "admin", "ex-fin")}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _subtree(units: list[dict], root: str) -> set[str]:
    out, stack = set(), [root]
    while stack:
        uid = stack.pop()
        if uid not in out:
            out.add(uid)
            stack += [u["id"] for u in units if u.get("parentId") == uid]
    return out


@pytest.fixture(scope="module")
def unit_head(client):
    measures = client.get("/api/measures", headers=H["coord"]).json()
    org = client.get("/api/admin/org-units", headers=H["admin"]).json()
    me = client.get("/api/auth/me", headers=H["ex-fin"]).json()
    unit = me["orgUnitId"]
    created = client.post("/api/admin/users", headers=H["admin"], json={
        "displayName": "Керівник підрозділу (тест доступу)", "role": "HEAD", "orgUnitId": unit}).json()
    scope = _subtree(org, unit)
    details = {m["id"]: client.get(f"/api/measures/{m['id']}", headers=H["coord"]).json() for m in measures}
    inside = {i for i, d in details.items() if any(a["orgUnitId"] in scope for a in d["assignments"])}
    assert inside and len(inside) < len(measures)
    return {"Authorization": f"Bearer {created['token']}"}, inside, set(details) - inside, scope


def test_unit_head_sees_only_own_unit_on_every_tab(client, unit_head):
    head, inside, outside, scope = unit_head
    assert {m["id"] for m in client.get("/api/measures", headers=head).json()} == inside
    assert client.get(f"/api/measures/{next(iter(outside))}", headers=head).status_code == 403
    assert client.get(f"/api/measures/{next(iter(inside))}", headers=head).status_code == 200

    program = client.get("/api/programs", headers=H["coord"]).json()[0]["id"]
    passport = client.get(f"/api/programs/{program}/passport", headers=head).json()
    assert {m["id"] for s in passport["sections"] for m in s["measures"]} <= inside

    executive = client.get("/api/dashboard/executive", headers=head).json()
    assert {c["id"] for c in executive["critical"]} <= inside
    assert {u["orgUnitId"] for u in executive["units"]} <= scope
    coord = client.get("/api/dashboard/coordinator", headers=head).json()
    assert {m["id"] for m in coord["reviewQueue"]} <= inside
    assert {f["measureId"] for f in coord["openFlags"]} <= inside

    assert {f["measureId"] for f in client.get("/api/flags", headers=head).json()} <= inside
    for r in client.get("/api/recommendations", headers=head).json():
        assert r["measureId"] in inside

    all_units = {u["id"] for u in client.get("/api/admin/org-units", headers=H["admin"]).json()}
    foreign_unit = next(iter(all_units - scope))
    assert client.get(f"/api/dashboard/units/{foreign_unit}", headers=head).status_code == 403

    own_risks = {r["id"] for r in client.get("/api/risks", headers=head).json()}
    all_risks = {r["id"] for r in client.get("/api/risks", headers=H["coord"]).json()}
    assert own_risks < all_risks
    foreign_risk = next(iter(all_risks - own_risks))
    assert client.get(f"/api/risks/{foreign_risk}", headers=head).status_code == 403
    assert client.get(f"/api/risk-model/risks/{foreign_risk}", headers=head).status_code == 403
    overview = client.get("/api/risk-model/overview", headers=head).json()
    assert {r["riskId"] for r in overview["risks"]} <= own_risks


def test_whole_program_roles_see_everything(client):
    total = len(client.get("/api/measures", headers=H["coord"]).json())
    for role in ("head", "analyst"):
        assert len(client.get("/api/measures", headers=H[role]).json()) == total, role
    risks = len(client.get("/api/risks", headers=H["coord"]).json())
    assert len(client.get("/api/risks", headers=H["head"]).json()) == risks


def test_executor_sees_only_risks_of_own_measures(client):
    mine = client.get("/api/measures?mine=true", headers=H["ex-fin"]).json()
    own_risks = {m["risk"]["id"] for m in mine if m.get("risk")}
    seen = {r["id"] for r in client.get("/api/risks", headers=H["ex-fin"]).json()}
    assert seen == own_risks
    seen_ind = {i["riskId"] for i in client.get("/api/indicators", headers=H["ex-fin"]).json()}
    assert seen_ind <= own_risks


def test_unit_head_coverage_gaps_stay_within_scope(client, unit_head):
    from tests.test_access_sweep import _drop_measure

    head, inside, _, scope = unit_head
    coord = H["coord"]
    program = client.get("/api/programs", headers=coord).json()[0]
    section = next(s for s in client.get(f"/api/programs/{program['id']}/passport", headers=coord).json()["sections"]
                   if s["number"] == 2)
    org = client.get("/api/admin/org-units", headers=H["admin"]).json()
    other_unit = next(u["id"] for u in org if u["id"] not in scope and u.get("parentId"))
    created = client.post("/api/measures", headers=coord, json={
        "sectionId": section["id"], "title": "Чужий захід розділу 2 без ризику",
        "plannedDeadline": program["periodEnd"], "assignments": [{"orgUnitId": other_unit, "isResponsible": True}],
    })
    assert created.status_code == 201
    foreign = created.json()["id"]
    try:
        whole = client.get(f"/api/programs/{program['id']}/coverage", headers=coord).json()
        own = client.get(f"/api/programs/{program['id']}/coverage", headers=head).json()
    finally:
        _drop_measure(uuid.UUID(foreign))
    assert any(g["ruleCode"] == "C2" and g["measureId"] == foreign for g in whole)
    assert {g["measureId"] for g in own if g.get("measureId")} <= inside
    assert not [g for g in own if g["ruleCode"] == "C1"]
