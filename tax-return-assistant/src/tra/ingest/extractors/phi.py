"""Private health insurance statement. The membership number is never read."""

from __future__ import annotations

import re

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, lines, require_redacted, search, status

_P1 = r"1 July\s*-\s*31 March"
_P2 = r"1 April\s*-\s*30 June"
_FIELDS = [
    (rf"^Premiums eligible for rebate {_P1}\s+({AMOUNT})$", "phi.premiums_p1", "premiums 1 Jul–31 Mar"),
    (rf"^Rebate received {_P1}\s+({AMOUNT})$", "phi.rebate_p1", "rebate received 1 Jul–31 Mar"),
    (rf"^Premiums eligible for rebate {_P2}\s+({AMOUNT})$", "phi.premiums_p2", "premiums 1 Apr–30 Jun"),
    (rf"^Rebate received {_P2}\s+({AMOUNT})$", "phi.rebate_p2", "rebate received 1 Apr–30 Jun"),
]


class PhiExtractor:
    doc_types = frozenset({"PHI"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        fund = next((line for _, line in lines(rt) if not re.search(r"statement|redacted|\d", line, re.I)), "Health fund")
        code = search(rt, r"^Benefit code\s+(\d+)")
        notes = f"benefit code {code[1].group(1)}" if code else ""
        result = ExtractResult(doc_date=when)
        found = 0
        for pattern, key, label in _FIELDS:
            hit = search(rt, pattern)
            if hit:
                found += 1
                result.figures.append(figure(key, f"{fund} – {label}", amount(hit[1].group(1)), doc_id, hit[0],
                                             when, notes=notes))
        result.parse_status = status(found, 4)
        return result
