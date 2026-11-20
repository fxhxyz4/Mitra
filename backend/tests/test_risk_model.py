from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.enums import KriDirection, RiskLevel
from app.main import app
from app.models import CorruptionRisk, Incident, Indicator, IndicatorValue
from app.services import risk_model as rm

D = Decimal


def kri(base, target, current, *, n=None, unit="%", weight=1, independent=True, direction=None,
        at=date(2026, 6, 30), history=(), target_date=None):
    i = Indicator(name="KRI", unit=unit, baseline=D(base), target=D(target), weight=D(weight), lag_months=6,
                  independent=independent, direction=direction, target_date=target_date)
    i.values = [IndicatorValue(value=D(v), measured_at=d) for v, d in history]
    i.values.append(IndicatorValue(value=D(current), measured_at=at, sample_size=n))
    return i


def test_example_food_procurement():
    """KRI₁ «один учасник» B 45, T 25, C 40, n 120 → δ = 9,1 в.п., зміна 5 < δ → p₁ = 0.
    KRI₂ «перевищення ціни» B 18, T 8, C 13 → p₂ = 0,5. RRS = 0,6·0 + 0,4·0,5 = 0,20 — незначне."""
    k1 = rm.kri_progress(kri(45, 25, 40, n=120), date(2026, 7, 1))
    assert round(k1.delta, 1) == 9.1 and k1.noise and k1.p == 0 and k1.state == rm.NO_CHANGE_STATE
    k2 = rm.kri_progress(kri(18, 8, 13), date(2026, 7, 1))
    assert k2.delta == 5 and not k2.noise and k2.p == 0.5
    k1.indicator.weight, k2.indicator.weight = D("0.6"), D("0.4")
    rrs = rm.rrs_of([k1, k2])
    assert round(rrs, 3) == 0.2 and rm.rrs_category(rrs) == "незначне зниження"


def test_progress_direction_clip_and_self_report():
    up = rm.kri_progress(kri(49, 90, 70, direction=KriDirection.HIGHER), date(2026, 7, 1))  # більше — краще
    assert round(up.p, 3) == round(21 / 41, 3)
    worse = rm.kri_progress(kri(20, 10, 60), date(2026, 7, 1))
    assert worse.p == -1 and worse.state == rm.WORSENING  # обрізано до [−1; 1]
    self_rep = rm.kri_progress(kri(18, 8, 13, independent=False), date(2026, 7, 1))
    assert self_rep.p == 0.25 and self_rep.self_report_discount  # позитивний прогрес × 0,5
    neg_self = rm.kri_progress(kri(20, 10, 60, independent=False), date(2026, 7, 1))
    assert neg_self.p == -1 and not neg_self.self_report_discount  # негативний — повністю


def test_insufficient_data_rule_d1():
    i = kri(45, 25, 40, n=20)
    i.min_sample = 30
    res = rm.kri_progress(i, date(2026, 7, 1))
    assert any("менший за мінімум" in r for r in res.insufficient)
    old = rm.kri_progress(kri(45, 25, 40, at=date(2025, 3, 1)), date(2026, 7, 1))
    assert any("два періоди" in r for r in old.insufficient)
    none = rm.kri_progress(Indicator(name="x", unit="%", baseline=D(1), target=D(0), weight=D(1)), date(2026, 7, 1))
    assert none.p is None and none.state == rm.NO_DATA


