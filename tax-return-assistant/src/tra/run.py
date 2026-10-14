"""`tra prepare`: confirmed figures → draft return, both calculations, every check, the workpaper."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from . import __version__
from .checks import load_checks_cfg, load_citations, run_all_checks
from .checks.context import CheckContext
from .checks.notes import rank_notes
from .checks.prior_year import load_prior_year
from .dates import fy_label
from .figures import read_cgt, read_figures, read_prefill
from .filing.index import DocumentIndex
from .labels import load_labels
from .models import ReviewNote
from .notes_store import read_notes
from .privacy.audit import AuditLog
from .privacy.guard import atomic_write_text, check_value
from .return_.prepare import build_draft
from .taxcalc.calc_a import calculate_a
from .taxcalc.calc_b import calculate_b
from .taxcalc.rates import RatesError, load_rates
from .taxcalc.result import TaxResult
from .workpaper.build import WorkpaperContext, build_workpaper
from .workspace import Workspace


class PrepareError(Exception):
    pass


@dataclass
class PrepareResult:
    workpaper: Path
    notes: list[ReviewNote]
    calc_a: TaxResult


def next_workpaper_path(ws: Workspace) -> Path:
    n = 1
    while True:
        path = ws.output_dir / f"{ws.client_code}_{fy_label(ws.income_year)}_Workpaper_DRAFT_v{n}.xlsx"
        if not path.exists():
            return path
        n += 1


def prepare_client(ws: Workspace, audit: AuditLog, prepared_by: str) -> PrepareResult:
    state = ws.load_state()
    labels = load_labels()
    try:
        rates = load_rates(ws.income_year)
    except RatesError as exc:
        raise PrepareError(str(exc)) from None
    figures, errors = read_figures(ws.figures_csv, labels)
    events, cgt_errors = read_cgt(ws.cgt_csv)
    problems = [f"figures.csv {e}" for e in errors] + [f"cgt_events.csv {e}" for e in cgt_errors]
    if problems:
        raise PrepareError("Fix these rows, then run prepare again:\n  " + "\n  ".join(problems))

    documents = DocumentIndex(ws.index_csv).load()
    prefill = read_prefill(ws.prefill_json)
    prior = load_prior_year(ws)
    draft = build_draft(ws.client_code, ws.income_year, figures, events, labels, resident=state.resident)
    calc_a = calculate_a(draft, state, rates)
    calc_b = calculate_b(draft, state, rates, labels)
    ctx = CheckContext(draft=draft, rates=rates, state=state, calc_a=calc_a, calc_b=calc_b, labels=labels,
                       figures=figures, documents=documents, prefill=prefill, prior_year=prior,
                       cfg=load_checks_cfg(), citations=load_citations(), cgt_events=events)
    notes = rank_notes(run_all_checks(ctx) + read_notes(ws.ingest_notes_json))

    prefill_totals: dict[str, Decimal] = {}
    for line in prefill:
        prefill_totals[line.label_key] = prefill_totals.get(line.label_key, Decimal("0")) + line.amount
    path = next_workpaper_path(ws)
    build_workpaper(path, WorkpaperContext(
        client_code=ws.client_code, income_year=ws.income_year, state=state, documents=documents,
        figures=[f for f in figures if f.confirmed], draft=draft, rates=rates, calc_a=calc_a, calc_b=calc_b,
        notes=notes, prefill=prefill_totals, prior_year=prior, labels=labels, prepared_by=prepared_by,
        tool_version=__version__, cgt_events=events, citations=ctx.citations))

    last_return = {key: str(line.amount) for key, line in draft.lines.items()}
    check_value(last_return, "last_return.json")
    atomic_write_text(ws.last_return_json, json.dumps(last_return, indent=2), "last_return.json", prechecked=True)
    risks = Counter(n.risk for n in notes)
    audit.record("workpaper_generated", client=ws.client_code, file=path.name,
                 figures=sum(f.confirmed for f in figures), notes_high=risks["High"], notes_medium=risks["Medium"],
                 notes_low=risks["Low"])
    return PrepareResult(path, notes, calc_a)
