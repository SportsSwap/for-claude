"""The client list and finding one client's workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from werkzeug.exceptions import NotFound

from ...figures import read_figures
from ...filing.index import DocumentIndex
from ...labels import load_labels
from ...settings import Settings, validate_client_code
from ...workspace import Workspace
from ..status import job_status
from .prepare import load_summary

_FY = re.compile(r"^FY(\d{4})$")


@dataclass
class ClientRow:
    code: str
    income_year: int
    status: str
    documents: int
    to_confirm: int
    high_notes: int | None
    estimate: Decimal | None  # positive payable, negative refund
    last_change: datetime


def _last_change(ws: Workspace) -> datetime:
    times = [p.stat().st_mtime for p in (ws.work_dir.iterdir() if ws.work_dir.is_dir() else []) if p.is_file()]
    if ws.index_csv.exists():
        times.append(ws.index_csv.stat().st_mtime)
    return datetime.fromtimestamp(max(times, default=0.0))


def client_row(ws: Workspace) -> ClientRow:
    figures, _errors = read_figures(ws.figures_csv, load_labels())
    summary = load_summary(ws)
    return ClientRow(code=ws.client_code, income_year=ws.income_year, status=job_status(ws),
                     documents=len(DocumentIndex(ws.index_csv).load()),
                     to_confirm=sum(1 for f in figures if not f.confirmed and f.notes != "prefill"),
                     high_notes=sum(n.risk == "High" for n in summary.notes) if summary else None,
                     estimate=summary.net if summary else None, last_change=_last_change(ws))


def list_clients(tra_home: Path) -> list[ClientRow]:
    rows = []
    work = Path(tra_home) / "Work"
    for state in sorted(work.glob("*/FY*/state.json")) if work.is_dir() else []:
        m = _FY.match(state.parent.name)
        if m:
            rows.append(client_row(Workspace(tra_home, state.parent.parent.name, int(m.group(1)))))
    return sorted(rows, key=lambda r: r.last_change, reverse=True)


def workspace_for(settings: Settings, code: str, fy: int) -> Workspace:
    try:
        validate_client_code(code, settings.client_code_pattern)
    except ValueError:
        raise NotFound() from None
    ws = Workspace(settings.tra_home, code, fy)
    if not ws.state_json.exists():
        raise NotFound()
    return ws
