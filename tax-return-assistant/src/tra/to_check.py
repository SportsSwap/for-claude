"""Things to check: what to look at in a document before downloading it or confirming its figures.

Put together each time (nothing stored) from three places: the readers' doubts (reading_notes.json),
the review notes the import raised for the document, and its unconfirmed figures that need a closer
look (read by the AI reader or Claude, a suggested label, or no page). The built-in readers find a
line or they don't, so there are no confidence scores: each item says what was missed or guessed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass

from .checks import label_name
from .figures import read_figures
from .labels import load_labels
from .models import Figure
from .reading_notes import load_reading_notes

# Import notes worth seeing on the document: manual entry, no date, FYI fallback, area not handled,
# hospital cover days, and the AI reader's problems. Not I4 (a duplicate is skipped, not filed).
NOTE_CHECKS = frozenset({"I1", "I2", "I3", "I6", "I7", "A2", "A3"})


@dataclass(frozen=True)
class CheckItem:
    text: str
    risk: str = ""
    figure_id: str | None = None
    counted: bool = True  # False for "Came attached to email D012": worth showing, nothing to check


def _figure_reasons(f: Figure, labels) -> str:
    reasons = []
    if f.method == "ai":
        reasons.append("read by the AI reader or Claude")
    if (f.notes or "").startswith("suggested label"):
        reasons.append(f"label suggested ({label_name(labels, f.label_key)})")
    if f.page is None:
        reasons.append("the page isn't known")
    return ", and ".join(reasons)


def _all_items(ws) -> dict[str, list[CheckItem]]:
    items: dict[str, list[CheckItem]] = defaultdict(list)
    for doc_id, entry in load_reading_notes(ws).items():
        items[doc_id] += [CheckItem(d) for d in entry.get("doubts", [])]
        if entry.get("from_email"):
            items[doc_id].append(CheckItem(f"Came attached to email {entry['from_email']}.", counted=False))
    path = ws.ingest_notes_json
    for note in json.loads(path.read_text(encoding="utf-8")) if path.exists() else []:
        if note.get("check_id") in NOTE_CHECKS:
            for doc_id in note.get("doc_ids", []):
                items[doc_id].append(CheckItem(note["message"], note.get("risk", "")))
    labels = load_labels()
    figures, _errors = read_figures(ws.figures_csv, labels)
    for f in figures:
        reasons = _figure_reasons(f, labels) if f.doc_id and not f.confirmed else ""
        if reasons:
            items[f.doc_id].append(CheckItem(f"{f.figure_id}: {reasons}. Check it before confirming.",
                                             figure_id=f.figure_id))
    return items


def things_to_check(ws, doc_id: str) -> list[CheckItem]:
    return _all_items(ws).get(doc_id, [])


def to_check_counts(ws) -> dict[str, int]:
    counts = {doc_id: sum(i.counted for i in found) for doc_id, found in _all_items(ws).items()}
    return {doc_id: n for doc_id, n in counts.items() if n}


def to_check_by_figure(ws) -> dict[str, list[str]]:
    """figure_id -> what to check about that figure, for the Figures tab."""
    out: dict[str, list[str]] = {}
    for found in _all_items(ws).values():
        for item in found:
            if item.figure_id:
                reason = item.text.split(": ", 1)[1]
                out.setdefault(item.figure_id, []).append(reason[0].upper() + reason[1:])
    return out
