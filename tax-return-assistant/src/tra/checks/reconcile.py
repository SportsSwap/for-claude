"""R1-R7: every figure traces to a filed document of this income year and nothing is counted twice."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from ..dates import fy_bounds, fy_label
from ..models import ReviewNote
from ..money import ZERO, format_dollars
from . import label_name
from .context import CheckContext


def check_reconcile(ctx: CheckContext) -> list[ReviewNote]:
    notes: list[ReviewNote] = []
    known_docs = {d.doc_id for d in ctx.documents}
    confirmed = [f for f in ctx.figures if f.confirmed]

    for f in confirmed:  # R1
        where = label_name(ctx.labels, f.label_key)
        if not f.doc_id:
            msg = (f"{f.figure_id} ({where}, {format_dollars(f.amount)}) has no source document. Attach the source or "
                   "confirm it with the client.")
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
            notes.append(ReviewNote("High", "R2", f"{label_name(ctx.labels, key)}: return shows "
                                    f"{format_dollars(line.amount)} but its figures add up to "
                                    f"{format_dollars(sums.get(key, ZERO))}.", abs(line.amount - sums.get(key, ZERO)),
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
                    f"and {o.figure_id} (source document) are both confirmed for {format_dollars(p.amount)}. "
                    "Confirm only one.",
                    p.amount, "preparer", "confirm", label_key=p.label_key, figure_ids=(p.figure_id, o.figure_id)))
                break

    from_ai = [f for f in confirmed if f.method == "ai"]  # R6
    if from_ai:
        notes.append(ReviewNote("Medium", "R6", f"{len(from_ai)} figure(s) were read by the AI reader. Check each "
                                "one against its source.", sum((abs(f.amount) for f in from_ai), ZERO), "reviewer",
                                "confirm", figure_ids=tuple(f.figure_id for f in from_ai)))

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
                f"documents showing {format_dollars(f.amount)}. Check they aren't the same document sent twice.",
                f.amount,
                "preparer", "confirm", label_key=f.label_key, figure_ids=(first.figure_id, f.figure_id),
                doc_ids=(first.doc_id, f.doc_id)))

    notes += _outside_year(ctx, confirmed)  # R7
    return notes


def _dmy(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _outside_year(ctx: CheckContext, confirmed) -> list[ReviewNote]:
    """R7: a document used in the return but dated outside the income year.

    30 June is inside the year, so period-end statements pass. Annual statements
    (config: annual_statement_types) issued up to annual_statement_days after 30 June
    pass. The pre-fill report is issued after the year ends, so any later date passes;
    one dated during the year, before 30 June, is probably an earlier year's report.
    Undated documents are skipped: their filename uses the ingest date and I2 says so.
    """
    year = ctx.draft.income_year
    start, end = fy_bounds(year)
    grace_end = end + timedelta(days=int(ctx.cfg.get("annual_statement_days", 120)))
    annual = set(ctx.cfg.get("annual_statement_types", ()))
    notes = []
    for doc in ctx.documents:
        used = [f for f in confirmed if f.doc_id == doc.doc_id]
        prefill = doc.doc_type == "PREFILL"
        compared = prefill and any(p.doc_id == doc.doc_id for p in ctx.prefill)
        if not doc.date_detected or not (used or compared):
            continue
        when = doc.doc_date
        if prefill and when >= end:
            continue
        if not prefill and (start <= when <= end or (doc.doc_type in annual and end < when <= grace_end)):
            continue
        if prefill and when >= start:
            message = (f"{doc.doc_id} (PREFILL) is dated {_dmy(when)}. The ATO pre-fill report for "
                       f"{fy_label(year)} is normally issued after {_dmy(end)}, so this may be an earlier year's "
                       "report, or one downloaded before the year's data was in. Confirm which income year it "
                       "covers before relying on the pre-fill comparison; if it is the wrong one, ingest this "
                       "year's.")
        else:
            fix = "ingest this year's pre-fill instead" if prefill else "unconfirm its figures"
            message = (f"{doc.doc_id} ({doc.doc_type}) is dated {_dmy(when)}, outside {fy_label(year)} "
                       f"({_dmy(start)} to {_dmy(end)}), but it is used in this return. Confirm which income year "
                       "it belongs to: the date alone doesn't settle it, so check the document. If it is another "
                       f"year's, {fix}.")
        notes.append(ReviewNote("Medium", "R7", message,
                                sum((abs(f.amount) for f in used), ZERO) if used else None, "preparer", "confirm",
                                figure_ids=tuple(f.figure_id for f in used), doc_ids=(doc.doc_id,)))
    return notes
