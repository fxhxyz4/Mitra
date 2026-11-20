import io
import json
from datetime import date

import pytest
from docx import Document as Docx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app
from app.services import documents, templates as t

from .conftest import down, reply

H = {name: {"Authorization": f"Bearer {tok}"} for name, tok in {
    "coord": "demo-coord", "admin": "demo-admin", "ex_com": "demo-ex-com", "ex_fin": "demo-ex-fin", "ex_hr": "demo-ex-hr",
}.items()}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def txt(rows: list[tuple[str, str]]) -> bytes:
    return "\n".join(["Синтетичний документ", *(f"{k}: {v}" for k, v in rows)]).encode()


def docx(rows: list[tuple[str, str]]) -> bytes:
    d = Docx()
    d.add_paragraph("Синтетичний документ")
    table = d.add_table(rows=len(rows), cols=2)
    for i, (k, v) in enumerate(rows):
        table.cell(i, 0).text, table.cell(i, 1).text = k, v
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def xlsx_header(rows: list[tuple[str, str]]) -> bytes:
    wb = Workbook()
    wb.active.append(["Картка заходу"])
    wb.active.append([k for k, _ in rows])
    wb.active.append([v for _, v in rows])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def measure(client: TestClient, who: str, code: str) -> dict:
    return next(m for m in client.get("/api/measures?mine=true", headers=H[who]).json() if m["code"] == code)


def report(client: TestClient, who: str, name: str, data: bytes):
    return client.post("/api/ai/intake/report", headers=H[who], files={"file": (name, data)})


def history(client: TestClient, entity_id: str) -> list[dict]:
    return client.get(f"/api/measures/{entity_id}/history", headers=H["admin"]).json()  # newest first




@pytest.mark.parametrize(("value", "expected"), [
    ("2026-H2", "2026-H2"), ("ІІ півріччя 2026 р.", "2026-H2"), ("перше півріччя 2026 року", "2026-H1"),
    ("за рік", None),
])
def test_half_year(value: str, expected: str | None) -> None:
    assert t.half_year(value) == expected


@pytest.mark.parametrize(("value", "expected"), [
    ("Виконано", "done"), ("Захід виконано в повному обсязі", "done"), ("Не виконано", "not_done"),
    ("Виконано частково", "not_done"), ("у роботі", None),
])
def test_outcome(value: str, expected: str | None) -> None:
    assert t.outcome(value) == expected


@pytest.mark.parametrize(("value", "expected"), [
    ("до 30.09.2026", (date(2026, 9, 30), False)),
    ("IV квартал 2026", (date(2026, 12, 31), False)),
    ("Червень 2026 року", (date(2026, 6, 30), False)),
    ("ІІ півріччя 2026", (date(2026, 12, 31), False)),
    ("Постійно", (date(2027, 12, 31), True)),
    ("Щопівроку", (date(2027, 12, 31), True)),
    ("колись", (None, False)),
])
def test_deadline(value: str, expected: tuple[date | None, bool]) -> None:
    assert t.deadline(value, date(2027, 12, 31)) == expected


def test_measure_code_and_section() -> None:
    assert t.measure_code("Захід 2.07") == "2.7"
    assert t.measure_code("5", section=3) == "3.5"
    assert t.measure_code("5") is None
    assert t.section_number("Розділ ІІ") == 2


def test_template_fields_from_lines_and_tables() -> None:
    rows = [("Найменування заходу", "Захід"), ("Звітний період", "2026-H2"), ("Стан виконання", "Виконано"),
            ("Опис результату виконання заходу або пояснення причин невиконання", "Перший рядок")]
    lines = documents.read("a.txt", txt(rows) + "\nпродовження опису\nПідпис: ____".encode())
    assert t.extract(t.REPORT, lines)["description"] == "Перший рядок продовження опису"
    card = [("№ з/п", "2.1"), ("Найменування заходу", "Захід"), ("Строк виконання", "Постійно"),
            ("Відповідальні за виконання", "Юридичне управління"), ("Індикатори виконання заходу", "Частка")]
    fields = t.extract(t.MEASURE_CARD, documents.read("b.xlsx", xlsx_header(card)))
    assert fields["indicator"] == "Частка" and fields["responsible"] == "Юридичне управління"


