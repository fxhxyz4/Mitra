import pytest
from fastapi.testclient import TestClient

from app.main import app

H = {k: {"Authorization": f"Bearer demo-{k}"} for k in ("coord", "head", "analyst", "admin", "ex-fin", "ex-proc")}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_access_by_role(client: TestClient) -> None:
    """Аналітик — усе; керівник — основний і розширений режими; виконавець — лише колеги; решта — нічого."""
    for path in ("/api/analytics/summary", "/api/analytics/performance", "/api/analytics/performance/export"):
        for role in ("analyst", "head"):
            assert client.get(path, headers=H[role]).status_code == 200, (path, role)
        for role in ("coord", "admin", "ex-fin"):
            assert client.get(path, headers=H[role]).status_code == 403, (path, role)
    for path in ("/api/analytics/overview", "/api/analytics/export"):
        assert client.get(path, headers=H["analyst"]).status_code == 200
        for role in ("head", "coord", "ex-fin"):
            assert client.get(path, headers=H[role]).status_code == 403, (path, role)
    assert client.get("/api/analytics/peers", headers=H["ex-fin"]).status_code == 200
    for role in ("analyst", "head", "coord", "admin"):
        assert client.get("/api/analytics/peers", headers=H[role]).status_code == 403
    assert client.get("/api/analytics/performance?period=2026-H3", headers=H["analyst"]).status_code == 422


def test_summary_adds_up(client: TestClient) -> None:
    s = client.get("/api/analytics/summary", headers=H["analyst"]).json()
    assert s["scope"] is None
    assert s["overdue"] == sum(x["overdue"] for x in s["sections"])
    assert s["total"] == sum(x["total"] for x in s["sections"])
    assert s["verdict"]["level"] in ("good", "attention", "behind") and s["verdict"]["text"]
    assert s["attention"] and len(s["upcoming"]) <= 5
    assert all(0 <= d["daysLeft"] <= 30 for d in s["upcoming"])


def _subtree(units: list[dict], root: str) -> set[str]:
    out, stack = set(), [root]
    while stack:
        uid = stack.pop()
        if uid not in out:
            out.add(uid)
            stack += [u["id"] for u in units if u.get("parentId") == uid]
    return out


def test_head_sees_only_own_unit_and_subordinate_units(client: TestClient) -> None:
    full = client.get("/api/analytics/performance", headers=H["analyst"]).json()
    org = client.get("/api/admin/org-units", headers=H["analyst"]).json()
    # Підрозділ без підпорядкованих (у кореневого піддерево — уся організація).
    unit = next(u for u in full["units"] if u["orgUnitId"] and u["tasks"] and len(_subtree(org, u["orgUnitId"])) == 1)
    scope = _subtree(org, unit["orgUnitId"])
    other = next(u for u in full["units"] if u["orgUnitId"] and u["orgUnitId"] not in scope)
    created = client.post("/api/admin/users", headers=H["admin"], json={
        "displayName": "Керівник підрозділу (тест)", "role": "HEAD", "orgUnitId": unit["orgUnitId"]}).json()
    head = {"Authorization": f"Bearer {created['token']}"}

    r = client.get("/api/analytics/performance", headers=head).json()
    assert r["scope"] == unit["name"]
    assert r["totals"]["tasks"] == sum(u["tasks"] for u in full["units"] if u["orgUnitId"] in scope)
    assert {u["orgUnitId"] for u in r["units"]} <= scope and unit["orgUnitId"] in {u["orgUnitId"] for u in r["units"]}
    assert all(p["orgUnitId"] in scope for p in r["people"])
    s = client.get("/api/analytics/summary", headers=head).json()
    assert s["scope"] == unit["name"]

    assert client.get(f"/api/analytics/performance?orgUnitId={other['orgUnitId']}", headers=head).status_code == 403
    stranger = next(p for p in full["people"] if p["orgUnitId"] not in scope)
    assert client.get(f"/api/analytics/performance?userId={stranger['userId']}", headers=head).status_code == 403
    assert client.get(f"/api/analytics/performance/export?orgUnitId={other['orgUnitId']}", headers=head).status_code == 403


def test_executor_sees_no_named_colleagues(client: TestClient) -> None:
    fin = client.get("/api/auth/me", headers=H["ex-fin"]).json()
    proc = client.get("/api/auth/me", headers=H["ex-proc"]).json()
    program = next(p for p in client.get("/api/programs", headers=H["coord"]).json() if p["status"] == "APPROVED")
    passport = client.get(f"/api/programs/{program['id']}/passport", headers=H["coord"]).json()
    section = next(s for s in passport["sections"] if s["number"] == 1)
    secret = "Спільний захід фінансів і закупівель (перевірка)"
    assert client.post("/api/measures", headers=H["coord"], json={
        "sectionId": section["id"], "title": secret, "plannedDeadline": program["periodEnd"],
        "assignments": [{"orgUnitId": fin["orgUnitId"], "userId": fin["id"], "isResponsible": True},
                        {"orgUnitId": proc["orgUnitId"], "userId": proc["id"]}],
    }).status_code == 201

    r = client.get("/api/analytics/peers", headers=H["ex-fin"]).json()
    assert r["me"]["name"] == fin["displayName"] and r["sharedMeasures"] >= 1
    assert set(r) == {"programTitle", "asOf", "sharedMeasures", "me", "average", "colleagues", "minGroup"}
    # Без рейтингування: жодних імен чи підрозділів колег, середнє лише від minGroup людей.
    assert proc["displayName"] not in str(r) and secret not in str(r)
    assert (r["average"] is not None) == (r["colleagues"] >= r["minGroup"])
    if r["average"]:
        assert r["average"]["orgUnit"] == ""


