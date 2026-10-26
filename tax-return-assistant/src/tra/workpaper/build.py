"""Build the Excel workpaper (spec §9), laid out like the firm's individual tax workpapers.

B01 Summary is the hub: every return item in ATO order with a "Go to" link to its tab. Each item tab
(01 Salaries and Wages, 10 Interest Received, D05 Other Work Deductions, ...) appears only when the
client has figures for it, has the same header block, shows ATO pre-fill and client documents
separately, and ends each item with "Transferred to: Item 10 L", a link back to its Summary line.

Figures and rates are the only typed-in numbers; every total, the Summary and the whole tax
calculation are live formulas, so the reviewer can follow the working in Excel. Calculation B's
results sit beside the formulas as a check. Layout and styling come from layout.py.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.worksheet import Worksheet

from ..checks import label_name
from ..dates import days_in_fy, fy_bounds, fy_label
from ..labels import LabelDef, return_key
from ..models import ClientState, Document, Figure, ReviewNote
from ..privacy.guard import FileLockedError, check_workbook
from ..return_.cgt import discount_eligible
from ..return_.prepare import DraftReturn
from ..review_store import note_key
from ..taxcalc.calc_a import DEDUCTION_KEYS
from ..taxcalc.rates import Rates
from ..taxcalc.result import TaxResult
from . import layout as L

BANNER = "DRAFT – NOT FOR LODGMENT"
SUMMARY_TAB = "B01 Summary"
CGT_TAB = "M03 Capital Gains"
TAXCALC_TAB = "Tax Calc"
FIRST_ROW = 5  # Sources and Review Notes: data starts below title, subtitle, blank and header rows
BODY_ROW = 11  # item tabs and the Summary: the body starts below the header block
TAXCALC_HEAD = 8

TAXCALC_ROWS = [
    ("total_income", "Total income"),
    ("deductions", "Total deductions"),
    ("taxable_income", "Taxable income (cents dropped)"),
    ("basic_tax", "Tax on taxable income"),
    ("lito", "Low income tax offset"),
    ("sapto", "Seniors and pensioners tax offset"),
    ("offsets_used", "Non-refundable offsets used (limited to tax)"),
    ("medicare_levy", "Medicare levy"),
    ("mls_income", "Income for MLS purposes"),
    ("mls", "Medicare levy surcharge"),
    ("repayment_income", "Repayment income (HELP)"),
    ("help", "HELP compulsory repayment"),
    ("phi_adjustment", "Private health insurance rebate adjustment"),
    ("franking_credits", "Less: franking credits (refundable)"),
    ("payg_withheld", "Less: PAYG withheld"),
    ("tfn_withheld", "Less: TFN amounts withheld"),
    ("net_result", "Estimated payable / (refund)"),
]

# What each item tab is for: the blue "i" line under its header.
PURPOSE = {
    "01 Salaries and Wages": "record salary and wages, allowances and the income test amounts from income statements",
    "10 Interest Received": "record details of interest received",
    "11 Dividends Received": "record dividends received and their franking credits",
    "15 Business Professional": "record business income and expenses (complete P8 in Xero Tax)",
    "24 Other Income": "record other income",
    "C15 Losses": "record tax losses of earlier income years claimed this year",
    CGT_TAB: "record capital gains events and work out the net capital gain",
    "M25 Rental Property": "record rental income and expenses",
    "D01 MV Expenses": "record work-related car expenses",
    "D02 Travel": "record work-related travel expenses",
    "D03 Clothing": "record work-related clothing, laundry and dry-cleaning expenses",
    "D04 Self Education": "record work-related self-education expenses",
    "D05 Other Work Deductions": "record other work-related deductions claimed",
    "D06 Low Value Pool": "record the low-value pool deduction",
    "D07 Int Div Deductions": "record interest and dividend deductions",
    "D09 Donations": "record gifts and donations claimed",
    "D10 Cost Managing Tax": "record the cost of managing tax affairs",
    "D15 D11 - D15 Deductions": "record personal superannuation contributions and other deductions (D11 to D15)",
    "PHI Private Health": "record private health insurance premiums and the rebate received",
}


@dataclass
class WorkpaperContext:
    client_code: str
    income_year: int
    state: ClientState
    documents: list[Document]
    figures: list[Figure]  # confirmed only
    draft: DraftReturn
    rates: Rates
    calc_a: TaxResult
    calc_b: TaxResult
    notes: list[ReviewNote]
    prefill: dict[str, Decimal]
    prior_year: dict[str, Decimal]
    labels: dict[str, LabelDef]
    prepared_by: str
    tool_version: str
    cgt_events: list = field(default_factory=list)
    citations: dict = field(default_factory=dict)
    responses: dict = field(default_factory=dict)  # note_key -> the preparer's response (review.json)
    doc_summaries: dict = field(default_factory=dict)  # doc_id -> automatic summary (doc_summary.py)
    doc_descriptions: dict = field(default_factory=dict)  # doc_id -> the preparer's description


@dataclass
class WorkpaperMap:
    total_cells: list[str] = field(default_factory=list)
    summary_cells: dict[str, str] = field(default_factory=dict)
    taxcalc_cells: dict[str, str] = field(default_factory=dict)


def _q(sheet: str) -> str:
    return f"'{sheet}'"


def _link(location: str) -> str:
    if location.startswith(("http://", "https://")):
        return location
    path = Path(location)
    return path.as_uri() if path.is_absolute() else location


def _jump(cell, sheet: str, target: str = "A1") -> None:
    """An internal link to another tab of this workbook."""
    cell.hyperlink = Hyperlink(ref="", location=f"{_q(sheet)}!{target}")


def _back_link(ws: Worksheet, coordinate: str) -> None:
    cell = ws[coordinate]
    cell.value = f"↩ {SUMMARY_TAB}"
    _jump(cell, SUMMARY_TAB)
    L.style_link_box(cell)


def _title(ws: Worksheet, title: str, subtitle: str, back: str | None = None) -> None:
    ws["A1"] = title
    L.style_title(ws["A1"])
    ws["A2"] = subtitle
    L.style_subtitle(ws["A2"])
    if back:
        _back_link(ws, back)


def _item_ref(d: LabelDef) -> str:
    """'Item 10 L', 'Item D5 E', 'Item 1' (no letter when the label isn't a single code)."""
    code = f" {d.label}" if d.label and len(d.label) <= 2 else ""
    return f"{d.item}{code}" if d.item in ("PHI", "HELP") else f"Item {d.item}{code}"


def _sheet_header(ws: Worksheet, heading: str, workpaper: str, ctx: WorkpaperContext, *,
                  right: tuple[str, str, str], back: str | None) -> None:
    """The firm's header block: client and year on the left, who prepared and reviewed it on the right."""
    ws["B2"] = heading
    L.style_title(ws["B2"])
    if back:
        _back_link(ws, back)
    _, end = fy_bounds(ctx.income_year)
    label, value, when = right
    for row, (left_label, left_value) in enumerate(
            [("Client code", ctx.client_code), ("Year ended", end), ("Status", "Draft – not for lodgment")], start=4):
        L.style_label(ws.cell(row=row, column=2, value=left_label))
        cell = ws[f"D{row}"]
        cell.value = left_value
        if isinstance(left_value, date):
            cell.number_format = L.LONG_DATE
            L.align_left(cell)
        if left_label == "Status":
            L.style_draft(cell)
    for row, (right_label, right_value, right_date) in enumerate(
            [("Workpaper", workpaper, None), ("Prepared by", ctx.prepared_by, date.today()),
             ("Reviewed by", "", None)], start=4):
        L.style_label(ws[f"{label}{row}"])
        ws[f"{label}{row}"] = right_label
        ws[f"{value}{row}"] = right_value
        if right_date:
            ws[f"{when}{row}"] = right_date
            ws[f"{when}{row}"].number_format = L.DATE
    for coordinate in (f"{value}6", f"{when}6"):  # the reviewer fills these in
        L.style_input(ws[coordinate], "@")


def _purpose(ws: Worksheet, text: str, note: str) -> None:
    ws["B8"] = f"i  The purpose of this worksheet is to {text}."
    L.style_purpose(ws["B8"])
    ws["B9"] = note
    L.style_subtitle(ws["B9"])


# --- item tabs ------------------------------------------------------------------------------

# Columns B to K: ref, date, detail, source, page, method, substantiated, amount, key (hidden), comments.
ITEM_HEADERS = ["Ref", "Date", "Detail", "Source document", "Page", "Method", "Substantiated", "Amount", "key",
                "Comments"]
FIRST_COL, LAST_COL = 2, 11
AMOUNT, KEY = "I", "J"
ITEM_NOTE = ("Confirmed figures only. Each amount links to its filed source document and page. "
             "Blue amounts are typed in; dark grey amounts are formulas.")


def _write_header(ws: Worksheet, row: int) -> None:
    for col, header in enumerate(ITEM_HEADERS, start=FIRST_COL):
        ws.cell(row=row, column=col, value=header)
    L.style_header_row(ws, row, len(ITEM_HEADERS), first=FIRST_COL)


def _write_rows(ws: Worksheet, figures: list[Figure], docs: dict[str, Document], row: int) -> int:
    for f in figures:
        ws.cell(row=row, column=2, value=f.figure_id)
        if f.date:
            ws.cell(row=row, column=3, value=f.date).number_format = L.DATE
        ws.cell(row=row, column=4, value=f.description)
        doc = docs.get(f.doc_id or "")
        source = ws.cell(row=row, column=5)
        if doc:
            source.value = doc.filed_name
            source.hyperlink = _link(doc.filed_location)
            L.style_link(source)
        else:
            source.value = "NO SOURCE" if not f.doc_id else f"{f.doc_id} (not in index)"
            L.style_warning(source)
        ws.cell(row=row, column=6, value=f.page if f.page is not None else ("" if doc else "–"))
        ws.cell(row=row, column=7, value=f.method)
        ws.cell(row=row, column=8, value="" if f.substantiated is None else ("Y" if f.substantiated else "N"))
        L.style_input(ws.cell(row=row, column=9, value=f.amount))
        ws.cell(row=row, column=10, value=f.label_key)
        ws.cell(row=row, column=11, value="" if f.notes == "prefill" else f.notes)  # its section says so
        L.rule_rows(ws, row, row, FIRST_COL, LAST_COL)
        row += 1
    return row


SUNDRY_HEADING = "Sundry rental expenses"


def _figure_groups(figures: list[Figure], d: LabelDef, labels: dict[str, LabelDef]) -> list[tuple[str, list[Figure], str]]:
    """ATO pre-fill first, then the client's own documents, as the firm's workpapers show them. A label with a
    breakdown (Item 21 U's rental categories) shows each category with its own subtotal instead, in schedule
    order, with whatever is left on the label itself as sundry last."""
    prefill = [f for f in figures if f.notes == "prefill"]
    own = [f for f in figures if f.notes != "prefill"]
    groups = [("ATO pre-fill", prefill, "Subtotal – ATO pre-fill")]
    if any(f.label_key != d.key for f in own):
        for key in [k for k in labels if labels[k].part_of == d.key] + [d.key]:
            items = [f for f in own if f.label_key == key]
            heading = SUNDRY_HEADING if key == d.key else labels[key].description
            groups.append((heading, items, f"Subtotal – {heading}"))
    else:
        groups.append(("Client documents and adjustments", own, "Subtotal – client documents"))
    return [g for g in groups if g[1]]


RENTAL_DEDUCTION_KEYS = ("rent.interest", "rent.capital_works", "rent.other")


def _item_section(ws: Worksheet, row: int, d: LabelDef, figures: list[Figure], docs: dict[str, Document],
                  transfers: list, labels: dict[str, LabelDef]) -> tuple[int, str]:
    """One return label: a section bar, its figures (pre-fill and client documents), the total and the
    'Transferred to' link. Labels are never added together. Returns the next free row and the total cell."""
    ws.cell(row=row, column=2, value=f"{_item_ref(d)}  {d.description}")
    L.style_section(ws, row, FIRST_COL, LAST_COL)
    _write_header(ws, row + 1)
    row += 2
    groups = _figure_groups(figures, d, labels)
    subtotals, start = [], row
    for heading, items, subtotal_label in groups:
        L.style_subheading(ws.cell(row=row, column=4, value=heading))
        row += 1
        start = row
        row = _write_rows(ws, items, docs, row)
        if len(groups) > 1:
            ws.cell(row=row, column=4, value=subtotal_label)
            L.style_label(ws.cell(row=row, column=4))
            L.style_subtotal(ws.cell(row=row, column=9, value=f"=SUM({AMOUNT}{start}:{AMOUNT}{row - 1})"))
            subtotals.append(f"{AMOUNT}{row}")
            row += 1
    ws.cell(row=row, column=4, value=f"Total {d.description} ({_item_ref(d)})")
    L.style_label(ws.cell(row=row, column=4))
    formula = "=" + "+".join(subtotals) if subtotals else f"=SUM({AMOUNT}{start}:{AMOUNT}{row - 1})"
    L.style_total(ws.cell(row=row, column=9, value=formula))
    total = f"{AMOUNT}{row}"
    ws.cell(row=row + 1, column=8, value="Transferred to:")
    L.style_label(ws.cell(row=row + 1, column=8))
    link = ws.cell(row=row + 1, column=9, value=_item_ref(d))
    L.style_link_box(link)
    transfers.append((link, d.key))
    return row + 4, total


def _item_tab(ws: Worksheet, tab: str, figures: list[Figure], ctx: WorkpaperContext,
              docs: dict[str, Document], wp: WorkpaperMap, transfers: list) -> None:
    _sheet_header(ws, tab.split(" ", 1)[1], tab, ctx, right=("H", "I", "K"), back="K2")
    _purpose(ws, PURPOSE.get(tab, "record the amounts for this part of the return"), ITEM_NOTE)
    row = BODY_ROW
    totals: dict[str, str] = {}
    # One section per return label; a rental category's figures sit in Item 21 U's section.
    of = {f.figure_id: return_key(ctx.labels, f.label_key) for f in figures}
    for key in [k for k in ctx.labels if any(of[f.figure_id] == k for f in figures)]:
        row, totals[key] = _item_section(ws, row, ctx.labels[key], [f for f in figures if of[f.figure_id] == key],
                                         docs, transfers, ctx.labels)
        wp.total_cells.append(f"{_q(tab)}!{totals[key]}")
    if "rent.gross" in totals or any(k in totals for k in RENTAL_DEDUCTION_KEYS):
        less = "".join(f"-{totals[k]}" for k in RENTAL_DEDUCTION_KEYS if k in totals)
        ws.cell(row=row, column=4, value="Net rent")
        L.style_label(ws.cell(row=row, column=4))
        L.style_total(ws.cell(row=row, column=9, value=f"={totals.get('rent.gross', '0')}{less}"))
        wp.total_cells.append(f"{_q(tab)}!{AMOUNT}{row}")
    ws.column_dimensions[KEY].hidden = True
    L.set_widths(ws, L.ITEM_WIDTHS)
    L.setup_print(ws)


def _cgt_tab(ws: Worksheet, figures: list[Figure], ctx: WorkpaperContext, docs: dict[str, Document],
             wp: WorkpaperMap, transfers: list) -> dict[str, str]:
    """Prior-loss figures, the CGT event schedule and the s102-5 method statement, as formulas."""
    _sheet_header(ws, "Capital Gains", CGT_TAB, ctx, right=("H", "I", "K"), back="K2")
    _purpose(ws, PURPOSE[CGT_TAB],
             "Net capital gain per the ITAA 1997 s102-5 method statement: losses reduce non-discount gains first.")
    ws.cell(row=BODY_ROW, column=2, value="Capital losses brought forward")
    L.style_section(ws, BODY_ROW, FIRST_COL, LAST_COL)
    _write_header(ws, BODY_ROW + 1)
    first = BODY_ROW + 2
    end = _write_rows(ws, figures, docs, first)
    ws.cell(row=end, column=4, value="Capital losses brought forward")
    L.style_label(ws.cell(row=end, column=4))
    # No prior-loss figures: nothing to sum (a SUM over the empty range would include this cell).
    prior_losses = ws.cell(row=end, column=9, value=f"=SUM(I{first}:I{end - 1})" if end > first else "=0")
    L.style_total(prior_losses)
    wp.total_cells.append(f"{_q(CGT_TAB)}!I{end}")

    head = end + 3
    ws.cell(row=head - 1, column=2, value="CGT events")
    L.style_section(ws, head - 1, FIRST_COL, 12)
    # B event, C acquired, D asset, E source, F page, G disposed, H proceeds, I cost base, K gain, L discount.
    headers = {2: "Event", 3: "Acquired", 4: "Asset", 5: "Source document", 6: "Page", 7: "Disposed",
               8: "Proceeds", 9: "Cost base", 11: "Gain / (loss)", 12: "Discount eligible"}
    for col, h in headers.items():
        ws.cell(row=head, column=col, value=h)
    L.style_header_row(ws, head, 11, first=FIRST_COL)
    row = head + 1
    for e in [e for e in ctx.cgt_events if e.confirmed]:
        ws.cell(row=row, column=2, value=e.event_id)
        ws.cell(row=row, column=3, value=e.acquired).number_format = L.DATE
        ws.cell(row=row, column=4, value=e.asset)
        doc = docs.get(e.doc_id or "")
        ws.cell(row=row, column=5, value=doc.filed_name if doc else "NO SOURCE")
        ws.cell(row=row, column=6, value=e.page)
        ws.cell(row=row, column=7, value=e.disposed).number_format = L.DATE
        L.style_input(ws.cell(row=row, column=8, value=e.proceeds))
        L.style_input(ws.cell(row=row, column=9, value=e.cost_base))
        L.style_formula(ws.cell(row=row, column=11, value=f"=H{row}-I{row}"))
        ws.cell(row=row, column=12, value="Y" if discount_eligible(e.acquired, e.disposed) else "N")
        L.rule_rows(ws, row, row, FIRST_COL, 12)
        row += 1
    first_event, last_event = head + 1, max(head + 1, row - 1)
    g, h = f"K{first_event}:K{last_event}", f"L{first_event}:L{last_event}"
    half = "0.5" if ctx.state.resident else "1"
    calc = [
        ("total", "Total current year capital gains (18 H)", f'=SUMIF({g},">0")'),
        ("nd", "Gains not eligible for the discount", f'=SUMIFS({g},{g},">0",{h},"N")'),
        ("dg", "Gains eligible for the discount", f'=SUMIFS({g},{g},">0",{h},"Y")'),
        ("losses", "Capital losses: this year plus brought forward", f'=-SUMIF({g},"<0")+I{end}'),
        ("nd_after", "Non-discount gains after losses", "=MAX(0,{nd}-{losses})"),
        ("dg_after", "Discount gains after remaining losses", "=MAX(0,{dg}-MAX(0,{losses}-{nd}))"),
        ("net", f"Net capital gain (18 A){' — 50% discount applied' if ctx.state.resident else ''}",
         "=ROUND({nd_after}+{dg_after}*" + half + ",2)"),
    ]
    refs: dict[str, str] = {}
    row += 2
    ws.cell(row=row - 1, column=2, value="Method statement (ITAA 1997 s102-5)")
    L.style_section(ws, row - 1, FIRST_COL, LAST_COL)
    for key, label, formula in calc:
        refs[key] = f"I{row}"
        ws.cell(row=row, column=4, value=label)
        cell = ws.cell(row=row, column=9, value=formula.format(**refs))
        (L.style_total if key in ("total", "net") else L.style_formula)(cell)
        wp.total_cells.append(f"{_q(CGT_TAB)}!I{row}")
        if key in ("total", "net"):
            link = ws.cell(row=row, column=11, value=_item_ref(ctx.labels[f"cgt.{'total_gains' if key == 'total' else 'net_gain'}"]))
            L.style_link_box(link)
            transfers.append((link, f"cgt.{'total_gains' if key == 'total' else 'net_gain'}"))
        row += 1
    ws.column_dimensions[KEY].hidden = True
    L.set_widths(ws, {**L.ITEM_WIDTHS, "G": 11, "K": 14, "L": 11})
    L.setup_print(ws)
    return {"cgt.total_gains": f"{_q(CGT_TAB)}!$I${refs['total'][1:]}",
            "cgt.net_gain": f"{_q(CGT_TAB)}!$I${refs['net'][1:]}"}


# --- B01 Summary (the hub) -----------------------------------------------------------------

# Columns B to M.
SUMMARY_HEADERS = ["ITR item", "Code", "Item", "Go to", "Amount (per schedule)", "Tax credits", "ATO pre-fill",
                   "Difference", "Prior year", "Movement", "Review notes", "key"]
SUMMARY_LAST = 13
SUMMARY_SECTIONS = [
    ("Income", {"income", "franking", "withheld", "rental_income", "rental_deduction", "business_income",
                "business_deduction", "cgt", "info"}, "total_income", "Total income"),
    ("Deductions", {"deduction"}, "deductions", "Total deductions"),
    ("Losses", {"loss"}, None, None),
    ("Income tests and private health insurance", {"it", "phi"}, None, None),
]
TAX_SUMMARY = [("total_income", "Total income"), ("deductions", "Total deductions"),
               ("taxable_income", "Taxable income"), ("basic_tax", "Tax on taxable income"),
               ("net_result", "Estimated amount payable / (refundable)")]


def _taxcalc_ref(name: str) -> str:
    row = TAXCALC_HEAD + 1 + [n for n, _ in TAXCALC_ROWS].index(name)
    return f"{_q(TAXCALC_TAB)}!$B${row}"


def _summary(ws: Worksheet, ctx: WorkpaperContext, tab_of: dict[str, str], cgt_refs: dict[str, str],
             wp: WorkpaperMap) -> tuple[dict[str, str], dict[str, str]]:
    """Returns where each label's amount is (for the tax calculation) and where to land a 'Transferred to' link."""
    _sheet_header(ws, "Summary", SUMMARY_TAB, ctx, right=("I", "J", "L"), back=None)
    _purpose(ws, "summarise the amounts for the income tax return. Totals come from the supporting "
                 "worksheets; use Go to to see the working",
             "Blue = typed in (pre-fill, prior year). Difference compares this year with the ATO pre-fill. "
             "The tax figures are worked out on the Tax Calc tab.")
    row = BODY_ROW
    ws.cell(row=row, column=2, value="Tax Summary")
    L.style_section(ws, row, 2, SUMMARY_LAST - 1)
    row += 1
    for name, text in TAX_SUMMARY:
        ws.cell(row=row, column=4, value=text)
        cell = ws.cell(row=row, column=6, value=f"={_taxcalc_ref(name)}")
        (L.style_total if name == "net_result" else L.style_formula)(cell)
        L.rule_rows(ws, row, row, 2, 7)
        row += 1
    row += 1

    per_label = defaultdict(Counter)
    for n in ctx.notes:
        if n.label_key:
            per_label[n.label_key][n.risk] += 1
    refs: dict[str, str] = {}
    landing: dict[str, str] = {}
    for title, roles, total_name, total_text in SUMMARY_SECTIONS:
        keys = [k for k, d in ctx.labels.items() if d.role in roles and not (d.role == "info" and not d.computed)
                and (k in tab_of or k in cgt_refs or k in ctx.prefill or k in ctx.prior_year)]
        if not keys:
            continue
        ws.cell(row=row, column=2, value=title)
        L.style_section(ws, row, 2, SUMMARY_LAST - 1)
        for col, h in enumerate(SUMMARY_HEADERS, start=2):
            ws.cell(row=row + 1, column=col, value=h)
        L.style_header_row(ws, row + 1, len(SUMMARY_HEADERS) - 1, first=2)
        row += 2
        for key in keys:
            d = ctx.labels[key]
            col = 7 if d.role == "withheld" else 6
            ws.cell(row=row, column=2, value=f"Item {d.item}" if d.item not in ("PHI", "HELP") else d.item)
            ws.cell(row=row, column=3, value=d.label if len(d.label) <= 2 else "")
            ws.cell(row=row, column=4, value=d.description)
            tab = CGT_TAB if key in cgt_refs else tab_of.get(key)
            if tab:
                go = ws.cell(row=row, column=5, value="Go to")
                _jump(go, tab)
                L.style_link_box(go)
            amount = ws.cell(row=row, column=col)
            if key in cgt_refs:
                amount.value = f"={cgt_refs[key]}"
            elif key in tab_of:
                t = _q(tab_of[key])
                amount.value = f'=SUMIFS({t}!${AMOUNT}:${AMOUNT},{t}!${KEY}:${KEY},"{key}")'
            else:
                amount.value = 0
            letter = L.letter(col)
            if isinstance(amount.value, str):
                L.style_formula(amount)
                wp.summary_cells[key] = f"{_q(SUMMARY_TAB)}!{letter}{row}"
            else:
                L.style_input(amount)
            if key in ctx.prefill:
                L.style_input(ws.cell(row=row, column=8, value=ctx.prefill[key]))
            L.style_formula(ws.cell(row=row, column=9, value=f'=IF(H{row}="","",F{row}+G{row}-H{row})'))
            if key in ctx.prior_year:
                L.style_input(ws.cell(row=row, column=10, value=ctx.prior_year[key]))
            L.style_formula(ws.cell(row=row, column=11,
                                    value=f'=IF(OR(J{row}="",J{row}=0),"",(F{row}+G{row}-J{row})/J{row})'), L.PERCENT)
            counts = per_label.get(key)
            if counts:
                ws.cell(row=row, column=12, value=", ".join(f"{counts[r]} {r}" for r in ("High", "Medium", "Low") if counts[r]))
            ws.cell(row=row, column=13, value=key)
            L.rule_rows(ws, row, row, 2, SUMMARY_LAST - 1)
            refs[key] = f"{_q(SUMMARY_TAB)}!${letter}${row}"
            landing[key] = f"{letter}{row}"
            row += 1
        if total_name:
            ws.cell(row=row, column=4, value=total_text)
            L.style_label(ws.cell(row=row, column=4))
            L.style_total(ws.cell(row=row, column=6, value=f"={_taxcalc_ref(total_name)}"))
            row += 1
        row += 1
    ws.column_dimensions["M"].hidden = True
    L.set_widths(ws, L.SUMMARY_WIDTHS)
    L.setup_print(ws, landscape=True)
    return refs, landing


# --- rates ---------------------------------------------------------------------------------

class _Block:
    """Writes label/value rows down a sheet and remembers where each value went."""

    def __init__(self, ws: Worksheet, row: int):
        self.ws, self.row, self.refs = ws, row, {}

    def heading(self, text: str) -> None:
        self.row += 1
        self.ws.cell(row=self.row, column=1, value=text)
        L.style_section(self.ws, self.row, 1, 5)
        self.row += 1

    def value(self, name: str, label: str, value, fmt: str = L.NUMBER) -> None:
        self.ws.cell(row=self.row, column=1, value=label)
        L.style_input(self.ws.cell(row=self.row, column=2, value=value), fmt)
        L.rule_rows(self.ws, self.row, self.row, 1, 2)
        self.refs[name] = f"Rates!$B${self.row}"
        self.row += 1

    def table(self, name: str, headers: list[str], rows: list[list], fmts: list[str]) -> None:
        for col, h in enumerate(headers, start=1):
            self.ws.cell(row=self.row, column=col, value=h)
        L.style_header_row(self.ws, self.row, len(headers))
        first = self.row + 1
        for values in rows:
            self.row += 1
            for col, (v, fmt) in enumerate(zip(values, fmts), start=1):
                L.style_input(self.ws.cell(row=self.row, column=col, value=v), fmt)
            L.rule_rows(self.ws, self.row, self.row, 1, len(headers))
        last = self.row
        for col in range(1, len(headers) + 1):
            letter = chr(ord("A") + col - 1)
            self.refs[f"{name}.{col}"] = f"Rates!${letter}${first}:${letter}${last}"
        self.refs[f"{name}.row1"] = f"Rates!$B${first}:${chr(ord('A') + len(headers) - 1)}${first}"
        self.row += 1


def _rates(ws: Worksheet, ctx: WorkpaperContext) -> dict[str, str]:
    r, st = ctx.rates, ctx.state
    _title(ws, f"Rates and thresholds — FY{r.income_year}",
           "Copied from config/rates so this workbook stands alone. Blue = input.", back="E1")
    status = ws.cell(row=3, column=1, value=(
        f"Status: {r.status}" + (f" (verified by {r.verified_by} on {r.verified_on})" if r.status == "verified"
                                 else " — every figure must be checked against ato.gov.au by a registered agent")))
    if r.status != "verified":
        L.style_warning(status)
    b = _Block(ws, 4)
    b.heading("Resident tax rates")
    b.table("brackets", ["Income over", "Marginal rate", "Tax on income up to threshold"],
            [[x.from_, x.rate, x.base] for x in r.brackets], [L.WHOLE, L.PERCENT, L.NUMBER])
    b.heading("Low income tax offset")
    b.value("lito_max", "Maximum offset", r.lito.max)
    b.value("lito_full_to", "Full offset up to", r.lito.full_to, L.WHOLE)
    b.value("lito_t1_rate", "First taper rate", r.lito.taper1_rate, L.RATE)
    b.value("lito_t1_to", "First taper ends at", r.lito.taper1_to, L.WHOLE)
    b.value("lito_t2_base", "Offset at end of first taper", r.lito.taper2_base)
    b.value("lito_t2_rate", "Second taper rate", r.lito.taper2_rate, L.RATE)
    sapto = st.sapto_status != "none"
    threshold = r.medicare.sapto_single if sapto else r.medicare.single
    b.heading(f"Medicare levy ({'SAPTO single' if sapto else 'single'} thresholds)")
    b.value("ml_rate", "Levy rate", r.medicare.rate, L.PERCENT)
    b.value("ml_shade", "Shade-in rate over the lower threshold", r.medicare.shade_in, L.PERCENT)
    b.value("ml_lower", "Lower threshold", threshold.lower, L.WHOLE)
    b.value("ml_upper", "Full levy from", threshold.upper, L.WHOLE)
    if sapto:
        s = r.sapto[st.sapto_status]
        b.heading(f"Seniors and pensioners tax offset ({st.sapto_status.replace('_', ' ')})")
        b.value("sapto_max", "Maximum offset", s.max)
        b.value("sapto_shade", "Shade-out threshold", s.shade_out, L.WHOLE)
        b.value("sapto_cut", "Cut-out threshold", s.cut_out, L.WHOLE)
        b.value("sapto_taper", "Taper rate", r.sapto_taper, L.PERCENT)
    family = st.has_spouse or st.dependants > 0
    uplift = r.mls.family_per_child_after_first * max(0, st.dependants - 1) if family else Decimal("0")
    tiers = r.mls.family if family else r.mls.single
    b.heading(f"Medicare levy surcharge and PHI rebate tiers ({'family' if family else 'single'})")
    b.table("mls", ["Income over", "MLS rate"], [[t.from_ + uplift if t.from_ else t.from_, t.rate] for t in tiers],
            [L.WHOLE, L.PERCENT])
    for n, period in enumerate(r.phi_rebate, start=1):
        b.heading(f"PHI rebate {period.start:%d/%m/%Y}–{period.end:%d/%m/%Y} (age band {st.age_band}): base, tier 1-3")
        b.table(f"phi{n}", ["Rates", "Base", "Tier 1", "Tier 2", "Tier 3"],
                [["Rebate %", *period.rates[st.age_band]]], ["@", L.RATE, L.RATE, L.RATE, L.RATE])
    b.heading(f"HELP repayment ({r.help.method.replace('_', ' ')})")
    if r.help.method == "marginal":
        b.table("help", ["Repayment income over", "Base", "Rate"], [[x.from_, x.base, x.rate] for x in r.help.bands],
                [L.WHOLE, L.NUMBER, L.PERCENT])
        b.value("help_flat_from", "Flat rate applies from", r.help.flat_from, L.WHOLE)
        b.value("help_flat_rate", "Flat rate on total repayment income", r.help.flat_rate, L.PERCENT)
    else:
        b.table("help", ["Repayment income from", "Rate on total income"], [[x.from_, x.rate] for x in r.help.bands],
                [L.WHOLE, L.PERCENT])
    b.heading("Other rates (for reference)")
    b.value("car_rate", "Car cents per km", r.car.rate)
    b.value("car_cap", "Cents per km business km limit", r.car.km_cap, L.WHOLE)
    b.value("wfh_rate", "Working from home fixed rate per hour", r.wfh_rate)
    b.row += 1
    for name, url in r.sources.items():
        ws.cell(row=b.row, column=1, value=f"Source: {name}")
        ws.cell(row=b.row, column=2, value=url)
        b.row += 1
    L.set_widths(ws, L.RATES_WIDTHS)
    L.setup_print(ws, landscape=False)
    return b.refs


# --- tax calc ------------------------------------------------------------------------------

def _tax_calc(ws: Worksheet, ctx: WorkpaperContext, s: dict[str, str], r: dict[str, str], wp: WorkpaperMap) -> str:
    st = ctx.state
    _title(ws, f"Estimated tax — {ctx.client_code} {fy_label(ctx.income_year)}",
           "Column B is worked out by the formulas below. Column C is the tool's independent calculation B. "
           "Any difference is highlighted and raised as a High review note.", back="E1")
    ws["A4"], ws["A5"], ws["A6"] = "Days in income year", "Days without private hospital cover", "HELP debt"
    L.style_input(ws.cell(row=4, column=2, value=days_in_fy(ctx.income_year)), L.WHOLE)
    uncovered = 0 if st.hospital_cover_days is None else max(0, days_in_fy(ctx.income_year) - st.hospital_cover_days)
    L.style_input(ws.cell(row=5, column=2, value=uncovered), L.WHOLE)
    if st.hospital_cover_days is None:
        ws.cell(row=5, column=5, value="Assumed covered all year (see review notes)")
    ws.cell(row=6, column=2, value="Yes" if st.help_debt else "No")
    days, days_uncovered = "$B$4", "$B$5"

    head = TAXCALC_HEAD
    for col, h in enumerate(["Component", "Workpaper (formula)", "Python check (calc B)", "Difference",
                             "How it's worked out"], start=1):
        ws.cell(row=head, column=col, value=h)
    L.style_header_row(ws, head, 5)
    row_of = {name: head + 1 + i for i, (name, _) in enumerate(TAXCALC_ROWS)}
    c = {name: f"$B${row}" for name, row in row_of.items()}

    def S(key: str) -> str:
        return s.get(key, "0")  # a label with nothing this year has no Summary line

    rent = f"({S('rent.gross')}-{S('rent.interest')}-{S('rent.capital_works')}-{S('rent.other')})"
    income = "+".join(S(k) for k in ("income.salary", "income.allowances", "income.interest", "income.div_unfranked",
                                     "income.div_franked", "income.franking_credit", "cgt.net_gain", "income.other"))
    ti = c["taxable_income"]
    mlsi = c["mls_income"]
    bf, br, bb = r["brackets.1"], r["brackets.2"], r["brackets.3"]
    mls_from, mls_rate = r["mls.1"], r["mls.2"]
    tier_pos = f"MATCH(MAX(0,{mlsi}-0.001),{mls_from},1)"

    if st.sapto_status != "none":
        sapto = (f"=ROUND(MAX(0,{r['sapto_max']}-{r['sapto_taper']}*MAX(0,{mlsi}-{r['sapto_shade']})),2)",
                 "Max offset less taper × rebate income over the shade-out threshold")
    else:
        sapto = ("=0", "Not eligible")
    if not st.help_debt:
        help_ = ("=0", "No HELP debt")
    elif ctx.rates.help.method == "marginal":
        ri = c["repayment_income"]
        lk = f"{ri}-0.001"
        help_ = (f"=ROUND(IF({ri}<=0,0,IF({ri}>={r['help_flat_from']},{r['help_flat_rate']}*{ri},"
                 f"LOOKUP({lk},{r['help.1']},{r['help.2']})+({ri}-LOOKUP({lk},{r['help.1']},{r['help.1']}))"
                 f"*LOOKUP({lk},{r['help.1']},{r['help.3']}))),2)",
                 "Marginal: base + rate × income over the threshold; flat % of total income at the top")
    else:
        ri = c["repayment_income"]
        help_ = (f"=ROUND(IF({ri}<INDEX({r['help.1']},1),0,LOOKUP({ri},{r['help.1']},{r['help.2']})*{ri}),2)",
                 "Rate for the income band × total repayment income")

    phi_parts = []
    for n in (1, 2):
        phi_parts.append(f"({S(f'phi.rebate_p{n}')}-ROUND({S(f'phi.premiums_p{n}')}*INDEX({r[f'phi{n}.row1']},{tier_pos}),2))")

    formulas = {
        "total_income": (f"={income}+{rent}+{S('income.business_income')}-{S('income.business_expenses')}",
                         "Income labels + net rent + net capital gain + business net (B01 Summary)"),
        "deductions": ("=" + "+".join(S(k) for k in DEDUCTION_KEYS), "D1–D10, D12, D15 (B01 Summary)"),
        "taxable_income": (f"=MAX(0,ROUNDDOWN({c['total_income']}-{c['deductions']}-{S('loss.l1')},0))",
                           "Total income − deductions − prior-year losses; cents dropped"),
        "basic_tax": (f"=ROUND(LOOKUP({ti},{bf},{bb})+({ti}-LOOKUP({ti},{bf},{bf}))*LOOKUP({ti},{bf},{br}),2)",
                      "Base amount for the bracket + marginal rate × income over the threshold (Rates)"),
        "lito": (f"=ROUND(IF({ti}<={r['lito_full_to']},{r['lito_max']},IF({ti}<={r['lito_t1_to']},"
                 f"{r['lito_max']}-{r['lito_t1_rate']}*({ti}-{r['lito_full_to']}),"
                 f"MAX(0,{r['lito_t2_base']}-{r['lito_t2_rate']}*({ti}-{r['lito_t1_to']})))),2)",
                 "$700 reducing by 5c then 1.5c per $1 (Rates)"),
        "sapto": sapto,
        "offsets_used": (f"=MIN({c['basic_tax']},{c['lito']}+{c['sapto']})", "Offsets cannot exceed the tax"),
        "medicare_levy": (f"=ROUND(IF({ti}<={r['ml_lower']},0,MIN({r['ml_rate']}*{ti},{r['ml_shade']}*({ti}-{r['ml_lower']}))),2)",
                          "2%, shaded in above the low-income threshold"),
        "mls_income": (f"={ti}+{S('it.rfb')}+{S('it.resc')}+{S('ded.d12')}+MAX(0,-{rent})",
                       "Taxable income + fringe benefits + reportable super (employer + D12) + net rental loss"),
        "mls": (f"=ROUND(LOOKUP(MAX(0,{mlsi}-0.001),{mls_from},{mls_rate})*({ti}+{S('it.rfb')})*{days_uncovered}/{days},2)",
                "Tier rate × (taxable income + fringe benefits) × days without cover"),
        "repayment_income": (f"={mlsi}", "Same income test items as MLS"),
        "help": help_,
        "phi_adjustment": ("=ROUND(" + "+".join(phi_parts) + ",2)",
                           "Rebate received − entitlement at the client's tier, each period"),
        "franking_credits": (f"={S('income.franking_credit')}", "Item 11 U"),
        "payg_withheld": (f"={S('income.salary_tax_withheld')}", "Item 1 tax withheld"),
        "tfn_withheld": (f"={S('income.interest_tfn_withheld')}+{S('income.div_tfn_withheld')}", "Items 10 M and 11 V"),
        "net_result": (f"=ROUND({c['basic_tax']}-{c['offsets_used']}+{c['medicare_levy']}+{c['mls']}+{c['help']}"
                       f"+{c['phi_adjustment']}-{c['franking_credits']}-{c['payg_withheld']}-{c['tfn_withheld']},2)",
                       "Positive = estimated payable; negative = estimated refund"),
    }
    b_values = ctx.calc_b.components()
    for name, label in TAXCALC_ROWS:
        row = row_of[name]
        ws.cell(row=row, column=1, value=label)
        formula, how = formulas[name]
        cell = ws.cell(row=row, column=2, value=formula)
        (L.style_total if name in ("taxable_income", "net_result") else L.style_formula)(cell)
        L.style_input(ws.cell(row=row, column=3, value=b_values[name]))
        L.style_formula(ws.cell(row=row, column=4, value=f"=B{row}-C{row}"))
        ws.cell(row=row, column=5, value=how)
        L.rule_rows(ws, row, row, 1, 5)
        wp.taxcalc_cells[name] = f"{_q(TAXCALC_TAB)}!B{row}"
    L.flag_nonzero(ws, f"D{head + 1}:D{head + len(TAXCALC_ROWS)}")
    note_row = head + len(TAXCALC_ROWS) + 2
    ws.cell(row=note_row, column=1, value="Estimate only. Xero Tax produces the figure that is lodged; use this to "
            "cross-check it. Items flagged in Review Notes are not included in this estimate.")
    L.style_subtitle(ws.cell(row=note_row, column=1))
    L.set_widths(ws, L.TAXCALC_WIDTHS)
    L.setup_print(ws)
    return f"{_q(TAXCALC_TAB)}!$B${row_of['net_result']}"


# --- sources, review notes, cover ------------------------------------------------------------

def _sources(ws: Worksheet, ctx: WorkpaperContext) -> None:
    _title(ws, f"Source documents — {ctx.client_code} {fy_label(ctx.income_year)}",
           "Every filed document. Originals are filed unchanged; the tool keeps no copy of their text.", back="L1")
    headers = ["Doc ID", "Filed name", "Type", "Category", "Document date", "Date found", "Pages", "Parse status",
               "Store", "Redacted on read", "SHA-256 (first 16)", "Summary", "Description"]
    for col, h in enumerate(headers, start=1):
        ws.cell(row=FIRST_ROW - 1, column=col, value=h)
    L.style_header_row(ws, FIRST_ROW - 1, len(headers))
    for row, d in enumerate(ctx.documents, start=FIRST_ROW):
        ws.cell(row=row, column=1, value=d.doc_id)
        name = ws.cell(row=row, column=2, value=d.filed_name)
        name.hyperlink = _link(d.filed_location)
        L.style_link(name)
        ws.cell(row=row, column=3, value=d.doc_type)
        ws.cell(row=row, column=4, value=d.category)
        ws.cell(row=row, column=5, value=d.doc_date).number_format = L.DATE
        ws.cell(row=row, column=6, value="Y" if d.date_detected else "N")
        ws.cell(row=row, column=7, value=d.pages)
        ws.cell(row=row, column=8, value=d.parse_status)
        ws.cell(row=row, column=9, value=d.store)
        ws.cell(row=row, column=10, value=", ".join(f"{k}×{v}" for k, v in sorted(d.redaction_counts.items())))
        ws.cell(row=row, column=11, value=d.sha256[:16])
        L.style_wrap(ws.cell(row=row, column=12, value=ctx.doc_summaries.get(d.doc_id, "")))
        L.style_wrap(ws.cell(row=row, column=13, value=ctx.doc_descriptions.get(d.doc_id, "")))
        L.rule_rows(ws, row, row, 1, len(headers))
    ws.freeze_panes = f"A{FIRST_ROW}"
    L.set_widths(ws, L.SOURCES_WIDTHS)
    L.setup_print(ws, header_row=FIRST_ROW - 1)


def _citation_text(ctx: WorkpaperContext, citation_id: str | None) -> str:
    return citation_text(ctx.citations, citation_id)


def citation_text(citations: dict, citation_id: str | None) -> str:
    if not citation_id:
        return ""
    entry = citations.get(citation_id)
    if not entry:
        return f"{citation_id} (citation to be confirmed by reviewer)"
    return entry["ref"] + ("" if entry.get("verified") else " (citation to be confirmed by reviewer)")


def _review_notes(ws: Worksheet, ctx: WorkpaperContext) -> None:
    _title(ws, f"Review notes — {ctx.client_code} {fy_label(ctx.income_year)}",
           "Every flag, assumption and client question, ranked by risk then dollar impact. Respond in column J.",
           back="J1")
    headers = ["#", "Risk", "Area", "Note", "$ impact", "For", "Action", "Citation", "Refs", "Response"]
    for col, h in enumerate(headers, start=1):
        ws.cell(row=FIRST_ROW - 1, column=col, value=h)
    L.style_header_row(ws, FIRST_ROW - 1, len(headers))
    for i, n in enumerate(ctx.notes, start=1):
        row = FIRST_ROW + i - 1
        ws.cell(row=row, column=1, value=i)
        L.style_risk(ws.cell(row=row, column=2, value=n.risk), n.risk)
        area = n.check_id + (f" · {label_name(ctx.labels, n.label_key)}" if n.label_key else "")
        L.style_wrap(ws.cell(row=row, column=3, value=area))
        L.style_wrap(ws.cell(row=row, column=4, value=n.message))
        if n.dollar_impact is not None:
            L.style_formula(ws.cell(row=row, column=5, value=n.dollar_impact))
        ws.cell(row=row, column=6, value=n.audience)
        ws.cell(row=row, column=7, value=n.action)
        L.style_wrap(ws.cell(row=row, column=8, value=_citation_text(ctx, n.citation_id)))
        ws.cell(row=row, column=9, value=", ".join(n.figure_ids + n.doc_ids))
        if note_key(n) in ctx.responses:
            L.style_wrap(ws.cell(row=row, column=10, value=ctx.responses[note_key(n)]))
        L.rule_rows(ws, row, row, 1, len(headers))
    ws.freeze_panes = f"A{FIRST_ROW}"
    L.set_widths(ws, L.NOTES_WIDTHS)
    L.setup_print(ws, header_row=FIRST_ROW - 1)


def _cover(ws: Worksheet, ctx: WorkpaperContext, net_ref: str) -> None:
    ws.merge_cells("A1:B2")
    ws["A1"] = BANNER
    L.style_banner(ws["A1"])
    start, end = fy_bounds(ctx.income_year)
    for row, text, size in ((4, ctx.client_code, 18), (5, "Individual Tax Return", 14),
                            (6, f"Year ended {end:%d %B %Y}".replace(" 0", " "), 12)):
        L.style_cover_name(ws.cell(row=row, column=1, value=text), size)
    risks = Counter(n.risk for n in ctx.notes)
    rows = [
        ("Client code", ctx.client_code),
        ("Income year", f"{fy_label(ctx.income_year)} ({start:%d %B %Y} – {end:%d %B %Y})"),
        ("Partner", ""),
        ("Manager", ""),
        ("Reviewer (registered tax agent)", ""),
        ("Preparer", ctx.prepared_by),
        ("Prepared on", date.today().strftime("%d/%m/%Y")),
        ("Tool version", ctx.tool_version),
        ("Rates file", f"FY{ctx.rates.income_year}: {ctx.rates.status}"),
        ("Estimated payable / (refund)", f"={net_ref}"),
        ("Review notes", f"{risks['High']} High, {risks['Medium']} Medium, {risks['Low']} Low"),
        ("Review date", ""),
        ("Sign-off", ""),
    ]
    first = 8
    for i, (label, value) in enumerate(rows, start=first):
        L.style_label(ws.cell(row=i, column=1, value=label))
        cell = ws.cell(row=i, column=2, value=value)
        if isinstance(value, str) and value.startswith("="):
            L.style_total(cell)
        elif value == "":
            L.style_input(cell, "@")
        if label == "Rates file" and ctx.rates.status != "verified":
            L.style_warning(cell)
    L.rule_rows(ws, first, first + len(rows) - 1, 1, 2)
    contents = ws.cell(row=first + len(rows) + 1, column=1, value=f"→ Start at {SUMMARY_TAB}")
    _jump(contents, SUMMARY_TAB)
    L.style_link_box(contents)
    text_row = first + len(rows) + 3
    for line in (
        "Prepared by the Tax Return Assistant from documents supplied by the client.",
        "This is a draft. It must be reviewed and signed off by a registered tax agent before anything is lodged.",
        "Nothing has been lodged with the ATO. The return is prepared and lodged in Xero Tax.",
    ):
        L.style_subtitle(ws.cell(row=text_row, column=1, value=line))
        text_row += 1
    L.set_widths(ws, L.COVER_WIDTHS)
    L.setup_print(ws, landscape=False)


# --- entry point ---------------------------------------------------------------------------

def build_workpaper(path: Path, ctx: WorkpaperContext) -> WorkpaperMap:
    wp = WorkpaperMap()
    docs = {d.doc_id: d for d in ctx.documents}
    by_tab: dict[str, list[Figure]] = defaultdict(list)
    for f in ctx.figures:
        by_tab[ctx.labels[f.label_key].tab].append(f)
    tab_order = sorted(by_tab, key=lambda t: min(ctx.labels[f.label_key].order for f in by_tab[t]))
    has_cgt = bool(by_tab.get(CGT_TAB)) or any(e.confirmed for e in ctx.cgt_events)
    if has_cgt and CGT_TAB not in tab_order:
        tab_order.append(CGT_TAB)
        tab_order.sort(key=lambda t: 317 if t == CGT_TAB else min(ctx.labels[f.label_key].order for f in by_tab[t]))

    wb = Workbook()
    cover = wb.active
    cover.title = "Cover"
    summary = wb.create_sheet(SUMMARY_TAB)
    tab_sheets = {tab: wb.create_sheet(tab) for tab in tab_order}
    tax_calc = wb.create_sheet(TAXCALC_TAB)
    rates = wb.create_sheet("Rates")
    sources = wb.create_sheet("Sources")
    notes = wb.create_sheet("Review Notes")

    cgt_refs: dict[str, str] = {}
    tab_of: dict[str, str] = {}
    transfers: list = []
    for tab in tab_order:
        figures = by_tab.get(tab, [])
        if tab == CGT_TAB:
            cgt_refs = _cgt_tab(tab_sheets[tab], figures, ctx, docs, wp, transfers)
        else:
            _item_tab(tab_sheets[tab], tab, figures, ctx, docs, wp, transfers)
        for f in figures:
            tab_of[return_key(ctx.labels, f.label_key)] = tab  # a rental category's tab is Item 21 U's
    summary_refs, landing = _summary(summary, ctx, tab_of, cgt_refs, wp)
    for cell, key in transfers:  # "Transferred to: Item 10 L" lands on that line of the Summary
        if key in landing:
            _jump(cell, SUMMARY_TAB, landing[key])
    rate_refs = _rates(rates, ctx)
    net_ref = _tax_calc(tax_calc, ctx, summary_refs, rate_refs, wp)
    _sources(sources, ctx)
    _review_notes(notes, ctx)
    _cover(cover, ctx, net_ref)
    for ws in wb.worksheets:
        L.finish_sheet(ws)

    check_workbook(wb, path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    wb.save(tmp)
    try:
        os.replace(tmp, path)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise FileLockedError(path) from None
    return wp
