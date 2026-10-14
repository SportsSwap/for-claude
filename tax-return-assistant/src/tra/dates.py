"""Date parsing and Australian income year helpers.

An income year is named by the year it ends: FY2026 runs 1 July 2025 to
30 June 2026.
"""

from __future__ import annotations

import re
from datetime import date, datetime

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

DATE_PATTERN = r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2} [A-Za-z]{3,9} \d{4}"

_LABELLED = re.compile(
    rf"(?:statement date|payment date|date paid|issue date)\s*[:\-]?\s*({DATE_PATTERN})", re.I)
_PERIOD_END = re.compile(rf"(?:\bto|period ending)\s*[:\-]?\s*({DATE_PATTERN})", re.I)


def parse_date(raw: str) -> date | None:
    s = str(raw).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.strptime(s, "%Y-%m-%d").date()
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
        if m:
            day, month, year = (int(g) for g in m.groups())
            return date(year + 2000 if year < 100 else year, month, day)
        m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]{3,9}) (\d{4})", s)
        if m and m.group(2)[:3].lower() in _MONTHS:
            return date(int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1)))
    except ValueError:
        return None
    return None


def find_doc_date(text: str) -> date | None:
    """The document's own date: a labelled date first, otherwise the end of its period."""
    for pattern in (_LABELLED, _PERIOD_END):
        for m in pattern.finditer(text):
            found = parse_date(m.group(1))
            if found:
                return found
    return None


def fy_label(year: int) -> str:
    return f"FY{year}"


def fy_bounds(year: int) -> tuple[date, date]:
    return date(year - 1, 7, 1), date(year, 6, 30)


def days_in_fy(year: int) -> int:
    start, end = fy_bounds(year)
    return (end - start).days + 1
