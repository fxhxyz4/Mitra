import calendar
import re
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException

from .documents import Document, Table
from .rules import similarity


@dataclass(frozen=True)
class FieldSpec:
    key: str
    title: str
    aliases: tuple[str, ...]
    required: bool = False


@dataclass(frozen=True)
class Template:
    code: str
    title: str
    fields: tuple[FieldSpec, ...]


REPORT = Template("A", "Звіт виконавця про виконання заходу", (
    FieldSpec("code", "Номер заходу", ("номер заходу", "№ заходу", "№ з п", "№")),
    FieldSpec("title", "Найменування заходу", ("найменування заходу", "назва заходу", "зміст заходу", "захід"), True),
    FieldSpec("period", "Звітний період", ("звітний період", "період"), True),
    FieldSpec("actual_date", "Фактичний строк виконання", ("фактичний строк", "фактичний термін")),
    FieldSpec("outcome", "Стан виконання", ("стан виконання", "стан"), True),
    FieldSpec("description", "Опис результату виконання заходу або пояснення причин невиконання",
              ("опис результат", "пояснення причин", "причини невиконання", "інформація про причини"), True),
    FieldSpec("evidence", "Підтвердні документи", ("підтвердні документи", "підтвердні матеріали")),
))

MEASURE_CARD = Template("B", "Картка заходу антикорупційної програми", (
    FieldSpec("section", "Розділ програми", ("розділ програми", "розділ")),
    FieldSpec("code", "№ з/п", ("№ з п", "номер заходу", "№")),
    FieldSpec("title", "Найменування заходу", ("найменування заходу", "назва заходу", "заходи впливу",
                                                "зміст заходу"), True),
    FieldSpec("deadline", "Строк виконання", ("строк виконання", "терміни", "строк", "термін"), True),
    FieldSpec("responsible", "Відповідальні за виконання", ("відповідальні", "відповідальний"), True),
    FieldSpec("indicator", "Індикатори виконання заходу", ("індикатор",), True),
    FieldSpec("risk", "Корупційний ризик", ("корупційний ризик",)),
    FieldSpec("evidence", "Підтвердні документи / примітка", ("підтвердні документи", "підтвердні матеріали",
                                                               "примітка")),
))


def normalize(text: str) -> str:
    text = re.sub(r"['’`ʼ]", "ʼ", text.lower())
    return " ".join(re.findall(r"[\wʼ№]+", text))


def _starts_with(words: list[str], alias: list[str]) -> bool:
    return len(words) >= len(alias) and all(w.startswith(a) for w, a in zip(words, alias, strict=False))


def field_for(template: Template, label: str) -> str | None:
    words = normalize(label).split()
    best, best_len = None, 0
    for f in template.fields:
        for alias in f.aliases:
            a = normalize(alias)
            if _starts_with(words, a.split()) and len(a) > best_len:
                best, best_len = f.key, len(a)
    return best


def _join(cells: list[str]) -> str:
    out: list[str] = []
    for c in cells:
        if c and c not in out:
            out.append(c)
    return " ".join(out)


def _from_table(template: Template, table: Table, out: dict[str, str]) -> None:
    for i, header in enumerate(table):
        keys = [field_for(template, c) if c else None for c in header]
        if sum(k is not None for k in keys) >= 3:  # header row of a «one measure per row» table
            row = next((r for r in table[i + 1:] if any(r)), None)
            for k, v in zip(keys, row or [], strict=False):
                if k and v:
                    out.setdefault(k, v)
            return
    for r in table:  # «поле | значення» rows
        if len(r) >= 2 and (key := field_for(template, r[0])):
            out.setdefault(key, _join(r[1:]))


_LABEL_LINE = re.compile(r"^([^:\t]{1,90})[:\t]\s*(.*)$")
_FOOTER = re.compile(r"^(виконавець|підпис|дата|посада|склав|підготував|керівник)\b")


def _from_lines(template: Template, lines: list[str], out: dict[str, str]) -> None:
    current: str | None = None
    found: dict[str, list[str]] = {}
    for line in lines:
        m = _LABEL_LINE.match(line)
        key = field_for(template, m[1]) if m else None
        if m and key:
            current = key if key not in found else None
            if current:
                found[current] = [m[2]] if m[2] else []
        elif m and _FOOTER.match(normalize(m[1])):
            current = None
        elif current:
            found[current].append(line)
    for k, v in found.items():
        out.setdefault(k, " ".join(v).strip())


