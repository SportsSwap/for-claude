"""An email's attachments are filed and read as documents of their own. All data is made up at test time."""

import io
import json
from email.message import EmailMessage

import openpyxl
import pytest

from tra.demo import _write_pdf
from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.pipeline import ingest_file
from tra.labels import load_labels
from tra.privacy.audit import AuditLog
from tra.reading_notes import load_reading_notes

from webctx import make_client, new_client

DIVIDEND = ["SAMPLE MINING LTD", "Dividend statement", "Payment date 20 March 2026", "Unfranked amount 0.00",
            "Franked amount 700.00", "Franking credit 300.00"]


def _pdf_bytes(tmp_path, lines) -> bytes:
    path = tmp_path / "src.pdf"
    _write_pdf(path, lines)
    return path.read_bytes()


def _xlsx_bytes(tmp_path, rows) -> bytes:
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    path = tmp_path / "src.xlsx"
    wb.save(path)
    return path.read_bytes()


def _message(body, attachments=(), attached_emails=()):
    msg = EmailMessage()
    msg["Subject"] = "My tax papers"
    msg["From"] = "Pat Sample <pat@example.com>"
    msg["Date"] = "Fri, 14 Aug 2026 09:30:00 +0000"
    msg.set_content(body)
    for name, data, maintype, subtype in attachments:
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    for inner in attached_emails:
        msg.add_attachment(inner)
    return msg


def _eml(path, body, attachments=(), attached_emails=()):
    path.write_bytes(_message(body, attachments, attached_emails).as_bytes())
    return path


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    from tra.settings import Settings

    return new_client(Settings.from_env())


def _ingest(ws, path):
    return ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path))


def _uploads_empty(ws):
    folder = ws.work_dir / "_uploads"
    return not folder.exists() or not any(folder.iterdir())


def test_email_and_attachments_filed(ws, tmp_path):
    path = _eml(tmp_path / "a.eml", "Donations to Red Cross: $500", [
        ("dividends.pdf", _pdf_bytes(tmp_path, DIVIDEND), "application", "pdf"),
        ("my list.xlsx", _xlsx_bytes(tmp_path, [["Item", "Amount"], ["Work phone", 480]]), "application",
         "vnd.openxmlformats-officedocument.spreadsheetml.sheet")])
    report = _ingest(ws, path)
    docs = DocumentIndex(ws.index_csv).load()
    assert [d.doc_type for d in docs] == ["EMAIL", "DIVSTMT", "CLIENTXLS"]
    email_id = docs[0].doc_id
    notes = load_reading_notes(ws)
    assert notes[docs[1].doc_id]["from_email"] == email_id and notes[docs[2].doc_id]["from_email"] == email_id
    assert [(n, a.doc.doc_type) for n, a in report.attachments] == [(1, "DIVSTMT"), (2, "CLIENTXLS")]
    figures, _ = read_figures(ws.figures_csv, load_labels())
    assert sorted({f.doc_id for f in figures}) == [d.doc_id for d in docs]
    assert _uploads_empty(ws)


def test_word_attachment_stored_only(ws, tmp_path):
    _ingest(ws, _eml(tmp_path / "a.eml", "Letter attached", [("letter.docx", b"PK\x03\x04 sample", "application",
                                                                "vnd.openxmlformats-officedocument.wordprocessingml.document")]))
    email, word = DocumentIndex(ws.index_csv).load()
    assert (word.category, word.parse_status, word.filed_name.endswith(".docx")) == ("Other", "stored", True)
    assert load_reading_notes(ws)[word.doc_id]["from_email"] == email.doc_id


def test_unusable_attachment_is_a_doubt(ws, tmp_path):
    _ingest(ws, _eml(tmp_path / "a.eml", "Zip attached", [("papers.zip", b"PK zip", "application", "zip")]))
    [email] = DocumentIndex(ws.index_csv).load()
    assert load_reading_notes(ws)[email.doc_id]["doubts"] == [
        "Attachment 1 (.zip) wasn't filed: Sawnx can't use that kind of file. Save it from the email and look at it."]


def test_damaged_attachment(ws, tmp_path):
    _ingest(ws, _eml(tmp_path / "a.eml", "Statement attached", [("st.pdf", b"not a pdf at all", "application", "pdf")]))
    email, broken = DocumentIndex(ws.index_csv).load()
    assert (email.doc_type, broken.parse_status) == ("EMAIL", "manual_needed")
    notes = (ws.ingest_notes_json).read_text(encoding="utf-8")
    assert '"I1"' in notes and broken.doc_id in notes
    assert load_reading_notes(ws)[broken.doc_id]["from_email"] == email.doc_id


def test_same_email_twice(ws, tmp_path):
    path = _eml(tmp_path / "a.eml", "Hi", [("dividends.pdf", _pdf_bytes(tmp_path, DIVIDEND), "application", "pdf")])
    _ingest(ws, path)
    again = _ingest(ws, path)
    assert again.duplicate and again.attachments == []
    assert len(DocumentIndex(ws.index_csv).load()) == 2


