"""Property manager / rental statements."""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache

from ...paths import CONFIG_DIR
from .base import AMOUNT, ExtractResult, amount, doc_date, figure, lines, require_redacted
from .words import load_sheet_words, match_labels

SUNDRY = "rent.other"  # Item 21 U itself: an expense no category fits, or one that fits more than one


@lru_cache(maxsize=1)
def _rental_words() -> dict[str, tuple[str, ...]]:
    return load_sheet_words(CONFIG_DIR / "rental_words.yaml")


def rental_category(description: str) -> str:
    """The rental schedule category (or Item 21 Q / F) an expense line's words point to, else sundry."""
    keys = match_labels(description, _rental_words())
    return keys[0] if len(keys) == 1 else SUNDRY


# "Ownership share 50%", "Owner's share: 50 %", "Your share 33.33%": a suggestion for the Rental page.
_SHARE = re.compile(r"\b(?:ownership\s+share|owner'?s?\s+share|your\s+share|ownership)\b\s*:?\s*"
                    r"(\d{1,3}(?:\.\d{1,2})?)\s?%", re.I)


def ownership_share(rt) -> Decimal | None:
    for _page, line in lines(rt):
        m = _SHARE.search(line)
        if m and Decimal(0) < Decimal(m.group(1)) <= Decimal(100):
            return Decimal(m.group(1))
    return None


_GROSS = re.compile(rf"^Total rent received\s+({AMOUNT})$", re.I)
_LINE = re.compile(rf"^(?P<desc>[A-Za-z].*?)\s+(?P<amt>{AMOUNT})$")
_STOP = re.compile(r"^(?:Total expenses|Net to owner|Net)\b", re.I)


class RentalExtractor:
    doc_types = frozenset({"RENTSTMT"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        result = ExtractResult(doc_date=when)
        share = ownership_share(rt)
        if share is not None:
            result.facts["ownership_share"] = share
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
                key = rental_category(m.group("desc"))
                result.figures.append(figure(key, m.group("desc"), amount(m.group("amt")), doc_id, page, when))
        if result.parse_status != "parsed":
            result.doubts.append("Didn't find the total rent received.")
        return result
