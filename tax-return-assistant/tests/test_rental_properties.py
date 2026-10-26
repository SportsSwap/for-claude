"""Rental properties: the client's share, private use and the firm's rows (docs/specs/2026-10-26-rental-properties-
design.md). Made-up data only."""

import json
from decimal import Decimal

import pytest
from webctx import make_client, new_client

from tra.labels import load_labels
from tra.models import Figure
from tra.privacy.audit import AuditLog
from tra.rental import (ROWS, Property, RentalSetup, compute, default_setup, load_rental, rental_return_totals,
                        save_rental)
from tra.return_.prepare import build_draft

LABELS = load_labels()


def _fig(fid, key, amount, doc="D001", description="x"):
    return Figure(fid, key, description, Decimal(amount), None, doc, 1, "parser", True, None, "")


def _setup(**kw):
    p = Property(id="P1", name="Property 1", share=Decimal(kw.pop("share", "100")),
                 private_use=Decimal(kw.pop("private_use", "0")), **kw)
    return RentalSetup(properties=[p])


# --- the rows ----------------------------------------------------------------------------------------------------

def test_rows_follow_the_firms_sheet():
    assert [r.letter for r in ROWS] == list("ABCDEFGHIJKLMNOPQRSTUVWX")
    assert [r.heading for r in ROWS if r.key] == [
        "Rental Income", "Other Income", "Advertising", "Body Corporate", "Borrowing Expenses", "Cleaning",
        "Council Rates", "Deductions for Decline in Value", "Gardening/Lawnmowing", "Insurance", "Interest on Loans",
        "Land Tax", "Legal Expenses", "Pest Control", "Agent Fees", "Repairs and Maintenance",
        "Capital Works Deductions", "Office Supplies", "Travel Expenses", "Water Charges", "Sundry Rental Expenses"]
    assert {r.key for r in ROWS if r.key} == {k for k, d in LABELS.items() if d.tab == "M25 Rental Property"}
    assert [r.letter for r in ROWS if r.itemised] == ["Q", "V"]


def test_other_rental_income_is_part_of_gross_rent():
    d = LABELS["rent.other_income"]
    assert (d.item, d.label, d.part_of, d.role) == ("21", "P", "rent.gross", "rental_income")


# --- the share and private use ------------------------------------------------------------------------------------

def test_a_half_share_halves_everything():
    figures = [_fig("F1", "rent.gross", "24000.00"), _fig("F2", "rent.other_income", "100.01"),
               _fig("F3", "rent.interest", "21000.40", doc="D002"), _fig("F4", "rent.council_rates", "1234.55")]
    totals = rental_return_totals(figures, _setup(share="50"), LABELS)
    assert totals == {"rent.gross": Decimal("12050.01"), "rent.interest": Decimal("10500.20"),
                      "rent.other": Decimal("617.28")}  # 1234.55 / 2 = 617.275 -> 617.28, rounded half up like Excel


def test_itemised_rows_round_each_line():
    figures = [_fig("F1", "rent.repairs", "211.50"), _fig("F2", "rent.repairs", "430.00")]
    [result] = compute(figures, _setup(share="50"), LABELS)
    repairs = result.row("Q")
    assert [line.share for line in repairs.lines] == [Decimal("105.75"), Decimal("215.00")]
    assert repairs.share == Decimal("320.75")


def test_private_use_reduces_ticked_rows_only():
    figures = [_fig("F1", "rent.gross", "10000"), _fig("F2", "rent.insurance", "1000"),
               _fig("F3", "rent.agent_fees", "800")]
    [result] = compute(figures, _setup(private_use="25"), LABELS)
    assert result.row("A").share == Decimal("10000.00")   # income is never apportioned
    assert result.row("K").share == Decimal("750.00")     # insurance: ticked by default
    assert result.row("P").share == Decimal("800.00")     # agent fees: not ticked by default


def test_an_untick_turns_apportioning_off():
    figures = [_fig("F2", "rent.insurance", "1000")]
    setup = _setup(private_use="25", apportion={"rent.insurance": False})
    assert compute(figures, setup, LABELS)[0].row("K").share == Decimal("1000.00")


def test_this_taxpayer_only_isnt_shared():
    figures = [_fig("F1", "rent.insurance", "1000"), _fig("F2", "rent.insurance", "300")]
    setup = _setup(share="50")
    setup.columns = {"F2": "taxpayer"}
    row = compute(figures, setup, LABELS)[0].row("K")
    assert (row.agent, row.owners, row.taxpayer, row.share) == (Decimal("0"), Decimal("1000"), Decimal("300"),
                                                                Decimal("800.00"))


def test_statement_figures_go_to_the_agent_column():
    figures = [_fig("F1", "rent.council_rates", "100", doc="D001"), _fig("F2", "rent.council_rates", "50", doc="D002")]
    row = compute(figures, _setup(), LABELS, doc_types={"D001": "RENTSTMT", "D002": "OTHER"})[0].row("H")
    assert (row.agent, row.owners) == (Decimal("100"), Decimal("50"))


