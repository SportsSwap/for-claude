"""Confirming and correcting figures. Every change goes through the same figures.csv code as an Excel edit."""

from __future__ import annotations

from typing import NamedTuple

from ...checks import label_name
from ...figures import append_figures, read_figures, write_figures
from ...filing.index import DocumentIndex
from ...ingest.extractors.ai_reader import TEXT_MATCH
from ...labels import figure_allowed, load_labels
from ...models import Figure
from ...money import parse_amount
from ...privacy.audit import AuditLog
from ...workspace import Workspace


class FiguresFileProblem(ValueError):
    """figures.csv has rows that need fixing before Sawnx can change it."""


def label_choices() -> list[tuple[str, str]]:
    labels = load_labels()
    usable = sorted((d for d in labels.values() if figure_allowed(d)), key=lambda d: d.order)
    return [(d.key, label_name(labels, d.key)) for d in usable]


def figure_rows(ws: Workspace) -> list[Figure]:
    figures, errors = read_figures(ws.figures_csv, load_labels())
    if errors:
        raise FiguresFileProblem("figures.csv has rows to fix first: " + "; ".join(errors))
    return figures


def _label(key: str) -> str:
    if key not in dict(label_choices()):
        raise ValueError("Choose a label from the list.")
    return key


def _amount(raw: str):
    try:
        return parse_amount(raw)
    except ValueError:
        raise ValueError(f"{raw!r} isn't an amount. Use numbers like 1234.56.") from None


def set_figure(ws: Workspace, figure_id: str, *, confirmed: bool | None = None, substantiated: bool | None = None,
               label_key: str | None = None, amount: str | None = None,
               audit: AuditLog) -> Figure:
    figures = figure_rows(ws)
    fig = next((f for f in figures if f.figure_id == figure_id), None)
    if fig is None:
        raise ValueError(f"There's no figure {figure_id}.")
    changed = []
    if label_key is not None and label_key != fig.label_key:
        fig.label_key, changed = _label(label_key), changed + ["label_key"]
    if amount is not None and _amount(amount) != fig.amount:
        fig.amount, changed = _amount(amount), changed + ["amount"]
        if fig.notes == TEXT_MATCH:
            fig.notes = ""  # the new amount isn't the one found in the document's text
    if confirmed is not None and confirmed != fig.confirmed:
        fig.confirmed, changed = confirmed, changed + ["confirmed"]
    if substantiated is not None and substantiated != fig.substantiated:
        fig.substantiated, changed = substantiated, changed + ["substantiated"]
    if changed:
        write_figures(ws.figures_csv, figures)
        audit.record("figure_changed", client=ws.client_code, figure_id=figure_id, fields=changed)
    return fig


def _waiting(f: Figure) -> bool:
    """Unconfirmed and not a pre-fill row. Pre-fill rows are left for the preparer: confirming one as well as the
    document behind it counts the income twice (check R4)."""
    return not f.confirmed and f.notes != "prefill"


def waiting_by_document(figures: list[Figure]) -> dict[str, list[str]]:
    """The figure ids each document has waiting to be confirmed, in document order. Confirm all posts these back,
    so only the figures the preparer was shown get confirmed."""
    ids: dict[str, list[str]] = {}
    for f in figures:
        if f.doc_id and _waiting(f):
            ids.setdefault(f.doc_id, []).append(f.figure_id)
    return dict(sorted(ids.items()))


class BulkConfirm(NamedTuple):
    confirmed: int  # shown figures now confirmed
    newer: int  # figures from the document waiting that weren't shown (added since the page was opened)


def confirm_document_figures(ws: Workspace, doc_id: str, audit: AuditLog, *, figure_ids) -> BulkConfirm:
    """Confirm the figures the preparer was shown (figure_ids) that are still unconfirmed, were read from this
    document and aren't pre-fill rows. Anything else waiting for the document, such as a row added in Excel, by
    Read again or by tra ai-add since the page was opened, is left unconfirmed and counted in `newer`."""
    if doc_id not in {d.doc_id for d in DocumentIndex(ws.index_csv).load()}:
        raise ValueError(f"There's no document {doc_id}.")
    shown = set(figure_ids)
    figures = figure_rows(ws)
    waiting = [f for f in figures if f.doc_id == doc_id and _waiting(f)]
    chosen = [f for f in waiting if f.figure_id in shown]
    newer = len(waiting) - len(chosen)
    if not chosen:
        return BulkConfirm(0, newer)
    for f in chosen:
        f.confirmed = True
    write_figures(ws.figures_csv, figures)
    audit.record("figures_confirmed_bulk", client=ws.client_code, doc_id=doc_id, count=len(chosen))
    return BulkConfirm(len(chosen), newer)


def add_figure(ws: Workspace, *, label_key: str, description: str, amount: str, doc_id: str | None,
               page: int | None, audit: AuditLog) -> Figure:
    figure_rows(ws)  # refuse to append to a file with rows that need fixing
    if doc_id and doc_id not in {d.doc_id for d in DocumentIndex(ws.index_csv).load()}:
        raise ValueError(f"There's no document {doc_id}.")
    fig = Figure(figure_id="", label_key=_label(label_key), description=(description or "").strip(),
                 amount=_amount(amount), date=None, doc_id=doc_id or None, page=page, method="manual",
                 confirmed=False, substantiated=None)
    [added] = append_figures(ws.figures_csv, [fig])
    audit.record("figure_added", client=ws.client_code, figure_id=added.figure_id, method="manual")
    return added
