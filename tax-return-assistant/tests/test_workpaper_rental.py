"""The firm-style rental tab: one per property, the client's share and private use as formulas of blue inputs, and
the Item 21 labels transferred to the Summary. Made-up data only (the demo client)."""

import re
from decimal import Decimal

import openpyxl
import pytest
from wpctx import demo_context

from tra.models import Figure
from tra.rental import ROWS, Property, RentalSetup
from tra.workpaper.build import build_workpaper

SUMMARY = "B01 Summary"
DETAIL, TICK, AGENT, OWNERS, TAXPAYER, LETTER, SHARE, PRIOR, SOURCES, KEY = range(2, 12)


def _build(tmp_path, rental=None, mutate=None):
    ctx = demo_context(tmp_path, rental=rental, mutate=mutate)
    path = tmp_path / "wp.xlsx"
    build_workpaper(path, ctx)
    return openpyxl.load_workbook(path), ctx


def _half(name="Sample St", **kw):
    return RentalSetup(properties=[Property(id="P1", name=name, share=Decimal("50"), share_source="person", **kw)])


def _row_of(ws, text, col=DETAIL):
    return next(r for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=col).value == text)


def test_one_tab_per_property_named_like_the_firms(tmp_path):
    wb, _ = _build(tmp_path)
    assert "M25 Rental Property 1" in wb.sheetnames and "M25 Rental Property" not in wb.sheetnames
    (tmp_path / "b").mkdir()
    wb, _ = _build(tmp_path / "b", rental=_half())
    assert "M25 Rental Sample St" in wb.sheetnames


def test_the_tab_has_the_firms_sections_and_every_row(tmp_path):
    wb, _ = _build(tmp_path, rental=_half())
    ws = wb["M25 Rental Sample St"]
    texts = [ws.cell(row=r, column=DETAIL).value for r in range(1, ws.max_row + 1)]
    for section in ("Property Details", "Ownership", "Income / Expenses"):
        assert section in texts
    letters = [ws.cell(row=r, column=LETTER).value for r in range(1, ws.max_row + 1)
               if ws.cell(row=r, column=LETTER).value]
    assert [x for x in letters if len(x) == 1] == [r.letter for r in ROWS]
    for row in ROWS:
        assert row.heading in texts, row.heading
    headers = [ws.cell(row=_row_of(ws, "Detail"), column=c).value for c in range(DETAIL, SOURCES + 1)]
    assert headers == ["Detail", "Apportion?", "Agent Summary", "Owners' Contribution",
                       "This Taxpayer's Contribution Only", None, "Taxpayer's Share", "Prior Period", "Sources"]


def test_share_and_private_use_are_blue_inputs(tmp_path):
    from tra.workpaper import layout as L
    wb, _ = _build(tmp_path, rental=_half(private_use=Decimal("10"), weeks_rented=40))
    ws = wb["M25 Rental Sample St"]
    share = ws.cell(row=_row_of(ws, "This taxpayer's share"), column=SHARE)
    private = ws.cell(row=_row_of(ws, "Private use percentage"), column=SHARE)
    weeks = ws.cell(row=_row_of(ws, "No. of weeks rented this year"), column=SHARE)
    assert (share.value, private.value, weeks.value) == (0.5, 0.1, 40)
    assert share.font.color.rgb.endswith(L.INPUT_BLUE) and share.number_format == L.PERCENT
    others = ws.cell(row=_row_of(ws, "Other owners' share"), column=SHARE).value
    assert others == f"=1-{share.coordinate}"


def test_statement_figures_sit_in_agent_summary_with_a_share_formula(tmp_path):
    wb, _ = _build(tmp_path, rental=_half())
    ws = wb["M25 Rental Sample St"]
    r = _row_of(ws, "Council Rates")
    assert ws.cell(row=r, column=AGENT).value == 2100 and ws.cell(row=r, column=OWNERS).value is None
    assert ws.cell(row=r, column=TICK).value == "✓"
    formula = ws.cell(row=r, column=SHARE).value
    assert re.fullmatch(rf'=ROUND\(\(\(D{r}\+E{r}\)\*\$H\$\d+\+F{r}\)\*IF\(C{r}="✓",1-\$H\$\d+,1\),2\)', formula)
    assert ws.cell(row=_row_of(ws, "Agent Fees"), column=TICK).value is None  # not apportioned by default
    sources = ws.cell(row=r, column=SOURCES)
    assert sources.value.startswith("D") and sources.hyperlink is not None