def test_not_the_template_lists_missing_fields() -> None:
    with pytest.raises(HTTPException) as e:
        t.extract(t.REPORT, documents.read("a.txt", txt([("Тема", "Довідка")])))
    assert e.value.status_code == 422
    assert "Стан виконання" in e.value.detail["missingFields"]


def test_unsupported_or_empty_file() -> None:
    with pytest.raises(HTTPException) as e:
        documents.read("a.jpg", b"\xff\xd8")
    assert e.value.status_code == 415
    with pytest.raises(HTTPException) as e:
        documents.read("a.txt", b"   \n")
    assert e.value.status_code == 422




def _report_rows(code: str, title: str, outcome: str, text: str) -> list[tuple[str, str]]:
    return [("Номер заходу", code), ("Найменування заходу", title), ("Звітний період", "ІІ півріччя 2026 р."),
            ("Стан виконання", outcome),
            ("Опис результату виконання заходу або пояснення причин невиконання", text)]


def test_report_by_code_is_a_draft_only(client: TestClient, model) -> None:
    sent = model(down)
    before = measure(client, "ex_com", "3.2")
    text = "Розміщено 3 роз'яснення на внутрішньому порталі, посилання: https://portal.example/coi"
    r = report(client, "ex_com", "zvit.docx", docx(_report_rows("3.2", "Роз'яснення", "Виконано", text)))
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["measureId"], d["measureSource"], d["period"]) == (before["id"], "document", "2026-H2")
    assert (d["outcome"], d["outcomeSource"], d["text"], d["textSource"]) == ("done", "rule", text, "document")
    assert d["modelUsed"] is False and d["draftKey"] and d["disclaimer"] and not sent

    after = measure(client, "ex_com", "3.2")
    assert after["status"] == before["status"] and after.get("evidence") == before.get("evidence")
    intake = [e for e in history(client, before["id"]) if e["action"] == "ai_intake_report"]
    assert intake and intake[0]["newValue"]["draftKey"] == d["draftKey"]

    edited = text + " Додатково 1 відеоролик."
    s = client.post(f"/api/measures/{before['id']}/submit", headers=H["ex_com"], data={
        "resultDescription": edited, "aiDraftKey": d["draftKey"], "documentTypes": "звіт",
        "documentDates": "2026-06-30"}, files=[("files", ("zvit.docx", b"x"))])
    assert s.status_code == 200, s.text
    submit = [e for e in history(client, before["id"]) if e["action"] == "submit"][0]["newValue"]
    assert submit["aiDraftEdited"] is True and submit["aiDraftMeasureChanged"] is False


def test_unknown_draft_key_is_rejected(client: TestClient) -> None:
    m = measure(client, "ex_com", "3.4")
    r = client.post(f"/api/measures/{m['id']}/submit", headers=H["ex_com"],
                    data={"nonExecutionReason": "Перенесено", "aiDraftKey": "nope"})
    assert r.status_code == 422
    assert measure(client, "ex_com", "3.4")["status"] == m["status"]


def test_foreign_measure_is_not_offered(client: TestClient, model) -> None:
    model(down)
    hr = measure(client, "ex_hr", "3.1")
    r = report(client, "ex_com", "zvit.txt", txt(_report_rows("3.1", hr["title"], "Не виконано", "Не проведено.")))
    d = r.json()
    assert all(c["code"] != "3.1" for c in d["candidates"])
    assert any("3.1" in w for w in d["warnings"])


def test_model_chooses_only_among_candidates(client: TestClient, model) -> None:
    sent = model(reply({"choice": 2}))
    rows = _report_rows("", "Інформаційні матеріали для працівників (пілот)", "Не виконано",
                        "Матеріали погоджуються, публікацію перенесено на січень.")
    d = report(client, "ex_com", "zvit.txt", txt(rows)).json()
    listed = json.loads(sent[0]["messages"][1]["content"])["заходи"]
    assert d["measureSource"] == "model" and d["outcome"] == "not_done"
    assert d["measureId"] == next(c["measureId"] for c in d["candidates"] if c["code"] == listed[1]["код"])


def test_model_answer_out_of_range_falls_back(client: TestClient, model) -> None:
    model(reply({"choice": 7}))
    rows = _report_rows("", "Щось зовсім інше про паливо і склади", "Виконано", "Зроблено 2 звірки, протокол №5.")
    d = report(client, "ex_com", "zvit2.txt", txt(rows)).json()
    assert d["measureSource"] in (None, "rule") and d["warnings"]


