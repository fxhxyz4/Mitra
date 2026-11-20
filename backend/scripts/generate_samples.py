"""
    python -m scripts.generate_samples                 # датасет у data/zrazky-dataset/{dev,test} + expected.json
    python -m scripts.generate_samples --zrazky ../docs/zrazky   # файли-зразки для документації
"""
import argparse
import json
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from docx import Document as Docx
from openpyxl import Workbook

from app.services import dataset

SEED = 20261117
BANNER = "Синтетичний документ. Умовне відомство сектору безпеки і оборони (вигадане)."
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "zrazky-dataset"
TEST_SHARE = 0.3

Rows = list[tuple[str, str]]

REPORT_LABELS = {
    "standard": ("Номер заходу", "Найменування заходу", "Звітний період", "Фактичний строк виконання",
                 "Стан виконання", "Опис результату виконання заходу або пояснення причин невиконання",
                 "Підтвердні документи"),
    "alt": ("№ заходу", "Назва заходу", "Період", "Фактичний термін виконання", "Стан",
            "Опис результатів виконання / інформація про причини невиконання", "Підтвердні матеріали"),
}
CARD_LABELS = ("Розділ програми", "№ з/п", "Найменування заходу", "Строк виконання", "Відповідальні за виконання",
               "Індикатори виконання заходу", "Корупційний ризик", "Примітка")
OUTCOME_TEXT = {
    "vykonano": ("Виконано", "виконано", "Захід виконано в повному обсязі"),
    "ne_vykonano": ("Не виконано", "не виконано"),
    "chastkovo": ("Виконано частково", "частково виконано"),
    "v_roboti": ("Не виконано", "не виконано (у роботі)"),
}
EXPECTED_OUTCOME = {"vykonano": "done", "ne_vykonano": "not_done", "chastkovo": "not_done", "v_roboti": "not_done"}
PERIOD_TEXT = ("І півріччя 2026 р.", "2026-H1", "перше півріччя 2026 року")


@dataclass
class Case:
    file: str
    template: str
    token: str
    expect_status: int = 200
    expected: dict[str, Any] = field(default_factory=dict)




def write_docx(path: Path, heading: str, rows: Rows, header_layout: bool) -> None:
    d = Docx()
    d.add_paragraph(BANNER)
    d.add_heading(heading, level=1)
    if header_layout:
        table = d.add_table(rows=2, cols=len(rows))
        for i, (label, value) in enumerate(rows):
            table.cell(0, i).text, table.cell(1, i).text = label, value
    else:
        table = d.add_table(rows=len(rows), cols=2)
        for i, (label, value) in enumerate(rows):
            table.cell(i, 0).text, table.cell(i, 1).text = label, value
    table.style = "Table Grid"
    d.save(path)


def write_xlsx(path: Path, heading: str, rows: Rows, header_layout: bool) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Документ"
    ws.append([BANNER])
    ws.append([heading])
    if header_layout:
        ws.append([label for label, _ in rows])
        ws.append([value for _, value in rows])
    else:
        for row in rows:
            ws.append(list(row))
    wb.save(path)


