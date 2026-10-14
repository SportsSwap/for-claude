"""Shared pieces for extractors.

An extractor reads redacted text and returns *unconfirmed* figures, each
tagged with the page it came from. Anything it can't read is left for manual
entry rather than guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterator, Protocol

from ...dates import find_doc_date
from ...models import Figure, PrefillLine
from ...money import parse_amount
from ...privacy.redact import RedactedText

AMOUNT = r"\(?-?\$?\s?\d[\d,]*(?:\.\d{1,2})?\)?"


@dataclass
class ExtractResult:
    figures: list[Figure] = field(default_factory=list)
    prefill: list[PrefillLine] = field(default_factory=list)
    doc_date: date | None = None
    parse_status: str = "manual_needed"  # parsed | partial | manual_needed
    facts: dict = field(default_factory=dict)  # non-figure facts, e.g. hospital_cover_days


class Extractor(Protocol):
    doc_types: frozenset[str]

    def extract(self, rt: RedactedText, doc_id: str) -> ExtractResult: ...


def require_redacted(rt: object) -> RedactedText:
    if not isinstance(rt, RedactedText):
        raise TypeError("extractors accept redacted text only")
    return rt


def lines(rt: RedactedText) -> Iterator[tuple[int, str]]:
    """(page number, stripped line) for every non-empty line."""
    for page_no, page in enumerate(rt.pages, start=1):
        for line in page.splitlines():
            line = " ".join(line.split())
            if line:
                yield page_no, line


def first_line(rt: RedactedText) -> str:
    return next((line for _, line in lines(rt)), "")


def search(rt: RedactedText, pattern: str) -> tuple[int, re.Match] | None:
    """First line matching ``pattern`` (case-insensitive), with its page."""
    regex = re.compile(pattern, re.I)
    for page_no, line in lines(rt):
        m = regex.search(line)
        if m:
            return page_no, m
    return None


def status(found: int, expected: int) -> str:
    if found == 0:
        return "manual_needed"
    return "parsed" if found >= expected else "partial"


def doc_date(rt: RedactedText) -> date | None:
    return find_doc_date(rt.text)


def figure(label_key: str, description: str, amount: Decimal, doc_id: str, page: int,
           when: date | None, *, notes: str = "", substantiated: bool | None = None) -> Figure:
    return Figure(figure_id="", label_key=label_key, description=description, amount=amount, date=when,
                  doc_id=doc_id, page=page, method="parser", confirmed=False,
                  substantiated=substantiated, notes=notes)


def amount(raw: str) -> Decimal:
    return parse_amount(raw)
