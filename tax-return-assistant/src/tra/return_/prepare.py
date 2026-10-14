"""Confirmed figures → draft return lines, each remembering the figures behind it."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..labels import LabelDef
from ..money import ZERO
from .cgt import CgtSummary, compute_cgt


@dataclass(frozen=True)
class LabelLine:
    label_key: str
    amount: Decimal
    figure_ids: tuple[str, ...]


@dataclass
class DraftReturn:
    client_code: str
    income_year: int
    lines: dict[str, LabelLine] = field(default_factory=dict)
    cgt: CgtSummary | None = None

    def amount(self, key: str) -> Decimal:
        line = self.lines.get(key)
        return line.amount if line else ZERO


def build_draft(client_code: str, income_year: int, figures, cgt_events, labels: dict[str, LabelDef],
                *, resident: bool = True) -> DraftReturn:
    totals: dict[str, Decimal] = {}
    ids: dict[str, list[str]] = {}
    for f in figures:
        if not f.confirmed or f.label_key not in labels:
            continue
        totals[f.label_key] = totals.get(f.label_key, ZERO) + f.amount
        ids.setdefault(f.label_key, []).append(f.figure_id)
    draft = DraftReturn(client_code, income_year)
    for key in labels:  # ATO order
        if key in totals:
            draft.lines[key] = LabelLine(key, totals[key], tuple(ids[key]))
    draft.cgt = compute_cgt(cgt_events, draft.amount("cgt.prior_losses"), resident=resident)
    if draft.cgt.events_used:
        for key, value in (("cgt.total_gains", draft.cgt.total_current_gains),
                           ("cgt.net_gain", draft.cgt.net_capital_gain)):
            draft.lines[key] = LabelLine(key, value, draft.cgt.events_used)
    return draft
