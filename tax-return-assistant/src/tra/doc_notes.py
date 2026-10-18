"""The preparer's own description of each document (doc_notes.json), kept as part of the evidence trail.

Shown in Sawnx beside the automatic summary and written into the workpaper's
Sources tab. Saved through the output guard like everything else.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .privacy.guard import atomic_write_text, check_value
from .workspace import Workspace

LOCATION = "doc_notes.json"
MAX_TEXT = 500


def doc_notes_path(ws: Workspace) -> Path:
    return ws.work_dir / "doc_notes.json"


def load_doc_notes(ws: Workspace) -> dict[str, dict]:
    path = doc_notes_path(ws)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_doc_note(ws: Workspace, doc_id: str, text: str, by: str) -> None:
    """Blank text removes the description."""
    text = (text or "").strip()
    if len(text) > MAX_TEXT:
        raise ValueError(f"Keep the description to {MAX_TEXT} characters.")
    notes = load_doc_notes(ws)
    if text:
        notes[doc_id] = {"text": text, "by": by, "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    else:
        notes.pop(doc_id, None)
    check_value(notes, LOCATION)
    atomic_write_text(doc_notes_path(ws), json.dumps(notes, indent=2), LOCATION, prechecked=True)
