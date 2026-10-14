from datetime import date

from checkctx import D, doc, fig, ids, make_ctx

from tra.checks import load_citations
from tra.checks.sanity import check_sanity
from tra.figures import CgtEvent
from tra.models import ClientState


def run(*figures, documents=None, state=None, cgt_events=()):
    return check_sanity(make_ctx(list(figures), documents=documents, state=state, cgt_events=cgt_events))


def test_citations_load():
    c = load_citations()
    assert c["itaa97_s900_35"]["ref"] == "ITAA 1997 s900-35"
    assert all(v["verified"] is False for v in c.values())


def test_s1_deductions_vs_income():
    assert ids(run(fig("F1", "income.salary", 50000), fig("F2", "ded.d15", 20000)), "S1")
    assert ids(run(fig("F1", "income.salary", 50000), fig("F2", "ded.d5", 9000, substantiated=True)), "S1")
    assert ids(run(fig("F1", "income.salary", 50000), fig("F2", "ded.d5", 1000, substantiated=True)), "S1") == []


def test_s2_missing_expected_document():
    docs = [doc("D001", "PREFILL"), doc("D002", "DIVSTMT")]
    notes = run(fig("F1", "income.interest", 400, doc="D001"), fig("F2", "income.div_franked", 100, doc="D002"),
                documents=docs)
    [note] = ids(notes, "S2")
    assert note.label_key == "income.interest" and note.audience == "client"
    ok = run(fig("F1", "income.interest", 400, doc="D003"), documents=[doc("D003", "BANKSTMT")])
    assert ids(ok, "S2") == []


def test_s3_rental_one_sided():
    assert ids(run(fig("F1", "rent.gross", 20000)), "S3")
    assert ids(run(fig("F1", "rent.other", 500)), "S3")
    assert ids(run(fig("F1", "rent.gross", 20000), fig("F2", "rent.other", 500)), "S3") == []


def test_s4_substantiation():
    [note] = ids(run(fig("F1", "ded.d5", 300), fig("F2", "ded.d5", 220, substantiated=None)), "S4")
    assert note.risk == "High" and note.citation_id == "itaa97_s900_35" and note.dollar_impact == D("520")
    assert ids(run(fig("F1", "ded.d5", 280)), "S4") == []
    assert ids(run(fig("F1", "ded.d5", 520, substantiated=True)), "S4") == []


def test_s5_car_cap():
    [note] = ids(run(fig("F1", "ded.d1", 4500, substantiated=True)), "S5")
    assert note.citation_id == "itaa97_s28_25" and note.risk == "High"
    assert ids(run(fig("F1", "ded.d1", 4500, substantiated=True, notes="logbook 62%")), "S5") == []
    assert ids(run(fig("F1", "ded.d1", 4400, substantiated=True)), "S5") == []


def test_s6_clothing():
    assert ids(run(fig("F1", "ded.d3", 150, description="Black work pants")), "S6")[0].citation_id == "tr97_12"
    assert ids(run(fig("F1", "ded.d3", 150, description="Hi-vis safety vest")), "S6") == []


def test_s7_capital_vs_repair():
    [note] = ids(run(fig("F1", "rent.gross", 9000), fig("F2", "rent.other", 4000, description="Replace hot water system")), "S7")
    assert note.citation_id == "tr97_23"
    assert ids(run(fig("F1", "rent.gross", 9000), fig("F2", "rent.other", 400, description="Repairs - leaking tap")), "S7") == []


def _event(acquired, disposed):
    return CgtEvent("C001", "BHP shares", acquired, disposed, D("15000"), D("9000"), "D001", 1, True)


def test_s8_cgt_dates():
    near = ids(run(cgt_events=[_event(date(2025, 3, 1), date(2026, 3, 15))]), "S8")
    assert [n.risk for n in near] == ["High"] and near[0].citation_id == "itaa97_s115_25"
    far = ids(run(cgt_events=[_event(date(2020, 3, 1), date(2026, 3, 15))]), "S8")
    assert [n.risk for n in far] == ["Medium"]
    assert ids(run(), "S8") == []


def test_s9_mls_exposure():
    question = ids(run(fig("F1", "income.salary", 120000), state=ClientState("TEST01", 2026, hospital_cover_days=200)), "S9")
    assert question and question[0].audience == "client" and question[0].action == "question"
    assumed = ids(run(fig("F1", "income.salary", 120000)), "S9")
    assert assumed and assumed[0].action == "assumption"
    assert ids(run(fig("F1", "income.salary", 90000)), "S9") == []
    assert ids(run(fig("F1", "income.salary", 120000), state=ClientState("TEST01", 2026, hospital_cover_days=365)), "S9") == []


def test_s10_interest_purpose():
    assert ids(run(fig("F1", "rent.gross", 9000), fig("F2", "rent.interest", 8000, description="Redraw loan interest")), "S10")
    assert ids(run(fig("F1", "rent.gross", 9000), fig("F2", "rent.interest", 8000, description="Loan interest")), "S10") == []


def test_s11_gifts():
    assert ids(run(fig("F1", "ded.d9", "1.50", description="Red Cross DGR")), "S11")
    assert ids(run(fig("F1", "ded.d9", 50, description="School raffle")), "S11")
    assert ids(run(fig("F1", "ded.d9", 50, description="Red Cross (DGR)")), "S11") == []


def test_s12_unhandled_areas():
    assert ids(run(documents=[doc("D001", "MFUND")]), "S12")
    assert ids(run(state=ClientState("TEST01", 2026, has_spouse=True)), "S12")
    assert ids(run(fig("F1", "income.business_income", 1000)), "S12")
    assert ids(run(documents=[doc("D001", "CGT")]), "S12")
    assert ids(run(documents=[doc("D001", "CGT")], cgt_events=[_event(date(2020, 1, 1), date(2026, 1, 1))]), "S12") == []
    assert ids(run(), "S12") == []


def test_s13_asset_claimed_outright():
    [note] = ids(run(fig("F1", "ded.d5", 1499, substantiated=True, description="OFFICEWORKS: Laptop computer")), "S13")
    assert note.citation_id == "itaa97_s40_80" and note.risk == "Medium"
    assert ids(run(fig("F1", "ded.d5", 250, substantiated=True, description="Laptop bag")), "S13") == []
    assert ids(run(fig("F1", "ded.d5", 520, description="Union fees")), "S13") == []


def test_s14_residency_assumed_and_non_resident_flagged():
    [note] = ids(run(fig("F1", "income.salary", 50000)), "S14")
    assert note.risk == "Low" and note.action == "assumption"
    flagged = run(fig("F1", "income.salary", 50000), state=ClientState("TEST01", 2026, resident=False))
    assert any(n.check_id == "S12" and "resident" in n.message.lower() for n in flagged)
    assert ids(flagged, "S14") == []


def test_s12_financial_investment_deductions():
    assert any("investment loss" in n.message for n in ids(run(fig("F1", "ded.d8", 900)), "S12"))
