"""Clients' own spreadsheets: rows with words Sawnx knows become suggested figures; the rest go to Things to check.

Every spreadsheet here is made up at test time.
"""

import csv
from datetime import datetime
from decimal import Decimal

import openpyxl
import pytest

from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.extractors import get_extractor
from tra.ingest.extractors.words import load_sheet_words, match_labels
from tra.ingest.pipeline import ingest_file
from tra.ingest.readers import load
from tra.labels import load_labels
from tra.privacy.audit import AuditLog
from tra.reading_notes import load_reading_notes

from webctx import new_client


def _xlsx(path, *sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for n, rows in enumerate(sheets, start=1):
        ws = wb.create_sheet(f"Sheet{n}")
        for row in rows:
            ws.append(row)
    wb.save(path)
    return path


def _read(path, doc_id="D001"):
    return get_extractor("CLIENTXLS").extract(load(path).redacted, doc_id)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    from tra.settings import Settings

    return new_client(Settings.from_env())


def _ingest(ws, path):
    return ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path))


def test_rows_with_words_become_suggested_figures(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Red Cross donation", 500], ["Union fees", "$480.00"]])
    result = _read(path)
    assert [(f.label_key, f.amount, f.description, f.page) for f in result.figures] == [
        ("ded.d9", Decimal("500.00"), "Sheet 1 row 2: Red Cross donation", 1),
        ("ded.d5", Decimal("480.00"), "Sheet 1 row 3: Union fees", 1)]
    assert all(not f.confirmed and f.notes == "suggested label" and f.method == "parser" for f in result.figures)
    assert result.parse_status == "partial"


def test_unknown_row_is_a_doubt(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Red Cross donation", 500], [None, None], ["Misc", 120]])
    result = _read(path)
    assert len(result.figures) == 1
    assert result.doubts == ["Sheet 1 row 4: Misc $120.00 has no label, so it wasn't added."]


def test_ambiguous_word_is_a_doubt(tmp_path):
    result = _read(_xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Interest", 55.1]]))
    assert result.figures == []
    [doubt] = result.doubts
    assert doubt.startswith("Sheet 1 row 2: Interest $55.10 could be ")
    assert doubt.endswith(", so it wasn't added.")
    assert result.parse_status == "manual_needed"


def test_longer_phrase_wins(tmp_path):
    result = _read(_xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Bank interest", 55.1]]))
    assert [f.label_key for f in result.figures] == ["income.interest"]


def test_private_words_block_a_suggestion():
    assert match_labels("Gym membership fee", load_sheet_words()) == []


def test_text_amounts_negatives_and_totals(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Description", "Cost"], ["Work phone", "$1,234.50"],
                                       ["Union fees refund", "(120.00)"], ["Total", 1114.5]])
    result = _read(path)
    assert [f.amount for f in result.figures] == [Decimal("1234.50"), Decimal("-120.00")]
    assert result.doubts == []


def test_category_column_used(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Date", "Category", "Details", "Amount"],
                                       [datetime(2025, 9, 14), "Donations", "Red Cross", 50]])
    [fig] = _read(path).figures
    assert (fig.label_key, fig.description, fig.date.isoformat()) == ("ded.d9", "Sheet 1 row 2: Donations: Red Cross",
                                                                      "2025-09-14")


def test_amount_column_found_without_header(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["My deductions 2026"], ["Red Cross donation", 500], ["Work phone", 480]])
    assert [f.label_key for f in _read(path).figures] == ["ded.d9", "ded.d5"]


def test_share_sales_sheet(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Company", "Date bought", "Date sold", "Units", "Cost base", "Proceeds"],
                                       ["SAMPLE MINING LTD", "1/02/2020", "3/03/2026", 100, 2000, 3500]])
    result = _read(path)
    assert result.figures == []
    [doubt] = result.doubts
    assert "Sheet 1" in doubt and "share sales" in doubt and "CGT events" in doubt


def test_second_sheet_is_page_2(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Work phone", 480]],
                 [["Item", "Amount"], ["Red Cross donation", 50]])
    figures = _read(path).figures
    assert [(f.page, f.description) for f in figures] == [(1, "Sheet 1 row 2: Work phone"),
                                                         (2, "Sheet 2 row 2: Red Cross donation")]


