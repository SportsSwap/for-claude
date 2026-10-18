"""A one-line summary of each filed document: what it is, who issued it, its date, and the figures it supports.

Built from the index and figures.csv each time (nothing stored), so it always
matches the figures. No AI is involved; the AI reader's figures are marked.
"""

from __future__ import annotations

from collections import Counter

from .checks import label_name
from .figures import read_figures
from .filing.index import DocumentIndex
from .labels import LabelDef, load_labels
from .models import Document, Figure
from .money import format_dollars
from .ingest.classify import DocType, load_doc_types
from .workspace import Workspace

MAX_FIGURES = 4


def _issuer(figures: list[Figure]) -> str | None:
    heads = []
    for f in figures:
        for sep in (" – ", ": "):
            if sep in f.description:
                heads.append(f.description.split(sep, 1)[0].strip())
                break
    return Counter(heads).most_common(1)[0][0] if heads else None


def summarize(doc: Document, figures: list[Figure], labels: dict[str, LabelDef],
              doc_types: dict[str, DocType]) -> str:
    if doc.parse_status == "stored":
        return "Stored only, not read."
    mine = [f for f in figures if f.doc_id == doc.doc_id]
    kind = doc_types[doc.doc_type].description if doc.doc_type in doc_types else doc.doc_type
    if not mine:
        return f"{kind} · Couldn't read this document's figures; add a description and enter them by hand."
    parts = [kind]
    issuer = _issuer(mine)
    if issuer:
        parts.append(issuer)
    if doc.date_detected:
        parts.append(f"dated {doc.doc_date.strftime('%d %b %Y')}")
    shown = [f"{label_name(labels, f.label_key)} {format_dollars(f.amount)}" for f in mine[:MAX_FIGURES]]
    more = f" and {len(mine) - MAX_FIGURES} more" if len(mine) > MAX_FIGURES else ""
    parts.append("supports " + "; ".join(shown) + more)
    if any(f.method == "ai" for f in mine):
        parts.append("figures read by the AI reader")
    return " · ".join(parts)


def summaries(ws: Workspace) -> dict[str, str]:
    """doc_id -> summary, for every filed document."""
    labels, doc_types = load_labels(), load_doc_types()
    figures, _errors = read_figures(ws.figures_csv, labels)
    return {d.doc_id: summarize(d, figures, labels, doc_types) for d in DocumentIndex(ws.index_csv).load()}
