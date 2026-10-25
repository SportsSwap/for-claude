"""The preparer's own file notes about a client, for all years: TRA_HOME/Work/<code>/client_notes.json."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..privacy.guard import atomic_write_text, check_value
from .ids import new_id

LOCATION = "client_notes.json"


def notes_path(tra_home: Path, code: str) -> Path:
    return Path(tra_home) / "Work" / code / "client_notes.json"


def _load(tra_home: Path, code: str) -> list[dict]:
    path = notes_path(tra_home, code)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _save(tra_home: Path, code: str, notes: list[dict]) -> None:
    check_value(notes, LOCATION)
    atomic_write_text(notes_path(tra_home, code), json.dumps(notes, indent=2), LOCATION, prechecked=True)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise ValueError("Write something first.")
    return text


def list_notes(tra_home: Path, code: str) -> list[dict]:
    return list(reversed(_load(tra_home, code)))  # notes are appended, so this is newest first


def add_note(tra_home: Path, code: str, text: str, by: str, income_year: int | None = None) -> dict:
    note = {"id": new_id(), "text": _text(text), "income_year": income_year, "by": by, "at": _now(),
            "edited_at": None}
    _save(tra_home, code, _load(tra_home, code) + [note])
    return note


def edit_note(tra_home: Path, code: str, note_id: str, text: str) -> dict:
    notes = _load(tra_home, code)
    note = next((n for n in notes if n["id"] == note_id), None)
    if note is None:
        raise ValueError("That note no longer exists.")
    note.update(text=_text(text), edited_at=_now())
    _save(tra_home, code, notes)
    return note


def delete_note(tra_home: Path, code: str, note_id: str) -> None:
    notes = _load(tra_home, code)
    kept = [n for n in notes if n["id"] != note_id]
    if len(kept) == len(notes):
        raise ValueError("That note no longer exists.")
    _save(tra_home, code, kept)
