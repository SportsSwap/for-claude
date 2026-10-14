"""C1: the two calculations must agree to the cent. C2: the rates file must be verified."""

from __future__ import annotations

from ..models import ReviewNote
from .context import CheckContext


def check_dual_calc(ctx: CheckContext) -> list[ReviewNote]:
    a, b = ctx.calc_a.components(), ctx.calc_b.components()
    return [
        ReviewNote("High", "C1", f"Calculation check: {name} differs between the two calculations "
                   f"(A {a[name]} vs B {b[name]}). Do not rely on the estimate until this is resolved.",
                   abs(a[name] - b[name]), "reviewer", "confirm")
        for name in a if a[name] != b[name]
    ]


def check_rates_status(ctx: CheckContext) -> list[ReviewNote]:
    if ctx.rates.status == "verified":
        return []
    return [ReviewNote("High", "C2", f"FY{ctx.rates.income_year} rates not yet verified against ato.gov.au "
                       "by a registered agent", None, "reviewer", "confirm")]
