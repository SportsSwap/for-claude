import json
from datetime import date

import pytest
from webctx import make_client

from tra.privacy.audit import AuditLog
from tra.web.app_settings import disable_ai_reader, enable_ai_reader, load_app_settings


def test_settings_page_shows_ai_off_and_approval_label(tmp_path, monkeypatch):
    _app, client, _settings = make_client(tmp_path, monkeypatch)
    page = client.get("/settings").get_data(as_text=True)
    assert "AI reader" in page and "Needs privacy officer approval" in page and "Off" in page
    assert "127.0.0.1:8766" in page


def test_enable_needs_name_and_date(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "a.jsonl")
    with pytest.raises(ValueError):
        enable_ai_reader(settings.tra_home, "  ", date(2026, 10, 20), audit)
    with pytest.raises(ValueError):
        enable_ai_reader(settings.tra_home, "Privacy Officer", None, audit)
    resp = client.post("/settings/ai-reader", data={"action": "on", "approved_by": "", "approved_on": ""},
                       follow_redirects=True)
    assert "approver" in resp.get_data(as_text=True).lower()
    assert load_app_settings(settings.tra_home).ai_reader is False


def test_enable_and_disable_audited(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    client.post("/settings/ai-reader", data={"action": "on", "approved_by": "Privacy Officer",
                                             "approved_on": "2026-10-20"})
    s = load_app_settings(settings.tra_home)
    assert (s.ai_reader, s.approved_by, s.approved_on) == (True, "Privacy Officer", "2026-10-20")
    assert "AI reader: on" in client.get("/").get_data(as_text=True)
    disable_ai_reader(settings.tra_home, AuditLog(settings.tra_home / "audit" / "x.jsonl"))
    assert load_app_settings(settings.tra_home).ai_reader is False
    actions = []
    for path in (settings.tra_home / "audit").glob("*.jsonl"):
        actions += [json.loads(line)["action"] for line in path.read_text(encoding="utf-8").splitlines()]
    assert "ai_reader_enabled" in actions and "ai_reader_disabled" in actions
