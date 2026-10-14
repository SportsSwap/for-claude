"""[ClientCode]_[FY]_[DocType]_[YYYY-MM-DD].ext"""

from __future__ import annotations

from datetime import date

from ..dates import fy_label
from ..privacy.guard import check_text


def filed_name(client_code: str, income_year: int, doc_type: str, doc_date: date, suffix: str,
               existing: set[str]) -> str:
    stem = f"{client_code}_{fy_label(income_year)}_{doc_type}_{doc_date.isoformat()}"
    ext = suffix.lower()
    name = f"{stem}{ext}"
    n = 2
    while name in existing:
        name = f"{stem}_{n:02d}{ext}"
        n += 1
    check_text(name, "filename")
    return name
