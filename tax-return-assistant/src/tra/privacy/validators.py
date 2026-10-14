"""Check-digit validators for Australian identifiers.

Each function takes a digits-only string and returns False for the wrong
length or any non-digit, so callers can pass candidate matches straight in.
"""

_TFN_WEIGHTS = {
    9: (1, 4, 3, 7, 5, 8, 6, 9, 10),
    8: (10, 7, 8, 4, 6, 3, 5, 1),
}
_MEDICARE_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9)
_ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


def _digits(value: str) -> list[int] | None:
    if not value or not value.isascii() or not value.isdigit():
        return None
    return [int(c) for c in value]


def tfn_valid(digits: str) -> bool:
    """ATO tax file number: weighted sum divisible by 11."""
    d = _digits(digits)
    if d is None or len(d) not in _TFN_WEIGHTS:
        return False
    return sum(x * w for x, w in zip(d, _TFN_WEIGHTS[len(d)])) % 11 == 0


def medicare_valid(digits: str) -> bool:
    """Medicare card number, with or without the 11th-digit IRN.

    The first digit is 2-6 and the 9th digit is the weighted sum of the
    first eight, mod 10.
    """
    d = _digits(digits)
    if d is None or len(d) not in (10, 11) or not 2 <= d[0] <= 6:
        return False
    return sum(x * w for x, w in zip(d[:8], _MEDICARE_WEIGHTS)) % 10 == d[8]


def luhn_valid(digits: str) -> bool:
    """Payment card numbers (Luhn mod 10)."""
    d = _digits(digits)
    if d is None or len(d) < 2:
        return False
    total = 0
    for i, x in enumerate(reversed(d)):
        if i % 2 == 1:
            x *= 2
            if x > 9:
                x -= 9
        total += x
    return total % 10 == 0


def abn_valid(digits: str) -> bool:
    """Australian Business Number: subtract 1 from the first digit, weighted sum divisible by 89."""
    d = _digits(digits)
    if d is None or len(d) != 11:
        return False
    d[0] -= 1
    return sum(x * w for x, w in zip(d, _ABN_WEIGHTS)) % 89 == 0
