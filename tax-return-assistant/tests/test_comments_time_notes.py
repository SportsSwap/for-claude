from datetime import date, timedelta

import pytest
from webctx import build_test01, make_client, new_client

from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.comments import add_comment, list_comments
from tra.web.jobs import add_task
from tra.web.notifications import notifications
from tra.web.timesheet import add_time, my_week


def _audit(tmp_path):
    return AuditLog(tmp_path / "a.jsonl")


def test_comments_on_documents_and_jobs(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    home = settings.tra_home
    add_comment(home, "TEST01", "doc:TEST01/2026/D001", "Is this the final statement?", "nicho", _audit(tmp_path))
    add_comment(home, "TEST01", "job:ret-TEST01-2026", "Waiting on pre-fill", "nicho", _audit(tmp_path))
    assert [c["text"] for c in list_comments(home, "TEST01", "doc:TEST01/2026/D001")] == ["Is this the final statement?"]
    assert len(list_comments(home, "TEST01")) == 2
    with pytest.raises(SensitiveDataBlocked):
        add_comment(home, "TEST01", "job:ret-TEST01-2026", f"TFN {make_tfn()}", "nicho", _audit(tmp_path))
    with pytest.raises(ValueError):
        add_comment(home, "TEST01", "elsewhere", "x", "nicho", _audit(tmp_path))
    with pytest.raises(ValueError):
        add_comment(home, "TEST01", "job:ret-TEST01-2026", "  ", "nicho", _audit(tmp_path))


def test_time_entries_and_week(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    home = settings.tra_home
    add_time(home, "ret-TEST01-2026", date.today().isoformat(), "45", "Checked figures", "nicho", _audit(tmp_path))
    add_time(home, "ret-TEST01-2026", (date.today() - timedelta(days=30)).isoformat(), "30", "Old", "nicho",
             _audit(tmp_path))
    week, total = my_week(home, "nicho")
    assert [e["what"] for e in week] == ["Checked figures"] and total == 45
    with pytest.raises(ValueError):
        add_time(home, "ret-TEST01-2026", date.today().isoformat(), "0", "x", "nicho", _audit(tmp_path))
    with pytest.raises(ValueError):
        add_time(home, "job-nope", date.today().isoformat(), "10", "x", "nicho", _audit(tmp_path))


def test_notifications(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    build_test01(settings)
    home = settings.tra_home
    add_task(home, "Overdue thing", job_id=None, due=(date.today() - timedelta(days=2)).isoformat(), assignee="",
             by="nicho", audit=_audit(tmp_path))
    add_task(home, "Due today", job_id=None, due=date.today().isoformat(), assignee="", by="nicho",
             audit=_audit(tmp_path))
    add_comment(home, "TEST01", "job:ret-TEST01-2026", "Please check", "alex", _audit(tmp_path))
    texts = [n.text for n in notifications(home, "nicho")]
    assert any("Overdue thing" in t and "overdue" in t for t in texts)
    assert any("Due today" in t and "today" in t for t in texts)
    assert any("Please check" in t for t in texts)


def test_pages(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    resp = client.post("/comments", data={"code": "TEST01", "target": "job:ret-TEST01-2026", "text": "Hello",
                                           "next": "/jobs/ret-TEST01-2026"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/jobs/ret-TEST01-2026")
    resp = client.post("/jobs/ret-TEST01-2026/time", data={"date": date.today().isoformat(), "minutes": "20",
                                                            "what": "Phone call"})
    assert resp.status_code == 302
    page = client.get("/jobs/ret-TEST01-2026").get_data(as_text=True)
    assert "Hello" in page and "Phone call" in page
    assert "Phone call" in client.get("/?tab=time").get_data(as_text=True)
    assert "Hello" not in client.get("/?tab=notifications").get_data(as_text=True)  # your own comment
    add_comment(settings.tra_home, "TEST01", "job:ret-TEST01-2026", "From a colleague", "someone-else",
                _audit(tmp_path))
    assert "From a colleague" in client.get("/?tab=notifications").get_data(as_text=True)