def write_txt(path: Path, heading: str, rows: Rows, header_layout: bool) -> None:
    lines = [BANNER, heading, *(f"{label}: {value}" for label, value in rows)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


WRITERS: dict[str, Callable[[Path, str, Rows, bool], None]] = {"docx": write_docx, "xlsx": write_xlsx, "txt": write_txt}




def load() -> dict[str, Any]:
    return json.loads(dataset.DEFAULT_FILE.read_text(encoding="utf-8"))["tablytsi"]


def paraphrase(title: str, rnd: random.Random) -> str:
    words = title.split()
    if rnd.random() < 0.5:
        return " ".join(words[: max(6, len(words) * 2 // 3)]) + "…"
    return "Щодо заходу: " + " ".join(words[1:])


class Index:
    def __init__(self, t: dict[str, Any]) -> None:
        self.t = t
        self.units = {u["id"]: u["nazva"] for u in t["pidrozdily"]}
        self.user_unit = {u["id"]: u["pidrozdil_id"] for u in t["korystuvachi"]}
        self.sections = {r["kod"]: r["nomer"] for r in t["rozdily"]}
        self.risks = {r["id"]: r for r in t["ryzyky"]}
        self.evidence: dict[str, list[str]] = {}
        for e in t["pidtverdzhennia"]:
            ref = e["nazva"] + (f", {e['data_dokumenta']}" if e["data_dokumenta"] else "")
            self.evidence.setdefault(e["zakhid_id"], []).append(ref)

    def code(self, z: dict[str, Any]) -> str:
        return f"{self.sections[z['rozdil_kod']]}.{z['nomer_u_rozdili']}"

    def token(self, z: dict[str, Any]) -> str:
        return dataset.executor_token(self.user_unit[z["vykonavets_korystuvach_id"]])

    def unit_names(self, z: dict[str, Any]) -> list[str]:
        ids = [z["vidpovidalnyi_pidrozdil_id"], *(u.strip() for u in z["spivvykonavtsi"].split(";") if u.strip())]
        return [self.units[i] for i in ids]


def report_rows(ix: Index, z: dict[str, Any], v: dict[str, Any], rnd: random.Random,
                with_code: bool, title: str, labels: tuple[str, ...]) -> Rows:
    values = (
        ix.code(z) if with_code else "",
        title,
        rnd.choice(PERIOD_TEXT),
        v["fakt_data"],
        rnd.choice(OUTCOME_TEXT[v["status"]]),
        v["opys_rezultatu"],
        "; ".join(ix.evidence.get(z["id"], [])),
    )
    rows = [(label, value) for label, value in zip(labels, values, strict=True) if value]
    if rnd.random() < 0.3:  # column order differs between units
        rows = [rows[1], rows[0], *rows[2:]] if with_code else rows[::-1]
    return rows


def card_rows(ix: Index, z: dict[str, Any], rnd: random.Random) -> tuple[Rows, str | None]:
    risk = ix.risks.get(z["ryzyk_id"])
    risk_text = ""
    if risk:
        risk_text = rnd.choice([f"{risk['id']} {risk['nazva']}", risk["nazva"], risk["zmist"]])
    indicator = z["indykator_vykonannia"] or (risk["indykator_ryzyku"] if risk else "")
    values = (
        f"Розділ {ix.sections[z['rozdil_kod']]}" if rnd.random() < 0.6 else "",
        ix.code(z) if rnd.random() < 0.5 else str(z["nomer_u_rozdili"]),
        z["zmist"],
        z["strok_tekst"],
        "; ".join(ix.unit_names(z)),
        indicator,
        risk_text,
        z["potribni_pidtverdzhennia"],
    )
    return [(label, value) for label, value in zip(CARD_LABELS, values, strict=True) if value], \
        risk["id"] if risk else None


def build(out: Path) -> list[Case]:
    t = load()
    ix = Index(t)
    rnd = random.Random(SEED)
    zakhody = {z["id"]: z for z in t["zakhody"]}
    cases: list[Case] = []
    for split in ("dev", "test"):
        (out / split).mkdir(parents=True, exist_ok=True)

    def emit(name: str, fmt: str, heading: str, rows: Rows, header: bool, case: Case) -> None:
        split = "test" if rnd.random() < TEST_SHARE else "dev"
        case.file = f"{split}/{name}.{fmt}"
        WRITERS[fmt](out / case.file, heading, rows, header)
        cases.append(case)

    for n, v in enumerate(t["vykonannia_2026_h1"]):
        z = zakhody[v["zakhid_id"]]
        if not v["opys_rezultatu"]:
            continue
        variant = n % 4
        with_code = variant == 0
        title = paraphrase(z["zmist"], rnd) if variant == 2 else z["zmist"]
        labels = REPORT_LABELS["alt" if variant == 3 else "standard"]
        fmt = ("docx", "xlsx", "txt", "docx")[variant]
        rows = report_rows(ix, z, v, rnd, with_code, title, labels)
        emit(f"A-{z['id']}", fmt, "Звіт про виконання заходу антикорупційної програми", rows, fmt == "xlsx",
             Case("", "A", ix.token(z), expected={
                 "measureCode": ix.code(z), "outcome": EXPECTED_OUTCOME[v["status"]], "period": "2026-H1",
                 "withCode": with_code, "paraphrased": variant == 2}))

    for n, z in enumerate(t["zakhody"]):
        fmt = ("docx", "xlsx", "txt")[n % 3]
        rows, risk = card_rows(ix, z, rnd)
        emit(f"B-{z['id']}", fmt, "Картка заходу антикорупційної програми", rows, fmt != "txt",
             Case("", "B", "demo-coord", expected={
                 "section": ix.sections[z["rozdil_kod"]], "code": ix.code(z), "title": z["zmist"],
                 "deadline": z["strok_data"] or "2027-12-31", "isPermanent": z["strok_typ"] != "data",
                 "units": ix.unit_names(z), "risk": risk}))

    # Negative cases: wrong template, empty description, a measure of another unit.
    z = zakhody["Z-01"]
    emit("N-not-template", "txt", "Довідка", [("Тема", z["zmist"]), ("Зміст", "Довільний текст без полів звіту")],
         False, Case("", "A", ix.token(z), expect_status=422))
    emit("N-empty-description", "docx", "Звіт", [("Найменування заходу", z["zmist"]), ("Звітний період", "2026-H1"),
                                                  ("Стан виконання", "Не виконано")],
         False, Case("", "A", ix.token(z), expect_status=422))
    other = zakhody["Z-14"]
    v = next(x for x in t["vykonannia_2026_h1"] if x["zakhid_id"] == other["id"])
    emit("N-foreign-measure", "docx", "Звіт", report_rows(ix, other, v, rnd, True, other["zmist"],
                                                           REPORT_LABELS["standard"]),
         False, Case("", "A", ix.token(z), expected={"foreignCode": ix.code(other)}))
    return cases



DEMO_REPORT: Rows = [
    ("Номер заходу", "2.2"),
    ("Найменування заходу", "Щокварталу оприлюднювати аналіз закупівель з одним учасником із зазначенням причин"),
    ("Звітний період", "ІІ півріччя 2026 р."),
    ("Фактичний строк виконання", "31.12.2026"),
    ("Стан виконання", "Виконано"),
    ("Опис результату виконання заходу або пояснення причин невиконання",
     "У ІІ півріччі 2026 р. оприлюднено 2 квартальні аналізи закупівель з одним учасником (за ІІІ і IV квартали). "
     "Проаналізовано 41 процедуру, для 12 зазначено причини участі одного учасника. "
     "Частка процедур з одним учасником зменшилась з 31 % до 27 %."),
    ("Підтвердні документи", "Аналіз закупівель з одним учасником за ІІІ квартал 2026 р. (умовний), "
                             "посилання на оприлюднення від 15.10.2026; аналіз за IV квартал 2026 р. (умовний)"),
]
DEMO_CARD: Rows = [
    ("Розділ програми", "Розділ 2"),
    ("№ з/п", ""),
    ("Найменування заходу", "Запровадити звірку актів виконаних ремонтних робіт з дефектними відомостями "
                            "до їх підписання"),
    ("Строк виконання", "IV квартал 2026"),
    ("Відповідальні за виконання", "Державне підприємство «Умовний ремонтний завод»; Управління внутрішнього аудиту"),
    ("Індикатори виконання заходу", "Частка актів виконаних робіт, звірених з дефектними відомостями"),
    ("Корупційний ризик", "KR14 Завищення обсягів ремонтних робіт"),
    ("Примітка", "реєстр звірених актів; наказ про порядок звірки (умовний)"),
]


def write_samples(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    write_docx(target / "zrazok-A-zvit-vykonavtsia.docx", "Звіт про виконання заходу антикорупційної програми",
               DEMO_REPORT, header_layout=False)
    card = [(label, value) for label, value in DEMO_CARD if value]
    write_docx(target / "zrazok-B-kartka-zakhodu.docx", "Картка заходу антикорупційної програми", card,
               header_layout=False)
    write_xlsx(target / "zrazok-B-kartka-zakhodu.xlsx", "Картка заходу антикорупційної програми", card,
               header_layout=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--zrazky", type=Path, help="записати лише файли-зразки в цю теку")
    args = parser.parse_args()
    if args.zrazky:
        write_samples(args.zrazky)
        print(f"Зразки: {args.zrazky}")
        return
    cases = build(args.out)
    (args.out / "expected.json").write_text(
        json.dumps([asdict(c) for c in cases], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(cases)} документів: {args.out}")


if __name__ == "__main__":
    main()
