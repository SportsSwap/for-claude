"""last_prepare.json: the latest prepare's estimate, both calculations and notes.

Written by every prepare (the `tra prepare` command and Sawnx), so Sawnx shows
the result whichever was used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .models import ReviewNote
from .notes_store import _from_dict, _to_dict
from .privacy.guard import atomic_write_text, check_value
from .taxcalc.result import TaxResult
from .workspace import Workspace

LOCATION = "last_prepare.json"


@dataclass
class PrepareSummary:
    workpaper: str
    prepared_at: str
    prepared_by: str
    net: Decimal
    a: dict[str, Decimal]
    b: dict[str, Decimal]
    notes: list[ReviewNote]

    def differing(self) -> set[str]:
        return {k for k in self.a if self.a[k] != self.b.get(k)}


def save_summary(ws: Workspace, workpaper: str, prepared_by: str, calc_a: TaxResult, calc_b: TaxResult,
                 notes: list[ReviewNote]) -> PrepareSummary:
    summary = PrepareSummary(workpaper=workpaper, prepared_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                             prepared_by=prepared_by, net=calc_a.net_result, a=calc_a.components(),
                             b=calc_b.components(), notes=list(notes))
    data = {"workpaper": summary.workpaper, "prepared_at": summary.prepared_at, "prepared_by": prepared_by,
            "net": str(summary.net), "a": {k: str(v) for k, v in summary.a.items()},
            "b": {k: str(v) for k, v in summary.b.items()}, "notes": [_to_dict(n) for n in summary.notes]}
    check_value(data, LOCATION)
    atomic_write_text(ws.last_prepare_json, json.dumps(data, indent=2), LOCATION, prechecked=True)
    return summary


def load_summary(ws: Workspace) -> PrepareSummary | None:
    if not ws.last_prepare_json.exists():
        return None
    d = json.loads(ws.last_prepare_json.read_text(encoding="utf-8"))
    return PrepareSummary(workpaper=d["workpaper"], prepared_at=d["prepared_at"], prepared_by=d["prepared_by"],
                          net=Decimal(d["net"]), a={k: Decimal(v) for k, v in d["a"].items()},
                          b={k: Decimal(v) for k, v in d["b"].items()}, notes=[_from_dict(n) for n in d["notes"]])
