"""Jobs and tasks (FYI-style), in TRA_HOME/sawnx_jobs.json. Clients are referred to by code only.

Every client-year has a return job, "Individual tax return FY<year>", whose status is the
return's own status (web/status.py); only its due date, assignee and notes are stored.
Custom jobs (BAS, advice...) carry their own status. Tasks belong to a job or stand alone.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value
from ..workspace import Workspace
from .status import job_status

LOCATION = "sawnx_jobs.json"
JOB_STATUSES = ("Not started", "In progress", "Waiting on client", "Done")
_RETURN_ID = re.compile(r"^ret-([A-Z0-9]{2,12})-(\d{4})$")
MAX_TEXT = 300


@dataclass
class JobRow:
    id: str
    kind: str  # return | custom
    code: str
    income_year: int | None
    name: str
    status: str
    due: date | None
    assignee: str
    notes: str

    @property
    def done(self) -> bool:
        return self.status in ("Done", "Reviewed")

    @property
    def overdue(self) -> bool:
        return bool(self.due and self.due < date.today() and not self.done)


@dataclass
class Task:
    id: str
    title: str
    job_id: str | None
    code: str | None
    due: str
    assignee: str
    done: bool
    by: str
    created_at: str
    done_at: str | None = None

    @property
    def due_date(self) -> date | None:
        return date.fromisoformat(self.due) if self.due else None

    @property
    def overdue(self) -> bool:
        return bool(self.due_date and self.due_date < date.today() and not self.done)


def _path(tra_home: Path) -> Path:
    return Path(tra_home) / "sawnx_jobs.json"


def _load(tra_home: Path) -> dict:
    path = _path(tra_home)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {"returns": data.get("returns", {}), "jobs": data.get("jobs", []), "tasks": data.get("tasks", [])}


def _save(tra_home: Path, data: dict) -> None:
    check_value(data, LOCATION)
    atomic_write_text(_path(tra_home), json.dumps(data, indent=2), LOCATION, prechecked=True)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _text(value: str, what: str, required: bool = False) -> str:
    value = " ".join((value or "").split()) if what != "notes" else (value or "").strip()
    if required and not value:
        raise ValueError(f"Enter the {what}.")
    if len(value) > MAX_TEXT:
        raise ValueError(f"Keep the {what} to {MAX_TEXT} characters.")
    return value


def _due(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError("Use a date like 2026-10-31 for the due date.") from None


def client_years(tra_home: Path) -> dict[str, list[int]]:
    years: dict[str, list[int]] = {}
    for state in (Path(tra_home) / "Work").glob("*/FY*/state.json"):
        fy = state.parent.name[2:]
        if fy.isdigit():
            years.setdefault(state.parent.parent.name, []).append(int(fy))
    return {k: sorted(v, reverse=True) for k, v in years.items()}


def list_jobs(tra_home: Path) -> list[JobRow]:
    data = _load(tra_home)
    rows = []
    for code, years in sorted(client_years(tra_home).items()):
        for fy in years:
            job_id = f"ret-{code}-{fy}"
            extra = data["returns"].get(job_id, {})
            rows.append(JobRow(id=job_id, kind="return", code=code, income_year=fy,
                               name=f"Individual tax return FY{fy}", status=job_status(Workspace(tra_home, code, fy)),
                               due=date.fromisoformat(extra["due"]) if extra.get("due") else None,
                               assignee=extra.get("assignee", ""), notes=extra.get("notes", "")))
    for j in data["jobs"]:
        rows.append(JobRow(id=j["id"], kind="custom", code=j["code"], income_year=None, name=j["name"],
                           status=j["status"], due=date.fromisoformat(j["due"]) if j.get("due") else None,
                           assignee=j.get("assignee", ""), notes=j.get("notes", "")))
    return rows


def find_job(tra_home: Path, job_id: str) -> JobRow | None:
    return next((j for j in list_jobs(tra_home) if j.id == job_id), None)


def add_job(tra_home: Path, code: str, name: str, *, due: str, assignee: str, notes: str, by: str,
            audit: AuditLog) -> JobRow:
    if code not in client_years(tra_home):
        raise ValueError("Choose a client from the list.")
    data = _load(tra_home)
    job = {"id": f"job-{secrets.token_hex(5)}", "code": code, "name": _text(name, "job name", required=True),
           "status": JOB_STATUSES[0], "due": _due(due), "assignee": _text(assignee, "assignee"),
           "notes": _text(notes, "notes"), "by": by, "created_at": _now()}
    data["jobs"].append(job)
    _save(tra_home, data)
    audit.record("job_added", client=code, job=job["id"])
    return find_job(tra_home, job["id"])


def update_job(tra_home: Path, job_id: str, *, status: str | None = None, due: str | None = None,
               assignee: str | None = None, notes: str | None = None, audit: AuditLog) -> None:
    data = _load(tra_home)
    m = _RETURN_ID.match(job_id)
    if m:
        if status is not None:
            raise ValueError("A tax return job's status follows the return itself.")
        if m.group(1) not in client_years(tra_home) or int(m.group(2)) not in client_years(tra_home)[m.group(1)]:
            raise ValueError("There's no such job.")
        entry = data["returns"].setdefault(job_id, {})
        code = m.group(1)
    else:
        entry = next((j for j in data["jobs"] if j["id"] == job_id), None)
        if entry is None:
            raise ValueError("There's no such job.")
        code = entry["code"]
        if status is not None:
            if status not in JOB_STATUSES:
                raise ValueError("Choose a status from the list.")
            entry["status"] = status
    if due is not None:
        entry["due"] = _due(due)
    if assignee is not None:
        entry["assignee"] = _text(assignee, "assignee")
    if notes is not None:
        entry["notes"] = _text(notes, "notes")
    _save(tra_home, data)
    audit.record("job_updated", client=code, job=job_id)


def list_tasks(tra_home: Path) -> list[Task]:
    return [Task(**t) for t in _load(tra_home)["tasks"]]


def add_task(tra_home: Path, title: str, *, job_id: str | None, due: str, assignee: str, by: str,
             audit: AuditLog) -> Task:
    code = None
    if job_id:
        job = find_job(tra_home, job_id)
        if job is None:
            raise ValueError("There's no such job.")
        code = job.code
    data = _load(tra_home)
    task = {"id": f"task-{secrets.token_hex(5)}", "title": _text(title, "task", required=True), "job_id": job_id or None,
            "code": code, "due": _due(due), "assignee": _text(assignee, "assignee"), "done": False, "by": by,
            "created_at": _now(), "done_at": None}
    data["tasks"].append(task)
    _save(tra_home, data)
    audit.record("task_added", client=code, task=task["id"])
    return Task(**task)


def set_task_done(tra_home: Path, task_id: str, done: bool, audit: AuditLog) -> None:
    data = _load(tra_home)
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if task is None:
        raise ValueError("There's no such task.")
    task["done"], task["done_at"] = bool(done), (_now() if done else None)
    _save(tra_home, data)
    audit.record("task_done" if done else "task_reopened", client=task.get("code"), task=task_id)


def _sorted(tasks: list[Task]) -> list[Task]:
    return sorted(tasks, key=lambda t: (t.due or "9999", t.created_at))


def my_tasks(tra_home: Path, user: str) -> list[Task]:
    """Open tasks assigned to this Windows user, or to nobody."""
    return _sorted([t for t in list_tasks(tra_home)
                    if not t.done and (not t.assignee or t.assignee.lower() == user.lower())])


def delegated_tasks(tra_home: Path, user: str) -> list[Task]:
    return _sorted([t for t in list_tasks(tra_home)
                    if not t.done and t.assignee and t.assignee.lower() != user.lower()])


__all__ = ["JOB_STATUSES", "JobRow", "Task", "add_job", "add_task", "asdict", "client_years", "delegated_tasks",
           "find_job", "list_jobs", "list_tasks", "my_tasks", "set_task_done", "update_job"]
