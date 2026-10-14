"""Everything a check might need, in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..labels import LabelDef
from ..models import ClientState, Document, Figure, PrefillLine
from ..return_.prepare import DraftReturn
from ..taxcalc.rates import Rates
from ..taxcalc.result import TaxResult


@dataclass
class CheckContext:
    draft: DraftReturn
    rates: Rates
    state: ClientState
    calc_a: TaxResult
    calc_b: TaxResult
    labels: dict[str, LabelDef]
    figures: list[Figure] = field(default_factory=list)  # all figures, confirmed or not
    documents: list[Document] = field(default_factory=list)
    prefill: list[PrefillLine] = field(default_factory=list)
    prior_year: dict[str, Decimal] = field(default_factory=dict)
    cfg: dict = field(default_factory=dict)
    citations: dict = field(default_factory=dict)
    cgt_events: list = field(default_factory=list)
