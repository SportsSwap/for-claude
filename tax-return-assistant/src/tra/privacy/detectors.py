"""Find sensitive identifiers in text.

Detection runs on a *scan copy* of the text in which money amounts, dates and
ABNs have been overwritten with ``x`` characters of the same length, so offsets
line up with the original text but those spans can never match. Each stage then
masks what it matched, so later stages cannot match the same characters again.

The bias is towards over-redaction: a redacted invoice number costs nothing, a
leaked TFN is a notifiable breach.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .validators import abn_valid, luhn_valid, medicare_valid, tfn_valid

TYPES = ("TFN", "MEDICARE", "CARD", "BSB", "ACCOUNT", "LICENCE", "PASSPORT")


@dataclass(frozen=True)
class Match:
    type: str
    start: int
    end: int


# --- Spans that are never identifiers -------------------------------------------------

_NEVER = [
    # ISO dates and timestamps the tool writes itself (2026-03-24, 2026-10-14T05:49:00+10:00).
    re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?(?!\d)"),
    # dd/mm/yyyy and d/m/yy.
    re.compile(r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}(?!\d)"),
    # Money: $-prefixed, thousands-separated, or with a decimal part.
    re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?"),
    re.compile(r"(?<![\d,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])"),
    re.compile(r"(?<![\d.])\d+\.\d+(?![\d.])"),
]

# A run of digit groups joined by a single space, tab, hyphen or line break.
_RUN = re.compile(r"(?<![\w$])\d+(?:(?:[ \t]|-|\n)\d+)*(?!\w)")
_GROUP = re.compile(r"\d+")

_TFN_KW = re.compile(r"\b(?:TFN|tax\s+file\s+(?:number|no\.?))", re.I)
_MEDICARE_KW = re.compile(r"\bmedicare\b", re.I)
_ABN_KW = re.compile(r"\bABN\b", re.I)
_BSB_KW = re.compile(r"\bBSB\b", re.I)
_ACCOUNT_KW = re.compile(r"\b(?:account|acct|acc\s*no|a/c)\b", re.I)
_LICENCE_KW = re.compile(r"\b(?:licen[cs]e|DL\s*no|driver)\b", re.I)
_PASSPORT_KW = re.compile(r"\bpassport\b", re.I)

_BSB_STANDALONE = re.compile(r"(?<![\w-])\d{3}-\d{3}(?![\w-])")
_BSB_AFTER_KW = re.compile(r"(?<!\d)\d{3}[ -]?\d{3}(?!\d)")
_LICENCE_TOKEN = re.compile(r"(?<!\w)[A-Za-z0-9]{4,10}(?!\w)")
_PASSPORT_TOKEN = re.compile(r"(?<!\w)[A-Z]{1,2}\d{7}(?!\w)")

_TFN_WINDOW = 40
_OTHER_WINDOW = 30


def _mask(scan: list[str], start: int, end: int) -> None:
    for i in range(start, end):
        if scan[i] != "\n":
            scan[i] = "x"


def _runs(scan: str) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """Digit-group runs as (start, end, [(group_start, group_end), ...])."""
    runs = []
    for m in _RUN.finditer(scan):
        start, end = m.span()
        # Part of a hyphenated reference such as INV-2026-0042.
        if start >= 2 and scan[start - 1] == "-" and scan[start - 2].isalnum():
            continue
        if end + 1 < len(scan) and scan[end] == "-" and scan[end + 1].isalnum():
            continue
        groups = [(start + g.start(), start + g.end()) for g in _GROUP.finditer(m.group())]
        runs.append((start, end, groups))
    return runs


def _digits(text: str, groups: list[tuple[int, int]]) -> str:
    return "".join(text[a:b] for a, b in groups)


def _mask_never(text: str) -> list[str]:
    scan = list(text)
    for pattern in _NEVER:
        for m in pattern.finditer(text):
            _mask(scan, *m.span())
    return scan


def _mask_abns(text: str, scan: list[str]) -> None:
    joined = "".join(scan)
    for start, end, groups in _runs(joined):
        digits = _digits(text, groups)
        after_kw = bool(_ABN_KW.search(joined[max(0, start - 10):start]))
        if after_kw or (len(digits) == 11 and abn_valid(digits)):
            _mask(scan, start, end)


def _prefix_match(text, groups, lengths) -> tuple[int, int] | None:
    """Span of the shortest group prefix whose digit count is in ``lengths`` (tried in order)."""
    totals, count = [], 0
    for a, b in groups:
        count += b - a
        totals.append(count)
    for want in lengths:
        if want in totals:
            i = totals.index(want)
            return groups[0][0], groups[i][1]
    return None


def _first_run_after(kw_end: int, scan: str, window: int):
    """Runs that start within ``window`` characters after a keyword, nearest first."""
    for start, end, groups in _runs(scan):
        if kw_end <= start <= kw_end + window:
            yield start, end, groups


def _context_matches(text: str, scan: list[str]) -> list[Match]:
    found: list[Match] = []

    def take(type_: str, start: int, end: int) -> None:
        found.append(Match(type_, start, end))
        _mask(scan, start, end)

    # Each keyword claims the first digit run after it with the right length,
    # whatever its check digit: a mistyped TFN is still a TFN.
    for kw, type_, window, lengths in (
        (_TFN_KW, "TFN", _TFN_WINDOW, (9, 8)),
        (_MEDICARE_KW, "MEDICARE", _OTHER_WINDOW, (10, 11)),
    ):
        for k in kw.finditer(text):
            for _start, _end, groups in _first_run_after(k.end(), "".join(scan), window):
                span = _prefix_match(text, groups, lengths)
                if span and "x" not in "".join(scan[span[0]:span[1]]):
                    take(type_, *span)
                    break

    joined = "".join(scan)
    for k in _BSB_KW.finditer(joined):
        m = _BSB_AFTER_KW.search(joined, k.end(), k.end() + _OTHER_WINDOW)
        if m:
            take("BSB", *m.span())
    joined = "".join(scan)
    for m in _BSB_STANDALONE.finditer(joined):
        take("BSB", *m.span())

    for k in _ACCOUNT_KW.finditer(text):
        for start, end, groups in _first_run_after(k.end(), "".join(scan), _OTHER_WINDOW):
            if 5 <= len(_digits(text, groups)) <= 10 and "x" not in "".join(scan[start:end]):
                take("ACCOUNT", start, end)
                break

    joined = "".join(scan)
    for k in _LICENCE_KW.finditer(joined):
        for m in _LICENCE_TOKEN.finditer(joined, k.end(), k.end() + _OTHER_WINDOW + 10):
            if m.start() > k.end() + _OTHER_WINDOW:
                break
            if sum(c.isdigit() for c in m.group()) >= 4:
                take("LICENCE", *m.span())
                break
        joined = "".join(scan)

    for k in _PASSPORT_KW.finditer(joined):
        m = _PASSPORT_TOKEN.search(joined, k.end(), k.end() + _OTHER_WINDOW + 9)
        if m:
            take("PASSPORT", *m.span())

    return found


def _checksum_type(digits: str) -> str | None:
    n = len(digits)
    if 13 <= n <= 19 and luhn_valid(digits):
        return "CARD"
    if n == 11 and abn_valid(digits):
        return "ABN"
    if n in (10, 11) and medicare_valid(digits):
        return "MEDICARE"
    if n in (8, 9) and tfn_valid(digits):
        return "TFN"
    return None


def _numeric_matches(text: str, scan: list[str]) -> list[Match]:
    """Checksum-validated TFN, Medicare and card numbers, with no keyword needed.

    The whole run is tried first, then group-aligned sub-windows, so a TFN
    printed next to another number is still found.
    """
    found = []
    for _start, _end, groups in _runs("".join(scan)):
        i = 0
        while i < len(groups):
            for j in range(len(groups) - 1, i - 1, -1):
                window = groups[i:j + 1]
                kind = _checksum_type(_digits(text, window))
                if kind:
                    if kind != "ABN":
                        found.append(Match(kind, window[0][0], window[-1][1]))
                    i = j + 1
                    break
            else:
                i += 1
    return found


def _dedupe(matches: list[Match]) -> list[Match]:
    kept: list[Match] = []
    for m in sorted(matches, key=lambda m: (m.start, -(m.end - m.start))):
        if kept and m.start < kept[-1].end:
            continue
        kept.append(m)
    return kept


def find_sensitive(text: str, *, context: bool = True) -> list[Match]:
    """Non-overlapping matches sorted by position.

    ``context=False`` returns only checksum-validated TFN, Medicare and card
    numbers, which is what the repository hygiene scan uses.
    """
    scan = _mask_never(text)
    found: list[Match] = []
    if context:
        found += _context_matches(text, scan)
    _mask_abns(text, scan)
    found += _numeric_matches(text, scan)
    return _dedupe(found)
