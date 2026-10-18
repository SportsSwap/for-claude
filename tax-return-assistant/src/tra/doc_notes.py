"""The preparer's own notes on each document (doc_notes.json): a description and a status.

Kept as part of the evidence trail: shown in Sawnx beside the automatic summary
and written into the workpaper's Sources tab. Saved through the output guard.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .privacy.guard import atomic_write_text, check_value

LOCATION = "doc_notes.json"
MAX_TEXT = 500
STATUSES = ("", "To review", "Final", "Superseded")


def doc_notes_path(ws) -> Path:
    return ws.work_dir / "doc_notes.json"


def load_doc_notes(ws) -> dict[str, dict]:
    path = doc_notes_path(ws)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save(ws, notes: dict) -> None:
    check_value(notes, LOCATION)
    atomic_write_text(doc_notes_path(ws), json.dumps(notes, indent=2), LOCATION, prechecked=True)


def _update(ws, doc_id: str, by: str, **fields) -> None:
    notes = load_doc_notes(ws)
    entry = {**notes.get(doc_id, {}), **fields, "by": by, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    if entry.get("text") or entry.get("status"):
        notes[doc_id] = entry
    else:
        notes.pop(doc_id, None)
    _save(ws, notes)


def save_doc_note(ws, doc_id: str, text: str, by: str) -> None:
    """Blank text removes the description (the status is kept)."""
    text = (text or "").strip()
    if len(text) > MAX_TEXT:
        raise ValueError(f"Keep the description to {MAX_TEXT} characters.")
    _update(ws, doc_id, by, text=text)


def set_doc_status(ws, doc_id: str, status: str, by: str) -> None:
    if status not in STATUSES:
        raise ValueError("Choose a status from the list.")
    _update(ws, doc_id, by, status=status)
