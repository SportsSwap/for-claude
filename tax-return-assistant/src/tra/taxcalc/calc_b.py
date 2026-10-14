"""Calculation B: the same result as calculation A, reached a different way.

Where A sums tax slice by slice, B uses the ATO's published "base amount plus
marginal rate" for the bracket the income falls in. Where A names each label,
B adds up labels by their role in labels.yaml. Offsets, levies and HELP use
lookups and explicit bands instead of A's formulas. Nothing is shared with A
except the money and date helpers.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from decimal import Decimal

from ..dates import days_in_fy
from ..labels import LabelDef
from ..models import ClientState
from ..money import round_cents, truncate_dollars
from ..return_.prepare import DraftReturn
from .rates import Rates
from .result import TaxResult

_NIL = Decimal("0")
_SIGN = {"income": 1, "franking": 1, "rental_income": 1, "rental_deduction": -1, "business_income": 1,
         "business_deduction": -1}


def _sum_role(draft: DraftReturn, labels: dict[str, LabelDef], *roles: str) -> Decimal:
    return sum((line.amount for key, line in draft.lines.items() if labels[key].role in roles), _NIL)


def _published_tax(ti: Decimal, rates: Rates) -> Decimal:
    froms = [b.from_ for b in rates.brackets]
    bracket = rates.brackets[max(0, bisect_left(froms, ti) - 1)]
    return bracket.base + bracket.rate * (ti - bracket.from_)


def _lito_table(ti: Decimal, rates: Rates) -> Decimal:
    l = rates.lito  # noqa: E741
    table = [(_NIL, l.max, _NIL), (l.full_to, l.max, l.taper1_rate), (l.taper1_to, l.taper2_base, l.taper2_rate)]
    start, base, rate = table[max(0, bisect_left([row[0] for row in table], ti) - 1)]
    value = base - rate * (ti - start)
    return value if value > 0 else _NIL


def _medicare_bands(ti: Decimal, sapto: bool, rates: Rates) -> Decimal:
    m = rates.medicare
    threshold = m.sapto_single if sapto else m.single
    if ti <= threshold.lower:
        return _NIL
    if ti <= threshold.upper:
        return m.shade_in * (ti - threshold.lower)
    return m.rate * ti


def _sapto_bands(rebate_income: Decimal, status: str, rates: Rates) -> Decimal:
    if status == "none":
        return _NIL
    s = rates.sapto[status]
    if rebate_income <= s.shade_out:
        return s.max
    if rebate_income >= s.cut_out:
        return _NIL
    return s.max - rates.sapto_taper * (rebate_income - s.shade_out)


def _tier(income: Decimal, thresholds: list[Decimal]) -> int:
    return max(0, bisect_left(thresholds, income) - 1)


def _mls_thresholds(state: ClientState, rates: Rates) -> tuple[list[Decimal], list[Decimal]]:
    family = state.has_spouse or state.dependants > 0
    tiers = rates.mls.family if family else rates.mls.single
    uplift = rates.mls.family_per_child_after_first * (state.dependants - 1) if family and state.dependants > 1 else _NIL
    return [t.from_ if t.from_ == 0 else t.from_ + uplift for t in tiers], [t.rate for t in tiers]


def _help_slices(ri: Decimal, rates: Rates) -> Decimal:
    h = rates.help
    if h.method == "percent_of_income":
        position = bisect_right([b.from_ for b in h.bands], ri) - 1
        return h.bands[position].rate * ri if position >= 0 else _NIL
    if ri >= h.flat_from:
        return h.flat_rate * ri
    total = _NIL
    uppers = [b.from_ for b in h.bands[1:]] + [ri]
    for band, upper in zip(h.bands, uppers):
        total += band.rate * max(_NIL, min(ri, upper) - band.from_)
    return total


def calculate_b(draft: DraftReturn, state: ClientState, rates: Rates, labels: dict[str, LabelDef]) -> TaxResult:
    total_income = sum((line.amount * _SIGN[labels[k].role] for k, line in draft.lines.items()
                        if labels[k].role in _SIGN), _NIL)
    deductions = _sum_role(draft, labels, "deduction")
    losses = _sum_role(draft, labels, "loss")
    taxable = truncate_dollars(total_income - deductions - losses)
    if taxable < 0:
        taxable = _NIL

    rental_net = _sum_role(draft, labels, "rental_income") - _sum_role(draft, labels, "rental_deduction")
    it_items = _sum_role(draft, labels, "it")
    income_test = taxable + it_items + (-rental_net if rental_net < 0 else _NIL)
    rfb = draft.lines["it.rfb"].amount if "it.rfb" in draft.lines else _NIL

    tax = round_cents(_published_tax(taxable, rates))
    lito = round_cents(_lito_table(taxable, rates))
    sapto = round_cents(_sapto_bands(income_test, state.sapto_status, rates))
    offsets = lito + sapto if lito + sapto < tax else tax
    medicare = round_cents(_medicare_bands(taxable, state.sapto_status != "none", rates))

    thresholds, mls_rates = _mls_thresholds(state, rates)
    tier = _tier(income_test, thresholds)
    year_days = days_in_fy(draft.income_year)
    covered = year_days if state.hospital_cover_days is None else min(year_days, state.hospital_cover_days)
    mls = round_cents(mls_rates[tier] * (taxable + rfb) * (year_days - covered) / year_days)

    help_repay = round_cents(_help_slices(income_test, rates) if state.help_debt else _NIL)

    phi_lines = sorted(k for k in draft.lines if labels[k].role == "phi")
    entitled = received = _NIL
    for n, period in enumerate(rates.phi_rebate, start=1):
        premiums = draft.lines.get(f"phi.premiums_p{n}")
        if premiums is not None:
            entitled += round_cents(premiums.amount * period.rates[state.age_band][tier])
    for key in phi_lines:
        if key.startswith("phi.rebate_p"):
            received += draft.lines[key].amount
    phi = round_cents(received - entitled)

    franking = _sum_role(draft, labels, "franking")
    withheld = {k: line.amount for k, line in draft.lines.items() if labels[k].role == "withheld"}
    payg = withheld.get("income.salary_tax_withheld", _NIL)
    tfn = sum((v for k, v in withheld.items() if k != "income.salary_tax_withheld"), _NIL)
    owed = [tax, -offsets, medicare, mls, help_repay, phi]
    credits = [franking, payg, tfn]
    net = round_cents(sum(owed, _NIL) - sum(credits, _NIL))
    return TaxResult(total_income=total_income, deductions=deductions, taxable_income=taxable, basic_tax=tax,
                     lito=lito, sapto=sapto, offsets_used=offsets, medicare_levy=medicare, mls_income=income_test,
                     mls=mls, repayment_income=income_test, help=help_repay, phi_adjustment=phi,
                     franking_credits=franking, payg_withheld=payg, tfn_withheld=tfn, net_result=net)
