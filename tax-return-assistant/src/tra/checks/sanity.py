"""S1-S13: patterns a reviewer would query. Where the treatment is uncertain the
note says so and cites the provision or ruling; it never changes the return."""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from ..dates import days_in_fy
from ..models import ReviewNote
from ..money import ZERO
from ..return_.cgt import anniversary, discount_eligible
from . import label_name
from .context import CheckContext

WORK_RELATED = ("ded.d1", "ded.d2", "ded.d3", "ded.d4", "ded.d5")
RENTAL_DEDUCTIONS = ("rent.interest", "rent.capital_works", "rent.other")
# label group -> (labels, document types that should support them)
EXPECTED_SOURCES = [
    ("interest", ("income.interest",), {"INTSTMT", "BANKSTMT"}),
    ("dividends", ("income.div_unfranked", "income.div_franked", "income.franking_credit"), {"DIVSTMT"}),
    ("salary or wages", ("income.salary",), {"INCSTMT", "PREFILL"}),
]
NEAR_ANNIVERSARY_DAYS = 30


def _matches(text: str, keywords) -> str | None:
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}", text, re.I):
            return kw
    return None


def _confirmed(ctx: CheckContext, *keys: str):
    return [f for f in ctx.figures if f.confirmed and f.label_key in keys]


def _note(risk, check_id, message, impact=None, *, audience="reviewer", action="confirm", label_key=None,
          citation=None, figures=(), docs=()) -> ReviewNote:
    return ReviewNote(risk, check_id, message, impact, audience, action, label_key=label_key, citation_id=citation,
                      figure_ids=tuple(f.figure_id for f in figures), doc_ids=tuple(docs))


