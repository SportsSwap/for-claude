"""Comments on documents and jobs: Work/<code>/comments.json, through the output guard."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value
from .ids import new_id
from .stars import KEY

LOCATION = "comments.json"
MAX_TEXT = 1000
_JOB = re.compile(r"^(ret-[A-Z0-9]{2,12}-\d{4}|job-[0-9a-z]{10})$")


def _path(tra_home: Path, code: str) -> Path:
    return Path(tra_home) / "Work" / code / "comments.json"


def _load(tra_home: Path, code: str) -> list[dict]:
    path = _path(tra_home, code)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def valid_target(code: str, target: str) -> bool:
    kind, _, ref = (target or "").partition(":")
    if kind == "doc":
        m = KEY.match(ref)
        return bool(m and m.group(1) == code)
    return kind == "job" and bool(_JOB.match(ref))


def add_comment(tra_home: Path, code: str, target: str, text: str, by: str, audit: AuditLog) -> dict:
    if not valid_target(code, target):
        raise ValueError("That comment isn't attached to a document or job Sawnx knows.")
    text = (text or "").strip()
    if not text:
        raise ValueError("Write something first.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"Keep comments to {MAX_TEXT} characters.")
    comments = _load(tra_home, code)
    comment = {"id": new_id(), "target": target, "text": text, "by": by,
               "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    data = comments + [comment]
    check_value(data, LOCATION)
    atomic_write_text(_path(tra_home, code), json.dumps(data, indent=2), LOCATION, prechecked=True)
    audit.record("comment_added", client=code, target=target)
    return comment


def forget_comments(tra_home: Path, code: str, target: str) -> None:
    """Remove the comments on one document (when it is deleted forever)."""
    comments = _load(tra_home, code)
    kept = [c for c in comments if c["target"] != target]
    if len(kept) != len(comments):
        check_value(kept, LOCATION)
        atomic_write_text(_path(tra_home, code), json.dumps(kept, indent=2), LOCATION, prechecked=True)


def list_comments(tra_home: Path, code: str, target: str | None = None) -> list[dict]:
    return [c for c in _load(tra_home, code) if target is None or c["target"] == target]


def all_comments(tra_home: Path) -> list[tuple[str, dict]]:
    out = []
    for path in (Path(tra_home) / "Work").glob("*/comments.json"):
        out += [(path.parent.name, c) for c in json.loads(path.read_text(encoding="utf-8"))]
    return sorted(out, key=lambda x: x[1]["at"], reverse=True)
