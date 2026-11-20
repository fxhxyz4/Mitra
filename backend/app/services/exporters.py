import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_TYPE = "application/pdf"
FONTS = Path(__file__).resolve().parent.parent / "fonts"


def to_xlsx(sheets: dict[str, list[list]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name[:31])  # Excel sheet name limit
        for row in rows:
            ws.append(row)
        if rows:
            for c in ws[1]:
                c.font = Font(bold=True)
            ws.freeze_panes = "A2"
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 8), 60)
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(sheets: dict[str, list[list]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    for i, (name, rows) in enumerate(sheets.items()):
        if i:
            w.writerow([])
        w.writerow([f"# {name}"])
        w.writerows([["" if v is None else v for v in r] for r in rows])
    return "﻿" + buf.getvalue()


class Docx:

    def __init__(self) -> None:
        from docx import Document
        from docx.shared import Pt

        self.doc = Document()
        style = self.doc.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)

    def heading(self, text: str, level: int = 1) -> None:
        self.doc.add_heading(text, level=level)

    def para(self, text: str, bold: bool = False) -> None:
        p = self.doc.add_paragraph()
        p.add_run(text).bold = bold

    def image(self, data: bytes, width_cm: float = 3.5) -> None:
        from docx.shared import Cm

        self.doc.add_picture(io.BytesIO(data), width=Cm(width_cm))

    def bullets(self, items: Iterable[str]) -> None:
        for t in items:
            self.doc.add_paragraph(t, style="List Bullet")

    def table(self, rows: list[list]) -> None:
        if not rows:
            return
        t = self.doc.add_table(rows=0, cols=len(rows[0]))
        t.style = "Table Grid"
        for i, row in enumerate(rows):
            cells = t.add_row().cells
            for c, v in zip(cells, row, strict=False):
                c.text = "" if v is None else str(v)
                if i == 0:
                    for r in c.paragraphs[0].runs:
                        r.bold = True
        self.doc.add_paragraph()

    def bytes(self) -> bytes:
        buf = io.BytesIO()
        self.doc.save(buf)
        return buf.getvalue()


class Pdf:
    FONT = "DejaVuSerif"
    HEADING_SIZE: ClassVar[dict[int, int]] = {0: 16, 1: 14, 2: 12}
    TEXT_SIZE = 11
    TABLE_SIZE = 8

    def __init__(self) -> None:
        from fpdf import FPDF

        self.pdf = FPDF(format="A4")
        self.pdf.set_margins(15, 15, 15)
        self.pdf.set_auto_page_break(True, margin=15)
        self.pdf.add_font(self.FONT, "", str(FONTS / "DejaVuSerif.ttf"))
        self.pdf.add_font(self.FONT, "B", str(FONTS / "DejaVuSerif-Bold.ttf"))
        self.pdf.add_page()

    def _text(self, text: str, size: float, bold: bool = False, align: str = "L") -> None:
        self.pdf.set_font(self.FONT, "B" if bold else "", size)
        self.pdf.multi_cell(0, size * 0.5, text, align=align, new_x="LMARGIN", new_y="NEXT")

    def heading(self, text: str, level: int = 1) -> None:
        self.pdf.ln(3)
        self._text(text, self.HEADING_SIZE.get(level, 12), bold=True, align="C" if level == 0 else "L")
        self.pdf.ln(2)

    def para(self, text: str, bold: bool = False) -> None:
        self._text(text, self.TEXT_SIZE, bold)
        self.pdf.ln(1.5)

    def image(self, data: bytes, width_cm: float = 3.5) -> None:
        from PIL import Image

        self.pdf.image(Image.open(io.BytesIO(data)).convert("L"), w=width_cm * 10)
        self.pdf.ln(1)

    def bullets(self, items: Iterable[str]) -> None:
        for t in items:
            self._text(f"•  {t}", self.TEXT_SIZE)
        self.pdf.ln(1.5)

    def table(self, rows: list[list]) -> None:
        if not rows:
            return
        cols = len(rows[0])
        self.pdf.set_font(self.FONT, "", self.TABLE_SIZE)
        with self.pdf.table(col_widths=self._widths(rows, cols), text_align="LEFT",
                            line_height=self.TABLE_SIZE * 0.5, padding=1) as t:
            for row in rows:
                cells = t.row()
                for i in range(cols):
                    v = row[i] if i < len(row) else None
                    cells.cell("" if v is None else str(v))
        self.pdf.ln(3)

    MIN_COL_MM = 17

    def _widths(self, rows: list[list], cols: int) -> tuple[float, ...]:
        longest = [max(len(str(r[i] or "")) for r in rows if i < len(r)) for i in range(cols)]
        raw = [min(max(n, 1), 60) for n in longest]
        free = self.pdf.epw - self.MIN_COL_MM * cols
        return tuple(self.MIN_COL_MM + free * w / sum(raw) for w in raw)

    def bytes(self) -> bytes:
        return bytes(self.pdf.output())