def test_return_labels_per_property():
    figures = [_fig("F1", "rent.gross", "20000"), _fig("F2", "rent.interest", "5000"),
               _fig("F3", "rent.capital_works", "2500"), _fig("F4", "rent.water", "700"), _fig("F5", "rent.other", "30")]
    [result] = compute(figures, _setup(), LABELS)
    assert result.return_labels == {"rent.gross": Decimal("20000.00"), "rent.interest": Decimal("5000.00"),
                                    "rent.capital_works": Decimal("2500.00"), "rent.other": Decimal("730.00")}
    assert result.row("W").share == Decimal("8230.00") and result.row("X").share == Decimal("11770.00")


# --- two properties -----------------------------------------------------------------------------------------------

def test_documents_go_to_their_property():
    p1 = Property(id="P1", name="Sample St", share=Decimal("50"))
    p2 = Property(id="P2", name="Example Rd", share=Decimal("100"))
    setup = RentalSetup(properties=[p1, p2], documents={"D001": "P1", "D002": "P2"})
    figures = [_fig("F1", "rent.gross", "1000", doc="D001"), _fig("F2", "rent.gross", "3000", doc="D002"),
               _fig("F3", "rent.gross", "500", doc="D003")]  # D003 not assigned: the first property
    results = compute(figures, setup, LABELS)
    assert [(r.prop.id, r.row("A").share) for r in results] == [("P1", Decimal("750.00")), ("P2", Decimal("3000.00"))]
    assert results[0].unassigned_docs == ["D003"]
    assert rental_return_totals(figures, setup, LABELS)["rent.gross"] == Decimal("3750.00")


# --- the draft return ---------------------------------------------------------------------------------------------

def test_the_draft_return_uses_the_share():
    figures = [_fig("F1", "rent.gross", "20000"), _fig("F2", "rent.gardening", "300"), _fig("F3", "income.salary", "1")]
    draft = build_draft("TEST01", 2026, figures, [], LABELS, rental=_setup(share="50"))
    assert draft.amount("rent.gross") == Decimal("10000.00") and draft.amount("rent.other") == Decimal("150.00")
    assert draft.amount("income.salary") == Decimal("1")
    assert set(draft.lines["rent.other"].figure_ids) == {"F2"}


def test_without_a_setup_the_draft_claims_it_all():
    figures = [_fig("F1", "rent.gross", "20000"), _fig("F2", "rent.other_income", "50")]
    draft = build_draft("TEST01", 2026, figures, [], LABELS)
    assert draft.amount("rent.gross") == Decimal("20050.00")


# --- S18 ------------------------------------------------------------------------------------------------------------

def _s18(figures, rental):
    from checkctx import ids, make_ctx

    from tra.checks.sanity import check_sanity
    return ids(check_sanity(make_ctx(figures, rental=rental)), "S18")


def test_s18_when_the_share_is_assumed():
    [note] = _s18([_fig("F1", "rent.gross", "20000")], None)
    assert note.risk == "Medium" and "assumed" in note.message and "100%" in note.message
    assert "Rental page" in note.message


def test_s18_when_the_share_was_only_suggested():
    setup = _setup(share="50", share_source="suggested", share_doc="D003")
    [note] = _s18([_fig("F1", "rent.gross", "20000")], setup)
    assert "50%" in note.message and "D003" in note.message


def test_no_s18_once_a_person_sets_the_share():
    assert _s18([_fig("F1", "rent.gross", "20000")], _setup(share="50", share_source="person")) == []
    assert _s18([_fig("F1", "income.salary", "1")], None) == []  # no rental at all


def test_s18_for_a_document_with_no_property():
    setup = RentalSetup(properties=[Property(id="P1", name="Sample St", share_source="person"),
                                    Property(id="P2", name="Example Rd", share_source="person")])
    [note] = _s18([_fig("F1", "rent.gross", "20000", doc="D004")], setup)
    assert "D004" in note.message and "Sample St" in note.message


# --- the readers suggest the share --------------------------------------------------------------------------------

def _statement(*extra):
    from tra.privacy.redact import redact_pages
    return redact_pages(["Rental statement", "Property manager: SAMPLE REALTY", *extra, "Total rent received 26,000.00",
                         "Council rates 2,100.00", "Total expenses 2,100.00", "Net to owner 23,900.00"])


@pytest.mark.parametrize("line, share", [("Ownership share 50%", "50"), ("Owner's share: 50 %", "50"),
                                         ("Your share 33.33%", "33.33"), ("Ownership: 100%", "100")])
