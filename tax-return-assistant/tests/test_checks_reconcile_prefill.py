from checkctx import D, doc, fig, ids, make_ctx, pre

from tra.checks.prefill import check_prefill
from tra.checks.reconcile import check_reconcile
from tra.models import ClientState


def test_r1_unsourced_and_unknown_doc():
    ctx = make_ctx([fig("F0001", "income.interest", 100), fig("F0002", "ded.d9", 50, doc=None),
                    fig("F0003", "ded.d5", 20, doc="D009")])
    notes = ids(check_reconcile(ctx), "R1")
    assert [n.figure_ids for n in notes] == [("F0002",), ("F0003",)]
    assert all(n.risk == "High" for n in notes)
    assert "D009" in notes[1].message
    assert notes[0].dollar_impact == D("50")


def test_r1_quiet_when_sourced():
    assert ids(check_reconcile(make_ctx([fig("F0001", "income.interest", 100)])), "R1") == []


def test_r2_label_total_mismatch():
    ctx = make_ctx([fig("F0001", "income.interest", 100)])
    assert ids(check_reconcile(ctx), "R2") == []
    from tra.return_.prepare import LabelLine
    ctx.draft.lines["income.interest"] = LabelLine("income.interest", D("150"), ("F0001",))
    [note] = ids(check_reconcile(ctx), "R2")
    assert note.risk == "High" and note.dollar_impact == D("50")


def test_r3_unconfirmed_listed_prefill_excluded():
    ctx = make_ctx([fig("F0001", "income.interest", 100, confirmed=False),
                    fig("F0002", "income.salary", 900, confirmed=False, notes="prefill"),
                    fig("F0003", "ded.d5", 20)])
    [note] = ids(check_reconcile(ctx), "R3")
    assert note.risk == "Medium" and note.figure_ids == ("F0001",)
    assert ids(check_reconcile(make_ctx([fig("F0003", "ded.d5", 20)])), "R3") == []


def test_r4_double_count():
    ctx = make_ctx([fig("F0001", "income.interest", "412.35"), fig("F0002", "income.interest", "412.35", notes="prefill")])
    [note] = ids(check_reconcile(ctx), "R4")
    assert note.risk == "High" and set(note.figure_ids) == {"F0001", "F0002"}
    ok = make_ctx([fig("F0001", "income.interest", "412.35"), fig("F0002", "income.interest", "412.35", confirmed=False,
                                                                   notes="prefill")])
    assert ids(check_reconcile(ok), "R4") == []


def test_p1_difference():
    ctx = make_ctx([fig("F0001", "income.interest", "400.00")], prefill=[pre("income.interest", "412.35", "CBA")])
    [note] = ids(check_prefill(ctx), "P1")
    assert note.risk == "High" and note.dollar_impact == D("12.35")
    within = make_ctx([fig("F0001", "income.interest", "411.50")], prefill=[pre("income.interest", "412.35")])
    assert ids(check_prefill(within), "P1") == []


def test_p2_prefill_item_missing():
    ctx = make_ctx([fig("F0001", "income.salary", 85000)],
                   prefill=[pre("income.salary", 85000), pre("income.div_franked", 1200, "BHP GROUP LTD")])
    [note] = ids(check_prefill(ctx), "P2")
    assert "BHP GROUP LTD" in note.message and note.label_key == "income.div_franked"
    assert ids(check_prefill(ctx), "P1") == []


def test_p3_no_prefill_document():
    assert ids(check_prefill(make_ctx([], documents=[doc("D001", "INCSTMT")])), "P3")[0].risk == "Medium"
    assert ids(check_prefill(make_ctx([], documents=[doc("D001", "PREFILL")])), "P3") == []


def test_p4_help_mismatch():
    with_debt = ClientState("TEST01", 2026, help_debt=True)
    assert ids(check_prefill(make_ctx([], prefill=[pre("help.indicator", 1)])), "P4")
    assert ids(check_prefill(make_ctx([], state=with_debt)), "P4")
    assert ids(check_prefill(make_ctx([], prefill=[pre("help.indicator", 1)], state=with_debt)), "P4") == []


def test_phi_totals_compared():
    figures = [fig("F0001", "phi.premiums_p1", 1800), fig("F0002", "phi.premiums_p2", 500)]
    ctx = make_ctx(figures, prefill=[pre("phi.premiums_total", 2400, "FUND")])
    [note] = ids(check_prefill(ctx), "P1")
    assert note.dollar_impact == D("100")
    ok = make_ctx([fig("F0001", "phi.premiums_p1", 1800), fig("F0002", "phi.premiums_p2", 600)],
                  prefill=[pre("phi.premiums_total", 2400)])
    assert ids(check_prefill(ok), "P1") == []
    missing = make_ctx([], prefill=[pre("phi.rebate_total", "581.89", "FUND")])
    assert ids(check_prefill(missing), "P2")
