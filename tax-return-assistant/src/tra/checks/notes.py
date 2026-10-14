"""Rank review notes: High, Medium, Low; within each, biggest dollar impact first."""

from __future__ import annotations

from ..models import ReviewNote

_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def rank_notes(notes: list[ReviewNote]) -> list[ReviewNote]:
    seen, unique = set(), []
    for n in notes:
        key = (n.check_id, n.label_key, n.doc_ids, n.figure_ids, n.message)
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return sorted(unique, key=lambda n: (_ORDER[n.risk], n.dollar_impact is None,
                                         -abs(n.dollar_impact) if n.dollar_impact is not None else 0))
