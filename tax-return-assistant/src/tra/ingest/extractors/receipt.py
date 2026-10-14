"""Receipts and tax invoices.

The label is only a suggestion (work-related, D5), so the result is always
``partial``: the preparer confirms the label in figures.csv.
"""

from __future__ import annotations

import re

from .base import AMOUNT, ExtractResult, amount, figure, first_line, lines, require_redacted, search
from ...dates import DATE_PATTERN, find_doc_date, parse_date

_TOTAL = rf"^(?:Total|Amount paid)\s+({AMOUNT})$"
_DATE = rf"\bDate\s*:?\s*({DATE_PATTERN})"
# An item line ends in a price with cents (so "ABN 51 824 753 556" is not an item).
_ITEM = re.compile(r"^(?P<desc>[A-Za-z].*?)\s+\$?\d[\d,]*\.\d{2}$")
_NOT_ITEM = re.compile(r"^(?:total|amount paid|subtotal|gst|balance)", re.I)


class ReceiptExtractor:
    doc_types = frozenset({"RECEIPT", "OTHER"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        date_hit = search(rt, _DATE)
        when = parse_date(date_hit[1].group(1)) if date_hit else find_doc_date(rt.text)
        supplier = first_line(rt)
        result = ExtractResult(doc_date=when)
        total = search(rt, _TOTAL)
        if not total:
            return result
        item = next((m.group("desc") for _, line in lines(rt)
                     if (m := _ITEM.match(line)) and not _NOT_ITEM.match(line)), "")
        description = f"{supplier}: {item}" if item else supplier
        is_receipt = any(word in rt.text.lower() for word in ("tax invoice", "receipt"))
        substantiated = True if (is_receipt and when and supplier) else None
        result.figures.append(figure("ded.d5", description, amount(total[1].group(1)), doc_id, total[0], when,
                                     notes="suggested label", substantiated=substantiated))
        result.parse_status = "partial"
        return result