def test_vague_description_is_rewritten_without_new_numbers(client: TestClient, model) -> None:
    hr = measure(client, "ex_hr", "3.1")
    rows = _report_rows("3.1", hr["title"], "Виконано", hr["title"]) + [
        ("Підтвердні документи", "Протокол комісії №14 від 02.10.2026")]
    model(reply({"text": "Оприлюднено 7 рішень, протокол №14 від 02.10.2026."}))
    d = report(client, "ex_hr", "a.txt", txt(rows)).json()
    assert d["textSource"] == "document"  # «7» is not in the document: the rewrite is dropped

    rows[-1] = ("Підтвердні документи", "Протокол комісії №14 від 02.10.2026 (витяг)")  # new prompt, not cached
    model(reply({"text": "Рішення комісії оприлюднено на порталі; підстава — протокол №14 від 02.10.2026."}))
    d = report(client, "ex_hr", "b.txt", txt(rows)).json()
    assert d["textSource"] == "model" and "№14" in d["text"] and d["documentText"] == hr["title"]


def test_report_roles_and_validation(client: TestClient) -> None:
    rows = _report_rows("3.2", "x", "Виконано", "y")
    assert report(client, "coord", "a.txt", txt(rows)).status_code == 403
    r = report(client, "ex_com", "a.txt", txt([("Тема", "Довідка")]))
    assert r.status_code == 422 and r.json()["detail"]["missingFields"]




def _program(client: TestClient) -> str:
    return client.get("/api/programs", headers=H["coord"]).json()[0]["id"]


def test_measure_card_draft(client: TestClient, model) -> None:
    model(down)
    pid = _program(client)
    total = client.get(f"/api/programs/{pid}/passport", headers=H["coord"]).json()["totals"]["measures"]
    card = [("Розділ програми", "Розділ 2"), ("Найменування заходу", "Запровадити звірку актів списання ПММ"),
            ("Строк виконання", "IV квартал 2026"),
            ("Відповідальні за виконання", "Управління логістики та матеріального забезпечення; Відділ уявний"),
            ("Індикатори виконання заходу", "Частка звірених актів"),
            ("Корупційний ризик", "КР-05 Завищення обсягів списання"), ("Примітка", "реєстр звірок")]
    r = client.post("/api/ai/intake/measure", headers=H["coord"], data={"programId": pid},
                    files={"file": ("kartka.xlsx", xlsx_header(card))})
    assert r.status_code == 200, r.text
    d = r.json()
    v, f = d["measure"], d["fields"]
    assert v["code"].startswith("2.") and v["plannedDeadline"] == "2026-12-31" and v["isPermanent"] is False
    assert len(v["assignments"]) == 1 and v["assignments"][0]["isResponsible"]
    assert v["riskId"] and f["risk"]["source"] == "rule" and f["title"]["source"] == "document"
    assert v["requiredEvidence"] == "реєстр звірок"
    assert any("Відділ уявний" in w for w in d["warnings"])
    assert client.get(f"/api/programs/{pid}/passport", headers=H["coord"]).json()["totals"]["measures"] == total


def test_measure_card_section_from_model(client: TestClient, model) -> None:
    sent = model(reply({"section": 3}))
    card = [("Найменування заходу", "Провести тренінг з доброчесності для нових працівників"),
            ("Строк виконання", "Постійно"), ("Відповідальні за виконання", "Управління персоналу"),
            ("Індикатори виконання заходу", "Частка навчених працівників")]
    d = client.post("/api/ai/intake/measure", headers=H["coord"], data={"programId": _program(client)},
                    files={"file": ("kartka.docx", docx(card))}).json()
    assert d["fields"]["section"]["source"] == "model" and d["measure"]["code"].startswith("3.")
    assert d["measure"]["isPermanent"] is True and d["modelUsed"] is True and sent


def test_measure_card_requires_coordinator(client: TestClient) -> None:
    r = client.post("/api/ai/intake/measure", headers=H["ex_com"], data={"programId": _program(client)},
                    files={"file": ("k.txt", b"x")})
    assert r.status_code == 403
