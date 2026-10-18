"""Prepare a client; the result (last_prepare.json) feeds the Prepare and Review pages and the client list."""

from __future__ import annotations

import re
from pathlib import Path

from ...dates import fy_label
from ...prepare_summary import PrepareSummary, load_summary
from ...privacy.audit import AuditLog
from ...run import prepare_client
from ...workspace import Workspace

COMPONENTS = [
    ("total_income", "Total income"), ("deductions", "Total deductions"),
    ("taxable_income", "Taxable income (cents dropped)"), ("basic_tax", "Tax on taxable income"),
    ("lito", "Low income tax offset"), ("sapto", "Seniors and pensioners tax offset"),
    ("offsets_used", "Non-refundable offsets used (limited to tax)"), ("medicare_levy", "Medicare levy"),
    ("mls_income", "Income for MLS purposes"), ("mls", "Medicare levy surcharge"),
    ("repayment_income", "Repayment income (HELP)"), ("help", "HELP compulsory repayment"),
    ("phi_adjustment", "Private health insurance rebate adjustment"),
    ("franking_credits", "Less: franking credits (refundable)"), ("payg_withheld", "Less: PAYG withheld"),
    ("tfn_withheld", "Less: TFN amounts withheld"), ("net_result", "Estimated payable / (refund)"),
]


def workpapers(ws: Workspace) -> list[Path]:
    pattern = re.compile(rf"^{re.escape(ws.client_code)}_{fy_label(ws.income_year)}_Workpaper_DRAFT_v(\d+)\.xlsx$")
    found = [(int(m.group(1)), p) for p in ws.output_dir.glob("*.xlsx") if (m := pattern.match(p.name))]
    return [p for _n, p in sorted(found, reverse=True)]


def run_prepare(ws: Workspace, audit: AuditLog, prepared_by: str) -> PrepareSummary:
    """prepare_client writes last_prepare.json itself (so `tra prepare` shows here too); read it back."""
    prepare_client(ws, audit, prepared_by)
    return load_summary(ws)


__all__ = ["COMPONENTS", "PrepareSummary", "load_summary", "run_prepare", "workpapers"]
