import asyncio
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.enums import KriDirection
from app.main import app
from app.models import Indicator, IndicatorValue
from app.services import intake
from app.services.assistant import Assistant
from tests.conftest import reply

H = {k: {"Authorization": f"Bearer demo-{k}"} for k in ("coord", "head", "admin", "ex-fin", "ex-proc")}
EDITABLE = {"PLANNED", "IN_PROGRESS", "RETURNED"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def proposed(client: TestClient) -> list[dict]:
    return client.get("/api/recommendations?status=PROPOSED", headers=H["head"]).json()


def test_rejected_recommendation_is_not_proposed_again(client: TestClient) -> None:
    rec = proposed(client)[0]
    key = rec["basis"]["dedupKey"]
    assert client.post(f"/api/recommendations/{rec['id']}/reject", headers=H["head"],
                       json={"comment": "недоцільно"}).status_code == 200
    assert client.post("/api/flags/evaluate", headers=H["coord"]).status_code == 200
    assert not [r for r in proposed(client) if r["basis"]["dedupKey"] == key]


def test_accepted_recommendation_can_be_completed(client: TestClient) -> None:
    rec = proposed(client)[0]
    head = client.get("/api/auth/me", headers=H["head"]).json()
    accepted = client.post(f"/api/recommendations/{rec['id']}/accept", headers=H["head"],
                           json={"responsibleId": head["id"], "dueDate": "2027-01-31"})
    assert accepted.status_code == 200
    url = f"/api/recommendations/{rec['id']}/complete"
    assert client.post(url, headers=H["coord"], json={"comment": "зроблено"}).status_code == 403
    done = client.post(url, headers=H["head"], json={"comment": "нараду проведено"})
    assert done.status_code == 200 and done.json()["status"] == "DONE"
    assert client.post(url, headers=H["head"], json={"comment": "ще раз"}).status_code == 409


def test_kri_direction_is_respected() -> None:
    ind = Indicator(name="x", baseline=Decimal(10), target=Decimal(10), direction=KriDirection.LOWER)
    ind.values = [IndicatorValue(value=Decimal(15), measured_at=date(2026, 1, 1))]
    assert not ind.is_improved() and not ind.is_target_reached()
    ind.values = [IndicatorValue(value=Decimal(8), measured_at=date(2026, 1, 1))]
    assert ind.is_improved() and ind.is_target_reached()


def test_measure_card_risk_with_empty_registry() -> None:
    assert asyncio.run(intake._risk(Assistant(db=None, enabled=False), "ризик закупівель", [])) == (None, None)


def test_executor_passport_shows_only_own_measures(client: TestClient) -> None:
    program = client.get("/api/programs", headers=H["coord"]).json()[0]["id"]
    own = {m["id"] for m in client.get(f"/api/measures?programId={program}", headers=H["ex-proc"]).json()}
    passport = client.get(f"/api/programs/{program}/passport", headers=H["ex-proc"]).json()
    shown = {m["id"] for sec in passport["sections"] for m in sec["measures"]}
    assert shown == own and passport["totals"]["measures"] == len(own)
    full = client.get(f"/api/programs/{program}/passport", headers=H["coord"]).json()
    assert full["totals"]["measures"] > len(own)


def _editable_measure(client: TestClient) -> dict:
    """Захід лише виконавця фінансів (не спільний із закупівлями: перевіряється чужий доступ)."""
    others = {m["id"] for m in client.get("/api/measures?mine=true", headers=H["ex-proc"]).json()}
    return next(m for m in client.get("/api/measures?mine=true", headers=H["ex-fin"]).json()
                if m["status"] in EDITABLE and m["id"] not in others)


def test_rewrite_accepts_only_grounded_text(client: TestClient, model) -> None:
    m = _editable_measure(client)
    url = f"/api/ai/measures/{m['id']}/rewrite"
    vague = f"{m['title']} 12"  # repeats the title, but has a number to build on

    model(reply({"text": "Проведено 99 перевірок."}))  # invented number → rejected
    r = client.post(url, headers=H["ex-fin"], json={"text": vague}).json()
    assert r["text"] is None and r["note"] == intake.REJECTED

    model(reply({"text": "Проведено 12 перевірок, результати оформлено протоколом."}))
    r = client.post(url, headers=H["ex-fin"], json={"text": vague}).json()
    assert r["text"].startswith("Проведено 12") and r["modelUsed"]

    concrete = client.post(url, headers=H["ex-fin"], json={"text": "Затверджено наказ № 15 від 01.03.2026."}).json()
    assert concrete["text"] is None and concrete["note"] == intake.NOTHING_TO_FIX
    assert client.post(url, headers=H["ex-proc"], json={"text": vague}).status_code == 403


def test_concurrent_audit_writes_keep_the_chain(client: TestClient) -> None:
    import threading

    from app import audit
    from app.db import SessionLocal

    barrier = threading.Barrier(8)

    def write(n: int) -> None:
        with SessionLocal() as db:
            barrier.wait()
            audit.record(db, None, "test", None, f"parallel-{n}")
            db.commit()

    threads = [threading.Thread(target=write, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with SessionLocal() as db:
        ok, _, broken = audit.verify_chain(db)
    assert ok, f"chain forked at entry {broken}"


def test_rule_answer_is_grouped_one_record_per_line() -> None:
    from app.services.data_chat import Item, rule_answer

    items = [
        Item("measure", 1, "Захід 1.11", {"назва": "Забезпечити виконання заходів " * 10}),
        Item("risk", 2, "Ризик KR04", {"опис": "Призначення на вразливі посади"}),
        Item("flag", 3, "Прапорець R1 заходу 1.5", {"пояснення": "Строк минув"}),
        Item("measure", 4, "Захід 1.2", {"назва": "Моніторинг реєстру"}),
    ]
    text = rule_answer(items)
    blocks = text.split("\n\n")
    assert blocks[0] == "Точної відповіді не знайдено. Найближчі записи:"  # similar records, not an answer
    assert blocks[1].splitlines() == ["Заходи", blocks[1].splitlines()[1], "• 1.2 — Моніторинг реєстру [4]"]
    assert blocks[1].splitlines()[1].startswith("• 1.11 — Забезпечити") and blocks[1].splitlines()[1].endswith("… [1]")
    assert blocks[2] == "Ризики\n• KR04 — Призначення на вразливі посади [2]"
    assert blocks[3] == "Прапорці\n• Прапорець R1 заходу 1.5 — Строк минув [3]"


def test_pdf_text_is_extracted_and_broken_pdf_is_refused() -> None:
    """Читання PDF (pypdf): реальний документ з репозиторію і пошкоджений файл."""
    from pathlib import Path

    from fastapi import HTTPException

    from app.services import documents

    pdf = Path(__file__).resolve().parents[2] / "docs" / "zavdannia-2.pdf"
    doc = documents.read(pdf.name, pdf.read_bytes())
    assert len(doc.text) > 500

    with pytest.raises(HTTPException) as e:
        documents.read("broken.pdf", b"%PDF-1.7 not really a pdf")
    assert e.value.status_code == 422


def test_final_status_is_not_overdue() -> None:
    from app.enums import MeasureStatus
    from app.models import Measure, MeasurePeriod

    m = Measure(title="x", planned_deadline=date(2026, 3, 1), is_permanent=False)
    m.periods = [MeasurePeriod(period="2026-H1", status=MeasureStatus.NOT_DONE)]
    assert not m.is_overdue(date(2026, 5, 1))
    m.periods[0].status = MeasureStatus.IN_PROGRESS
    assert m.is_overdue(date(2026, 5, 1))


def test_print_form_has_no_inline_script() -> None:
    from app.schemas import domain as s
    from app.services.reports import to_print_html

    import uuid

    r = s.NazkReport(report_id=uuid.uuid4(), program_title="П", org_unit="О", period="2026-H1",
                     period_end=date(2026, 6, 30), has_restricted_info=False, sections=[])
    assert "onclick" not in to_print_html(r) and "<script" not in to_print_html(r)


def test_import_of_indicator_changes_is_audited(client: TestClient) -> None:
    payload = {"indicators": [{"name": "Імпортований індикатор (журнал)", "unit": "шт.", "baseline": 10, "target": 5,
                               "values": [{"measuredAt": "2026-03-01", "value": 8}]}]}
    assert client.post("/api/admin/import", headers=H["coord"], json=payload).status_code == 200
    payload["indicators"][0]["target"] = 3
    assert client.post("/api/admin/import", headers=H["coord"], json=payload).status_code == 200
    log = client.get("/api/audit?limit=1000", headers=H["admin"]).json()
    changes = [e for e in log if e["entity"] == "indicator" and e["action"] == "import"]
    assert float(changes[0]["oldValue"]["target"]) == 5 and float(changes[0]["newValue"]["target"]) == 3
    assert any(e["entity"] == "indicator_value" and e["action"] == "import" for e in log)


def test_ambiguous_unit_in_measure_card_is_not_guessed() -> None:
    from app.services import templates as t

    names = ["Відділ закупівель", "Відділ кадрів", "Юридичний департамент"]
    assert [n for n in names if t.unit_score("Відділ", n) == 1.0] == names[:2]
    assert t.unit_score("Юридичний департамент", names[2]) == 1.0


def test_only_executor_entries_count_as_interim_results() -> None:
    from app.enums import MeasureStatus as St
    from app.models import Measure, MeasurePeriod, ProgressUpdate
    from app.services.dashboards import non_execution_risk

    m = Measure(title="x", planned_deadline=date(2026, 6, 20), is_permanent=False)
    p = MeasurePeriod(period="2026-H1", status=St.IN_PROGRESS)
    p.updates = [ProgressUpdate(status_from=St.DRAFT, status_to=St.PLANNED, author_id=None),
                 ProgressUpdate(status_from=St.PLANNED, status_to=St.IN_PROGRESS, author_id=None)]
    m.periods, m.flags = [p], []
    risk = non_execution_risk(m, date(2026, 6, 10))
    assert risk.level == "HIGH" and any("проміжних результатів немає" in r for r in risk.reasons)

    import uuid

    p.updates.append(ProgressUpdate(status_from=St.IN_PROGRESS, status_to=St.IN_PROGRESS, author_id=uuid.uuid4()))
    assert non_execution_risk(m, date(2026, 6, 10)).level == "MEDIUM"


def test_approved_result_offers_no_evidence_upload(client: TestClient) -> None:
    ex = {"Authorization": "Bearer demo-ex-hr"}
    done = next(m for m in client.get("/api/measures?mine=true", headers=ex).json() if m["status"] == "DONE")
    detail = client.get(f"/api/measures/{done['id']}", headers=ex).json()
    assert "uploadEvidence" not in detail["allowedActions"]
    r = client.post(f"/api/measures/{done['id']}/evidence", headers=ex,
                    data={"documentTypes": "акт", "documentDates": "2026-01-10"},
                    files=[("files", ("a.pdf", b"%PDF", "application/pdf"))])
    assert r.status_code == 409


def test_explicit_null_for_required_field_is_422(client: TestClient) -> None:
    m = client.get("/api/measures", headers=H["coord"]).json()[0]
    for body in ({"title": None}, {"plannedDeadline": None}, {"isPermanent": None}):
        assert client.patch(f"/api/measures/{m['id']}", headers=H["coord"], json=body).status_code == 422
    ind = client.get(f"/api/measures/{m['id']}", headers=H["coord"]).json()["indicator"] or next(
        i for r in client.get("/api/risks", headers=H["coord"]).json() for i in r["indicators"])
    r = client.patch(f"/api/indicators/{ind['id']}", headers=H["coord"],
                     json={"baseline": None, "justification": "перевірка порожнього значення"})
    assert r.status_code == 422
    user = client.get("/api/auth/me", headers=H["ex-proc"]).json()
    assert client.patch(f"/api/admin/users/{user['id']}", headers=H["admin"],
                        json={"orgUnitId": None}).status_code == 422
