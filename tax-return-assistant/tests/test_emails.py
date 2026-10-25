"""Reading emails (.eml and Outlook .msg): the text, the attachments, and figures from the text.

Every email here is made up at test time, identifiers included.
"""

from datetime import datetime, timezone
from decimal import Decimal
from email.message import EmailMessage

import pytest

from msgfile import write_msg
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.emails import MAX_ATTACHMENTS, email_page_text, read_email
from tra.ingest.extractors import get_extractor
from tra.ingest.pipeline import ingest_file
from tra.privacy.audit import AuditLog
from tra.privacy.redact import redact_pages

from webctx import new_client

SENT = datetime(2026, 8, 14, 9, 30, tzinfo=timezone.utc)


def _eml(path, body="", *, html=None, attachments=(), inline=(), attached_emails=(), sender="Pat Sample"):
    msg = EmailMessage()
    msg["Subject"] = "My tax papers"
    msg["From"] = f"{sender} <pat@example.com>"
    msg["To"] = "office@example.com"
    msg["Date"] = "Fri, 14 Aug 2026 09:30:00 +0000"
    if body:
        msg.set_content(body)
    if html is not None:
        if body:
            msg.add_alternative(html, subtype="html")
        else:
            msg.set_content(html, subtype="html")
    for name, data, maintype, subtype in attachments:
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    for data in inline:
        msg.add_attachment(data, maintype="image", subtype="png", disposition="inline", cid="<logo@example>")
    for inner in attached_emails:
        msg.add_attachment(inner)
    path.write_bytes(msg.as_bytes())
    return path


def _figures(text):
    rt = redact_pages([text])
    return get_extractor("EMAIL").extract(rt, "D001")


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    from tra.settings import Settings

    return new_client(Settings.from_env())


def test_eml_plain_body_and_attachments(tmp_path):
    path = _eml(tmp_path / "a.eml", "Hi, papers attached.\nThanks",
                attachments=[("statement.pdf", b"%PDF-1.4 sample", "application", "pdf")], inline=[b"\x89PNG logo"])
    content = read_email(path)
    assert content.subject == "My tax papers"
    assert content.sent == SENT
    assert "Hi, papers attached." in content.body
    assert [(a.suffix, a.data) for a in content.attachments] == [(".pdf", b"%PDF-1.4 sample")]


def test_eml_html_only_body(tmp_path):
    html = ("<html><head><style>p {color: red}</style></head><body><p>Donations: $500</p>"
            "<p>Work phone&nbsp;$480.00 &amp; more<br>Thanks</p><script>var x = 1;</script></body></html>")
    body = read_email(_eml(tmp_path / "a.eml", html=html)).body
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    assert lines == ["Donations: $500", "Work phone $480.00 & more", "Thanks"]


def test_eml_attached_email(tmp_path):
    inner = EmailMessage()
    inner["Subject"] = "Forwarded receipt"
    inner.set_content("Receipt for $50 donation")
    content = read_email(_eml(tmp_path / "a.eml", "See below", attached_emails=[inner]))
    [attachment] = content.attachments
    assert attachment.suffix == ".eml"
    assert b"Forwarded receipt" in attachment.data


def test_msg_subject_body_date_attachment(tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "My tax papers", "Hi, papers attached.", sent=SENT,
              attachments=[("statement.pdf", b"%PDF-1.4 sample")])
    content = read_email(path)
    assert (content.subject, content.body, content.sent) == ("My tax papers", "Hi, papers attached.", SENT)
    assert [(a.suffix, a.data) for a in content.attachments] == [(".pdf", b"%PDF-1.4 sample")]


def test_msg_html_body_when_no_text(tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "Papers", html=b"<p>Donations: $500</p>")
    assert read_email(path).body.strip() == "Donations: $500"


def test_msg_embedded_message_skipped(tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "Fwd", "See attached", embedded=[{"subject": "inner", "body": "hello"}])
    content = read_email(path)
    assert content.attachments == []
    assert content.skipped == ["An email attached inside this one couldn't be read. Save it from Outlook on its own "
                               "and import it."]


def test_msg_inline_image_skipped(tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "Papers", "Hi", inline_images=[("logo.png", b"\x89PNG logo")])
    assert read_email(path).attachments == []


def test_too_many_attachments(tmp_path):
    files = [(f"r{n}.pdf", b"%PDF-1.4 " + bytes([65 + n]), "application", "pdf") for n in range(MAX_ATTACHMENTS + 2)]
    content = read_email(_eml(tmp_path / "a.eml", "Lots", attachments=files))
    assert len(content.attachments) == MAX_ATTACHMENTS
    assert content.skipped == [f"Only the first {MAX_ATTACHMENTS} attachments were read; 2 more weren't."]


