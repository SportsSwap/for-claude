"""R1-R4: every figure traces to a filed document and nothing is counted twice."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..models import ReviewNote
from ..money import ZERO
from . import label_name
from .context import CheckContext


def check_reconcile(ctx: CheckContext) -> list[ReviewNote]:
    notes: list[ReviewNote] = []
    known_docs = {d.doc_id for d in ctx.documents}
    confirmed = [f for f in ctx.figures if f.confirmed]

    for f in confirmed:  # R1
        where = label_name(ctx.labels, f.label_key)
        if not f.doc_id:
            msg = f"{f.figure_id} ({where}, ${f.amount:,}) has no source document. Attach the source or confirm it with the client."
        elif f.doc_id not in known_docs:
            msg = f"{f.figure_id} ({where}) cites {f.doc_id}, which is not in the document index."
        else:
            continue
        notes.append(ReviewNote("High", "R1", msg, abs(f.amount), "preparer", "confirm", label_key=f.label_key,
                                figure_ids=(f.figure_id,)))

    sums: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for f in confirmed:
        sums[f.label_key] += f.amount
    for key, line in ctx.draft.lines.items():  # R2
        if ctx.labels[key].computed:
            continue
        if line.amount != sums.get(key, ZERO):
            notes.append(ReviewNote("High", "R2", f"{label_name(ctx.labels, key)}: return shows ${line.amount:,} but its "
                                    f"figures add up to ${sums.get(key, ZERO):,}.", abs(line.amount - sums.get(key, ZERO)),
                                    "reviewer", "confirm", label_key=key, figure_ids=line.figure_ids))

    pending = [f for f in ctx.figures if not f.confirmed and f.notes != "prefill"]  # R3
    if pending:
        notes.append(ReviewNote("Medium", "R3", f"{len(pending)} figure(s) not confirmed and left out of the return: "
                                + ", ".join(f.figure_id for f in pending), sum((f.amount for f in pending), ZERO),
                                "preparer", "confirm", figure_ids=tuple(f.figure_id for f in pending)))

    tolerance = Decimal(str(ctx.cfg.get("double_count_tolerance", 1)))  # R4
    from_prefill = [f for f in confirmed if f.notes == "prefill"]
    others = [f for f in confirmed if f.notes != "prefill"]
    for p in from_prefill:
        for o in others:
            if o.label_key == p.label_key and abs(o.amount - p.amount) <= tolerance:
                notes.append(ReviewNote(
                    "High", "R4", f"{label_name(ctx.labels, p.label_key)} may be counted twice: {p.figure_id} (pre-fill) "
                    f"and {o.figure_id} (source document) are both confirmed for ${p.amount:,}. Confirm only one.",
                    p.amount, "preparer", "confirm", label_key=p.label_key, figure_ids=(p.figure_id, o.figure_id)))
                break

    doc_types = {d.doc_id: d.doc_type for d in ctx.documents}  # R5
    seen: dict[tuple, object] = {}
    for f in others:
        key = (f.label_key, f.amount, doc_types.get(f.doc_id))
        first = seen.get(key)
        if first is None:
            seen[key] = f
        elif first.doc_id != f.doc_id and key[2] is not None:
            notes.append(ReviewNote(
                "High", "R5", f"{label_name(ctx.labels, f.label_key)}: {first.doc_id} and {f.doc_id} are both {key[2]} "
                f"documents showing ${f.amount:,}. Check they aren't the same document sent twice.", f.amount,
                "preparer", "confirm", label_key=f.label_key, figure_ids=(first.figure_id, f.figure_id),
                doc_ids=(first.doc_id, f.doc_id)))
    return notes