def test_trajectory_on_track_lagging_no_change():
    """Ціль на 31.12.2026, програма з 01.01.2026: на 01.07 очікувано ≈ половину шляху."""
    start, due, on = date(2026, 1, 1), date(2026, 12, 31), date(2026, 7, 1)
    vlk = rm.kri_progress(kri(25, 95, 26, target_date=due), on, start=start)  # ВЛК: 25 → 26 при цілі 95
    assert 0.49 < vlk.expected < 0.51 and vlk.state == rm.NO_CHANGE_STATE
    tenders = rm.kri_progress(kri(38, 25, 31, target_date=due), on, start=start)  # 38 → 31 при цілі 25: 54 %
    assert round(tenders.p, 2) == 0.54 and tenders.state == rm.ON_TRACK
    slow = rm.kri_progress(kri(50, 100, 60, target_date=due), on, start=start)  # 20 % шляху за пів строку
    assert slow.state == rm.LAGGING
    assert rm.progress_state(0.09, None) == rm.NO_CHANGE_STATE and rm.progress_state(0.1, None) == rm.ON_TRACK
    assert rm.expected_progress(kri(1, 0, 1, target_date=due), date(2027, 3, 1), start) == 1.0


def test_verdict_matrix():
    m = rm.verdict_of
    assert m(True, True, rm.ON_TRACK) == "WORKING" and m(True, True, rm.LAGGING) == "WORKING"
    assert m(True, True, rm.NO_CHANGE_STATE) == "FORMAL" and m(True, True, rm.WORSENING) == "WORSE_DESPITE"
    assert m(True, False, rm.ON_TRACK) == "EXTERNAL" and m(True, False, rm.NO_CHANGE_STATE) == "STAGNANT"
    assert m(True, False, rm.WORSENING) == "UNATTENDED"
    assert m(True, True, rm.NO_DATA) == "NO_DATA" and m(False, False, rm.ON_TRACK) == "NO_MEASURES"
    assert set(rm.VERDICTS) >= {"WORKING", "FORMAL", "WORSE_DESPITE", "EXTERNAL", "STAGNANT", "UNATTENDED"}


def _risk(ind, l0=3, c0=3, incidents=()):
    risk = CorruptionRisk(code="ВЛК", description="Неправомірна вигода у ВЛК", level=RiskLevel.from_score(l0 * c0),
                          probability=l0, impact=c0)
    risk.indicators, risk.incidents = [ind], list(incidents)
    return risk


def test_reassessment_hints_are_symmetric_and_do_not_change_the_score():
    """L-1 і L+1 — лише після двох кварталів поспіль; ймовірність у реєстрі не змінюється."""
    good = kri(30, 10, 12, history=[(30, date(2026, 1, 1)), (14, date(2026, 3, 31))])
    hints = rm.reassessment_hints(_risk(good), date(2026, 7, 1), date(2026, 1, 1))
    assert [h.rule for h in hints] == ["L-1"] and hints[0].suggested == 2
    once_bad = kri(20, 10, 30, history=[(20, date(2026, 1, 1)), (18, date(2026, 3, 31))])
    assert rm.reassessment_hints(_risk(once_bad), date(2026, 7, 1), date(2026, 1, 1)) == []  # лише один квартал
    bad = kri(20, 10, 30, history=[(20, date(2026, 1, 1)), (28, date(2026, 3, 31))])
    risk = _risk(bad)
    hints = rm.reassessment_hints(risk, date(2026, 7, 1), date(2026, 1, 1))
    assert [h.rule for h in hints] == ["L+1"] and hints[0].suggested == 4
    assert risk.probability == 3  # система бал НАЗК не змінює
    top = rm.reassessment_hints(_risk(bad, l0=4), date(2026, 7, 1), date(2026, 1, 1))
    assert top == []  # межа 4


def test_incident_gives_reason_to_reassess_p1():
    """На 5-му місяці вирок за хабар: за критеріями НАЗК ймовірність ≥ 4 — підстава переоцінити (P1)."""
    inc = Incident(occurred_on=date(2026, 5, 20), confirmed=True, source="ЄДРСР")
    hints = rm.reassessment_hints(_risk(kri(30, 10, 30), incidents=[inc]), date(2026, 7, 1), date(2026, 1, 1))
    p1 = next(h for h in hints if h.rule == "P1")
    assert p1.suggested == 4 and p1.source == "ЄДРСР" and "молодший 6 міс." in p1.text
    old = Incident(occurred_on=date(2025, 3, 1), confirmed=True, source="ЄДРСР")
    hints = rm.reassessment_hints(_risk(kri(30, 10, 30), l0=1, incidents=[old]), date(2026, 7, 1), date(2026, 1, 1))
    assert [h.suggested for h in hints if h.rule == "P1"] == [2]  # один випадок за 3 роки → L ≥ 2


