"""Dividend statements."""

from __future__ import annotations

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, first_line, require_redacted, search, status

_FIELDS = [
    (rf"^Unfranked amount\s+({AMOUNT})", "income.div_unfranked", "unfranked amount"),
    (rf"^Franked amount\s+({AMOUNT})", "income.div_franked", "franked amount"),
    (rf"^Franking credit\s+({AMOUNT})", "income.franking_credit", "franking credit"),
    (rf"^TFN withheld\s+({AMOUNT})", "income.div_tfn_withheld", "TFN withheld"),
]


class DividendExtractor:
    doc_types = frozenset({"DIVSTMT"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        company = first_line(rt) or "Company"
        result = ExtractResult(doc_date=when)
        found = 0
        for pattern, key, label in _FIELDS:
            hit = search(rt, pattern)
            if not hit:
                continue
            page, m = hit
            found += key != "income.div_tfn_withheld"
            value = amount(m.group(1))
            if value != 0:
                result.figures.append(figure(key, f"{company} – {label}", value, doc_id, page, when))
        result.parse_status = status(found, 3)
        return result
