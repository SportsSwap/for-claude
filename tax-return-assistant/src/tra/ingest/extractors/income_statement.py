"""Income statement (myGov) or PAYG payment summary."""

from __future__ import annotations

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, require_redacted, search, status

# (pattern, label key, description, required)
_FIELDS = [
    (rf"^Gross payments\s+({AMOUNT})", "income.salary", "gross payments", True),
    (rf"^Total tax withheld\s+({AMOUNT})", "income.salary_tax_withheld", "tax withheld", True),
    (rf"^Allowances\s+({AMOUNT})", "income.allowances", "allowances", False),
    (rf"^Reportable fringe benefits amount\s+({AMOUNT})", "it.rfb", "reportable fringe benefits", False),
    (rf"^Reportable employer superannuation contributions\s+({AMOUNT})", "it.resc",
     "reportable employer super contributions", False),
]


class IncomeStatementExtractor:
    doc_types = frozenset({"INCSTMT"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        payer_hit = search(rt, r"^Payer:?\s+(.+)$")
        payer = payer_hit[1].group(1).strip() if payer_hit else "Employer"
        result = ExtractResult(doc_date=when)
        required_found = 0
        any_found = 0
        for pattern, key, label, required in _FIELDS:
            hit = search(rt, pattern)
            if not hit:
                continue
            page, m = hit
            any_found += 1
            required_found += required
            value = amount(m.group(1))
            if value != 0:
                result.figures.append(figure(key, f"{payer} – {label}", value, doc_id, page, when))
        result.parse_status = status(required_found, 2) if any_found else "manual_needed"
        return result
