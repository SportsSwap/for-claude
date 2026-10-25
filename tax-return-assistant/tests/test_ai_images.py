"""Page images for scans: off until the privacy officer approves. No network: the client is a stand-in."""

import base64
import json
from datetime import date

import pytest
from test_ai_reader import FakeClient
from webctx import make_client, new_client

from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.extractors.ai_reader import AiReader, ai_reader_from_settings
from tra.ingest.page_images import MAX_PAGE_IMAGES, looks_garbled, pages_to_send, render_pages
from tra.ingest.pipeline import ingest_file
from tra.privacy.audit import AuditLog
from tra.privacy.redact import redact_pages
from tra.web.app_settings import (disable_ai_page_images, disable_ai_reader, enable_ai_page_images,
                                  enable_ai_reader, load_app_settings)

JPEG = b"\xff\xd8\xff"  # the start of every JPEG file
SOUP = "Th3 qu!ck br0wn ~~ |||l1 %$#@ fx0x 9a9 ;;;; Int3r3st 1O0.0O"  # what bad OCR leaves behind
TEXT = ["SAMPLE CREDIT UNION", "Yearly summary for members"]
ON = date(2026, 10, 25)


def _answer():
    return json.dumps({"doc_type": "OTHER", "figures": []})


def _blocks(call):
    content = call["messages"][0]["content"]
    return content if isinstance(content, list) else [{"type": "text", "text": content}]


def _images(call):
    blocks = _blocks(call)
    return [(blocks[i - 1]["text"], b) for i, b in enumerate(blocks) if b["type"] == "image"]


def _setup(tmp_path, monkeypatch, *, images: bool):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "settings.jsonl")
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    if images:
        enable_ai_page_images(settings.tra_home, "Privacy Officer", ON, audit)
    client = FakeClient(_answer())
    reader = ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}, client=client)
    return settings, new_client(settings), reader, client


def _ingest(settings, ws, path, reader):
    return ingest_file(path, ws, LocalStore(settings.tra_home), load_doc_types(), AuditLog(ws.audit_path),
                       ai_reader=reader)


# --- choosing and drawing pages -------------------------------------------------------------------------------

def test_ordinary_text_isnt_garbled():
    assert not looks_garbled("Opening balance $1,234.56 on 30/06/2026 – account [ACCOUNT REDACTED] (closing) 5%")
    assert not looks_garbled("Rent received from tenant's bond: 1,000.00 & cleaning -50.00")
    assert looks_garbled(SOUP)


def test_pages_to_send_picks_scans_and_garbled_pages():
    pages = ["Interest earned 123.45 from SAMPLE BANK", "", SOUP, "Closing balance 20,500.00"]
    assert pages_to_send(pages, (2,)) == [2, 3]
    assert pages_to_send(pages[:1], ()) == []


def test_at_most_twenty_pages():
    assert MAX_PAGE_IMAGES == 20
    assert pages_to_send([""] * 30, tuple(range(1, 31))) == list(range(1, 21))


def test_render_pages_gives_jpeg_bytes(make_pdf):
    path = make_pdf("scan.pdf", [TEXT, None])
    [(page, data)] = render_pages(path, [2])
    assert page == 2 and data.startswith(JPEG)


# --- what is sent ---------------------------------------------------------------------------------------------

def test_off_by_default_sends_no_pictures(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, client = _setup(tmp_path, monkeypatch, images=False)
    assert load_app_settings(settings.tra_home).ai_page_images is False
    _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None]), reader)
    [call] = client.calls
    assert _images(call) == [] and "picture" not in json.dumps(call["messages"])


def test_a_scanned_page_is_sent_as_a_picture(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, client = _setup(tmp_path, monkeypatch, images=True)
    _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None, ["Interest credited this year 123.45"]]), reader)
    [call] = client.calls
    [(label, block)] = _images(call)
    assert label == "--- Page 2 (picture; not blanked) ---"
    assert block["source"]["type"] == "base64" and block["source"]["media_type"] == "image/jpeg"
    assert "\n" not in block["source"]["data"] and base64.b64decode(block["source"]["data"]).startswith(JPEG)
    blocks = _blocks(call)
    assert blocks[-1]["type"] == "text" and "Interest credited this year 123.45" in blocks[-1]["text"]
    assert "picture" in call["system"]


