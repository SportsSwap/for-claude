"""Calculation A: tax built up slice by slice through the brackets.

Calculation B (calc_b.py) gets to the same numbers by a different route.
The two share nothing except the money and date helpers, so a mistake in
either one, or a typo in the rates file, shows up as a difference.
"""

from __future__ import annotations

from decimal import Decimal

from ..dates import days_in_fy
from ..models import ClientState
from ..money import ZERO, round_cents, truncate_dollars
from ..return_.prepare import DraftReturn
from .rates import Rates
from .result import TaxResult

DEDUCTION_KEYS = ("ded.d1", "ded.d2", "ded.d3", "ded.d4", "ded.d5", "ded.d6", "ded.d7", "ded.d8", "ded.d9",
                  "ded.d10", "ded.d12", "ded.d15")


def _bracket_tax(ti: Decimal, rates: Rates) -> Decimal:
    tax = ZERO
    bounds = [b.from_ for b in rates.brackets[1:]] + [None]
    for bracket, upper in zip(rates.brackets, bounds):
        top = ti if upper is None else min(ti, upper)
        if top > bracket.from_:
            tax += bracket.rate * (top - bracket.from_)
    return tax


def _lito(ti: Decimal, rates: Rates) -> Decimal:
    lito = rates.lito
    if ti <= lito.full_to:
        return lito.max
    if ti <= lito.taper1_to:
        return lito.max - lito.taper1_rate * (ti - lito.full_to)
    return max(ZERO, lito.taper2_base - lito.taper2_rate * (ti - lito.taper1_to))


def _sapto(rebate_income: Decimal, state: ClientState, rates: Rates) -> Decimal:
    if state.sapto_status == "none":
        return ZERO
    s = rates.sapto[state.sapto_status]
    return max(ZERO, s.max - rates.sapto_taper * max(ZERO, rebate_income - s.shade_out))


def _medicare(ti: Decimal, state: ClientState, rates: Rates) -> Decimal:
    m = rates.medicare
    lower = (m.sapto_single if state.sapto_status != "none" else m.single).lower
    if ti <= lower:
        return ZERO
    return min(m.rate * ti, m.shade_in * (ti - lower))


def _mls_tiers(state: ClientState, rates: Rates):
    if not (state.has_spouse or state.dependants):
        return rates.mls.single
    extra = rates.mls.family_per_child_after_first * max(0, state.dependants - 1)
    return tuple(type(t)(t.from_ + extra if t.from_ else t.from_, t.rate) for t in rates.mls.family)


def _tier_index(income: Decimal, tiers) -> int:
    index = 0
    for i, tier in enumerate(tiers):
        if income > tier.from_:
            index = i
    return index


def _help(ri: Decimal, rates: Rates) -> Decimal:
    h = rates.help
    if h.method == "marginal":
        if ri >= h.flat_from:
            return h.flat_rate * ri
        band = h.bands[_tier_index(ri, h.bands)]
        return band.base + band.rate * (ri - band.from_) if ri > band.from_ else ZERO
    rate = ZERO
    for row in h.bands:
        if ri >= row.from_:
            rate = row.rate
    return rate * ri


def calculate_a(draft: DraftReturn, state: ClientState, rates: Rates) -> TaxResult:
    d = draft.amount
    net_rent = d("rent.gross") - d("rent.interest") - d("rent.capital_works") - d("rent.other")
    business_net = d("income.business_income") - d("income.business_expenses")
    total_income = (d("income.salary") + d("income.allowances") + d("income.interest") + d("income.div_unfranked")
                    + d("income.div_franked") + d("income.franking_credit") + net_rent + d("cgt.net_gain")
                    + business_net + d("income.other"))
    deductions = sum((d(k) for k in DEDUCTION_KEYS), ZERO)
    ti = max(ZERO, truncate_dollars(total_income - deductions - d("loss.l1")))

    basic_tax = round_cents(_bracket_tax(ti, rates))
    rfb, resc = d("it.rfb"), d("it.resc")
    # Reportable super contributions = employer (RESC) + deductible personal contributions (D12).
    mls_income = ti + rfb + resc + d("ded.d12") + max(ZERO, -net_rent)
    lito = round_cents(_lito(ti, rates))
    sapto = round_cents(_sapto(mls_income, state, rates))
    offsets_used = min(basic_tax, lito + sapto)
    medicare = round_cents(_medicare(ti, state, rates))

    tiers = _mls_tiers(state, rates)
    days = days_in_fy(draft.income_year)
    uncovered = 0 if state.hospital_cover_days is None else max(0, days - state.hospital_cover_days)
    mls_rate = tiers[_tier_index(mls_income, tiers)].rate
    mls = round_cents(mls_rate * (ti + rfb) * uncovered / days)

    help_repay = round_cents(_help(mls_income, rates)) if state.help_debt else round_cents(ZERO)

    tier = _tier_index(mls_income, tiers)
    phi = ZERO
    for period, premiums, received in zip(rates.phi_rebate, ("phi.premiums_p1", "phi.premiums_p2"),
                                          ("phi.rebate_p1", "phi.rebate_p2")):
        entitled = round_cents(d(premiums) * period.rates[state.age_band][tier])
        phi += d(received) - entitled

    franking = d("income.franking_credit")
    payg = d("income.salary_tax_withheld")
    tfn_withheld = d("income.interest_tfn_withheld") + d("income.div_tfn_withheld")
    phi = round_cents(phi)
    net = basic_tax - offsets_used + medicare + mls + help_repay + phi - franking - payg - tfn_withheld
    return TaxResult(total_income=total_income, deductions=deductions, taxable_income=ti, basic_tax=basic_tax,
                     lito=lito, sapto=sapto, offsets_used=offsets_used, medicare_levy=medicare,
                     mls_income=mls_income, mls=mls, repayment_income=mls_income, help=help_repay,
                     phi_adjustment=phi, franking_credits=franking, payg_withheld=payg, tfn_withheld=tfn_withheld,
                     net_result=round_cents(net))