def test_validation_helpers():
    assert rm.kri_problem(D(10), D(10), None)
    assert rm.kri_problem(D(10), D(20), True) and rm.kri_problem(D(20), D(10), False)
    assert rm.kri_problem(D(20), D(10), True) is None and rm.kri_problem(D(20), D(10), None) is None
    assert rm.level_problem(RiskLevel.HIGH, 3, 4)  # 12 — критичний
    assert rm.level_problem(RiskLevel.CRITICAL, 3, 4) is None and rm.level_problem(None, 2, 2) is None
    assert rm.level_problem(None, None, None) and rm.level_problem(RiskLevel.LOW, 2, None)


def test_fcg_colors():
    """PRI = (2,4 + 4,8 + 9) / 27 = 60 %, EXEC = 24 / 27 = 88,9 % → FCG = 28,9 в.п. — червоний."""
    pri, exe = (12 * 0.2 + 6 * 0.8 + 9 * 1) / 27, (12 * 1 + 6 * 0.5 + 9 * 1) / 27
    fcg = (exe - pri) * 100
    assert round(pri * 100, 1) == 60.0 and round(exe * 100, 1) == 88.9 and round(fcg, 1) == 28.9
    assert rm.fcg_color(fcg) == "red" and rm.fcg_color(15) == "yellow" and rm.fcg_color(9.9) == "green"


H = {name: {"Authorization": f"Bearer {tok}"} for name, tok in {
    "coord": "demo-coord", "head": "demo-head", "analyst": "demo-analyst", "admin": "demo-admin",
    "ex_fin": "demo-ex-fin",
}.items()}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _overview(client, who):
    # Other test modules share the DB and may import more programmes: pick the demo one.
    pid = next(p["id"] for p in client.get("/api/programs", headers=H["coord"]).json() if "(демо)" in p["title"])
    return client.get(f"/api/risk-model/overview?programId={pid}", headers=H[who])


def test_overview_and_assessment(client):
    o = _overview(client, "head").json()
    assert {"pri", "exec", "fcg", "fcgColor", "verdictCounts", "risksWithDone", "risksWorking", "uncovered", "risks"} <= set(o)
    assert round(o["fcg"], 1) == round((o["exec"] - o["pri"]) * 100, 1)
    assert sum(o["verdictCounts"].values()) == len(o["risks"])
    r = next(x for x in o["risks"] if x["code"] == "КР-02")
    assert r["inherent"] == r["probability0"] * r["impact0"] and r["kris"][0]["p"] == 0  # 7 → 7: без змін
    assert r["kris"][0]["state"] == "NO_CHANGE" and r["effect"] == "NO_CHANGE"
    assert r["verdict"] in ("FORMAL", "STAGNANT") and r["verdictLabel"]
    assert not {"ceDecl", "residual", "probability1", "trace"} & set(r)  # формули ефективності прибрано
    assert client.get("/api/risk-model/overview", headers=H["admin"]).status_code == 403
    assert client.get("/api/risk-model/overview", headers=H["ex_fin"]).status_code == 403
    one = client.get(f"/api/risk-model/risks/{r['riskId']}", headers=H["analyst"]).json()
    assert one["code"] == "КР-02" and one["rulesetVersion"] == rm.RULESET_VERSION
    flags = [f for st in ("OPEN", "RESOLVED")  # другий модуль тестів міг уже зняти його рішенням керівника
             for f in client.get(f"/api/flags?type=FORMAL_CLOSURE&status={st}", headers=H["coord"]).json()]
    assert any(f["ruleCode"] == "F1" and f["measureCode"] == "2.2" for f in flags)  # виконано, ризик не змінився


