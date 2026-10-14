"""Assemble a WorkpaperContext for the demo client through the real pipeline."""

from tra.checks import load_checks_cfg, load_citations, run_all_checks
from tra.checks.context import CheckContext
from tra.demo import build_demo_documents
from tra.figures import read_cgt, read_figures, read_prefill, write_figures, write_header_files
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import CATEGORIES, load_doc_types
from tra.ingest.pipeline import ingest_file
from tra.labels import load_labels
from tra.models import ClientState
from tra.privacy.audit import AuditLog
from tra.return_.prepare import build_draft
from tra.taxcalc.calc_a import calculate_a
from tra.taxcalc.calc_b import calculate_b
from tra.taxcalc.rates import load_rates
from tra.workpaper.build import WorkpaperContext
from tra.workspace import Workspace


def demo_context(tmp_path, ids=None, state=None, mutate=None, cgt_rows=()):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    ws = Workspace(home, "DEMO01", 2026)
    ws.create(list(CATEGORIES))
    state = state or ClientState("DEMO01", 2026)
    ws.save_state(state)
    write_header_files(ws)
    demo = build_demo_documents(tmp_path / "inbox", ids) if ids else build_demo_documents(tmp_path / "inbox")
    audit, store, types = AuditLog(ws.audit_path), LocalStore(home), load_doc_types()
    for path in demo.paths.values():
        ingest_file(path, ws, store, types, audit)
    labels = load_labels()
    figures, errors = read_figures(ws.figures_csv, labels)
    assert errors == []
    for f in figures:
        f.confirmed = f.notes != "prefill"
    if mutate:
        mutate(figures)
    write_figures(ws.figures_csv, figures)
    if cgt_rows:
        with ws.cgt_csv.open("a", encoding="utf-8") as fh:
            fh.writelines(",".join(row) + "\r\n" for row in cgt_rows)
    events, errors = read_cgt(ws.cgt_csv)
    assert errors == []
    rates = load_rates(2026)
    draft = build_draft("DEMO01", 2026, figures, events, labels)
    a, b = calculate_a(draft, state, rates), calculate_b(draft, state, rates, labels)
    docs = DocumentIndex(ws.index_csv).load()
    prefill_lines = read_prefill(ws.prefill_json)
    ctx = CheckContext(draft=draft, rates=rates, state=state, calc_a=a, calc_b=b, labels=labels, figures=figures,
                       documents=docs, prefill=prefill_lines, prior_year={}, cfg=load_checks_cfg(),
                       citations=load_citations(), cgt_events=events)
    notes = run_all_checks(ctx)
    prefill = {}
    for line in prefill_lines:
        prefill[line.label_key] = prefill.get(line.label_key, 0) + line.amount
    return WorkpaperContext(client_code="DEMO01", income_year=2026, state=state, documents=docs,
                            figures=[f for f in figures if f.confirmed], draft=draft, rates=rates, calc_a=a, calc_b=b,
                            notes=notes, prefill=prefill, prior_year={}, labels=labels, prepared_by="tester",
                            tool_version="0.1.0", cgt_events=events, citations=load_citations())
