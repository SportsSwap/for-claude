"""Notifications, worked out each time: tasks and jobs due, the In Tray, recent comments by others."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .comments import all_comments
from .jobs import list_jobs, my_tasks

RECENT_DAYS = 7


@dataclass
class Notification:
    kind: str  # overdue | today | intray | comment
    text: str
    link: str


def _job_link(job_id: str | None) -> str:
    return f"/jobs/{job_id}" if job_id else "/?tab=tasks"


def notifications(tra_home: Path, user: str) -> list[Notification]:
    from .intray import list_tray

    today, out = date.today(), []
    for t in my_tasks(tra_home, user):
        if t.due_date and t.due_date < today:
            out.append(Notification("overdue", f"Task \"{t.title}\" is overdue (due {t.due_date:%d %b}).",
                                    _job_link(t.job_id)))
        elif t.due_date == today:
            out.append(Notification("today", f"Task \"{t.title}\" is due today.", _job_link(t.job_id)))
    for j in list_jobs(tra_home):
        if j.overdue and (not j.assignee or j.assignee.lower() == user.lower()):
            out.append(Notification("overdue", f"Job \"{j.name}\" ({j.code}) is overdue (due {j.due:%d %b}).",
                                    f"/jobs/{j.id}"))
    waiting = len(list_tray(tra_home))
    if waiting:
        out.append(Notification("intray", f"{waiting} document{'' if waiting == 1 else 's'} waiting in the In Tray.",
                                "/intray"))
    since = datetime.now().astimezone() - timedelta(days=RECENT_DAYS)
    for code, c in all_comments(tra_home):
        if c["by"].lower() != user.lower() and datetime.fromisoformat(c["at"]) >= since:
            link = f"/jobs/{c['target'][4:]}" if c["target"].startswith("job:") else "/documents"
            out.append(Notification("comment", f"{c['by']} on {code}: {c['text'][:120]}", link))
    return out
