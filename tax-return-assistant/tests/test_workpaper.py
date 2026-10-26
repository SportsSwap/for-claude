import re
import shutil
import subprocess
from decimal import Decimal

import openpyxl
import pytest
from wpctx import demo_context

from tra.labels import load_labels, return_key
from tra.privacy.guard import FileLockedError, SensitiveDataBlocked
from tra.workpaper.build import build_workpaper

SUMMARY = "B01 Summary"
# The rental tab has the firm's own layout (tests/test_workpaper_rental.py), one per property.
RENTAL_TAB = "M25 Rental Property 1"
ITEM_TABS = ("01 Salaries and Wages", "10 Interest Received", "11 Dividends Received",
             "D05 Other Work Deductions", "PHI Private Health")
# Item tab columns (the firm's layout starts in column B): B ref, E source, F page, I amount, J key (hidden).
REF, SOURCE, PAGE, DETAIL, AMOUNT, KEY = 2, 5, 6, 4, 9, 10
# Summary columns: E go-to link, F amount, G tax credits, M key (hidden).
GO, S_AMOUNT, S_CREDITS, S_KEY = 5, 6, 7, 13


@pytest.fixture
def built(tmp_path):
    ctx = demo_context(tmp_path)
    path = tmp_path / "wp.xlsx"
    wp_map = build_workpaper(path, ctx)
    return path, wp_map, ctx


def _summary_rows(ws):
    return {ws.cell(row=r, column=S_KEY).value: r for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=S_KEY).value}


def test_tabs_present(built):
    path, _, _ = built
    names = openpyxl.load_workbook(path).sheetnames
    for tab in ("Cover", SUMMARY, *ITEM_TABS, RENTAL_TAB, "Tax Calc", "Rates", "Sources", "Review Notes"):
        assert tab in names
    assert names[:2] == ["Cover", SUMMARY]
    assert names[-4:] == ["Tax Calc", "Rates", "Sources", "Review Notes"]
    assert "D01 MV Expenses" not in names and "M03 Capital Gains" not in names  # only the tabs this client needs


def test_totals_are_formulas(built):
    path, wp_map, _ = built
    wb = openpyxl.load_workbook(path)
    refs = wp_map.total_cells + list(wp_map.summary_cells.values()) + list(wp_map.taxcalc_cells.values())
    assert len(wp_map.taxcalc_cells) == 17
    assert "income.interest" in wp_map.summary_cells
    for ref in refs:
        sheet, cell = ref.rsplit("!", 1)
        value = wb[sheet.strip("'")][cell].value
        assert isinstance(value, str) and value.startswith("="), ref


def test_item_tabs_follow_the_firm_layout(built):
    path, _, _ = built
    wb = openpyxl.load_workbook(path)
    for tab in ITEM_TABS:
        ws = wb[tab]
        assert ws.sheet_view.showGridLines is False, tab
        top = [c for row in ws.iter_rows(max_row=9) for c in row]
        texts = {c.value for c in top if isinstance(c.value, str)}
        assert {"Client code", "DEMO01", "Year ended", "Workpaper", "Prepared by", "Reviewed by"} <= texts, tab
        assert any(t.startswith("i  The purpose of this worksheet") for t in texts), tab
        assert [c.hyperlink.location for c in top if c.hyperlink is not None] == [f"'{SUMMARY}'!A1"], tab
        fonts = {(c.font.name, c.font.sz) for row in ws.iter_rows(min_row=10) for c in row if c.value is not None}
        assert fonts <= {("Calibri", 10)}, (tab, fonts)


def test_transferred_to_links_land_on_the_summary_row(built):
    path, _, _ = built
    wb = openpyxl.load_workbook(path)
    summary = wb[SUMMARY]
    for tab in ITEM_TABS:
        ws = wb[tab]
        rows = [r for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=AMOUNT - 1).value == "Transferred to:"]
        assert rows, tab
        for r in rows:
            link = ws.cell(row=r, column=AMOUNT)
            sheet, cell = link.hyperlink.location.rsplit("!", 1)
            assert sheet == f"'{SUMMARY}'"
            section_key = next(ws.cell(row=x, column=KEY).value for x in range(r, 0, -1) if ws.cell(row=x, column=KEY).value)
            section_key = return_key(load_labels(), section_key)  # the last row may be a rental category of 21 U
            assert summary.cell(row=int(re.sub(r"\D", "", cell)), column=S_KEY).value == section_key, (tab, r)
            assert link.value  # 'Item 10 L', or 'PHI' for private health


