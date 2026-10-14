"""Extractor registry: one extractor per document type.

To add a layout, write a class with ``doc_types`` and ``extract(rt, doc_id)``
and add it to ``_EXTRACTORS``. An LLM-based extractor could plug in here
later, but only on redacted text and only after firm sign-off (spec §2).
"""

from __future__ import annotations

from .base import ExtractResult, Extractor
from .dividends import DividendExtractor
from .income_statement import IncomeStatementExtractor
from .interest import InterestExtractor
from .prefill import PrefillExtractor

_EXTRACTORS: list[Extractor] = [
    PrefillExtractor(),
    IncomeStatementExtractor(),
    InterestExtractor(),
    DividendExtractor(),
]

_REGISTRY = {doc_type: ext for ext in _EXTRACTORS for doc_type in ext.doc_types}


def get_extractor(doc_type: str) -> Extractor | None:
    return _REGISTRY.get(doc_type)


__all__ = ["ExtractResult", "Extractor", "get_extractor"]