def test_cell_with_a_comma_survives(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Donation, Red Cross", 500]])
    assert [f.description for f in _read(path).figures] == ["Sheet 1 row 2: Donation, Red Cross"]


def test_csv_file_is_read_too(ws, tmp_path):
    path = tmp_path / "a.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([["Item", "Amount"], ["Red Cross donation", "500"], ["Tax agent fee", "$330.00"]])
    report = _ingest(ws, path)
    assert report.doc.doc_type == "CLIENTXLS"
    figures, _ = read_figures(ws.figures_csv, load_labels())
    assert [f.label_key for f in figures] == ["ded.d9", "ded.d10"]


def test_ingest_files_client_sheet_in_other(ws, tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Red Cross donation", 500], ["Misc", 120]])
    report = _ingest(ws, path)
    [doc] = DocumentIndex(ws.index_csv).load()
    assert (doc.doc_type, doc.category, doc.parse_status) == ("CLIENTXLS", "Other", "partial")
    assert report.figures_added == 1
    assert load_reading_notes(ws)[doc.doc_id]["doubts"] == ["Sheet 1 row 3: Misc $120.00 has no label, so it "
                                                            "wasn't added."]


def test_override_type_still_wins(ws, tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Red Cross donation", 500]])
    report = ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path), "OTHER")
    assert report.doc.doc_type == "OTHER"


def test_xero_export_still_reads(ws, tmp_path):
    path = _xlsx(tmp_path / "pl.xlsx", [["Profit and Loss"], ["Sample Trading"], ["Account code", "Amount"],
                                        ["Trading Income"], ["Sales", 52000], ["Total Trading Income", 52000]])
    report = _ingest(ws, path)
    assert report.doc.doc_type == "XEROPL"
    figures, _ = read_figures(ws.figures_csv, load_labels())
    assert [(f.label_key, f.amount) for f in figures] == [("income.business_income", Decimal("52000"))]


def test_identifier_in_cell_never_written(ws, tmp_path, make_tfn):
    tfn = make_tfn()
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount", "Note"], ["Red Cross donation", 500, f"TFN {tfn}"],
                                       [f"Misc {tfn}", 20, ""]])
    _ingest(ws, path)
    for written in (ws.figures_csv, ws.reading_notes_json, ws.index_csv):
        assert tfn not in written.read_text(encoding="utf-8")
    figures, _ = read_figures(ws.figures_csv, load_labels())
    assert [f.label_key for f in figures] == ["ded.d9"]


def test_doubts_capped(tmp_path):
    rows = [["Item", "Amount"]] + [[f"Misc {n}", n + 1] for n in range(30)]
    doubts = _read(_xlsx(tmp_path / "a.xlsx", rows)).doubts
    assert len(doubts) == 21
    assert doubts[-1] == "And 10 more rows that weren't added."


def test_figures_capped(tmp_path):
    rows = [["Item", "Amount"]] + [["Red Cross donation", n + 1] for n in range(205)]
    result = _read(_xlsx(tmp_path / "a.xlsx", rows))
    assert len(result.figures) == 200
    assert result.doubts == ["Only the first 200 rows with amounts were read. Enter the rest by hand."]


# --- Fixes from the final review ---------------------------------------------------------------

def test_bank_export_gives_no_figures(tmp_path):
    path = tmp_path / "bank.csv"
    path.write_text("Date,Description,Debit,Credit,Balance\n01/07/2025,Optus mobile,45.00,,1234.56\n"
                    "04/07/2025,Red Cross donation,50.00,,1184.56\n", encoding="utf-8")
    result = _read(path)
    assert result.figures == []
    [doubt] = result.doubts
    assert "Sheet 1 looks like a bank statement" in doubt


def test_balance_column_is_never_the_amount(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Date", "Amount", "Description", "Balance"],
                                       ["01/07/2025", -15.99, "Netflix subscription", 2000.01]])
    result = _read(path)
    assert result.figures == [] and "bank statement" in result.doubts[0]


def test_total_word_anywhere_skips_the_row(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Red Cross donation", 50], ["Salvos donation", 30],
                                       ["Donations total", 80], ["Donations subtotal", 80]])
    assert [f.amount for f in _read(path).figures] == [Decimal("50.00"), Decimal("30.00")]


def test_receipt_list_is_not_share_sales(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Purchase date", "Supplier", "Item", "Quantity", "Amount"],
                                       ["1/02/2026", "SAMPLE HARDWARE", "Work tools", 1, 129]])
    result = _read(path)
    assert not any("share sales" in d for d in result.doubts)
    assert [f.label_key for f in result.figures] == ["ded.d5"]


def test_unreadable_sheet_is_a_doubt(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_text('Item,Amount\n"Red Cross donation,' + "x" * 140_000 + "\n", encoding="utf-8")
    result = _read(path)
    assert result.figures == []
    assert result.doubts == ["Sheet 1 couldn't be read as a table (a cell is too long or a quote isn't closed). "
                             "Open it and enter its figures by hand."]


def test_csv_saved_by_excel_in_windows_encoding(tmp_path):
    path = tmp_path / "a.csv"
    path.write_bytes("Item,Amount\nCafé donation for charity,10\n".encode("cp1252"))
    [fig] = _read(path).figures
    assert fig.description == "Sheet 1 row 2: Café donation for charity"


def test_headerless_bank_export_gives_no_figures(tmp_path):
    path = tmp_path / "CSVData.csv"
    path.write_text('01/07/2025,"-15.99","NETFLIX SUBSCRIPTION","+2000.01"\n'
                    '02/07/2025,"+3.21","CREDIT INTEREST","+2003.22"\n', encoding="utf-8")
    result = _read(path)
    assert result.figures == [] and "bank statement" in result.doubts[0]


def test_plus_sign_amount_is_read(tmp_path):
    path = _xlsx(tmp_path / "a.xlsx", [["Item", "Amount"], ["Red Cross donation", "+50.00"]])
    assert [f.amount for f in _read(path).figures] == [Decimal("50.00")]