def test_the_statement_reader_finds_the_share(line, share):
    from tra.ingest.extractors import get_extractor
    result = get_extractor("RENTSTMT").extract(_statement(line), "D001")
    assert result.facts["ownership_share"] == Decimal(share)


@pytest.mark.parametrize("line", ["Management fee 5.5%", "GST 10%", "Share of costs 150%"])
def test_other_percentages_arent_a_share(line):
    from tra.ingest.extractors import get_extractor
    assert "ownership_share" not in get_extractor("RENTSTMT").extract(_statement(line), "D001").facts


@pytest.mark.parametrize("given, kept", [(50, Decimal("50")), (33.5, Decimal("33.5")), (None, None), (150, None),
                                         (-5, None), ("half", None)])
def test_the_ai_reports_the_share_as_a_number_only(given, kept):
    from test_ai_reader import FakeClient

    from tra.ingest.extractors.ai_reader import AiReader
    from tra.privacy.redact import redact_pages
    answer = json.dumps({"doc_type": "RENTSTMT", "figures": [], "ownership_percent": given})
    client = FakeClient(answer)
    result = AiReader(client).extract(redact_pages(["SAMPLE REALTY owner statement"]), "D001")
    assert result.facts.get("ownership_share") == kept
    schema = client.calls[0]["output_config"]["format"]["schema"]
    assert "ownership_percent" in schema["required"]
    assert "never" in client.calls[0]["system"].lower() and "ownership_percent" in client.calls[0]["system"]


def _ingest_statement(settings, ws, tmp_path, name, *lines):
    from tra.demo import _write_pdf
    from tra.filing.local_store import LocalStore
    from tra.ingest.classify import load_doc_types
    from tra.ingest.pipeline import ingest_file
    path = tmp_path / name
    _write_pdf(path, ["Rental statement", "Property manager: SAMPLE REALTY", *lines, "Total rent received 26,000.00",
                      "Council rates 2,100.00", "Total expenses 2,100.00", "Net to owner 23,900.00"])
    return ingest_file(path, ws, LocalStore(settings.tra_home), load_doc_types(), AuditLog(ws.audit_path))


def test_an_imported_statement_suggests_the_share(tmp_path, monkeypatch):
    from tra.reading_notes import load_reading_notes
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    report = _ingest_statement(settings, ws, tmp_path, "a.pdf", "Ownership share 50%")
    [p] = load_rental(ws).properties
    assert (p.share, p.share_source, p.share_doc) == (Decimal("50"), "suggested", report.doc.doc_id)
    doubts = load_reading_notes(ws)[report.doc.doc_id]["doubts"]
    assert "Ownership share 50% read from this document: check it on the Rental page." in doubts


def test_a_share_a_person_set_is_never_changed(tmp_path, monkeypatch):
    from tra.reading_notes import load_reading_notes
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    save_rental(ws, _setup(share="100", share_source="person"), AuditLog(ws.audit_path))
    report = _ingest_statement(settings, ws, tmp_path, "a.pdf", "Ownership share 50%")
    [p] = load_rental(ws).properties
    assert (p.share, p.share_source) == (Decimal("100"), "person")
    doubts = load_reading_notes(ws)[report.doc.doc_id]["doubts"]
    assert any("50%" in d and "100%" in d for d in doubts)


# --- saving -------------------------------------------------------------------------------------------------------

def test_no_file_means_one_default_property(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    setup = load_rental(ws)
    assert setup == default_setup()
    [p] = setup.properties
    assert (p.id, p.name, p.share, p.share_source, p.private_use, p.weeks_rented, p.weeks_available) == (
        "P1", "Property 1", Decimal("100"), "default", Decimal("0"), 52, 52)


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    setup = RentalSetup(properties=[Property(id="P1", name="Sample St", share=Decimal("50"), share_source="person",
                                             private_use=Decimal("10"), weeks_rented=40, weeks_available=48,
                                             first_income="2019-07-01", apportion={"rent.insurance": False})],
                        documents={"D003": "P1"}, columns={"F0004": "taxpayer"})
    save_rental(ws, setup, AuditLog(ws.audit_path))
    assert load_rental(ws) == setup
    entries = [json.loads(line) for line in ws.audit_path.read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["action"] == "rental_changed" and "Sample St" not in json.dumps(entries[-1])


@pytest.mark.parametrize("bad", [{"share": "150"}, {"share": "-1"}, {"private_use": "101"}, {"weeks_rented": 53},
                                 {"name": ""}, {"name": "x" * 40}])
def test_bad_values_are_refused(tmp_path, monkeypatch, bad):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    fields = {"id": "P1", "name": "Sample St", "share": Decimal("50")}
    fields.update({k: (Decimal(v) if k in ("share", "private_use") else v) for k, v in bad.items()})
    with pytest.raises(ValueError):
        save_rental(ws, RentalSetup(properties=[Property(**fields)]), AuditLog(ws.audit_path))
    assert not ws.rental_json.exists()
