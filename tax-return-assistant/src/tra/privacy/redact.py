"""Redaction: the only way text gets from a reader into the rest of the tool.

Extractors and classifiers accept :class:`RedactedText` only. It can only be
built here, so raw text cannot be passed on by accident.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from . import detectors

PLACEHOLDER: dict[str, str] = {
    "TFN": "[TFN REDACTED]",
    "MEDICARE": "[MEDICARE REDACTED]",
    "CARD": "[CARD REDACTED]",
    "BSB": "[BSB REDACTED]",
    "ACCOUNT": "[ACCOUNT REDACTED]",
    "LICENCE": "[LICENCE REDACTED]",
    "PASSPORT": "[PASSPORT REDACTED]",
}

_KEY = object()


class RedactionError(Exception):
    """Redaction failed. The message never contains document text."""


@dataclass(frozen=True)
class RedactedText:
    pages: tuple[str, ...]
    counts: Mapping[str, int]
    _key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._key is not _KEY:
            raise TypeError("RedactedText can only be created by tra.privacy.redact")

    @property
    def text(self) -> str:
        return "\n\f\n".join(self.pages)


_MAX_PASSES = 10


def _redact_one(text: str, counts: Counter) -> str:
    """Redact until nothing is found, so the output always passes the output guard."""
    out = text
    for _ in range(_MAX_PASSES):
        matches = detectors.find_sensitive(out)
        if not matches:
            return out
        for m in reversed(matches):
            out = out[:m.start] + PLACEHOLDER[m.type] + out[m.end:]
            counts[m.type] += 1
    raise RuntimeError("redaction did not settle")


def redact_pages(pages: list[str]) -> RedactedText:
    """Redact every page. Any failure raises RedactionError and nothing is returned."""
    counts: Counter = Counter()
    try:
        redacted = tuple(_redact_one(page, counts) for page in pages)
    except Exception as exc:  # fail closed: no partial output, no text in the error
        raise RedactionError(f"redaction failed ({type(exc).__name__})") from None
    return RedactedText(pages=redacted, counts=MappingProxyType(dict(counts)), _key=_KEY)


def redact_text(text: str) -> str:
    return redact_pages([text]).pages[0]
