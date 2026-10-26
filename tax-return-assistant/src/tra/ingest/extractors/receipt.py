"""Receipts and tax invoices.

The label is only a suggestion (work-related, D5), so the result is always
``partial``: the preparer confirms the label in figures.csv.
"""

from __future__ import annotations

import re

from .base import AMOUNT, ExtractResult, amount, figure, first_line, lines, require_redacted, search
from ...dates import DATE_PATTERN, find_doc_date, parse_date

# "Total", "Amount paid", and an invoice's "Amount due", "Total (incl. GST)", "Invoice total", "Total amount".
_TOTAL = re.compile(rf"^(?:Total(?:\s+amount|\s+\(?inc(?:l|luding)?\.?\s+GST\)?)?|Amount\s+(?:paid|due)|Invoice\s+total)"
                    rf"\s*:?\s+({AMOUNT})(?:\s+AUD)?$", re.I)
NO_TOTAL = "Didn't find a total."  # dropped once the AI reader finds an amount: then there was a total
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
        # The first total that isn't nil: a paid invoice can say "Amount due 0.00" above its total.
        total = next(((page, m) for page, line in lines(rt)
                      if (m := _TOTAL.search(line)) and amount(m.group(1)) != 0), None)
        is_receipt = any(word in rt.text.lower() for word in ("tax invoice", "receipt"))
        if not total:
            if is_receipt:  # an unrecognised document isn't expected to have a total
                result.doubts.append(NO_TOTAL)
            return result
        item = next((m.group("desc") for _, line in lines(rt)
                     if (m := _ITEM.match(line)) and not _NOT_ITEM.match(line)), "")
        description = f"{supplier}: {item}" if item else supplier
        substantiated = True if (is_receipt and when and supplier) else None
        result.figures.append(figure("ded.d5", description, amount(total[1].group(1)), doc_id, total[0], when,
                                     notes="suggested label", substantiated=substantiated))
        result.parse_status = "partial"
        return result
