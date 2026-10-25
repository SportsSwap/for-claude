"""Layouts in the import: what they never take over, and which issuers make it into a file name. Made-up data only."""

import openpyxl
import pytest

from webctx import new_client

LAYOUT = """
name: SAMPLE WIDGETS member summary
doc_type: INTSTMT
match:
  all: ["sample widgets", "member summary"]
issuer: SAMPLE WIDGETS
fields:
  - label: income.interest
    line: "Interest paid"
    description: interest
added: "test"
"""


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from tra.settings import Settings

    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    folder = tmp_path / "layouts"
    folder.mkdir()
    (folder / "sample-widgets.yaml").write_text(LAYOUT, encoding="utf-8")
    monkeypatch.setattr("tra.ingest.layouts.LAYOUTS_DIR", folder)
    return new_client(Settings.from_env())


def _ingest(ws, path):
    from tra.filing.local_store import LocalStore
    from tra.ingest.classify import load_doc_types
    from tra.ingest.pipeline import ingest_file
    from tra.privacy.audit import AuditLog

    return ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path))


def _pdf(tmp_path, lines):
    from tra.demo import _write_pdf

    path = tmp_path / f"doc{len(list(tmp_path.glob('doc*.pdf')))}.pdf"
    _write_pdf(path, lines)
    return path


@pytest.mark.parametrize("lines, doc_type", [
    (["Pre-fill report", "SAMPLE WIDGETS member summary", "Interest paid 10.00"], "PREFILL"),
    (["Tax return for individuals", "Notice of assessment", "SAMPLE WIDGETS member summary", "Interest paid 10.00"],
     "PRIOR"),
])
def test_layouts_never_take_over_ato_documents(ws, tmp_path, lines, doc_type):
    assert _ingest(ws, _pdf(tmp_path, lines)).doc.doc_type == doc_type


def test_layouts_never_take_over_a_spreadsheet(ws, tmp_path):
    path = tmp_path / "list.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["SAMPLE WIDGETS member summary"])
    wb.active.append(["Interest paid", 10.00])
    wb.save(path)
    assert _ingest(ws, path).doc.doc_type == "CLIENTXLS"


def test_layout_still_reads_its_own_documents(ws, tmp_path):
    report = _ingest(ws, _pdf(tmp_path, ["SAMPLE WIDGETS member summary", "Statement date 15/07/2026",
                                         "Interest paid 10.00"]))
    assert report.doc.doc_type == "INTSTMT" and report.figures_added == 1
    assert report.doc.filed_name.endswith("Interest statement - SAMPLE WIDGETS.pdf")  # a learned layout's issuer


def test_interest_statement_first_line_never_names_the_file(ws, tmp_path):
    # No name in clients.json: the first line of a bank's statement is often the account holder, so it isn't used.
    report = _ingest(ws, _pdf(tmp_path, ["MR J CITIZEN", "SAMPLE BANK", "Interest summary",
                                         "Statement date 15/07/2026", "Interest earned 12.00"]))
    assert report.doc.doc_type == "INTSTMT" and report.figures_added == 1
    assert "CITIZEN" not in report.doc.filed_name and report.doc.filed_name.endswith("Interest statement.pdf")


def test_bank_statement_first_line_never_names_the_file(ws, tmp_path):
    report = _ingest(ws, _pdf(tmp_path, ["MS A SAMPLEPERSON", "Account statement", "Opening balance 100.00",
                                         "Interest paid 3.00", "Closing balance 103.00"]))
    assert report.doc.doc_type == "BANKSTMT"
    assert "SAMPLEPERSON" not in report.doc.filed_name


def test_labelled_payer_names_the_file(ws, tmp_path):
    report = _ingest(ws, _pdf(tmp_path, ["Income statement", "Payer: SAMPLE CO PTY LTD",
                                         "Period 1 July 2025 to 30 June 2026", "Gross payments 60,000.00",
                                         "Total tax withheld 11,000.00"]))
    assert report.doc.filed_name.endswith("Income statement - SAMPLE CO PTY LTD.pdf")