def test_sender_not_in_text(tmp_path):
    text = email_page_text(read_email(_eml(tmp_path / "a.eml", "Hi", sender="Pat Sample")))
    assert "Pat Sample" not in text and "pat@example.com" not in text
    assert text.startswith("Subject: My tax papers\nDate: 14/08/2026\n")


def test_body_lines_become_figures():
    result = _figures("Subject: Papers\nDate: 14/08/2026\n\nHi,\nDonations to Red Cross: $500\n"
                      "Work phone $480.00 for the year\nThanks")
    assert [(f.label_key, f.amount, f.page, f.notes, f.confirmed) for f in result.figures] == [
        ("ded.d9", Decimal("500.00"), 1, "suggested label", False),
        ("ded.d5", Decimal("480.00"), 1, "suggested label", False)]
    assert result.figures[0].description == "Email: Donations to Red Cross: $500"
    assert result.doc_date.isoformat() == "2026-08-14"
    assert result.parse_status == "partial"


def test_quoted_reply_ignored():
    text = ("Subject: Re: Papers\nDate: 14/08/2026\n\nDonations to Red Cross: $500\n"
            "> Donations to Red Cross: $500\n\nOn 3 Aug 2026, at 10:00, Office wrote:\n"
            "> Work phone $480.00\nWork phone $480.00\n")
    assert [f.label_key for f in _figures(text).figures] == ["ded.d9"]


def test_original_message_marker_stops_reading():
    text = "Subject: Re\nDate: 14/08/2026\n\nThanks\n-----Original Message-----\nDonations: $500\n"
    assert _figures(text).figures == []


def test_unlabelled_amount_line_is_a_doubt():
    result = _figures("Subject: Papers\nDate: 14/08/2026\n\nMisc stuff $120\nCall me on 0412 345 678\n")
    assert result.figures == []
    assert result.doubts == ['"Misc stuff $120" ($120.00) has no label, so it wasn\'t added.']
    assert result.parse_status == "manual_needed"


def test_two_amounts_on_a_line_is_a_doubt():
    [doubt] = _figures("Subject: P\nDate: 14/08/2026\n\nPhone $40 and internet $60\n").doubts
    assert "more than one amount" in doubt


def test_subject_line_not_read_for_figures():
    assert _figures("Subject: Donations $500\nDate: 14/08/2026\n\nHi\n").figures == []


def test_ingest_files_email_in_other(ws, tmp_path):
    report = ingest_file(_eml(tmp_path / "a.eml", "Donations to Red Cross: $500"), ws, LocalStore(ws.tra_home),
                         load_doc_types(), AuditLog(ws.audit_path))
    [doc] = DocumentIndex(ws.index_csv).load()
    assert (doc.doc_type, doc.category, doc.parse_status) == ("EMAIL", "Other", "partial")
    assert doc.filed_name.endswith(".eml") and doc.date_detected and doc.doc_date.isoformat() == "2026-08-14"
    assert report.figures_added == 1


def test_ingest_msg(ws, tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "Papers", "Work phone $480.00", sent=SENT)
    report = ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path))
    assert (report.doc.doc_type, report.figures_added) == ("EMAIL", 1)


def test_signature_identifier_blanked(ws, tmp_path, rng):
    bsb = f"{rng.randint(10, 99):03d}-{rng.randint(100, 999)}"
    account = "".join(str(rng.randint(0, 9)) for _ in range(8))
    body = f"Donations to Red Cross: $500\n\nKind regards\nPat\nBSB {bsb} Account {account}\n"
    report = ingest_file(_eml(tmp_path / "a.eml", body), ws, LocalStore(ws.tra_home), load_doc_types(),
                         AuditLog(ws.audit_path))
    assert report.doc.redaction_counts.get("BSB") == 1 and report.doc.redaction_counts.get("ACCOUNT") == 1
    for written in ws.work_dir.rglob("*"):
        if written.is_file():
            text = written.read_text(encoding="utf-8", errors="replace")
            assert bsb not in text and account not in text


