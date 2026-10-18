import html

from webctx import build_test01, ingest_demo, make_client, new_client

from tra.privacy.audit import AuditLog
from tra.review_store import load_review, note_key, save_response
from tra.web.services.activity import activity
from tra.web.services.prepare import run_prepare
from tra.web.status import job_status


def _prepared(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    summary = run_prepare(ws, AuditLog(ws.audit_path), "tester")
    return client, settings, ws, summary


def test_review_page_groups_notes_with_citations(tmp_path, monkeypatch):
    client, _settings, _ws, _summary = _prepared(tmp_path, monkeypatch)
    page = html.unescape(client.get("/c/TEST01/2026/review").get_data(as_text=True))
    assert page.index("C2") < page.index("P3") < page.index("S14")
    assert "1 High · 1 Medium · 1 Low" in page


def test_not_prepared_yet(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    assert "Prepare the return first" in client.get("/c/TEST01/2026/review").get_data(as_text=True)


def test_response_and_mark_reviewed_through_the_page(tmp_path, monkeypatch):
    client, _settings, ws, summary = _prepared(tmp_path, monkeypatch)
    c2 = next(n for n in summary.notes if n.check_id == "C2")
    resp = client.post("/c/TEST01/2026/review/response",
                       data={"key": note_key(c2), "text": "Booked", "resolved": "on"})
    assert resp.status_code == 302
    assert load_review(ws).responses[note_key(c2)]["resolved"] is True
    bad = client.post("/c/TEST01/2026/review/response", data={"key": "made-up", "text": "x"}, follow_redirects=True)
    assert "no longer raised" in bad.get_data(as_text=True).lower()
    assert "made-up" not in load_review(ws).responses
    client.post("/c/TEST01/2026/review/mark", data={"name": "A Reviewer"})
    assert job_status(ws) == "Reviewed"


def test_old_responses_shown_as_no_longer_raised(tmp_path, monkeypatch):
    client, _settings, ws, _summary = _prepared(tmp_path, monkeypatch)
    save_response(ws, "S4|ded.d5|F0009|", "Receipt found", True, "tester")
    page = client.get("/c/TEST01/2026/review").get_data(as_text=True)
    assert "No longer raised" in page and "Receipt found" in page


def test_activity_lists_this_client_only(tmp_path, monkeypatch):
    client, settings, ws, _summary = _prepared(tmp_path, monkeypatch)
    other = new_client(settings, "TEST02")
    ingest_demo(settings, other, "rental")
    texts = [text for _when, text in activity(ws)]
    assert any("prepared" in t for t in texts) and any("Client set up" in t for t in texts)
    assert not any("TEST02" in t or "RENTSTMT" in t for t in texts)
    page = client.get("/c/TEST01/2026/notes").get_data(as_text=True)
    assert "Client set up" in page
