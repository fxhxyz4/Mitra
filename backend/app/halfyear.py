import re
from datetime import date

_RE = re.compile(r"^(\d{4})-H([12])$")


def of(d: date) -> str:
    return f"{d.year}-H{1 if d.month <= 6 else 2}"


def parse(period: str) -> tuple[int, int]:
    m = _RE.match(period)
    if not m:
        raise ValueError(f"Invalid half-year '{period}', expected YYYY-H1 or YYYY-H2")
    return int(m[1]), int(m[2])


def start(period: str) -> date:
    y, h = parse(period)
    return date(y, 1 if h == 1 else 7, 1)


def end(period: str) -> date:
    """Кінцева дата півріччя: 30 червня або 31 грудня."""
    y, h = parse(period)
    return date(y, 6, 30) if h == 1 else date(y, 12, 31)


def between(a: date, b: date) -> list[str]:
    out, cur = [], of(a)
    while start(cur) <= b:
        out.append(cur)
        y, h = parse(cur)
        cur = f"{y}-H2" if h == 1 else f"{y + 1}-H1"
    return out
