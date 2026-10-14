import json

from checkctx import D, fig, ids, make_ctx

from tra.checks import run_all_checks
from tra.checks.notes import rank_notes
from tra.checks.prior_year import check_prior_year, load_prior_year
from tra.models import ReviewNote
from tra.workspace import Workspace


def _y(prior, *figures):
    return check_prior_year(make_ctx(list(figures), prior_year={k: D(str(v)) for k, v in prior.items()}))


def test_y1_pct_and_floor():
    [note] = ids(_y({"income.interest": 1000}, fig("F1", "income.interest", 1300)), "Y1")
    assert note.risk == "Medium" and note.dollar_impact == D("300") and "+30%" in note.message
    assert ids(_y({"income.interest": 10}, fig("F1", "income.interest", 15)), "Y1") == []
    assert ids(_y({"income.interest": 1000}, fig("F1", "income.interest", 1150)), "Y1") == []
    assert ids(_y({"ded.d5": 2000}, fig("F1", "ded.d5", 500, substantiated=True)), "Y1")


def test_y2_disappeared():
    [note] = ids(_y({"rent.gross": 26000}, fig("F1", "income.salary", 1)), "Y2")
    assert note.audience == "client" and note.action == "question" and note.label_key == "rent.gross"
    assert ids(_y({"rent.gross": 26000}, fig("F1", "rent.gross", 26000)), "Y2") == []


def test_no_prior_year_no_notes():
    assert check_prior_year(make_ctx([fig("F1", "income.interest", 100)])) == []


def test_prior_from_csv_or_last_return(tmp_path):
    ws = Workspace(tmp_path, "SMIT01", 2026)
    assert load_prior_year(ws) == {}
    last = ws.for_year(2025)
    last.work_dir.mkdir(parents=True)
    last.last_return_json.write_text(json.dumps({"income.interest": "300.00"}))
    assert load_prior_year(ws) == {"income.interest": D("300.00")}
    ws.work_dir.mkdir(parents=True)
    ws.prior_year_csv.write_text("label_key,amount\nincome.interest,250.00\n")
    assert load_prior_year(ws) == {"income.interest": D("250.00")}


def _n(risk, impact, check="X1", label=None, message="m", figures=()):
    return ReviewNote(risk, check, message, None if impact is None else D(impact), "reviewer", "confirm",
                      label_key=label, figure_ids=figures)


def test_rank_order_and_dedupe():
    notes = [_n("Medium", "5000", "M"), _n("High", None, "H3"), _n("Low", "9", "L"), _n("High", "10", "H2"),
             _n("High", "-500", "H1"), _n("High", "10", "H2")]
    ranked = rank_notes(notes)
    assert [n.check_id for n in ranked] == ["H1", "H2", "H3", "M", "L"]


def test_rank_keeps_distinct_notes_for_same_label():
    a = _n("High", "50", "R1", "ded.d9", "F1 has no source", ("F1",))
    b = _n("High", "20", "R1", "ded.d9", "F2 has no source", ("F2",))
    assert rank_notes([a, b]) == [a, b]


def test_run_all_checks_combines_and_ranks():
    ctx = make_ctx([fig("F1", "income.interest", 100, doc=None), fig("F2", "ded.d5", 520)],
                   prior_year={"income.interest": D("1000")})
    notes = run_all_checks(ctx)
    found = {n.check_id for n in notes}
    assert {"C2", "R1", "P3", "S2", "S4", "Y1"} <= found
    order = {"High": 0, "Medium": 1, "Low": 2}
    assert [order[n.risk] for n in notes] == sorted(order[n.risk] for n in notes)
