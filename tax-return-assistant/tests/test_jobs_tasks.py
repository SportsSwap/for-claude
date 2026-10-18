from datetime import date, timedelta

import pytest
from webctx import build_test01, make_client, new_client

from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.jobs import (JOB_STATUSES, add_job, add_task, list_jobs, list_tasks, my_tasks, delegated_tasks,
                          set_task_done, update_job)


def _audit(tmp_path):
    return AuditLog(tmp_path / "a.jsonl")


def test_return_jobs_follow_the_return(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    build_test01(settings)
    new_client(settings, "DEMO01")
    jobs = {j.id: j for j in list_jobs(settings.tra_home)}
    assert jobs["ret-TEST01-2026"].name == "Individual tax return FY2026"
    assert jobs["ret-TEST01-2026"].status == "Figures confirmed" and jobs["ret-DEMO01-2026"].status == "New"
    update_job(settings.tra_home, "ret-TEST01-2026", due="2026-10-31", assignee="Nicho", notes="Needs pre-fill",
               audit=_audit(tmp_path))
    j = {j.id: j for j in list_jobs(settings.tra_home)}["ret-TEST01-2026"]
    assert (j.due, j.assignee, j.notes, j.kind) == (date(2026, 10, 31), "Nicho", "Needs pre-fill", "return")
    with pytest.raises(ValueError):
        update_job(settings.tra_home, "ret-TEST01-2026", status="Done", audit=_audit(tmp_path))


def test_custom_jobs(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    job = add_job(settings.tra_home, "TEST01", "BAS Q1", due="2026-11-28", assignee="", notes="", by="nicho",
                  audit=_audit(tmp_path))
    assert job.status == "Not started" and JOB_STATUSES[0] == "Not started"
    update_job(settings.tra_home, job.id, status="Waiting on client", audit=_audit(tmp_path))
    assert {j.id: j for j in list_jobs(settings.tra_home)}[job.id].status == "Waiting on client"
    with pytest.raises(ValueError):
        add_job(settings.tra_home, "NOPE01", "BAS", due="", assignee="", notes="", by="n", audit=_audit(tmp_path))
    with pytest.raises(ValueError):
        update_job(settings.tra_home, job.id, status="Lost", audit=_audit(tmp_path))
    with pytest.raises(ValueError):
        add_job(settings.tra_home, "TEST01", "", due="", assignee="", notes="", by="n", audit=_audit(tmp_path))


def test_overdue_flag(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    job = add_job(settings.tra_home, "TEST01", "Advice", due=yesterday, assignee="", notes="", by="n",
                  audit=_audit(tmp_path))
    assert {j.id: j for j in list_jobs(settings.tra_home)}[job.id].overdue is True
    update_job(settings.tra_home, job.id, status="Done", audit=_audit(tmp_path))
    assert {j.id: j for j in list_jobs(settings.tra_home)}[job.id].overdue is False


def test_tasks_mine_and_delegated(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    home = settings.tra_home
    mine = add_task(home, "Ask for pre-fill", job_id="ret-TEST01-2026", due="", assignee="", by="nicho",
                    audit=_audit(tmp_path))
    theirs = add_task(home, "Check rates", job_id=None, due="", assignee="Alex", by="nicho", audit=_audit(tmp_path))
    assert mine.code == "TEST01" and theirs.code is None
    assert [t.id for t in my_tasks(home, "nicho")] == [mine.id]
    assert [t.id for t in delegated_tasks(home, "nicho")] == [theirs.id]
    set_task_done(home, mine.id, True, _audit(tmp_path))
    assert my_tasks(home, "nicho") == [] and list_tasks(home)[0].done is True
    with pytest.raises(ValueError):
        add_task(home, "x", job_id="ret-NOPE01-2026", due="", assignee="", by="n", audit=_audit(tmp_path))


def test_identifiers_refused(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    with pytest.raises(SensitiveDataBlocked):
        add_task(settings.tra_home, f"Ring about TFN {make_tfn()}", job_id=None, due="", assignee="", by="n",
                 audit=_audit(tmp_path))


def test_jobs_pages(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    page = client.get("/jobs").get_data(as_text=True)
    assert "Individual tax return FY2026" in page
    resp = client.post("/jobs", data={"code": "TEST01", "name": "BAS Q1", "due": "2026-11-28", "assignee": ""})
    assert resp.status_code == 302
    [job] = [j for j in list_jobs(settings.tra_home) if j.kind == "custom"]
    assert client.get(f"/jobs/{job.id}").status_code == 200
    client.post(f"/jobs/{job.id}", data={"status": "In progress", "due": "2026-11-30", "assignee": "Nicho", "notes": ""})
    client.post(f"/jobs/{job.id}/tasks", data={"title": "Get bank statements", "due": "", "assignee": ""})
    [task] = list_tasks(settings.tra_home)
    client.post(f"/tasks/{task.id}/done", data={"done": "on", "next": "/"})
    assert list_tasks(settings.tra_home)[0].done is True
    home = client.get("/?tab=tasks").get_data(as_text=True)
    assert "My Tasks" in home and "Delegated Tasks" in home
    assert client.get("/jobs/nope").status_code == 404