def test_msg_without_olefile_says_what_to_install(ws, tmp_path, monkeypatch):
    import sys

    from tra.ingest.pipeline import IngestError

    path = tmp_path / "a.msg"
    write_msg(path, "Papers", "Work phone $480.00", sent=SENT)
    monkeypatch.setitem(sys.modules, "olefile", None)  # a laptop set up before olefile was added
    with pytest.raises(IngestError, match=r"pip install -e \."):
        ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path))
    assert DocumentIndex(ws.index_csv).load() == []


# --- Fixes from the final review ---------------------------------------------------------------

def test_amount_followed_by_a_comma():
    result = _figures("Subject: P\nDate: 14/08/2026\n\nI gave Red Cross a donation of $500, and the receipt is attached.\n"
                      "Union fees were $1,000, thanks\nAbout $80, each month\n")
    assert [(f.label_key, f.amount) for f in result.figures] == [("ded.d9", Decimal("500.00")),
                                                                 ("ded.d5", Decimal("1000.00"))]
    assert result.doubts == ['"About $80, each month" ($80.00) has no label, so it wasn\'t added.']


def test_total_line_in_email_not_counted_again():
    result = _figures("Subject: P\nDate: 14/08/2026\n\nRed Cross donation $50\nSalvos donation $30\n"
                      "Total donations $80\n")
    assert [f.amount for f in result.figures] == [Decimal("50.00"), Decimal("30.00")]


def test_html_table_cells_kept_apart(tmp_path):
    html = ("<table><tr><td>Bank interest</td><td>12.50</td></tr><tr><th>Donation</th><td>$500</td></tr></table>")
    lines = [" ".join(line.split()) for line in read_email(_eml(tmp_path / "a.eml", html=html)).body.splitlines()]
    assert "Bank interest 12.50" in lines and "Donation $500" in lines


def test_pasted_photo_is_kept(tmp_path):
    photo = b"\xff\xd8\xff" + bytes(40_000)
    msg = EmailMessage()
    msg["Subject"] = "Receipts"
    msg.set_content("Photos of my receipts")
    msg.add_attachment(photo, maintype="image", subtype="jpeg", disposition="inline", cid="<img1@phone>",
                       filename="IMG_0001.jpeg")
    msg.add_attachment(b"\x89PNG small logo", maintype="image", subtype="png", disposition="inline",
                       cid="<logo@example>")
    path = tmp_path / "a.eml"
    path.write_bytes(msg.as_bytes())
    assert [(a.suffix, len(a.data)) for a in read_email(path).attachments] == [(".jpeg", len(photo))]


def test_msg_link_attachment_is_noted(tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "Papers", "See the link", links=["Tax papers.pdf"])
    content = read_email(path)
    assert content.attachments == []
    assert content.skipped == ["Attachment 1 is a link (for example to OneDrive), not a file. Open the email to get "
                               "it."]


def test_rtf_only_msg_is_noted(tmp_path):
    path = tmp_path / "a.msg"
    write_msg(path, "Papers", rtf=b"compressed rtf")
    assert read_email(path).skipped == ["The email's text is in a format Sawnx can't read (rich text). Open the "
                                        "email and check it."]


def test_unknown_charset_still_read(tmp_path):
    raw = (b"Subject: Papers\r\nDate: Fri, 14 Aug 2026 09:30:00 +0000\r\nMIME-Version: 1.0\r\n"
           b"Content-Type: multipart/mixed; boundary=XX\r\n\r\n--XX\r\n"
           b"Content-Type: text/plain; charset=unknown-8bit\r\n\r\nDonations to Red Cross: $500\r\n--XX\r\n"
           b"Content-Type: application/pdf\r\nContent-Disposition: attachment; filename=a.pdf\r\n\r\n%PDF-1.4 x\r\n"
           b"--XX--\r\n")
    path = tmp_path / "a.eml"
    path.write_bytes(raw)
    content = read_email(path)
    assert "Donations to Red Cross: $500" in content.body and [a.suffix for a in content.attachments] == [".pdf"]


def test_email_without_amounts_is_read_not_manual():
    result = _figures("Subject: Papers\nDate: 14/08/2026\n\nPlease find my documents attached.\nThanks, Pat\n")
    assert (result.figures, result.doubts, result.parse_status) == ([], [], "parsed")


def test_msg_pasted_photo_is_kept(tmp_path):
    path = tmp_path / "a.msg"
    photo = b"\xff\xd8\xff" + bytes(40_000)
    write_msg(path, "Receipts", "Photo attached", inline_images=[("IMG_0001.jpeg", photo), ("logo.png", b"\x89PNG")])
    assert [(a.suffix, len(a.data)) for a in read_email(path).attachments] == [(".jpeg", len(photo))]