def test_a_document_that_is_all_scans_is_still_sent(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, client = _setup(tmp_path, monkeypatch, images=True)
    _ingest(settings, ws, make_pdf("scan.pdf", [None, None]), reader)
    [call] = client.calls
    assert [label for label, _ in _images(call)] == ["--- Page 1 (picture; not blanked) ---",
                                                     "--- Page 2 (picture; not blanked) ---"]


def test_a_garbled_page_is_sent(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, client = _setup(tmp_path, monkeypatch, images=True)
    _ingest(settings, ws, make_pdf("ocr.pdf", [TEXT, [SOUP]]), reader)
    [call] = client.calls
    assert [label for label, _ in _images(call)] == ["--- Page 2 (picture; not blanked) ---"]


def test_no_more_than_twenty_pictures(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, client = _setup(tmp_path, monkeypatch, images=True)
    _ingest(settings, ws, make_pdf("long.pdf", [TEXT] + [None] * 24), reader)
    [call] = client.calls
    assert len(_images(call)) == 20


def test_never_for_a_file_that_isnt_a_pdf(tmp_path, monkeypatch):
    settings, ws, reader, client = _setup(tmp_path, monkeypatch, images=True)
    path = tmp_path / "list.csv"
    path.write_text("Something,Amount\nOdd item,12.50\n", encoding="utf-8")
    _ingest(settings, ws, path, reader)
    assert all(_images(call) == [] for call in client.calls)


def test_reader_without_images_sends_plain_text():
    client = FakeClient(_answer())
    AiReader(client).extract(redact_pages(["SAMPLE CREDIT UNION interest 1.00"]), "D001")
    [call] = client.calls
    assert isinstance(call["messages"][0]["content"], str)


def test_pictures_are_audited_and_never_saved(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, _client = _setup(tmp_path, monkeypatch, images=True)
    report = _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None, None]), reader)
    entries = [json.loads(line) for line in ws.audit_path.read_text(encoding="utf-8").splitlines()]
    [sent] = [e for e in entries if e["action"] == "ai_page_images_sent"]
    assert (sent["client"], sent["doc_id"], sent["pages"]) == ("TEST01", report.doc.doc_id, [2, 3])
    assert sent["sha256"] == report.doc.sha256 and len(sent["sha256"]) == 64  # which file, so a reused id can't mislead
    assert set(sent) == {"ts", "user", "action", "client", "doc_id", "sha256", "pages"}
    for path in settings.tra_home.rglob("*"):
        assert path.suffix.lower() not in (".png", ".jpg", ".jpeg")
        if path.is_file() and path.suffix.lower() != ".pdf":
            assert JPEG not in path.read_bytes()


def test_no_audit_entry_when_no_pictures_are_sent(tmp_path, monkeypatch, make_pdf):
    settings, ws, reader, _client = _setup(tmp_path, monkeypatch, images=True)
    _ingest(settings, ws, make_pdf("odd.pdf", [TEXT + ["Interest credited this year 123.45"]]), reader)
    assert "ai_page_images_sent" not in ws.audit_path.read_text(encoding="utf-8")


# --- the switch -----------------------------------------------------------------------------------------------

def test_the_switch_needs_the_ai_reader_and_an_approver(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "a.jsonl")
    with pytest.raises(ValueError, match="AI reader"):
        enable_ai_page_images(settings.tra_home, "Privacy Officer", ON, audit)
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    with pytest.raises(ValueError, match="approver"):
        enable_ai_page_images(settings.tra_home, "  ", ON, audit)
    with pytest.raises(ValueError, match="approver"):
        enable_ai_page_images(settings.tra_home, "Privacy Officer", None, audit)
    assert load_app_settings(settings.tra_home).ai_page_images is False


def test_switching_on_and_off_is_audited(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "a.jsonl")
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    enable_ai_page_images(settings.tra_home, "Images Approver", date(2026, 10, 26), audit)
    s = load_app_settings(settings.tra_home)
    assert (s.ai_page_images, s.images_approved_by, s.images_approved_on) == (True, "Images Approver", "2026-10-26")
    assert (s.ai_reader, s.approved_by) == (True, "Privacy Officer")  # the AI reader's own approval is kept
    disable_ai_page_images(settings.tra_home, audit)
    s = load_app_settings(settings.tra_home)
    assert (s.ai_page_images, s.images_approved_by, s.ai_reader) == (False, None, True)
    entries = [json.loads(line) for line in (tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()]
    on = next(e for e in entries if e["action"] == "ai_page_images_enabled")
    assert (on["approved_by"], on["approved_on"]) == ("Images Approver", "2026-10-26")
    assert any(e["action"] == "ai_page_images_disabled" for e in entries)


def test_ai_reader_off_switches_page_images_off_too(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "a.jsonl")
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    enable_ai_page_images(settings.tra_home, "Privacy Officer", ON, audit)
    disable_ai_reader(settings.tra_home, audit)
    s = load_app_settings(settings.tra_home)
    assert (s.ai_reader, s.ai_page_images, s.images_approved_by, s.images_approved_on) == (False, False, None, None)
    entries = [json.loads(line) for line in (tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["action"] for e in entries][-2:] == ["ai_page_images_disabled", "ai_reader_disabled"]
    assert ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}, client=FakeClient()) is None
    # Switching the AI reader back on never quietly resumes pictures: they need their own approval again.
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    reader = ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}, client=FakeClient())
    assert reader.page_images is False
    page = _web.get("/settings").get_data(as_text=True)
    assert "Off" in page.split('id="images-badge"', 1)[1][:200]


