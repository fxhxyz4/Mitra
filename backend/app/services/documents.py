import io
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

Table = list[list[str]]


@dataclass
class Document:
    lines: list[str] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)

    @property
    def text(self) -> str:
        rows = ["\t".join(row) for table in self.tables for row in table]
        return "\n".join([*self.lines, *rows])


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def _docx(data: bytes) -> Document:
    from docx import Document as Docx

    d = Docx(io.BytesIO(data))
    tables = []
    for t in d.tables:
        rows = []
        for r in t.rows:
            cells: list[str] = []
            seen: set[int] = set()
            for c in r.cells:
                if id(c._tc) in seen:
                    continue
                seen.add(id(c._tc))
                cells.append(_clean(c.text))
            rows.append(cells)
        tables.append(rows)
    return Document(lines=[p.text.strip() for p in d.paragraphs if p.text.strip()], tables=tables)


def _xlsx(data: bytes) -> Document:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    tables = []
    for ws in wb.worksheets:
        rows = [[_clean(v) for v in row] for row in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        if rows:
            tables.append(rows)
    return Document(tables=tables)


def _pdf(data: bytes) -> Document:
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    return _txt(text.encode())


def _txt(data: bytes) -> Document:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(422, "Не вдалося прочитати текстовий файл")
    return Document(lines=[line.strip() for line in text.splitlines() if line.strip()])


READERS = {".docx": _docx, ".xlsx": _xlsx, ".pdf": _pdf, ".txt": _txt}


def read(file_name: str, data: bytes) -> Document:
    reader = READERS.get(Path(file_name).suffix.lower())
    if not reader:
        raise HTTPException(415, f"Формат не підтримується. Допустимі: {', '.join(READERS)}")
    try:
        doc = reader(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Не вдалося прочитати файл: {type(e).__name__}") from e
    if not doc.text.strip():
        raise HTTPException(422, "У файлі немає тексту (скановані документи без текстового шару не приймаються)")
    return doc
