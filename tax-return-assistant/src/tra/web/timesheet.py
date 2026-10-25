"""Time recorded against jobs: TRA_HOME/sawnx_time.json, through the output guard."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value
from .ids import new_id
from .jobs import find_job

LOCATION = "sawnx_time.json"


def _path(tra_home: Path) -> Path:
    return Path(tra_home) / "sawnx_time.json"


def list_time(tra_home: Path, job_id: str | None = None) -> list[dict]:
    path = _path(tra_home)
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return sorted([e for e in entries if job_id is None or e["job_id"] == job_id], key=lambda e: e["date"], reverse=True)


def add_time(tra_home: Path, job_id: str, day: str, minutes: str, what: str, by: str, audit: AuditLog) -> dict:
    job = find_job(tra_home, job_id)
    if job is None:
        raise ValueError("There's no such job.")
    try:
        when = date.fromisoformat((day or "").strip())
    except ValueError:
        raise ValueError("Use a date like 2026-10-18.") from None
    try:
        mins = int((minutes or "").strip())
    except ValueError:
        mins = 0
    if not 1 <= mins <= 1440:
        raise ValueError("Enter the minutes spent (1 to 1440).")
    what = " ".join((what or "").split())[:300]
    entry = {"id": new_id(), "job_id": job_id, "code": job.code, "date": when.isoformat(), "minutes": mins,
             "what": what, "by": by, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    data = list_time(tra_home) + [entry]
    check_value(data, LOCATION)
    atomic_write_text(_path(tra_home), json.dumps(data, indent=2), LOCATION, prechecked=True)
    audit.record("time_added", client=job.code, job=job_id, minutes=mins)
    return entry


def my_week(tra_home: Path, user: str) -> tuple[list[dict], int]:
    """This week's entries (Monday on) by this Windows user, newest first, and their total minutes."""
    monday = date.today() - timedelta(days=date.today().weekday())
    entries = [e for e in list_time(tra_home) if e["by"].lower() == user.lower() and e["date"] >= monday.isoformat()]
    return entries, sum(e["minutes"] for e in entries)