def test_ai_reader_off_without_pictures_audits_only_the_reader(tmp_path, monkeypatch):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "a.jsonl")
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    disable_ai_reader(settings.tra_home, audit)
    entries = [json.loads(line) for line in (tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "ai_page_images_disabled" not in [e["action"] for e in entries]


def test_the_switch_messages_say_what_is_sent(tmp_path, monkeypatch):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    on = {"action": "on", "approved_by": "Privacy Officer", "approved_on": "2026-10-25"}
    page = web.post("/settings/ai-reader", data=on, follow_redirects=True).get_data(as_text=True)
    assert "It only receives blanked-out text." in page
    web.post("/settings/ai-page-images", data=on)
    page = web.post("/settings/ai-reader", data=on, follow_redirects=True).get_data(as_text=True)
    assert "only receives blanked-out text" not in page  # switched on again while on: pictures still go
    assert "It receives blanked-out text, and pictures of scanned pages" in page
    page = web.post("/settings/ai-reader", data={"action": "off"}, follow_redirects=True).get_data(as_text=True)
    assert "Page images are off too." in page


def test_settings_page_shows_the_warning_and_badge(tmp_path, monkeypatch):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    page = web.get("/settings").get_data(as_text=True)
    assert "Send page images for scans" in page and 'id="images-badge"' in page
    assert "can&#39;t be blanked out first" in page or "can't be blanked out first" in page
    assert "Switch the AI reader on first" in page
    assert "Off" in page.split('id="images-badge"', 1)[1][:200]


def test_settings_route_switches_it(tmp_path, monkeypatch):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    resp = web.post("/settings/ai-page-images", data={"action": "on", "approved_by": "Privacy Officer",
                                                      "approved_on": "2026-10-25"}, follow_redirects=True)
    assert resp.status_code == 200 and "Switch the AI reader on first: page images" in resp.get_data(as_text=True)
    assert load_app_settings(settings.tra_home).ai_page_images is False
    web.post("/settings/ai-reader", data={"action": "on", "approved_by": "Privacy Officer", "approved_on": "2026-10-25"})
    resp = web.post("/settings/ai-page-images", data={"action": "on", "approved_by": "", "approved_on": ""},
                    follow_redirects=True)
    assert "approver" in resp.get_data(as_text=True).lower()
    web.post("/settings/ai-page-images", data={"action": "on", "approved_by": "Privacy Officer",
                                               "approved_on": "2026-10-25"})
    assert load_app_settings(settings.tra_home).ai_page_images is True
    page = web.get("/settings").get_data(as_text=True)
    assert "On" in page.split('id="images-badge"', 1)[1][:200]
    web.post("/settings/ai-page-images", data={"action": "off"})
    assert load_app_settings(settings.tra_home).ai_page_images is False


def test_settings_post_needs_the_same_origin(tmp_path, monkeypatch):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    web.post("/settings/ai-reader", data={"action": "on", "approved_by": "Privacy Officer", "approved_on": "2026-10-25"})
    resp = web.post("/settings/ai-page-images", data={"action": "on", "approved_by": "Privacy Officer",
                                                      "approved_on": "2026-10-25"},
                    headers={"Origin": "http://evil.example"})
    assert resp.status_code in (400, 403) and load_app_settings(settings.tra_home).ai_page_images is False
