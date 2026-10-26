"""Fixes from the independent review of rental properties (26 Oct 2026). Made-up data only."""

import json
from decimal import Decimal

import openpyxl
import pytest
from webctx import ingest_demo, make_client, new_client
from wpctx import demo_context

from tra.models import Figure
from tra.privacy.audit import AuditLog
from tra.rental import (Property, RentalFileProblem, RentalSetup, load_rental, save_rental, suggest_share, validate)
from tra.workpaper.build import _q, build_workpaper, rental_tab_name

SUMMARY = "B01 Summary"


def _summary_formula(wb, key):
    ws = wb[SUMMARY]
    row = next(r for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=13).value == key)
    return ws.cell(row=row, column=6).value


# --- 1. an apostrophe in a property name -------------------------------------------------------------------------

def test_quoted_tab_names_double_an_apostrophe():
    assert _q("M25 Rental O'Brien St") == "'M25 Rental O''Brien St'"
    assert not rental_tab_name("Smith'", set()).endswith("'")  # Excel won't take a name ending in one


def test_an_apostrophe_name_still_reaches_the_summary(tmp_path):
    rental = RentalSetup(properties=[Property(id="P1", name="O'Brien St", share_source="person")])
    ctx = demo_context(tmp_path, rental=rental)
    build_workpaper(tmp_path / "wp.xlsx", ctx)
    wb = openpyxl.load_workbook(tmp_path / "wp.xlsx")
    assert "M25 Rental O'Brien St" in wb.sheetnames
    assert _summary_formula(wb, "rent.gross").startswith("='M25 Rental O''Brien St'!H")


# --- 2. names that differ only in capitals ----------------------------------------------------------------------

def test_tab_names_never_clash_ignoring_capitals():
    assert rental_tab_name("sample st", {"M25 Rental Sample St"}) == "M25 Rental sample st 2"


def test_two_properties_cant_share_a_name():
    setup = RentalSetup(properties=[Property(id="P1", name="Sample St"), Property(id="P2", name="sample st ")])
    with pytest.raises(ValueError, match="different name"):
        validate(setup)


# --- 3 and 4. NaN and a blank share -------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["NaN", "sNaN", "Infinity", "-inf", "1e2"])
def test_not_a_real_number_is_refused(bad):
    setup = RentalSetup(properties=[Property(id="P1", name="Sample St", share=Decimal(bad))])
    with pytest.raises(ValueError):
        validate(setup)


def _post(web, **fields):
    data = {"name": "Sample St", "share": "50", "private_use": "0", "weeks_rented": "52", "weeks_available": "52"}
    data.update(fields)
    return web.post("/c/TEST01/2026/rental/P1", data=data, follow_redirects=True)


@pytest.mark.parametrize("share", ["", "  ", "NaN", "abc"])
def test_the_rental_page_refuses_a_missing_or_odd_share(tmp_path, monkeypatch, share):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ingest_demo(settings, ws, "rental")
    resp = _post(web, share=share)
    assert resp.status_code == 200 and "share" in resp.get_data(as_text=True).lower()
    assert load_rental(ws).properties[0].share_source == "default"


def test_private_use_left_blank_is_nil(tmp_path, monkeypatch):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ingest_demo(settings, ws, "rental")
    _post(web, private_use="")
    assert load_rental(ws).properties[0].private_use == Decimal("0")


# --- 5. a damaged rental.json --------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["{", "[]", '{"properties": "x"}', '{"properties": [{"id": "P1", "name": "A"}]}',
                                  '{"properties": [{"id": "P1", "name": "A", "share": "abc"}]}',
                                  '{"properties": [{"id": "P1", "name": "A", "share": "NaN"}]}'])
def test_a_damaged_file_says_so_plainly(tmp_path, monkeypatch, text):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ws.rental_json.parent.mkdir(parents=True, exist_ok=True)
    ws.rental_json.write_text(text, encoding="utf-8")
    with pytest.raises(RentalFileProblem, match="rental.json"):
        load_rental(ws)
    assert web.get("/c/TEST01/2026/rental").status_code == 200  # the page explains, it doesn't crash


def test_prepare_reports_a_damaged_file(tmp_path, monkeypatch):
    from tra.run import PrepareError, prepare_client
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ws.rental_json.write_text("{", encoding="utf-8")
    with pytest.raises(PrepareError, match="rental.json"):
        prepare_client(ws, AuditLog(ws.audit_path), "tester")