def test_attachment_names_never_recorded(ws, tmp_path):
    name = "pat-sample-dividends-secret.pdf"
    _ingest(ws, _eml(tmp_path / "a.eml", "Hi", [(name, _pdf_bytes(tmp_path, DIVIDEND), "application", "pdf")]))
    for path in [ws.index_csv, ws.audit_path, *ws.work_dir.rglob("*.json"), *ws.work_dir.rglob("*.csv")]:
        assert "pat-sample" not in path.read_text(encoding="utf-8"), path.name


def test_nested_email_depth(ws, tmp_path):
    innermost = _message("Deep down")
    inner = _message("Forwarded: Work phone $480.00", attached_emails=[innermost])
    _ingest(ws, _eml(tmp_path / "a.eml", "See attached", attached_emails=[inner]))
    docs = DocumentIndex(ws.index_csv).load()
    assert [(d.doc_type, d.parse_status) for d in docs] == [("EMAIL", "parsed"), ("EMAIL", "partial"),
                                                            ("OTHER", "stored")]


def test_sawnx_import_shows_attachments(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    data = _message("Donations to Red Cross: $500", [("st.pdf", _pdf_bytes(tmp_path, DIVIDEND), "application",
                                                      "pdf")]).as_bytes()
    page = client.post("/c/TEST01/2026/import", data={"return_type": "individual", "mode_0": "read",
                                                      "files": [(io.BytesIO(data), "x.eml")]},
                       content_type="multipart/form-data").get_data(as_text=True)
    results = page[page.index('aria-label="Import results"'):]
    assert "Email from the client" in results
    assert "Attachment 1" in results and "Dividend statement" in results
    assert results.index("Attachment 1") > results.index("Email from the client")


def test_cli_ingest_lists_attachments(tmp_path):
    from click.testing import CliRunner

    from tra.cli import main

    home = tmp_path / "home"
    home.mkdir()
    env = {"TRA_HOME": str(home), "TRA_STORE": "local"}
    runner = CliRunner()
    assert runner.invoke(main, ["new", "TEST01"], env=env).exit_code == 0
    path = _eml(tmp_path / "a.eml", "Hi", [("st.pdf", _pdf_bytes(tmp_path, DIVIDEND), "application", "pdf")])
    result = runner.invoke(main, ["ingest", "TEST01", str(path)], env=env)
    assert result.exit_code == 0, result.output
    assert "attachment 1: D002 DIVSTMT parsed 2 figures" in result.output


# --- Fixes from the final review ---------------------------------------------------------------

def test_unexpected_attachment_error_doesnt_stop_the_others(ws, tmp_path, monkeypatch):
    from tra.ingest.extractors.client_sheet import ClientSheetExtractor

    def boom(self, rt, doc_id):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ClientSheetExtractor, "extract", boom)
    path = _eml(tmp_path / "a.eml", "Hi", [
        ("list.xlsx", _xlsx_bytes(tmp_path, [["Item", "Amount"], ["Work phone", 480]]), "application",
         "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("dividends.pdf", _pdf_bytes(tmp_path, DIVIDEND), "application", "pdf")])
    report = _ingest(ws, path)
    assert [d.doc_type for d in DocumentIndex(ws.index_csv).load()] == ["EMAIL", "DIVSTMT"]
    assert [n for n, _ in report.attachments] == [2]
    assert load_reading_notes(ws)[report.doc.doc_id]["doubts"] == [
        "Attachment 1 (.xlsx) couldn't be filed. Save it from the email and import it on its own."]
    assert _uploads_empty(ws)


def test_cover_note_email_needs_no_manual_entry(ws, tmp_path):
    from tra.doc_summary import summaries

    report = _ingest(ws, _eml(tmp_path / "a.eml", "Please find my documents attached.",
                              [("dividends.pdf", _pdf_bytes(tmp_path, DIVIDEND), "application", "pdf")]))
    email = report.doc
    assert email.parse_status == "parsed"
    assert not [n for n in report.notes if n.check_id == "I1"]
    assert summaries(ws)[email.doc_id] == "Email from the client · no amounts in its text"


def test_cover_note_email_not_sent_to_ai_reader(ws, tmp_path):
    calls = []

    class Reader:
        def extract(self, rt, doc_id):
            calls.append(doc_id)
            from tra.ingest.extractors import ExtractResult
            return ExtractResult()

    ingest_file(_eml(tmp_path / "a.eml", "Please find my documents attached."), ws, LocalStore(ws.tra_home),
                load_doc_types(), AuditLog(ws.audit_path), ai_reader=Reader())
    assert calls == []


def test_odd_attachment_names_kept_out(ws, tmp_path, make_tfn):
    tfn = make_tfn()
    _ingest(ws, _eml(tmp_path / "a.eml", "Hi", [("Pat statement.2025 final", b"x", "application", "octet-stream"),
                                                (f"notes.{tfn}", b"y", "application", "octet-stream")]))
    [email] = DocumentIndex(ws.index_csv).load()
    doubts = load_reading_notes(ws)[email.doc_id]["doubts"]
    assert doubts == [f"Attachment {n} (an unknown file type) wasn't filed: Sawnx can't use that kind of file. Save it "
                      "from the email and look at it." for n in (1, 2)]
    assert "2025 final" not in json.dumps(doubts) and tfn not in json.dumps(doubts)
