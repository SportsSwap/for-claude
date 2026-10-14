"""Build a CheckContext from a handful of figures, for check tests."""

from datetime import date, datetime
from decimal import Decimal

from tra.checks import load_checks_cfg
from tra.checks.context import CheckContext
from tra.labels import load_labels
from tra.models import ClientState, Document, Figure, PrefillLine
from tra.return_.prepare import build_draft
from tra.taxcalc.calc_a import calculate_a
from tra.taxcalc.rates import load_rates

LABELS = load_labels()
RATES = load_rates(2026)
D = Decimal


def fig(fid, key, amount, *, doc="D001", confirmed=True, notes="", substantiated=None, description="item"):
    return Figure(fid, key, description, D(str(amount)), None, doc, 1 if doc else None,
                  "parser" if doc else "manual", confirmed, substantiated, notes)


def doc(doc_id, doc_type="INCSTMT"):
    return Document(doc_id, doc_type, "Income", f"X_FY2026_{doc_type}_2026-06-30.pdf", "C:/x", date(2026, 6, 30),
                    True, 1, doc_id * 8, datetime(2026, 7, 1).astimezone(), {}, "parsed", "local")


def pre(key, amount, payer="PAYER", doc_id="D001"):
    return PrefillLine(key, payer, D(str(amount)), doc_id, 1)


def make_ctx(figures=(), documents=None, prefill=(), prior_year=None, state=None, cgt_events=(), **kw):
    figures = list(figures)
    state = state or ClientState("TEST01", 2026)
    draft = build_draft("TEST01", 2026, figures, list(cgt_events), LABELS)
    a = calculate_a(draft, state, RATES)
    documents = [doc("D001")] if documents is None else documents
    return CheckContext(draft=draft, rates=RATES, state=state, calc_a=a, calc_b=a, labels=LABELS, figures=figures,
                        documents=documents, prefill=list(prefill), prior_year=prior_year or {},
                        cfg=load_checks_cfg(), citations={}, cgt_events=list(cgt_events), **kw)


def ids(notes, check_id):
    return [n for n in notes if n.check_id == check_id]
