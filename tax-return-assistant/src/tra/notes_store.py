"""Review notes raised during ingest, kept until `tra prepare` ranks them with the rest."""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path

from .models import ReviewNote
from .privacy.guard import atomic_write_text, check_value


def _to_dict(note: ReviewNote) -> dict:
    d = dataclasses.asdict(note)
    d["dollar_impact"] = None if note.dollar_impact is None else str(note.dollar_impact)
    d["figure_ids"], d["doc_ids"] = list(note.figure_ids), list(note.doc_ids)
    return d


def _from_dict(d: dict) -> ReviewNote:
    impact = d.get("dollar_impact")
    return ReviewNote(**{**d, "dollar_impact": None if impact is None else Decimal(impact),
                         "figure_ids": tuple(d.get("figure_ids", ())), "doc_ids": tuple(d.get("doc_ids", ()))})


def read_notes(path: Path) -> list[ReviewNote]:
    if not path.exists():
        return []
    return [_from_dict(d) for d in json.loads(path.read_text(encoding="utf-8"))]


def append_notes(path: Path, notes: list[ReviewNote]) -> None:
    if not notes:
        return
    data = [_to_dict(n) for n in read_notes(path) + list(notes)]
    check_value(data, path.name)
    atomic_write_text(path, json.dumps(data, indent=2), path.name, prechecked=True)
