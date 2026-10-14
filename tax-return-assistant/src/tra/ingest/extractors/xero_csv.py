"""Xero report exports (CSV or XLSX), for sole traders.

Profit and loss rows become business income/expense figures by section.
Balance sheet, bank transaction and chart of accounts exports are filed for
reference and produce no figures.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .base import AMOUNT, ExtractResult, amount, doc_date, figure, lines, require_redacted
from ...paths import CONFIG_DIR

_ROW = re.compile(rf'^(?P<name>[^,]+),\s*"?(?P<amt>{AMOUNT})"?\s*$')
_SUMMARY = re.compile(r"^(?:total|net|gross profit)\b", re.I)


def load_xero_mapping(path: Path | None = None) -> dict:
    return yaml.safe_load((path or CONFIG_DIR / "xero_mapping.yaml").read_text(encoding="utf-8"))


class XeroExportExtractor:
    doc_types = frozenset({"XEROPL", "XEROBS", "XEROBANK", "XEROCOA"})

    def __init__(self, mapping: dict | None = None):
        self._mapping = mapping

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        when = doc_date(rt)
        result = ExtractResult(doc_date=when, parse_status="parsed")
        if "profit and loss" not in rt.text.lower():
            return result
        sections = (self._mapping or load_xero_mapping())["pl_sections"]
        current: str | None = None
        unknown = False
        for page, line in lines(rt):
            m = _ROW.match(line)
            if not m:
                # Any other non-amount line is a heading; one we don't know resets the section.
                current = sections.get(line.strip().strip(","))
                continue
            if _SUMMARY.match(m.group("name").strip()):
                continue
            if current is None:
                unknown = True
                continue
            result.figures.append(figure(current, m.group("name").strip(), amount(m.group("amt")), doc_id, page, when,
                                         notes="xero export"))
        if unknown:
            result.parse_status = "partial"
        if not result.figures:
            result.parse_status = "manual_needed" if not unknown else "partial"
        return result
