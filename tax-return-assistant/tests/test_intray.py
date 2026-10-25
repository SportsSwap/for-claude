import io
import json
import os

import pytest
from webctx import make_client, new_client

from tra.cabinets import CabinetSpace
from tra.demo import _write_pdf
from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.labels import load_labels
from tra.privacy.audit import AuditLog
from tra.web.client_names import set_name
from tra.web.intray import add_to_tray, discard_item, file_item, list_tray, tray_dir


def _named_client(settings, code="CITI01", name="Jane Citizen", fy=2026):
    ws = new_client(settings, code, fy)
    set_name(settings.tra_home, code, name, AuditLog(ws.audit_path))
    return ws


def _income_pdf(tmp_path, tfn, name="statement.pdf"):
    path = tmp_path / name
    _write_pdf(path, ["Income statement", "Payer: SAMPLE CO PTY LTD", "Payee: JANE CITIZEN", f"Payee TFN {tfn}",
                      "Period 1 July 2025 to 30 June 2026", "Gross payments 60,000.00", "Total tax withheld 11,000.00"])
    return path


def test_suggestions_from_the_document(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    _named_client(settings)
    tfn = make_tfn()
    item = add_to_tray(settings.tra_home, _income_pdf(tmp_path, tfn), "tester", AuditLog(tmp_path / "a.jsonl"))
    s = item.suggestion
    assert (s["code"], s["cabinet"], s["year"], s["folder"], s["doc_type"], s["mode"]) == \
           ("CITI01", "Tax return", 2026, "Income", "INCSTMT", "read")
    assert any("[TFN REDACTED]" in line for line in item.preview)
    raw = (tray_dir(settings.tra_home) / "tray.json").read_text(encoding="utf-8")
    assert tfn not in raw and "statement.pdf" not in raw


def test_same_file_added_twice_is_one_item(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    pdf = _income_pdf(tmp_path, make_tfn())
    audit = AuditLog(tmp_path / "a.jsonl")
    a = add_to_tray(settings.tra_home, pdf, "tester", audit)
    b = add_to_tray(settings.tra_home, pdf, "tester", audit)
    assert a.id == b.id and len(list_tray(settings.tra_home)) == 1


def test_file_for_the_return(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = _named_client(settings)
    audit = AuditLog(ws.audit_path)
    item = add_to_tray(settings.tra_home, _income_pdf(tmp_path, make_tfn()), "tester", audit)
    outcome = file_item(settings, item.id, code="CITI01", cabinet="Tax return", year=2026, folder="Income",
                        mode="read", audit=audit)
    assert outcome.doc.doc_type == "INCSTMT" and outcome.figures_added == 2
    assert len(read_figures(ws.figures_csv, load_labels())[0]) == 2
    assert list_tray(settings.tra_home) == []
    assert [p.name for p in tray_dir(settings.tra_home).iterdir()] == ["tray.json"]


def test_file_into_a_cabinet_and_unset_year(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    _named_client(settings)
    src = tmp_path / "letter.docx"
    src.write_bytes(b"PK letter for jane")
    audit = AuditLog(tmp_path / "a.jsonl")
    item = add_to_tray(settings.tra_home, src, "tester", audit)
    assert item.suggestion["mode"] == "store" and not item.readable
    with pytest.raises(ValueError, match="FY2024"):
        file_item(settings, item.id, code="CITI01", cabinet="Tax return", year=2024, folder="Other", mode="store",
                  audit=audit)
    outcome = file_item(settings, item.id, code="CITI01", cabinet="Correspondence", year=None, folder="Letters",
                        mode="store", audit=audit)
    [doc] = DocumentIndex(CabinetSpace(settings.tra_home, "CITI01", "Correspondence").index_csv).load()
    assert outcome.doc.doc_id == doc.doc_id and doc.category == "Letters"


def test_emails_suggest_correspondence(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    src = tmp_path / "x.eml"
    src.write_bytes(b"From: someone")
    item = add_to_tray(settings.tra_home, src, "tester", AuditLog(tmp_path / "a.jsonl"))
    assert (item.suggestion["cabinet"], item.suggestion["folder"]) == ("Correspondence", "Emails")


def test_discard(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "a.jsonl")
    item = add_to_tray(settings.tra_home, _income_pdf(tmp_path, make_tfn()), "tester", audit)
    discard_item(settings.tra_home, item.id, audit)
    assert list_tray(settings.tra_home) == [] and len(os.listdir(tray_dir(settings.tra_home))) == 1
    with pytest.raises(ValueError):
        discard_item(settings.tra_home, item.id, audit)


def test_in_tray_pages(tmp_path, monkeypatch, make_tfn):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    _named_client(settings)
    tfn = make_tfn()
    pdf = _income_pdf(tmp_path, tfn).read_bytes()
    resp = client.post("/intray", content_type="multipart/form-data",
                       data={"files": [(io.BytesIO(pdf), f"Jane_Citizen_{tfn}.pdf")]})
    assert resp.status_code == 302
    page = client.get("/intray").get_data(as_text=True)
    assert "Jane Citizen" in page and tfn not in page and "Jane_Citizen_" not in page
    assert "In Tray" in client.get("/").get_data(as_text=True)
    [item] = list_tray(settings.tra_home)
    assert client.get(f"/intray/{item.id}/view").data.startswith(b"%PDF")
    resp = client.post(f"/intray/{item.id}/file", data={"code": "CITI01", "cabinet": "Tax return", "year": "2026",
                                                         "folder": "Income", "mode": "read"})
    assert resp.status_code == 302 and list_tray(settings.tra_home) == []
    assert client.get("/intray/nope/view").status_code == 404
    entries = (tray_dir(settings.tra_home) / "tray.json").read_text(encoding="utf-8")
    assert json.loads(entries) == []


def _client_email(tmp_path):
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = "Tax papers from Jane Citizen"
    msg["Date"] = "Fri, 14 Aug 2026 09:30:00 +0000"
    msg.set_content("Hi, Jane Citizen here.\nDonations to Red Cross: $500\n")
    pdf = tmp_path / "src.pdf"
    _write_pdf(pdf, ["SAMPLE MINING LTD", "Dividend statement", "Payment date 20 March 2026",
                     "Franked amount 700.00", "Franking credit 300.00"])
    msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf", filename="div.pdf")
    path = tmp_path / "mail.eml"
    path.write_bytes(msg.as_bytes())
    return path


def test_email_in_tray_has_preview_and_client(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    _named_client(settings)
    item = add_to_tray(settings.tra_home, _client_email(tmp_path), "tester", AuditLog(tmp_path / "a.jsonl"))
    assert item.suggestion["code"] == "CITI01"
    assert (item.suggestion["cabinet"], item.suggestion["folder"], item.suggestion["mode"]) == (
        "Correspondence", "Emails", "store")
    assert any("Donations to Red Cross" in line for line in item.preview)


def test_email_filed_for_the_return_reads_attachments(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = _named_client(settings)
    audit = AuditLog(ws.audit_path)
    item = add_to_tray(settings.tra_home, _client_email(tmp_path), "tester", audit)
    outcome = file_item(settings, item.id, code="CITI01", cabinet="Tax return", year=2026, folder="Other",
                        mode="read", audit=audit)
    assert outcome.doc.doc_type == "EMAIL"
    assert [a.doc.doc_type for a in outcome.attachments] == ["DIVSTMT"]