def extract(template: Template, doc: Document) -> dict[str, str]:
    out: dict[str, str] = {}
    for table in doc.tables:
        _from_table(template, table, out)
    _from_lines(template, doc.lines, out)
    out = {k: v for k, v in out.items() if k and v.strip()}
    missing = [f.title for f in template.fields if f.required and f.key not in out]
    if missing:
        raise HTTPException(422, {
            "message": f"Документ не відповідає зразку {template.code} «{template.title}»",
            "missingFields": missing,
        })
    return out


_CODE = re.compile(r"(?<![\d.])([1-3])\s*[.,]\s*(\d{1,3})(?![\d.])")
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "і": 1, "іі": 2, "ііі": 3, "iv": 4, "іv": 4}


def measure_code(value: str | None, section: int | None = None) -> str | None:
    if not value:
        return None
    if m := _CODE.search(value):
        return f"{m[1]}.{int(m[2])}"
    if section and (m := re.fullmatch(r"\D*(\d{1,3})\D*", value)):
        return f"{section}.{int(m[1])}"
    return None


def section_number(value: str | None) -> int | None:
    if not value:
        return None
    if m := re.search(r"\b([1-3])\b", value):
        return int(m[1])
    for word in normalize(value).split():
        if _ROMAN.get(word, 0) in (1, 2, 3):
            return _ROMAN[word]
    return None


_YEAR = r"(20\d{2})"
_FIRST = r"(?:i|і|1|перше|першого|перший)"
_SECOND = r"(?:ii|іі|2|друге|другого|другий)"


def half_year(value: str | None) -> str | None:
    if not value:
        return None
    if m := re.search(r"(20\d{2})\s*-\s*H([12])", value, re.IGNORECASE):
        return f"{m[1]}-H{m[2]}"
    v = normalize(value)
    if m := re.search(rf"\b{_SECOND}\s+півріч\w*\s+{_YEAR}", v):
        return f"{m[1]}-H2"
    if m := re.search(rf"\b{_FIRST}\s+півріч\w*\s+{_YEAR}", v):
        return f"{m[1]}-H1"
    return None


def outcome(value: str | None) -> str | None:
    v = normalize(value or "")
    if re.search(r"\bне\s*викона|\bневикона|частков", v):
        return "not_done"
    if re.search(r"\bвикона(но|ний|на)\b", v):
        return "done"
    return None


_PERIODIC = re.compile(r"постійно|щоквартал|щомісяц|щотижн|щороку|щорічно|щопівроку|періодично|щодня")
_MONTHS = ("січ", "лют", "берез", "квіт", "трав", "черв", "лип", "серп", "верес", "жовт", "листопад", "груд")


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def deadline(value: str | None, program_end: date) -> tuple[date | None, bool]:
    v = normalize(value or "")
    if not v:
        return None, False
    if _PERIODIC.search(v):
        return program_end, True
    if m := re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})", value or ""):
        try:
            return date(int(m[3]), int(m[2]), int(m[1])), False
        except ValueError:
            return None, False
    if m := re.search(r"(20\d{2})-(\d{2})-(\d{2})", value or ""):
        try:
            return date(int(m[1]), int(m[2]), int(m[3])), False
        except ValueError:
            return None, False
    if m := re.search(rf"\b(iv|іv|iii|ііі|ii|іі|i|і|[1-4])\s+квартал\w*\s+{_YEAR}", v):
        q = int(m[1]) if m[1].isdigit() else _ROMAN[m[1]]
        return _month_end(int(m[2]), q * 3), False
    if hy := half_year(value):
        from .. import halfyear

        return halfyear.end(hy), False
    if m := re.search(rf"\b([а-яіїєґ]+)\s+{_YEAR}", v):
        month = next((i for i, stem in enumerate(_MONTHS, 1) if m[1].startswith(stem)), None)
        if month:
            return _month_end(int(m[2]), month), False
    return None, False


UNIT_MATCH_THRESHOLD = 0.75


def unit_parts(value: str) -> list[str]:
    return [p.strip(" .") for p in re.split(r"[;,\n]", value) if p.strip(" .")]


def unit_score(part: str, name: str) -> float:
    a, b = normalize(part), normalize(name)
    return 1.0 if a and (a in b or b in a) else round(similarity(a, b), 2)