def test_summary_is_the_hub(built):
    path, _, ctx = built
    wb = openpyxl.load_workbook(path)
    ws = wb[SUMMARY]
    rows = _summary_rows(ws)
    assert "income.interest" in rows and "ded.d5" in rows
    assert "ded.d1" not in rows  # nothing at D1, so no line for it
    assert ws.column_dimensions["M"].hidden
    with_figures = {f.label_key for f in ctx.figures}
    for key, r in rows.items():
        go = ws.cell(row=r, column=GO)
        if key in with_figures:
            tab = RENTAL_TAB if ctx.labels[key].tab == "M25 Rental Property" else ctx.labels[key].tab
            assert go.hyperlink.location == f"'{wb[tab].title}'!A1", key
    withheld = rows["income.salary_tax_withheld"]
    assert ws.cell(row=withheld, column=S_AMOUNT).value is None
    assert ws.cell(row=withheld, column=S_CREDITS).value.startswith("=SUMIFS(")
    labels = {ws.cell(row=r, column=c).value: r for r in range(1, ws.max_row + 1) for c in (2, 4)}
    for text in ("Tax Summary", "Taxable income", "Estimated amount payable / (refundable)", "Total income",
                 "Total deductions"):
        assert text in labels, text
    assert "'Tax Calc'!" in ws.cell(row=labels["Estimated amount payable / (refundable)"], column=S_AMOUNT).value


def test_every_figure_row_has_source(built):
    path, _, ctx = built
    wb = openpyxl.load_workbook(path)
    rental = {f.figure_id for f in ctx.figures if ctx.labels[f.label_key].tab == "M25 Rental Property"}
    ids = {f.figure_id for f in ctx.figures} - rental
    rows = 0
    for tab in ITEM_TABS:
        ws = wb[tab]
        for r in range(1, ws.max_row + 1):
            if ws.cell(row=r, column=REF).value in ids:
                rows += 1
                assert ws.cell(row=r, column=SOURCE).value, (tab, r)
                assert ws.cell(row=r, column=PAGE).value, (tab, r)
                assert ws.cell(row=r, column=SOURCE).hyperlink is not None
    assert rows == len(ids)
    sources = " ".join(str(c.value) for row in wb[RENTAL_TAB].iter_rows() for c in row if c.column == 10 and c.value)
    for f in ctx.figures:
        if f.figure_id in rental:
            assert f.doc_id in sources, f.figure_id  # each rental row lists its documents


def test_prefill_figures_have_their_own_section(tmp_path):
    def mutate(figures):
        for f in figures:
            if f.notes == "prefill" and f.label_key == "income.interest":
                f.confirmed = True

    ctx = demo_context(tmp_path, mutate=mutate)
    assert any(f.notes == "prefill" and f.label_key == "income.interest" for f in ctx.figures)
    path = tmp_path / "wp.xlsx"
    build_workpaper(path, ctx)
    ws = openpyxl.load_workbook(path)["10 Interest Received"]
    at = {ws.cell(row=r, column=DETAIL).value: r for r in range(1, ws.max_row + 1)}
    for text in ("ATO pre-fill", "Client documents and adjustments", "Subtotal – ATO pre-fill",
                 "Subtotal – client documents"):
        assert text in at, text
    total = ws.cell(row=at["Total Gross interest (Item 10 L)"], column=AMOUNT).value
    assert total == f"=I{at['Subtotal – ATO pre-fill']}+I{at['Subtotal – client documents']}"