def check_sanity(ctx: CheckContext) -> list[ReviewNote]:
    cfg, d, notes = ctx.cfg, ctx.draft.amount, []
    a = ctx.calc_a

    # S1 deductions unusually high
    work = sum((d(k) for k in WORK_RELATED), ZERO)
    if a.total_income > 0 and a.deductions > Decimal(str(cfg["deductions_to_income_max"])) * a.total_income:
        notes.append(_note("Medium", "S1", f"Deductions of ${a.deductions:,} are {a.deductions / a.total_income:.0%} of "
                           f"total income (${a.total_income:,}). Check each claim is supported.", a.deductions))
    elif d("income.salary") > 0 and work > Decimal(str(cfg["work_related_to_salary_max"])) * d("income.salary"):
        notes.append(_note("Medium", "S1", f"Work-related deductions (D1-D5) of ${work:,} are "
                           f"{work / d('income.salary'):.0%} of salary. Check each claim is supported.", work))

    # S2 income with no supporting document
    doc_types = {doc.doc_id: doc.doc_type for doc in ctx.documents}
    for name, keys, expected in EXPECTED_SOURCES:
        figs = _confirmed(ctx, *keys)
        if figs and not any(doc_types.get(f.doc_id) in expected for f in figs):
            notes.append(_note("Medium", "S2", f"The return includes {name} but there is no "
                               f"{' or '.join(sorted(expected))} document behind it. Ask the client for the statement.",
                               sum((f.amount for f in figs), ZERO), audience="client", action="question",
                               label_key=keys[0], figures=figs))

    # S3 rental income without expenses, or the reverse
    rent_deductions = sum((d(k) for k in RENTAL_DEDUCTIONS), ZERO)
    if d("rent.gross") > 0 and rent_deductions == 0:
        notes.append(_note("Medium", "S3", "Rental income with no rental expenses. Ask the client about interest, "
                           "rates, insurance, agent fees and depreciation.", d("rent.gross"), audience="client",
                           action="question", label_key="rent.gross"))
    elif rent_deductions > 0 and d("rent.gross") == 0:
        notes.append(_note("Medium", "S3", "Rental expenses with no rental income. Confirm the property was genuinely "
                           "available for rent.", rent_deductions, audience="client", action="question",
                           label_key="rent.other"))

    # S4 substantiation over $300
    work_figs = _confirmed(ctx, *WORK_RELATED)
    unsupported = [f for f in work_figs if f.substantiated is not True]
    if work > Decimal(str(cfg["substantiation_threshold"])) and unsupported:
        notes.append(_note("High", "S4", f"Work-related claims total ${work:,} (over $300), so written evidence is "
                           f"required for every claim. Not marked substantiated: "
                           f"{', '.join(f.figure_id for f in unsupported)}.",
                           sum((f.amount for f in unsupported), ZERO), audience="preparer", label_key="ded.d5",
                           citation="itaa97_s900_35", figures=unsupported))

    # S5 cents-per-km cap
    cap = ctx.rates.car.rate * ctx.rates.car.km_cap
    car = _confirmed(ctx, "ded.d1")
    if d("ded.d1") > cap and not any("logbook" in f.notes.lower() for f in car):
        notes.append(_note("High", "S5", f"Car expenses of ${d('ded.d1'):,} exceed the cents-per-km maximum of "
                           f"${cap:,.2f} ({ctx.rates.car.km_cap:,.0f} km x {ctx.rates.car.rate * 100:.0f}c). A logbook "
                           "is needed for a larger claim; note 'logbook' on the figure if one exists.",
                           d("ded.d1") - cap, label_key="ded.d1", citation="itaa97_s28_25", figures=car))

    # S6 conventional clothing
    for f in _confirmed(ctx, "ded.d3"):
        if _matches(f.description, cfg["clothing_keywords"]):
            notes.append(_note("Medium", "S6", f"{f.figure_id} '{f.description}' looks like conventional clothing, "
                               "which is not deductible unless it is a uniform, protective or occupation-specific.",
                               f.amount, label_key="ded.d3", citation="tr97_12", figures=[f]))

    # S7 rental repair that may be capital
    for f in _confirmed(ctx, "rent.other"):
        if _matches(f.description, cfg["capital_keywords"]):
            notes.append(_note("Medium", "S7", f"{f.figure_id} '{f.description}' may be a capital improvement or "
                               "depreciating asset rather than a repair. Confirm before claiming outright.", f.amount,
                               label_key="rent.other", citation="tr97_23", figures=[f]))

    # S8 CGT events
    for e in ctx.cgt_events:
        if not e.confirmed:
            continue
        held_just_over = (discount_eligible(e.acquired, e.disposed) and e.proceeds > e.cost_base
                          and e.disposed <= anniversary(e.acquired) + timedelta(days=NEAR_ANNIVERSARY_DAYS))
        if held_just_over:
            notes.append(_note("High", "S8", f"{e.event_id} {e.asset}: held only just over 12 months and the 50% "
                               "discount was applied. Confirm the contract (not settlement) dates.",
                               (e.proceeds - e.cost_base) / 2, label_key="cgt.net_gain", citation="itaa97_s115_25",
                               docs=[e.doc_id] if e.doc_id else []))
        else:
            notes.append(_note("Medium", "S8", f"{e.event_id} {e.asset}: confirm cost base (including incidental costs) "
                               "and acquisition and disposal dates.", abs(e.proceeds - e.cost_base),
                               label_key="cgt.net_gain", citation="itaa97_s115_25",
                               docs=[e.doc_id] if e.doc_id else []))

    # S9 Medicare levy surcharge exposure
    tiers = ctx.rates.mls.family if (ctx.state.has_spouse or ctx.state.dependants) else ctx.rates.mls.single
    threshold = tiers[1].from_
    days = days_in_fy(ctx.draft.income_year)
    if a.mls_income > threshold:
        cover = ctx.state.hospital_cover_days
        if cover is None:
            notes.append(_note("Medium", "S9", f"Income for MLS purposes (${a.mls_income:,}) is over ${threshold:,}. "
                               "Assumed the client held private hospital cover all year; confirm, or the Medicare "
                               "levy surcharge applies.", None, audience="client", action="assumption",
                               citation="mla1986"))
        elif cover < days:
            notes.append(_note("Medium", "S9", f"No private hospital cover for {days - cover} day(s) with income for MLS "
                               f"purposes of ${a.mls_income:,}: Medicare levy surcharge of ${a.mls:,} included. "
                               "Confirm the cover dates with the client.", a.mls, audience="client", action="question",
                               citation="mla1986"))

    # S10 interest on a redraw or line of credit
    for f in _confirmed(ctx, "rent.interest", "ded.d7"):
        if _matches(f.description, cfg["interest_purpose_keywords"]):
            notes.append(_note("Medium", "S10", f"{f.figure_id} '{f.description}': if any of the borrowing was used for "
                               "private purposes, only the investment portion of the interest is deductible.", f.amount,
                               label_key=f.label_key, citation="tr2000_2", figures=[f]))

    # S11 gifts
    for f in _confirmed(ctx, "ded.d9"):
        if f.amount < 2:
            notes.append(_note("Low", "S11", f"{f.figure_id}: gifts under $2 are not deductible.", f.amount,
                               label_key="ded.d9", citation="itaa97_div30", figures=[f]))
        elif "dgr" not in f"{f.description} {f.notes}".lower():
            notes.append(_note("Low", "S11", f"{f.figure_id} '{f.description}': confirm the recipient is a deductible "
                               "gift recipient (note 'DGR' on the figure once checked).", f.amount, label_key="ded.d9",
                               citation="itaa97_div30", figures=[f]))

    # S12 areas the tool doesn't prepare
    types = {doc.doc_type for doc in ctx.documents}
    if "MFUND" in types:
        notes.append(_note("High", "S12", "Managed fund (AMIT) statement filed: its components (gains, foreign income, "
                           "credits) must be entered manually.",
                           docs=[doc.doc_id for doc in ctx.documents if doc.doc_type == "MFUND"]))
    if ctx.state.has_spouse or ctx.state.dependants:
        notes.append(_note("High", "S12", "Spouse or dependants: the family Medicare levy reduction, family MLS and PHI "
                           "thresholds use family income, which the estimate does not include. Prepare in Xero Tax."))
    if d("income.business_income") or d("income.business_expenses"):
        notes.append(_note("High", "S12", "Business income from Xero is included as totals only. Complete the business "
                           "and professional items schedule (P8) in Xero Tax.", label_key="income.business_income"))
    if "CGT" in types and not ctx.cgt_events:
        notes.append(_note("High", "S12", "A capital gains document is filed but no CGT events are entered in "
                           "cgt_events.csv.", docs=[doc.doc_id for doc in ctx.documents if doc.doc_type == "CGT"]))

    # S13 asset claimed outright
    limit = Decimal(str(cfg["asset_threshold"]))
    for f in work_figs:
        if f.amount > limit and _matches(f.description, cfg["asset_keywords"]):
            notes.append(_note("Medium", "S13", f"{f.figure_id} '{f.description}' (${f.amount:,}) looks like a "
                               "depreciating asset. Only items costing $300 or less can be claimed outright; claim "
                               "decline in value instead.", f.amount, label_key=f.label_key, citation="itaa97_s40_80",
                               figures=[f]))
    return notes
