"""Money helpers. Decimal only; floats never touch an amount."""

from __future__ import annotations

import re
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
DOLLAR = Decimal("1")
ZERO = Decimal("0")

_AMOUNT = re.compile(r"^-?\$?\s?-?[\d,]*\d(?:\.\d+)?$")


def parse_amount(raw: str) -> Decimal:
    """Parse '1,234.56', '$1,234.56', '1234.5', '(1,234.56)' or '-1234.56'."""
    s = str(raw).strip()
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1].strip()
    if not _AMOUNT.match(s):
        raise ValueError(f"not an amount: {raw!r}")
    if s.count("-") > 1:
        raise ValueError(f"not an amount: {raw!r}")
    negative ^= "-" in s
    digits = s.replace("$", "").replace(",", "").replace("-", "").strip()
    try:
        value = Decimal(digits)
    except InvalidOperation:
        raise ValueError(f"not an amount: {raw!r}") from None
    return -value if negative else value


def round_cents(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def truncate_dollars(d: Decimal) -> Decimal:
    """ATO practice: cents are dropped from taxable income."""
    return d.quantize(DOLLAR, rounding=ROUND_DOWN)
