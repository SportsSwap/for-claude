"""The text of an email from a client ("Donations to Red Cross: $500").

A line with one amount (with $ or cents, so phone numbers and dates don't count) and words that point
to one label (words.py) becomes an unconfirmed figure with a suggested label. Other lines with an
amount go to Things to check. Reading stops where a quoted reply starts, so amounts the client
repeats from an earlier email aren't counted twice; if that part has amounts, Things to check says so.
"""

from __future__ import annotations

import re

from ...dates import DATE_PATTERN, parse_date
from ...labels import load_labels
from ...money import format_dollars, parse_amount, round_cents
from .base import ExtractResult, figure, require_redacted
from .client_sheet import MAX_DOUBTS, _could_be
from .words import load_sheet_words, match_labels

# $500, $1,000.50, or 12.50 (cents); a comma after it ("$500, thanks") isn't part of the amount.
_MONEY = re.compile(r"(?<![\w.$])(\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?|(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})"
                    r"(?!\d|\.\d|,\d)")
_TOTAL = re.compile(r"\b(?:sub-?\s?totals?|grand totals?|totals?)\b", re.I)
_REPLY = re.compile(r"^(?:on\b.+\bwrote:|-{2,}\s*original message\s*-{2,}|_{8,}|from:\s.+|sent from my\b.*)$", re.I)
_DATE = re.compile(rf"^Date:\s*({DATE_PATTERN})")


def _short(line: str) -> str:
    return line if len(line) <= 80 else line[:77] + "..."


class EmailBodyExtractor:
    doc_types = frozenset({"EMAIL"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        words, labels = load_sheet_words(), load_labels()
        text = rt.pages[0] if rt.pages else ""
        head, _, body = text.partition("\n\n")
        result = ExtractResult()
        for line in head.splitlines():
            m = _DATE.match(line.strip())
            if m:
                result.doc_date = parse_date(m.group(1))
        not_added: list[str] = []
        lines = body.splitlines()
        for n, raw in enumerate(lines):
            line = " ".join(raw.split())
            if _REPLY.match(line):
                if any(_MONEY.search(rest) for rest in lines[n + 1:]):
                    not_added.insert(0, "Amounts in the quoted or forwarded part of this email weren't read. "
                                        "Check that part by hand.")
                break
            if not line or line.startswith(">"):
                continue
            amounts = _MONEY.findall(line)
            if not amounts or _TOTAL.search(line):  # a total repeats the lines above it
                continue
            if len(amounts) > 1:
                not_added.append(f'"{_short(line)}" has more than one amount, so it wasn\'t added.')
                continue
            try:
                value = round_cents(parse_amount(amounts[0].replace(" ", "")))
            except ValueError:
                not_added.append(f'"{_short(line)}" has an amount Sawnx couldn\'t read, so it wasn\'t added.')
                continue
            if value == 0:
                continue
            keys = match_labels(_MONEY.sub(" ", line), words)
            if len(keys) != 1:
                why = "has no label" if not keys else f"could be {_could_be(keys, labels)}"
                not_added.append(f'"{_short(line)}" ({format_dollars(value)}) {why}, so it wasn\'t added.')
                continue
            result.figures.append(figure(keys[0], f"Email: {line}"[:120], value, doc_id, 1, None,
                                         notes="suggested label"))
        result.doubts += not_added[:MAX_DOUBTS]
        if len(not_added) > MAX_DOUBTS:
            result.doubts.append(f"And {len(not_added) - MAX_DOUBTS} more lines that weren't added.")
        # An email with no amounts in it (a covering note) has nothing to enter by hand.
        result.parse_status = "partial" if result.figures else ("manual_needed" if not_added else "parsed")
        return result
