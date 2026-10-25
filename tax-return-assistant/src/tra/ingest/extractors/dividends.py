"""Dividend statements.

Two layouts: one amount per line ("Franked amount 1,200.00"), and the share registries' table
(Link/MUFG, Computershare), where a header row names the columns and the row below holds the
amounts. A table is only used when it adds up (unfranked + franked = total, credit no more than
the franked amount allows); otherwise the statement is left for manual entry rather than guessed.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, first_line, lines, require_redacted, search, status

_FIELDS = [
    (rf"^Unfranked amount\s+({AMOUNT})", "income.div_unfranked", "unfranked amount"),
    (rf"^Franked amount\s+({AMOUNT})", "income.div_franked", "franked amount"),
    (rf"^Franking credit\s+({AMOUNT})", "income.franking_credit", "franking credit"),
    (rf"^TFN withheld\s+({AMOUNT})", "income.div_tfn_withheld", "TFN withheld"),
]
_WITHHOLDING = rf"^(?:less\s+)?(?:resident\s+|tfn\s+)?withholding tax\s+({AMOUNT})"
_WITHHOLDING_NOTE = "statement says 'withholding tax': confirm it is TFN withholding (item 11 V)"

# Header words for each numeric column. Each column is placed by where its word first appears.
_COLUMNS = {
    "rate": r"\brate\b|\bper\s+(?:share|security|unit)\b",
    "units": r"\bparticipating\b|\bnumber\s+of\b|\bshares\s+held\b|\bholding\b|\bunits\b",
    "unfranked": r"\bunfranked\b",
    "franked": r"\bfranked\b",
    "credit": r"\bfranking\b|\bimputation\b",
    "total": r"\btotal\b|\bgross\s+(?:payment|amount)\b",
    "withholding": r"\bwithholding\b|\btfn\b",
    "net": r"\bnet\s+(?:payment|amount)\b",
}
_TABLE_KEYS = {"unfranked": ("income.div_unfranked", "unfranked amount"),
               "franked": ("income.div_franked", "franked amount"),
               "credit": ("income.franking_credit", "franking credit")}
_NUMBER = re.compile(r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?")
_COMPANY = re.compile(r"\b(?:limited|ltd|group|trust|fund|corporation)\b", re.I)
_MAX_CREDIT_RATE = Decimal("30") / Decimal("70")  # the franking credit on a franked amount at 30% company tax


def _company(rt) -> str:
    for n, (_, line) in enumerate(lines(rt)):
        if n > 15:
            break
        if _COMPANY.search(line) and not re.search(r"registry|communications|po box|abn", line, re.I):
            return line
    return first_line(rt) or "Company"


def _header_columns(line: str) -> list[str] | None:
    """The numeric columns a registry table header names, left to right (None if it isn't one)."""
    if re.search(r"\d", line) or not (re.search(_COLUMNS["unfranked"], line, re.I)
                                      and re.search(_COLUMNS["franked"], line, re.I)):
        return None
    found = []
    for name, pattern in _COLUMNS.items():
        m = re.search(pattern, line, re.I)
        if m:
            found.append((m.start(), name))
    return [name for _, name in sorted(found)]


def _read_table(rt) -> tuple[dict[str, Decimal], int] | None:
    """The table's unfranked, franked and credit amounts (summed over its rows) and the page."""
    all_lines = list(lines(rt))
    for i, (page, line) in enumerate(all_lines):
        columns = _header_columns(line)
        if not columns:
            continue
        sums: dict[str, Decimal] = {}
        rows = 0
        for _, row in all_lines[i + 1:i + 12]:
            tokens = _NUMBER.findall(row)
            if len(tokens) < 3:
                if rows or re.search(r"\d", row):
                    break
                continue  # the header's second line
            if len(tokens) < len(columns):
                return None
            values = dict(zip(columns, (amount(t) for t in tokens[-len(columns):])))
            for name, value in values.items():
                sums[name] = sums.get(name, Decimal("0")) + value
            rows += 1
        if not rows:
            return None
        unfranked, franked = sums.get("unfranked", Decimal("0")), sums.get("franked", Decimal("0"))
        if "total" in sums and abs(unfranked + franked - sums["total"]) > Decimal("0.01"):
            return None
        if "credit" in sums and sums["credit"] > franked * _MAX_CREDIT_RATE + Decimal("0.01"):
            return None
        return {k: v for k, v in sums.items() if k in _TABLE_KEYS}, page
    return None


class DividendExtractor:
    doc_types = frozenset({"DIVSTMT"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        company = _company(rt)
        result = ExtractResult(doc_date=when)
        found: set[str] = set()

        def add(key: str, label: str, value: Decimal, page: int, notes: str = "") -> None:
            found.add(key)
            if value != 0:
                result.figures.append(figure(key, f"{company} – {label}", value, doc_id, page, when, notes=notes))

        table = _read_table(rt)
        if table:
            values, page = table
            for name, value in values.items():
                key, label = _TABLE_KEYS[name]
                add(key, label, value, page)
        for pattern, key, label in _FIELDS:
            hit = search(rt, pattern)
            if hit and key not in found:
                page, m = hit
                add(key, label, amount(m.group(1)), page)
        hit = search(rt, _WITHHOLDING)
        if hit and "income.div_tfn_withheld" not in found:
            page, m = hit
            add("income.div_tfn_withheld", "TFN withheld", amount(m.group(1)), page, notes=_WITHHOLDING_NOTE)
            result.doubts.append(_WITHHOLDING_NOTE[0].upper() + _WITHHOLDING_NOTE[1:] + ".")
        result.doubts += [f"Didn't find the {label}." for _, key, label in _FIELDS[:3] if key not in found]
        result.parse_status = status(len(found - {"income.div_tfn_withheld"}), 3)
        return result