def test_performance_totals_add_up(client: TestClient) -> None:
    r = client.get("/api/analytics/performance", headers=H["analyst"]).json()
    t = r["totals"]
    assert t["tasks"] == len(r["tasks"]) == sum(u["tasks"] for u in r["units"])
    assert t["returns"] == sum(u["returns"] for u in r["units"]) == sum(1 for e in r["events"] if e["kind"] == "returned")
    assert t["submissions"] == sum(x["submissions"] for x in r["tasks"])
    assert t["done"] == t["onTime"] + t["lateDone"]
    assert sum(x["reviews"] for x in r["reviewers"]) == t["decisions"]
    assert [e["at"] for e in r["events"]] == sorted((e["at"] for e in r["events"]), reverse=True)


def test_filters_narrow_the_scope(client: TestClient) -> None:
    full = client.get("/api/analytics/performance", headers=H["analyst"]).json()
    unit = next(u for u in full["units"] if u["tasks"])
    by_unit = client.get(f"/api/analytics/performance?orgUnitId={unit['orgUnitId']}", headers=H["analyst"]).json()
    assert by_unit["totals"]["tasks"] == unit["tasks"] and {u["orgUnitId"] for u in by_unit["units"]} == {unit["orgUnitId"]}

    person = next(p for p in full["people"] if p["tasks"])
    by_person = client.get(f"/api/analytics/performance?userId={person['userId']}", headers=H["analyst"]).json()
    assert by_person["totals"]["tasks"] == person["tasks"]
    assert all(person["userId"] in t["executorIds"] for t in by_person["tasks"])

    period = full["periods"][-1]
    by_period = client.get(f"/api/analytics/performance?period={period}", headers=H["analyst"]).json()
    assert by_period["period"] == period and all(t["period"] == period for t in by_period["tasks"])

    xlsx = client.get(f"/api/analytics/performance/export?orgUnitId={unit['orgUnitId']}", headers=H["analyst"])
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"


def test_return_is_attributed_to_the_submitter_and_reviewer(client: TestClient) -> None:
    me = client.get("/api/auth/me", headers=H["ex-fin"]).json()
    program = next(p for p in client.get("/api/programs", headers=H["coord"]).json() if p["status"] == "APPROVED")
    passport = client.get(f"/api/programs/{program['id']}/passport", headers=H["coord"]).json()
    section = next(s for s in passport["sections"] if s["number"] == 1)
    m = client.post("/api/measures", headers=H["coord"], json={
        "sectionId": section["id"], "title": "Перевірка виконання фінансових процедур (аудит)",
        "plannedDeadline": program["periodEnd"],
        "assignments": [{"orgUnitId": me["orgUnitId"], "userId": me["id"], "isResponsible": True}],
    }).json()

    def submit(text: str) -> None:
        res = client.post(f"/api/measures/{m['id']}/submit", headers=H["ex-fin"],
                          data={"resultDescription": text, "documentTypes": "акт", "documentDates": "2026-03-01"},
                          files=[("files", ("akt.txt", "Акт № 5 від 01.03.2026".encode(), "text/plain"))])
        assert res.status_code == 200, res.text

    def person() -> dict:
        r = client.get(f"/api/analytics/performance?userId={me['id']}", headers=H["analyst"]).json()
        return next(p for p in r["people"] if p["userId"] == me["id"]), r

    before, _ = person()
    submit("Проведено 3 перевірки, складено акт № 5.")
    assert client.post(f"/api/measures/{m['id']}/return", headers=H["coord"],
                       json={"comment": "Додайте кількість порушень"}).status_code == 200
    after_return, r = person()
    assert after_return["returns"] == before["returns"] + 1
    ret = next(e for e in r["events"] if e["kind"] == "returned" and e["measureId"] == m["id"])
    assert ret["executorId"] == me["id"] and ret["comment"] == "Додайте кількість порушень"
    assert ret["round"] >= 1 and ret["resolved"] is False

    submit("Проведено 3 перевірки, виявлено 2 порушення, складено акт № 5.")
    assert client.post(f"/api/measures/{m['id']}/approve", headers=H["coord"], json={}).status_code == 200
    done, r = person()
    assert done["submissions"] == before["submissions"] + 2
    ret = next(e for e in r["events"] if e["kind"] == "returned" and e["measureId"] == m["id"])
    assert ret["resolved"] is True
    task = next(t for t in r["tasks"] if t["measureId"] == m["id"])
    assert task["returns"] >= 1 and task["submissions"] >= 2 and task["status"] == "DONE"
