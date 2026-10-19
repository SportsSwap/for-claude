"""R7: a document used in the return is dated outside the income year (FY2026 = 1 Jul 2025 to 30 Jun 2026)."""

import dataclasses
from datetime import date

from checkctx import D, doc, fig, ids, make_ctx, pre

from tra.checks import run_all_checks
from tra.checks.reconcile import check_reconcile


def dated(doc_id, doc_type, when, *, detected=True):
    return dataclasses.replace(doc(doc_id, doc_type), doc_date=when, date_detected=detected)


def r7(documents, figures=(), prefill=()):
    return ids(check_reconcile(make_ctx(list(figures), documents=documents, prefill=list(prefill))), "R7")


def test_r7_dividend_paid_in_an_earlier_year():
    # The TEST02 trial: a dividend paid 28 March 2025 (FY2025) imported into the FY2026 return.
    figures = [fig("F0001", "income.div_franked", 1200, doc="D002"),
               fig("F0002", "income.franking_credit", "514.29", doc="D002")]
    [note] = r7([doc("D001"), dated("D002", "DIVSTMT", date(2025, 3, 28))], figures)
    assert note.risk == "Medium" and note.doc_ids == ("D002",)
    assert note.figure_ids == ("F0001", "F0002")
    assert note.dollar_impact == D("1714.29")
    assert "28 Mar 2025" in note.message and "FY2026" in note.message
    assert "1 Jul 2025 to 30 Jun 2026" in note.message
    assert "Confirm which income year" in note.message
    assert note.citation_id is None
    assert (note.audience, note.action) == ("preparer", "confirm")


def test_r7_runs_with_every_other_check():
    ctx = make_ctx([fig("F0001", "income.div_franked", 1200, doc="D002")],
                   documents=[dated("D002", "DIVSTMT", date(2025, 3, 28))])
    assert len(ids(run_all_checks(ctx), "R7")) == 1


def test_r7_quiet_for_dates_inside_the_year_including_30_june():
    documents = [dated("D001", "INCSTMT", date(2026, 6, 30)), dated("D002", "BANKSTMT", date(2026, 6, 30)),
                 dated("D003", "RECEIPT", date(2025, 7, 1)), dated("D004", "DIVSTMT", date(2026, 3, 24))]
    figures = [fig("F0001", "income.salary", 85000, doc="D001"), fig("F0002", "income.interest", 40, doc="D002"),
               fig("F0003", "ded.d5", 20, doc="D003"), fig("F0004", "income.div_franked", 900, doc="D004")]
    assert r7(documents, figures) == []


def test_r7_annual_statement_issued_within_120_days_after_year_end_is_fine():
    types = {"D001": "INCSTMT", "D002": "INTSTMT", "D003": "MFUND", "D004": "PHI", "D005": "RENTSTMT"}
    keys = {"INCSTMT": "income.salary", "INTSTMT": "income.interest", "MFUND": "income.interest",
            "PHI": "phi.premiums_p1", "RENTSTMT": "rent.gross"}
    figures = [fig(f"F000{i}", keys[t], 100, doc=d) for i, (d, t) in enumerate(types.items(), start=1)]
    day_120 = date(2026, 10, 28)
    assert r7([dated(d, t, day_120) for d, t in types.items()], figures) == []
    later = r7([dated(d, t, date(2026, 10, 29)) for d, t in types.items()], figures)
    assert [n.doc_ids for n in later] == [(d,) for d in types]


def test_r7_other_documents_dated_after_year_end():
    documents = [dated("D002", "DIVSTMT", date(2026, 7, 15)), dated("D003", "RECEIPT", date(2026, 7, 2)),
                 dated("D004", "BANKSTMT", date(2026, 7, 31))]
    figures = [fig("F0001", "income.div_franked", 500, doc="D002"), fig("F0002", "ded.d5", 80, doc="D003"),
               fig("F0003", "income.interest", 12, doc="D004")]
    notes = r7(documents, figures)
    assert [n.doc_ids for n in notes] == [("D002",), ("D003",), ("D004",)]
    assert "2 Jul 2026" in notes[1].message


def test_r7_annual_statement_from_before_the_year():
    figures = [fig("F0001", "income.interest", 300, doc="D002")]
    [note] = r7([dated("D002", "INTSTMT", date(2025, 6, 30))], figures)
    assert "30 Jun 2025" in note.message


def test_r7_prefill_issued_after_year_end_is_fine_however_late():
    lines = [pre("income.salary", 85000, doc_id="D001")]
    assert r7([dated("D001", "PREFILL", date(2026, 7, 15))], prefill=lines) == []
    assert r7([dated("D001", "PREFILL", date(2028, 3, 1))], prefill=lines) == []
    assert r7([dated("D001", "PREFILL", date(2026, 6, 30))], prefill=lines) == []


def test_r7_prefill_dated_during_or_before_the_year():
    lines = [pre("income.salary", 85000, doc_id="D001")]
    [during] = r7([dated("D001", "PREFILL", date(2025, 7, 20))], prefill=lines)
    assert during.risk == "Medium" and during.doc_ids == ("D001",)
    assert "20 Jul 2025" in during.message and "earlier year" in during.message
    assert during.dollar_impact is None
    [before] = r7([dated("D001", "PREFILL", date(2025, 6, 30))], prefill=lines)
    assert "30 Jun 2025" in before.message


def test_r7_skips_documents_not_used_or_undated():
    unconfirmed = [fig("F0001", "income.div_franked", 1200, doc="D002", confirmed=False)]
    assert r7([dated("D002", "DIVSTMT", date(2025, 3, 28))], unconfirmed) == []
    assert r7([dated("D001", "PREFILL", date(2025, 7, 20))]) == []  # no pre-fill lines read from it
    # Undated: the filename used the ingest date and I2 already says so.
    confirmed = [fig("F0001", "ded.d5", 50, doc="D002")]
    assert r7([dated("D002", "RECEIPT", date(2026, 10, 19), detected=False)], confirmed) == []
