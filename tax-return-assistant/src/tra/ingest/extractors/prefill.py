"""ATO individual pre-fill report.

Each line becomes a PrefillLine (for the pre-fill comparison checks) and, for
amounts that land on a return label, an unconfirmed figure marked ``prefill``
so a label with no other source can still be sourced to the pre-fill.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, lines, require_redacted
from ...models import PrefillLine

A = f"({AMOUNT})"
# (pattern, [label key per amount group]) — keys under phi.*_total and help.* are info only.
_LINES = [
    (rf"^Salary or wages\s+(?P<payer>.+?)\s+Gross payments\s+{A}\s+Tax withheld\s+{A}",
     ["income.salary", "income.salary_tax_withheld"]),
    (rf"^Interest\s+(?P<payer>.+?)\s+Gross interest\s+{A}\s+TFN amounts withheld\s+{A}",
     ["income.interest", "income.interest_tfn_withheld"]),
    (rf"^Dividends\s+(?P<payer>.+?)\s+Unfranked\s+{A}\s+Franked\s+{A}\s+Franking credit\s+{A}",
     ["income.div_unfranked", "income.div_franked", "income.franking_credit"]),
    (rf"^Private health insurance\s+(?P<payer>.+?)\s+Premiums eligible\s+{A}\s+Rebate received\s+{A}",
     ["phi.premiums_total", "phi.rebate_total"]),
]
_HELP = re.compile(r"^HELP\s+Debt balance indicator\s+(Yes|No)\b", re.I)
INFO_KEYS = frozenset({"phi.premiums_total", "phi.rebate_total", "help.indicator"})


class PrefillExtractor:
    doc_types = frozenset({"PREFILL"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        result = ExtractResult(doc_date=when)
        patterns = [(re.compile(p, re.I), keys) for p, keys in _LINES]
        for page, line in lines(rt):
            m = _HELP.match(line)
            if m:
                if m.group(1).lower() == "yes":
                    result.prefill.append(PrefillLine("help.indicator", "ATO", Decimal("1"), doc_id, page))
                result.parse_status = "parsed"
                continue
            for regex, keys in patterns:
                m = regex.match(line)
                if not m:
                    continue
                result.parse_status = "parsed"
                payer = m.group("payer").strip()
                for key, raw in zip(keys, m.groups()[1:]):
                    value = amount(raw)
                    if value == 0:
                        continue
                    result.prefill.append(PrefillLine(key, payer, value, doc_id, page))
                    if key not in INFO_KEYS:
                        result.figures.append(figure(key, f"{payer} (pre-fill)", value, doc_id, page, when,
                                                     notes="prefill"))
                break
        return result
