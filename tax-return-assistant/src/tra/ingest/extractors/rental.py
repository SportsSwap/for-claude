"""Property manager / rental statements."""

from __future__ import annotations

import re

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, lines, require_redacted

_GROSS = re.compile(rf"^Total rent received\s+({AMOUNT})$", re.I)
_LINE = re.compile(rf"^(?P<desc>[A-Za-z].*?)\s+(?P<amt>{AMOUNT})$")
_STOP = re.compile(r"^(?:Total expenses|Net to owner|Net)\b", re.I)


class RentalExtractor:
    doc_types = frozenset({"RENTSTMT"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        result = ExtractResult(doc_date=when)
        in_expenses = False
        for page, line in lines(rt):
            m = _GROSS.match(line)
            if m:
                result.figures.append(figure("rent.gross", "Total rent received", amount(m.group(1)), doc_id, page, when))
                result.parse_status = "parsed"
                in_expenses = True
                continue
            if not in_expenses:
                continue
            if _STOP.match(line):
                in_expenses = False
                continue
            m = _LINE.match(line)
            if m and amount(m.group("amt")) != 0:
                key = "rent.interest" if "interest" in m.group("desc").lower() else "rent.other"
                result.figures.append(figure(key, m.group("desc"), amount(m.group("amt")), doc_id, page, when))
        return result