def test_banner_and_rates_status(built):
    path, _, _ = built
    wb = openpyxl.load_workbook(path)
    assert wb["Cover"]["A1"].value == "DRAFT – NOT FOR LODGMENT"
    assert "A1:B2" in [str(r) for r in wb["Cover"].merged_cells.ranges]
    assert all(ws.page_setup.fitToWidth == 1 for ws in wb.worksheets)
    texts = [c.value for row in wb["Rates"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any("unverified" in t for t in texts)


def test_review_notes_ranked_with_citations(built):
    path, _, ctx = built
    ws = openpyxl.load_workbook(path)["Review Notes"]
    risks = [ws.cell(row=r, column=2).value for r in range(5, 5 + len(ctx.notes))]
    assert risks == [n.risk for n in ctx.notes]
    citations = [ws.cell(row=r, column=8).value for r in range(5, 5 + len(ctx.notes))]
    assert any(c and "s900-35" in c and "to be confirmed" in c for c in citations)


def test_guard_blocks_leak(tmp_path, make_tfn):
    tfn = make_tfn()
    ctx = demo_context(tmp_path)
    ctx.figures[0].description = f"note {tfn}"
    path = tmp_path / "leak.xlsx"
    with pytest.raises(SensitiveDataBlocked):
        build_workpaper(path, ctx)
    assert not path.exists()
    assert not list(tmp_path.glob("leak.xlsx*"))


def test_locked_file(tmp_path, monkeypatch):
    ctx = demo_context(tmp_path)

    def locked(*_args):
        raise PermissionError("locked")

    monkeypatch.setattr("tra.workpaper.build.os.replace", locked)
    with pytest.raises(FileLockedError):
        build_workpaper(tmp_path / "wp.xlsx", ctx)


def _recalculate(path, out_dir):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    subprocess.run([soffice, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(out_dir), str(path)],
                   check=True, capture_output=True, timeout=180)
    return openpyxl.load_workbook(out_dir / path.name, data_only=True)


@pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")), reason="LibreOffice not installed")
def test_recalc_matches_calc_a(built, tmp_path):
    path, wp_map, ctx = built
    wb = _recalculate(path, tmp_path / "recalc")
    expected = ctx.calc_a.components()
    for name, ref in wp_map.taxcalc_cells.items():
        sheet, cell = ref.rsplit("!", 1)
        value = wb[sheet.strip("'")][cell].value
        assert value is not None, name
        assert abs(Decimal(str(value)) - expected[name]) <= Decimal("0.01"), (name, value, expected[name])


def _set_salary(amount):
    def mutate(figures):
        for f in figures:
            if f.label_key == "income.salary" and f.confirmed:
                f.amount = Decimal(amount)
    return mutate


@pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")), reason="LibreOffice not installed")
@pytest.mark.parametrize("case", ["help_mls_cgt", "senior_low_income"])
def test_recalc_matches_calc_a_other_branches(tmp_path, case):
    from tra.models import ClientState
    if case == "help_mls_cgt":
        def mutate(figures):
            _set_salary("140000")(figures)
            from tra.models import Figure
            figures.append(Figure("F0900", "ded.d12", "Personal super contribution", Decimal("10000"), None, "D002",
                                  1, "manual", True, True, ""))

        ctx = demo_context(tmp_path, state=ClientState("DEMO01", 2026, help_debt=True, hospital_cover_days=200),
                           mutate=mutate,
                           cgt_rows=[["C001", "BHP shares", "2020-01-10", "2026-03-24", "15000.00", "9000.00", "D004", "1", "Y"],
                                     ["C002", "Crypto", "2025-10-01", "2026-02-01", "3000.00", "1000.00", "", "", "Y"]])
        assert ctx.calc_a.help > 0 and ctx.calc_a.mls > 0 and ctx.draft.amount("cgt.net_gain") > 0
        assert ctx.draft.amount("ded.d12") == Decimal("10000")
    else:
        ctx = demo_context(tmp_path, state=ClientState("DEMO01", 2026, sapto_status="single", age_band="70plus"),
                           mutate=_set_salary("12000"))
        assert ctx.calc_a.sapto > 0 and ctx.calc_a.lito > 0
    path = tmp_path / "wp.xlsx"
    wp_map = build_workpaper(path, ctx)
    wb = _recalculate(path, tmp_path / "recalc")
    expected = ctx.calc_a.components()
    for name, ref in wp_map.taxcalc_cells.items():
        sheet, cell = ref.rsplit("!", 1)
        value = wb[sheet.strip("'")][cell].value
        assert value is not None, name
        assert abs(Decimal(str(value)) - expected[name]) <= Decimal("0.01"), (case, name, value, expected[name])


def test_no_formula_sums_over_its_own_cell(tmp_path):
    from openpyxl.utils import range_boundaries
    ctx = demo_context(tmp_path, cgt_rows=[["C001", "BHP shares", "2020-01-10", "2026-03-24", "15000.00", "9000.00",
                                            "D004", "1", "Y"]])
    path = tmp_path / "wp.xlsx"
    build_workpaper(path, ctx)
    for ws in openpyxl.load_workbook(path).worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("=SUM("):
                    for rng in re.findall(r"SUM\(([A-Z]+\d+:[A-Z]+\d+)\)", cell.value):
                        min_col, min_row, max_col, max_row = range_boundaries(rng)
                        lo, hi = sorted((min_row, max_row))
                        assert not (min_col <= cell.column <= max_col and lo <= cell.row <= hi), \
                            f"{ws.title}!{cell.coordinate} {cell.value}"


def test_no_total_mixes_different_labels(built):
    path, _, _ = built
    wb = openpyxl.load_workbook(path)
    for name in ITEM_TABS:
        ws = wb[name]
        sums = 0
        for row in ws.iter_rows():
            for cell in row:
                m = re.fullmatch(r"=SUM\(I(\d+):I(\d+)\)", str(cell.value or ""))
                if m:
                    sums += 1
                    keys = {ws.cell(row=r, column=KEY).value for r in range(int(m.group(1)), int(m.group(2)) + 1)} - {None}
                    assert len(keys) == 1, f"{name}!{cell.coordinate} adds {keys}"
        assert sums >= 1, name


def test_rental_tab_shows_net_rent(built):
    path, _, _ = built
    ws = openpyxl.load_workbook(path)[RENTAL_TAB]
    labels = [ws.cell(row=r, column=2).value for r in range(1, ws.max_row + 1)]
    assert "Net Income / (Loss)" in labels


def test_combined_tabs_keep_separate_totals(tmp_path):
    from tra.models import Figure

    def mutate(figures):
        figures.append(Figure("F0901", "ded.d7", "Margin loan interest", Decimal("300"), None, "D002", 1, "manual",
                              True, True, ""))
        figures.append(Figure("F0902", "ded.d8", "Share registry fee", Decimal("40"), None, "D002", 1, "manual",
                              True, True, ""))

    ctx = demo_context(tmp_path, mutate=mutate)
    path = tmp_path / "wp.xlsx"
    build_workpaper(path, ctx)
    ws = openpyxl.load_workbook(path)["D07 Int Div Deductions"]
    texts = [ws.cell(row=r, column=DETAIL).value for r in range(1, ws.max_row + 1)]
    assert "Total Interest deductions (Item D7 I)" in texts and "Total Dividend deductions (Item D8 H)" in texts