def test_repairs_are_itemised_with_a_subtotal(tmp_path):
    wb, _ = _build(tmp_path, rental=_half())
    ws = wb["M25 Rental Sample St"]
    heading = _row_of(ws, "Repairs and Maintenance")
    line = _row_of(ws, "Repairs - leaking tap")
    assert line > heading and ws.cell(row=line, column=AGENT).value == 640
    subtotal = next(r for r in range(line, ws.max_row + 1) if ws.cell(row=r, column=LETTER).value == "Q")
    assert ws.cell(row=subtotal, column=SHARE).value == f"=SUM(H{heading + 1}:H{subtotal - 1})"


def test_totals_and_net(tmp_path):
    wb, _ = _build(tmp_path, rental=_half())
    ws = wb["M25 Rental Sample St"]
    w = _row_of(ws, "Total Expenses")
    x = _row_of(ws, "Net Income / (Loss)")
    c = _row_of(ws, "Total Income")
    assert ws.cell(row=x, column=SHARE).value == f"=H{c}-H{w}"
    assert ws.cell(row=w, column=SHARE).value.startswith("=")


def test_item_21_labels_are_transferred_to_the_summary(tmp_path):
    wb, ctx = _build(tmp_path, rental=_half())
    ws, summary = wb["M25 Rental Sample St"], wb[SUMMARY]
    keys = {summary.cell(row=r, column=13).value: r for r in range(1, summary.max_row + 1)}
    for key, text in (("rent.gross", "Gross rent (Item 21 P)"), ("rent.other", "Other rental deductions (Item 21 U)")):
        r = _row_of(ws, text)
        link = ws.cell(row=r + 1, column=SHARE)
        assert ws.cell(row=r + 1, column=LETTER).value == "Transferred to:"
        assert link.hyperlink.location == f"'{SUMMARY}'!F{keys[key]}"
        assert summary.cell(row=keys[key], column=6).value == f"='M25 Rental Sample St'!H{r}"
    assert ctx.draft.amount("rent.gross") == Decimal("13000.00")  # the demo's 26,000 at 50%


def test_two_properties_two_tabs_and_the_summary_adds_them(tmp_path):
    def mutate(figures):
        figures.append(Figure("F0901", "rent.gross", "Second property rent", Decimal("5000"), None, "D099", 1,
                              "manual", True, None, ""))
    rental = RentalSetup(properties=[Property(id="P1", name="Sample St"), Property(id="P2", name="Example Rd")],
                         documents={"D099": "P2"})
    wb, ctx = _build(tmp_path, rental=rental, mutate=mutate)
    assert {"M25 Rental Sample St", "M25 Rental Example Rd"} <= set(wb.sheetnames)
    summary = wb[SUMMARY]
    row = next(r for r in range(1, summary.max_row + 1) if summary.cell(row=r, column=13).value == "rent.gross")
    formula = summary.cell(row=row, column=6).value
    assert "'M25 Rental Sample St'!" in formula and "'M25 Rental Example Rd'!" in formula and "+" in formula
    assert ctx.draft.amount("rent.gross") == Decimal("31000.00")


@pytest.mark.parametrize("name, tab", [("A/B: C?", "M25 Rental A B C"), ("Lot 3 [rear]", "M25 Rental Lot 3 rear")])
def test_tab_names_are_made_safe_for_excel(tmp_path, name, tab):
    wb, _ = _build(tmp_path, rental=_half(name=name))
    assert tab in wb.sheetnames


def test_the_tab_follows_the_firm_style(tmp_path):
    wb, _ = _build(tmp_path, rental=_half())
    ws = wb["M25 Rental Sample St"]
    assert ws.sheet_view.showGridLines is False
    top = [c for row in ws.iter_rows(max_row=9) for c in row]
    texts = {c.value for c in top if isinstance(c.value, str)}
    assert {"Client code", "DEMO01", "Year ended", "Workpaper", "Prepared by", "Reviewed by"} <= texts
    assert [c.hyperlink.location for c in top if c.hyperlink is not None] == [f"'{SUMMARY}'!A1"]
    fonts = {(c.font.name, c.font.sz) for row in ws.iter_rows(min_row=10) for c in row if c.value is not None}
    assert fonts <= {("Calibri", 10)}
    assert ws.column_dimensions["K"].hidden  # the key column
