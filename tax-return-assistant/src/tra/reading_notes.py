"""What the readers weren't sure about, per document: reading_notes.json in the client's work folder.

{doc_id: {"doubts": ["Didn't find the franking credit.", ...], "from_email": "D012" or null}}.
Written during ingest inside the same roll-back as the figures; tra/to_check.py turns it into
each document's Things to check.
"""

from __future__ import annotations

import json

from .privacy.guard import atomic_write_text, check_value

LOCATION = "reading_notes.json"


def load_reading_notes(ws) -> dict[str, dict]:
    path = ws.reading_notes_json
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save(ws, notes: dict[str, dict]) -> None:
    check_value(notes, LOCATION)
    atomic_write_text(ws.reading_notes_json, json.dumps(notes, indent=2), LOCATION, prechecked=True)


def save_reading_notes(ws, doc_id: str, doubts: list[str], from_email: str | None = None, *,
                       layout: str | None = None) -> None:
    """``layout`` is the learned layout (config/layouts) that read the document, if one did."""
    notes = load_reading_notes(ws)
    notes[doc_id] = {"doubts": list(doubts), "from_email": from_email}
    if layout:
        notes[doc_id]["layout"] = layout
    _save(ws, notes)


def forget_reading_notes(ws, doc_id: str) -> None:
    if not hasattr(ws, "reading_notes_json"):
        return
    notes = load_reading_notes(ws)
    if notes.pop(doc_id, None) is not None:
        _save(ws, notes)