def test_incident_gives_hint_and_reassessment_by_working_group(client):
    o = _overview(client, "coord").json()
    r = next(x for x in o["risks"] if x["code"] == "КР-01")
    url = f"/api/risk-model/risks/{r['riskId']}"
    body = {"occurredOn": "2026-01-10", "source": "ЄДРСР, вирок (умовний)", "description": "Хабар"}
    assert client.post(f"{url}/incidents", headers=H["head"], json=body).status_code == 403
    client.post(f"{url}/incidents", headers=H["coord"], json={**body, "occurredOn": str(date.today())})
    one = client.get(url, headers=H["coord"]).json()
    assert one["probability0"] == 3  # бал НАЗК система сама не змінює
    assert any(h["rule"] == "P1" and h["suggested"] == 4 for h in one["hints"])
    assert any(s["ruleCode"] == "P1" for s in one["signals"])

    risk_url = f"/api/risks/{r['riskId']}"
    assert client.patch(risk_url, headers=H["head"], json={"probability": 4, "impact": 3,
                                                           "justification": "Рішення робочої групи"}).status_code == 403
    assert client.patch(risk_url, headers=H["coord"], json={"probability": 4, "impact": 3}).status_code == 422
    done = client.patch(risk_url, headers=H["coord"],
                        json={"probability": 4, "impact": 3, "justification": "Протокол робочої групи № 5: вирок"})
    assert done.status_code == 200 and done.json()["level"] == "CRITICAL" and done.json()["score"] == 12
    one = client.get(url, headers=H["coord"]).json()
    assert one["probability0"] == 4 and not any(h["rule"] == "P1" for h in one["hints"])
    log = client.get(f"/api/audit?entityId={r['riskId']}", headers=H["admin"]).json()
    assert any(e["action"] == "reassess" and e["newValue"]["justification"].startswith("Протокол") for e in log)

    ind = one["kris"][0]["indicatorId"]
    assert client.patch(f"/api/indicators/{ind}", headers=H["coord"], json={"baseline": 50}).status_code == 422
    r2 = client.patch(f"/api/indicators/{ind}", headers=H["coord"],
                      json={"baseline": 50, "justification": "Уточнено базу за даними Prozorro"})
    assert r2.status_code == 200
    sig = client.get("/api/risk-model/signals", headers=H["analyst"]).json()
    assert any(s["ruleCode"] == "B1" and s["riskCode"] == "КР-01" for s in sig)
    log = client.get(f"/api/audit?entityId={ind}", headers=H["admin"]).json()
    assert log[0]["newValue"]["justification"].startswith("Уточнено")


def test_kri_and_risk_validation(client):
    o = _overview(client, "coord").json()
    ind = next(x for x in o["risks"] if x["code"] == "КР-03")["kris"][0]  # 12 → 3, менше — краще
    why = {"justification": "Перевірка валідації цілі"}
    same = client.patch(f"/api/indicators/{ind['indicatorId']}", headers=H["coord"], json={"target": 12, **why})
    assert same.status_code == 422 and "дорівнює базі" in same.json()["detail"]
    wrong = client.patch(f"/api/indicators/{ind['indicatorId']}", headers=H["coord"],
                         json={"direction": "HIGHER", **why})
    assert wrong.status_code == 422
    flat = client.post("/api/indicators", headers=H["coord"], json={"name": "Плаский KRI", "baseline": 5, "target": 5})
    assert flat.status_code == 422

    bad = client.post("/api/risks", headers=H["coord"],
                      json={"code": "КР-V1", "description": "Перевірка", "level": "HIGH", "probability": 3, "impact": 4})
    assert bad.status_code == 422 and "не відповідає" in bad.json()["detail"]
    ok = client.post("/api/risks", headers=H["coord"],
                     json={"code": "КР-V2", "description": "Перевірка", "probability": 2, "impact": 3})
    assert ok.status_code == 201 and ok.json()["level"] == "HIGH"
