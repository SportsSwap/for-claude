"""P1-P4: compare the return with the ATO pre-fill report."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..models import ReviewNote
from ..money import ZERO
from . import label_name
from .context import CheckContext

# Pre-fill totals that compare against the sum of several labels.
AGGREGATES = {
    "phi.premiums_total": ("phi.premiums_p1", "phi.premiums_p2"),
    "phi.rebate_total": ("phi.rebate_p1", "phi.rebate_p2"),
}


def check_prefill(ctx: CheckContext) -> list[ReviewNote]:
    notes: list[ReviewNote] = []
    tolerance = Decimal(str(ctx.cfg.get("prefill_tolerance", 1)))
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    payers: dict[str, list[str]] = defaultdict(list)
    for line in ctx.prefill:
        totals[line.label_key] += line.amount
        payers[line.label_key].append(line.payer)

    for key, prefill_total in totals.items():
        if key == "help.indicator":
            continue
        targets = AGGREGATES.get(key, (key,))
        present = [k for k in targets if k in ctx.draft.lines]
        name = label_name(ctx.labels, key)
        if not present:  # P2
            notes.append(ReviewNote("High", "P2", f"Pre-fill shows {name} of ${prefill_total:,} from "
                                    f"{', '.join(payers[key])}, but the return has nothing for it. Find the source "
                                    "document or confirm with the client why it is excluded.", prefill_total, "preparer",
                                    "confirm", label_key=key))
            continue
        ours = sum((ctx.draft.amount(k) for k in targets), ZERO)
        if abs(ours - prefill_total) > tolerance:  # P1
            notes.append(ReviewNote("High", "P1", f"{name}: return ${ours:,} vs pre-fill ${prefill_total:,} "
                                    f"(difference ${ours - prefill_total:,}). Payers on pre-fill: "
                                    f"{', '.join(payers[key])}.", abs(ours - prefill_total), "preparer", "confirm",
                                    label_key=key))

    if not any(d.doc_type == "PREFILL" for d in ctx.documents):  # P3
        notes.append(ReviewNote("Medium", "P3", "No ATO pre-fill report has been ingested, so nothing could be compared "
                                "with ATO data. Download it from Online services for agents and ingest it.", None,
                                "preparer", "confirm"))

    prefill_help = totals.get("help.indicator", ZERO) > 0  # P4
    if prefill_help != ctx.state.help_debt:
        detail = ("Pre-fill shows a study loan (HELP) debt but the client is set up without one"
                  if prefill_help else "The client is set up with a HELP debt but the pre-fill doesn't show one")
        notes.append(ReviewNote("High", "P4", f"{detail}. Confirm with the client and correct help_debt in the client's state.json.",
                                None, "reviewer", "confirm", label_key="help.indicator"))
    return notes
