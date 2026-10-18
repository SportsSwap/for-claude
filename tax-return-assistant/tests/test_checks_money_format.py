"""Every dollar figure in a review note reads $x,xxx.xx, however the amount was typed in figures.csv
(Excel saves 1499.00 as 1499)."""

import re

from checkctx import D, doc, fig, ids, make_ctx, pre

from tra.checks.prefill import check_prefill
from tra.checks.prior_year import check_prior_year
from tra.checks.reconcile import check_reconcile
from tra.checks.sanity import check_sanity
from tra.models import ClientState
from tra.return_.prepare import LabelLine

MONEY = re.compile(r"-?\$-?[\d,.]*\d")
CENTS = re.compile(r"-?\$\d{1,3}(?:,\d{3})*\.\d{2}")
RULE_AMOUNTS = {"$300", "$2"}  # thresholds written into the note wording, not client figures


def badly_formatted(notes):
    return [m for n in notes for m in MONEY.findall(n.message) if m not in RULE_AMOUNTS and not CENTS.fullmatch(m)]


def test_sanity_notes_show_cents():
    notes = check_sanity(make_ctx([fig("F1", "income.salary", 50000), fig("F2", "ded.d15", 20000),
                                   fig("F3", "ded.d5", 1499, description="OFFICEWORKS: Laptop computer"),
                                   fig("F4", "ded.d5", "520.5"), fig("F5", "ded.d1", 4500)]))
    notes += check_sanity(make_ctx([fig("F1", "income.salary", 50000), fig("F2", "ded.d5", 9000, substantiated=True)]))
    notes += check_sanity(make_ctx([fig("F1", "income.salary", 120000)]))
    notes += check_sanity(make_ctx([fig("F1", "income.salary", "120000.5")],
                                   state=ClientState("TEST01", 2026, hospital_cover_days=200)))
    assert {"S1", "S4", "S5", "S9", "S13"} <= {n.check_id for n in notes}
    assert len(ids(notes, "S1")) == 2 and len(ids(notes, "S9")) == 2
    assert badly_formatted(notes) == []


def test_reconcile_notes_show_cents():
    ctx = make_ctx([fig("F1", "income.interest", 100), fig("F2", "ded.d9", 50, doc=None),
                    fig("F3", "income.div_unfranked", "412.4"),
                    fig("F4", "income.div_unfranked", "412.4", notes="prefill")])
    ctx.draft.lines["income.interest"] = LabelLine("income.interest", D("150.5"), ("F1",))
    notes = check_reconcile(ctx)
    docs = [doc("D002", "INCSTMT"), doc("D003", "INCSTMT")]
    notes += check_reconcile(make_ctx([fig("F1", "income.salary", 85000, doc="D002"),
                                       fig("F2", "income.salary", 85000, doc="D003")], documents=docs))
    assert {"R1", "R2", "R4", "R5"} <= {n.check_id for n in notes}
    assert badly_formatted(notes) == []


def test_prefill_notes_show_cents():
    ctx = make_ctx([fig("F1", "income.interest", 400), fig("F2", "income.salary", 85000)],
                   prefill=[pre("income.interest", "412.35", "CBA"), pre("income.salary", 85000),
                            pre("income.div_franked", 1200, "BHP GROUP LTD")])
    notes = check_prefill(ctx)
    assert {"P1", "P2"} <= {n.check_id for n in notes}
    assert badly_formatted(notes) == []


def test_prefill_difference_below_prefill_shows_minus_sign_first():
    ctx = make_ctx([fig("F1", "income.interest", 400)], prefill=[pre("income.interest", "412.35", "CBA")])
    [note] = ids(check_prefill(ctx), "P1")
    assert "return $400.00 vs pre-fill $412.35 (difference -$12.35)" in note.message


def test_prior_year_notes_show_cents():
    ctx = make_ctx([fig("F1", "income.interest", "1300.5")],
                   prior_year={"income.interest": D("1000"), "rent.gross": D("26000")})
    notes = check_prior_year(ctx)
    assert {"Y1", "Y2"} <= {n.check_id for n in notes}
    assert badly_formatted(notes) == []
