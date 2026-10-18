"""review.json: the preparer's responses to review notes, and the reviewed mark (Sawnx spec §7.1).

Responses are keyed by the note, not its row number, so they stay attached
when the return is prepared again, and they go into the Response column of
the next workpaper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .models import ReviewNote
from .privacy.audit import AuditLog
from .privacy.guard import atomic_write_text, check_value
from .workspace import Workspace

LOCATION = "review.json"


def note_key(note: ReviewNote) -> str:
    return "|".join([note.check_id, note.label_key or "", ",".join(note.figure_ids), ",".join(note.doc_ids)])


@dataclass
class Review:
    responses: dict[str, dict] = field(default_factory=dict)
    reviewed: dict | None = None


def review_path(ws: Workspace) -> Path:
    return ws.work_dir / "review.json"


def load_review(ws: Workspace) -> Review:
    path = review_path(ws)
    if not path.exists():
        return Review()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Review(responses=data.get("responses", {}), reviewed=data.get("reviewed"))


def _save(ws: Workspace, review: Review) -> None:
    data = {"responses": review.responses, "reviewed": review.reviewed}
    check_value(data, LOCATION)
    atomic_write_text(review_path(ws), json.dumps(data, indent=2), LOCATION, prechecked=True)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def save_response(ws: Workspace, key: str, text: str, resolved: bool, by: str) -> None:
    review = load_review(ws)
    text = (text or "").strip()
    if text or resolved:
        review.responses[key] = {"text": text, "resolved": bool(resolved), "by": by, "at": _now()}
    else:
        review.responses.pop(key, None)
    _save(ws, review)


def responses_by_key(ws: Workspace) -> dict[str, str]:
    return {k: v["text"] for k, v in load_review(ws).responses.items() if v.get("text")}


def mark_reviewed(ws: Workspace, name: str, workpaper: str, notes: list[ReviewNote], audit: AuditLog) -> None:
    """``notes`` are the latest workpaper's notes; every High one must be resolved first."""
    review = load_review(ws)
    open_high = [n for n in notes if n.risk == "High" and not review.responses.get(note_key(n), {}).get("resolved")]
    if open_high:
        raise ValueError("Resolve every High note first (" + ", ".join(n.check_id for n in open_high) + ").")
    name = (name or "").strip()
    if not name:
        raise ValueError("Enter the reviewer's name.")
    review.reviewed = {"by": name, "at": _now(), "workpaper": workpaper}
    _save(ws, review)
    audit.record("review_marked", client=ws.client_code, income_year=ws.income_year, workpaper=workpaper,
                 reviewer=name)
