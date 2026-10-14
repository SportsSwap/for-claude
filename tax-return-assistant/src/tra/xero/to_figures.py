"""Xero reports → filed JSON snapshots and unconfirmed figures.

Figures from Xero go through the same confirm step as everything else.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..dates import fy_bounds
from ..figures import append_figures
from ..filing.index import DocumentIndex
from ..ingest.extractors.xero_csv import load_xero_mapping
from ..ingest.pipeline import file_document
from ..models import Figure, ReviewNote
from ..money import parse_amount
from ..notes_store import append_notes
from ..privacy.guard import check_value

load_mapping = load_xero_mapping


@dataclass
class PullReport:
    doc_ids: dict[str, str]
    figures_added: int
    unknown_sections: list[str]


def pl_to_figures(report: dict, mapping: dict, doc_id: str) -> tuple[list[Figure], list[str]]:
    sections = mapping["pl_sections"]
    figures, unknown = [], []
    for section in report["Reports"][0].get("Rows", []):
        if section.get("RowType") != "Section":
            continue
        rows = [r for r in section.get("Rows", []) if r.get("RowType") == "Row"]
        title = section.get("Title", "")
        if not rows:
            continue
        if title not in sections:
            unknown.append(title)
            continue
        for r in rows:
            cells = r.get("Cells", [])
            figures.append(Figure(figure_id="", label_key=sections[title], description=str(cells[0].get("Value", "")),
                                  amount=parse_amount(str(cells[-1].get("Value", "0"))), date=None, doc_id=doc_id,
                                  page=1, method="xero", confirmed=False, substantiated=None,
                                  notes="xero profit and loss"))
    return figures, unknown


SNAPSHOTS = [  # (doc type, file stem, endpoint name)
    ("XEROPL", "xero_profit_and_loss", "ProfitAndLoss"),
    ("XEROBS", "xero_balance_sheet", "BalanceSheet"),
    ("XEROBANK", "xero_bank_transactions", "BankTransactions"),
    ("XEROCOA", "xero_chart_of_accounts", "Accounts"),
]


def pull_to_workspace(ws, store, audit, client, tenant_id: str) -> PullReport:
    start, end = fy_bounds(ws.income_year)
    data = {
        "XEROPL": client.profit_and_loss(start, end),
        "XEROBS": client.balance_sheet(end),
        "XEROBANK": {"BankTransactions": client.bank_transactions(start, end)},
        "XEROCOA": {"Accounts": client.accounts()},
    }
    doc_ids: dict[str, str] = {}
    notes: list[ReviewNote] = []
    unchanged: set[str] = set()
    index = DocumentIndex(ws.index_csv)
    with tempfile.TemporaryDirectory() as tmp:
        for doc_type, stem, _endpoint in SNAPSHOTS:
            check_value(data[doc_type], f"{stem}.json")
            path = Path(tmp) / f"{stem}.json"
            # Stable JSON, so the same Xero data always has the same hash and is not filed twice.
            path.write_text(json.dumps(data[doc_type], indent=2, sort_keys=True, default=str), encoding="utf-8")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            existing = index.find_by_sha(sha)
            if existing:
                doc_ids[doc_type] = existing.doc_id
                unchanged.add(doc_type)
                continue
            doc, filing_notes = file_document(
                path, ws, store, doc_type=doc_type, category="Business", doc_date=end, sha256=sha, pages=1,
                redaction_counts={}, parse_status="parsed", audit=audit)
            doc_ids[doc_type] = doc.doc_id
            notes += filing_notes
    figures, unknown = pl_to_figures(data["XEROPL"], load_mapping(), doc_ids["XEROPL"])
    if "XEROPL" in unchanged:
        figures, unknown = [], []  # already pulled: the profit and loss figures are in figures.csv
    added = append_figures(ws.figures_csv, figures) if figures else []
    if unknown:
        notes.append(ReviewNote("Medium", "I5", "Xero profit and loss sections not mapped to the return: "
                                + ", ".join(unknown) + ". Add them to config/xero_mapping.yaml or enter them manually.",
                                None, "preparer", "confirm", doc_ids=(doc_ids["XEROPL"],)))
    append_notes(ws.ingest_notes_json, notes)
    state = ws.load_state()
    state.xero_tenant_id = tenant_id
    ws.save_state(state)
    audit.record("xero_pull", client=ws.client_code, endpoints=[e for _, _, e in SNAPSHOTS],
                 doc_ids=list(doc_ids.values()), figures=len(added))
    return PullReport(doc_ids, len(added), unknown)
