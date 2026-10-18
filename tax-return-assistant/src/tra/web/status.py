"""Where a client's return is up to (spec §7.2). Worked out from the files each time."""

from __future__ import annotations

from pathlib import Path

from ..figures import read_figures
from ..filing.index import DocumentIndex
from ..labels import load_labels
from ..review_store import load_review
from ..workspace import Workspace

STATUSES = ("New", "Docs in", "Figures confirmed", "Prepared", "Reviewed")


def latest_workpaper(ws: Workspace) -> Path | None:
    from .services.prepare import workpapers

    papers = workpapers(ws)
    return papers[0] if papers else None


def _inputs_changed(ws: Workspace) -> float:
    paths = (ws.figures_csv, ws.state_json, ws.cgt_csv, ws.prior_year_csv)
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def _reviewed(ws: Workspace, workpaper: Path) -> bool:
    reviewed = load_review(ws).reviewed
    return bool(reviewed) and reviewed.get("workpaper") == workpaper.name


def job_status(ws: Workspace) -> str:
    if not DocumentIndex(ws.index_csv).load():
        return "New"
    figures, errors = read_figures(ws.figures_csv, load_labels())
    to_check = [f for f in figures if not f.confirmed and f.notes != "prefill"]
    if errors or to_check or not any(f.confirmed for f in figures):
        return "Docs in"
    workpaper = latest_workpaper(ws)
    if workpaper is None or workpaper.stat().st_mtime < _inputs_changed(ws):
        return "Figures confirmed"
    return "Reviewed" if _reviewed(ws, workpaper) else "Prepared"