def test_an_import_still_works_with_a_damaged_file(tmp_path, monkeypatch):
    from tra.reading_notes import load_reading_notes
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ws.rental_json.write_text("{", encoding="utf-8")
    doubt = suggest_share(ws, "D001", Decimal("50"), AuditLog(ws.audit_path))
    assert "rental.json" in doubt and ws.rental_json.read_text(encoding="utf-8") == "{"  # left for a person
    assert load_reading_notes(ws) == {}


# --- 6 and 7. which property a suggestion is for --------------------------------------------------------------------

def _two(ws, **p1):
    setup = RentalSetup(properties=[Property(id="P1", name="Sample St", **p1), Property(id="P2", name="Example Rd")])
    save_rental(ws, setup, AuditLog(ws.audit_path))


def test_with_two_properties_an_unassigned_document_only_adds_a_note(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    _two(ws)
    doubt = suggest_share(ws, "D007", Decimal("50"), AuditLog(ws.audit_path))
    assert "pick its property" in doubt.lower()
    assert [p.share_source for p in load_rental(ws).properties] == ["default", "default"]


def test_a_different_second_suggestion_doesnt_replace_the_first(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    audit = AuditLog(ws.audit_path)
    suggest_share(ws, "D001", Decimal("50"), audit)
    doubt = suggest_share(ws, "D002", Decimal("25"), audit)
    [p] = load_rental(ws).properties
    assert (p.share, p.share_doc) == (Decimal("50"), "D001")
    assert "25%" in doubt and "50%" in doubt


def test_a_document_pointing_at_a_removed_property(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ws.rental_json.write_text(json.dumps({"properties": [{"id": "P1", "name": "A", "share": "100",
                                                          "share_source": "default"}],
                                          "documents": {"D003": "P9"}}), encoding="utf-8")
    suggest_share(ws, "D003", Decimal("50"), AuditLog(ws.audit_path))
    assert load_rental(ws).properties[0].share == Decimal("50")


# --- 8. text that looks like a formula -------------------------------------------------------------------------------

def test_text_starting_with_an_equals_sign_stays_text(tmp_path):
    def mutate(figures):
        figures.append(Figure("F0901", "rent.repairs", "=HYPERLINK(\"x\")", Decimal("10"), None, "D099", 1,
                              "manual", True, None, ""))
    rental = RentalSetup(properties=[Property(id="P1", name="=1+2", share_source="person")])
    ctx = demo_context(tmp_path, rental=rental, mutate=mutate)
    build_workpaper(tmp_path / "wp.xlsx", ctx)
    wb = openpyxl.load_workbook(tmp_path / "wp.xlsx")
    ws = next(wb[n] for n in wb.sheetnames if n.startswith("M25"))
    cells = [c for row in ws.iter_rows() for c in row if c.value in ("=1+2", '=HYPERLINK("x")')]
    assert len(cells) >= 2 and all(c.data_type == "s" for c in cells)


def test_the_guard_checks_text_that_starts_with_an_equals_sign(make_tfn):
    from tra.privacy.guard import SensitiveDataBlocked, check_workbook
    wb = openpyxl.Workbook()
    cell = wb.active["A1"]
    cell.value = f"={make_tfn()}"
    cell.data_type = "s"
    with pytest.raises(SensitiveDataBlocked):
        check_workbook(wb, "x.xlsx")


# --- 9. Save columns only keeps real changes ---------------------------------------------------------------------------

def test_save_columns_keeps_only_real_changes(tmp_path, monkeypatch):
    from tra.web.services.figures import figure_rows
    _app, web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ingest_demo(settings, ws, "rental")
    rental = [f for f in figure_rows(ws) if f.label_key.startswith("rent.")]
    form = {f"col-{f.figure_id}": "agent" for f in rental}  # every dropdown as it was (the statement: agent)
    form[f"col-{rental[1].figure_id}"] = "taxpayer"
    resp = web.post("/c/TEST01/2026/rental/columns", data=form, follow_redirects=True)
    assert load_rental(ws).columns == {rental[1].figure_id: "taxpayer"}
    assert "1 figure moved" in resp.get_data(as_text=True)
    form[f"col-{rental[1].figure_id}"] = "agent"  # moved back to its default: nothing stored
    web.post("/c/TEST01/2026/rental/columns", data=form)
    assert load_rental(ws).columns == {}
