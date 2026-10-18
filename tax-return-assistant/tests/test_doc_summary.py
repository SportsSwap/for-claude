import html
import os

import openpyxl
import pytest
from webctx import build_test01, make_client, new_client

from tra.doc_notes import load_doc_notes, save_doc_note
from tra.doc_summary import summarize, summaries
from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.ingest.classify import load_doc_types
from tra.labels import load_labels
from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.services.prepare import run_prepare


def _docs(ws):
    return {d.doc_type: d for d in DocumentIndex(ws.index_csv).load()}


def test_income_statement_summary(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    figures, _ = read_figures(ws.figures_csv, load_labels())
    text = summarize(_docs(ws)["INCSTMT"], figures, load_labels(), load_doc_types())
    assert text.startswith("Income statement / PAYG payment summary · SAMPLE CO PTY LTD · dated 30 Jun 2026 · supports ")
    assert "Item 1 C Salary or wages" in text and "$60,000.00" in text and "$11,000.00" in text


def test_receipt_and_dividend_summaries(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    all_ = summaries(ws)
    docs = _docs(ws)
    assert "SAMPLE PROFESSIONAL ASSOCIATION" in all_[docs["RECEIPT"].doc_id] and "$250.00" in all_[docs["RECEIPT"].doc_id]
    assert "SAMPLE MINING LTD" in all_[docs["DIVSTMT"].doc_id] and "$300.00" in all_[docs["DIVSTMT"].doc_id]


def test_unread_and_stored_documents(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    import io
    client.post("/c/TEST01/2026/import", content_type="multipart/form-data",
                data={"return_type": "individual", "files": [(io.BytesIO(b"hello"), "letter.docx")],
                      "mode_0": "store", "folder_0": "Other"})
    [doc] = DocumentIndex(ws.index_csv).load()
    assert summaries(ws)[doc.doc_id] == "Stored only, not read."
    unread = doc.__class__(**{**doc.__dict__, "parse_status": "manual_needed", "doc_type": "OTHER"})
    assert "Couldn't read" in summarize(unread, [], load_labels(), load_doc_types())


def test_doc_notes_saved_and_guarded(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    save_doc_note(ws, "D004", "Union fees receipt, evidence for D5", "tester")
    assert load_doc_notes(ws)["D004"]["text"] == "Union fees receipt, evidence for D5"
    with pytest.raises(SensitiveDataBlocked):
        save_doc_note(ws, "D004", f"TFN {make_tfn()}", "tester")
    save_doc_note(ws, "D004", "  ", "tester")
    assert "D004" not in load_doc_notes(ws)


def test_files_page_shows_summary_and_saves_description(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    build_test01(settings)
    page = html.unescape(client.get("/c/TEST01/2026/files").get_data(as_text=True))
    assert "supports Item 1 C Salary or wages" in page
    resp = client.post("/c/TEST01/2026/doc/D003/description", data={"text": "Main payslip summary"})
    assert resp.status_code == 302
    assert "Main payslip summary" in client.get("/c/TEST01/2026/files").get_data(as_text=True)
    assert client.post("/c/TEST01/2026/doc/D999/description", data={"text": "x"}).status_code == 404


def test_workpaper_sources_has_summary_and_description(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    income = _docs(ws)["INCSTMT"].doc_id
    save_doc_note(ws, income, "Main payslip summary", "tester")
    summary = run_prepare(ws, AuditLog(ws.audit_path), "tester")
    sheet = openpyxl.load_workbook(os.path.join(ws.output_dir, summary.workpaper))["Sources"]
    rows = [r for r in sheet.iter_rows(values_only=True) if r and r[0] == income]
    assert rows and "SAMPLE CO PTY LTD" in rows[0][11] and rows[0][12] == "Main payslip summary"
    headers = [c for r in sheet.iter_rows(values_only=True) for c in r if c in ("Summary", "Description")]
    assert headers == ["Summary", "Description"]
