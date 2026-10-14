"""The result both calculations produce, compared component by component."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TaxResult:
    total_income: Decimal
    deductions: Decimal
    taxable_income: Decimal
    basic_tax: Decimal
    lito: Decimal
    sapto: Decimal
    offsets_used: Decimal
    medicare_levy: Decimal
    mls_income: Decimal
    mls: Decimal
    repayment_income: Decimal
    help: Decimal
    phi_adjustment: Decimal  # positive: rebate over-received, added to tax
    franking_credits: Decimal
    payg_withheld: Decimal
    tfn_withheld: Decimal
    net_result: Decimal  # positive: estimated payable; negative: estimated refund

    def components(self) -> dict[str, Decimal]:
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
