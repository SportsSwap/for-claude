"""Bank statements and interest summaries."""

from __future__ import annotations

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, first_line, require_redacted, search


class InterestExtractor:
    doc_types = frozenset({"INTSTMT", "BANKSTMT"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        bank = first_line(rt) or "Bank"
        result = ExtractResult(doc_date=when)
        hit = search(rt, rf"^(?:Interest earned|Total interest|Interest paid)\s+({AMOUNT})")
        if hit:
            page, m = hit
            result.parse_status = "parsed"
            value = amount(m.group(1))
            if value != 0:
                result.figures.append(figure("income.interest", f"{bank} – interest", value, doc_id, page, when))
        withheld = search(rt, rf"^TFN withholding\s+({AMOUNT})")
        if withheld and amount(withheld[1].group(1)) != 0:
            result.figures.append(figure("income.interest_tfn_withheld", f"{bank} – TFN withholding",
                                         amount(withheld[1].group(1)), doc_id, withheld[0], when))
        return result
