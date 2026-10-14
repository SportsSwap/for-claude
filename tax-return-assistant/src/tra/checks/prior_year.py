"""Y1-Y2: movements against last year's return."""

from __future__ import annotations

import json
from decimal import Decimal

from ..figures import read_prior_year
from ..models import ReviewNote
from ..workspace import Workspace
from . import label_name
from .context import CheckContext


def load_prior_year(ws: Workspace) -> dict[str, Decimal]:
    """prior_year.csv if the preparer filled it in, else last year's `tra prepare` output, else nothing."""
    if ws.prior_year_csv.exists():
        return read_prior_year(ws.prior_year_csv)
    last = ws.for_year(ws.income_year - 1).last_return_json
    if last.exists():
        return {k: Decimal(v) for k, v in json.loads(last.read_text(encoding="utf-8")).items()}
    return {}


def check_prior_year(ctx: CheckContext) -> list[ReviewNote]:
    pct = Decimal(str(ctx.cfg.get("prior_year_pct", "0.20")))
    floor = Decimal(str(ctx.cfg.get("prior_year_floor", 100)))
    notes = []
    for key, prior in ctx.prior_year.items():
        name = label_name(ctx.labels, key)
        if key not in ctx.draft.lines:
            if prior:
                notes.append(ReviewNote("Medium", "Y2", f"{name}: ${prior:,} last year and nothing this year. Ask the "
                                        "client whether this has stopped or a document is missing.", abs(prior),
                                        "client", "question", label_key=key))
            continue
        current = ctx.draft.amount(key)
        change = current - prior
        if abs(change) > pct * abs(prior) and abs(change) > floor:
            movement = f" ({change / prior:+.0%})" if prior else " (new this year)"
            notes.append(ReviewNote("Medium", "Y1", f"{name}: ${prior:,} last year, ${current:,} this year{movement}. "
                                    "Explain the movement on the workpaper.", abs(change), "reviewer", "confirm",
                                    label_key=key))
    return notes
