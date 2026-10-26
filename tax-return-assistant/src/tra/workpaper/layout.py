"""Every visual choice in the workpaper lives here.

The look follows the firm's individual tax workpapers: Calibri 10, dark grey text, no gridlines,
thin rules under each line, light-blue link boxes ("↩ B01 Summary", "Transferred to: Item 10 L") and
the accounting number format. build.py decides what goes in which cell, layout.py decides how it looks.
Convention: blue text marks typed-in inputs (figures, rates), dark grey marks formulas.
"""

from __future__ import annotations

from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

NUMBER = '_(* #,##0.00_);_(* \\(#,##0.00\\);_(* "-"??_);_(@_)'
WHOLE = '_(* #,##0_);_(* \\(#,##0\\);_(* "-"_);_(@_)'
PERCENT = '0.0%'
RATE = '0.000%'
DATE = 'dd/mm/yyyy'
LONG_DATE = 'd mmmm yyyy'

FONT = "Calibri"
SIZE = 10
INK = "333333"
SECTION_INK = "292929"
INPUT_BLUE = "1F4E9A"
LINK_BLUE = "27A9E1"
MUTED = "808080"
RULE = "D9D9D9"
LINK_FILL = PatternFill("solid", fgColor="DDEBF7")
SECTION_FILL = PatternFill("solid", fgColor="F2F2F2")
BANNER_FILL = PatternFill("solid", fgColor="B91C1C")
WARN_FILL = PatternFill("solid", fgColor="FEE2E2")
RISK_FILLS = {
    "High": PatternFill("solid", fgColor="FECACA"),
    "Medium": PatternFill("solid", fgColor="FEF3C7"),
    "Low": PatternFill("solid", fgColor="E0F2FE"),
}
_THIN = Side(style="thin", color="808080")
_RULE = Side(style="thin", color=RULE)
_DOUBLE = Side(style="double", color=INK)


def _font(*, bold: bool = False, italic: bool = False, size: float = SIZE, color: str = INK,
          underline: str | None = None) -> Font:
    return Font(name=FONT, size=size, bold=bold, italic=italic, color=color, underline=underline)


def style_title(cell) -> None:
    cell.font = _font(bold=True, size=14)


def style_subtitle(cell) -> None:
    cell.font = _font(italic=True, size=9, color=MUTED)


def style_purpose(cell) -> None:
    """The blue "i  The purpose of this worksheet is…" line under each header."""
    cell.font = _font(bold=True, color=LINK_BLUE)


def style_banner(cell) -> None:
    cell.font = _font(bold=True, size=18, color="FFFFFF")
    cell.fill = BANNER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center")


def style_cover_name(cell, size: int) -> None:
    cell.font = _font(bold=size >= 14, size=size)


def style_section(ws: Worksheet, row: int, first: int, last: int) -> None:
    """A section bar such as "Item 10 L  Gross interest" or "Income"."""
    for col in range(first, last + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = _font(bold=True, color=SECTION_INK)
        cell.fill = SECTION_FILL
        cell.border = Border(bottom=_THIN)


def style_subheading(cell) -> None:
    cell.font = _font(bold=True, italic=True, color=MUTED)


def style_header_row(ws: Worksheet, row: int, columns: int, first: int = 1) -> None:
    for col in range(first, first + columns):
        cell = ws.cell(row=row, column=col)
        cell.font = _font(bold=True)
        cell.border = Border(bottom=_THIN)
        cell.alignment = Alignment(vertical="bottom", wrap_text=True)


def style_label(cell) -> None:
    cell.font = _font(bold=True)


def style_input(cell, fmt: str = NUMBER) -> None:
    cell.font = _font(color=INPUT_BLUE)
    cell.number_format = fmt


def style_formula(cell, fmt: str = NUMBER) -> None:
    cell.font = _font()
    cell.number_format = fmt


def style_subtotal(cell, fmt: str = NUMBER) -> None:
    cell.font = _font(bold=True)
    cell.number_format = fmt
    cell.border = Border(top=_THIN)


def style_total(cell, fmt: str = NUMBER) -> None:
    cell.font = _font(bold=True)
    cell.number_format = fmt
    cell.border = Border(top=_THIN, bottom=_DOUBLE)


def style_warning(cell) -> None:
    cell.font = _font(bold=True, color="B91C1C")
    cell.fill = WARN_FILL


def style_draft(cell) -> None:
    cell.font = _font(bold=True, color="B91C1C")


def style_risk(cell, risk: str) -> None:
    cell.fill = RISK_FILLS.get(risk, SECTION_FILL)
    cell.font = _font(bold=True)


def style_link(cell) -> None:
    """A link to a filed document or web page."""
    cell.font = _font(color=INPUT_BLUE, underline="single")


def style_link_box(cell) -> None:
    """A light-blue box that jumps to another tab (the firm's "} B01 Summary" boxes)."""
    cell.font = _font(bold=True, color=LINK_BLUE)
    cell.fill = LINK_FILL
    cell.border = Border(bottom=_THIN)
    cell.alignment = Alignment(horizontal="center")


def align_left(cell) -> None:
    cell.alignment = Alignment(horizontal="left")


def style_wrap(cell) -> None:
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def rule_rows(ws: Worksheet, first_row: int, last_row: int, first_col: int, last_col: int) -> None:
    """A light rule under each line of a table, as the firm's workpapers have (gridlines are off)."""
    for row in range(first_row, last_row + 1):
        for col in range(first_col, last_col + 1):
            cell = ws.cell(row=row, column=col)
            if not cell.border.bottom.style:
                cell.border = Border(top=cell.border.top, bottom=_RULE)


def finish_sheet(ws: Worksheet) -> None:
    """Gridlines off, and every cell not styled on purpose in the base font (Calibri 10)."""
    ws.sheet_view.showGridLines = False
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None and (cell.font.name != FONT or cell.font.sz == 11):  # 11 = Excel's default
                f = cell.font
                rgb = getattr(f.color, "rgb", None)
                color = rgb if isinstance(rgb, str) and len(rgb) == 8 and rgb != "FF000000" else INK
                cell.font = Font(name=FONT, size=SIZE, bold=f.b, italic=f.i, underline=f.u, color=color)


def setup_print(ws: Worksheet, *, landscape: bool = True, header_row: int | None = None) -> None:
    """A4, one page wide, header row repeated on every printed page."""
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    if header_row:
        ws.print_title_rows = f"{header_row}:{header_row}"


def set_widths(ws: Worksheet, widths: dict[str, float]) -> None:
    for column, width in widths.items():
        ws.column_dimensions[column].width = width


def letter(col: int) -> str:
    return get_column_letter(col)


def flag_nonzero(ws: Worksheet, cell_range: str) -> None:
    """Red fill on any cell in the range that is not zero (to the cent)."""
    first = cell_range.split(":")[0]
    ws.conditional_formatting.add(cell_range, FormulaRule(formula=[f"ABS({first})>=0.01"], fill=WARN_FILL))


# Item tabs: A margin, B ref, C date, D detail, E source, F page, G method, H substantiated, I amount,
# J key (hidden), K comments.
ITEM_WIDTHS = {"A": 2, "B": 9, "C": 11, "D": 44, "E": 38, "F": 6, "G": 9, "H": 14, "I": 16, "J": 4, "K": 34}
# Summary: A margin, B item, C code, D item, E go to, F amount, G tax credits, H pre-fill, I difference,
# J prior year, K movement, L review notes, M key (hidden).
RENTAL_WIDTHS = {"A": 2, "B": 52, "C": 11, "D": 15, "E": 15, "F": 15, "G": 13, "H": 16, "I": 14, "J": 30, "K": 22}
SUMMARY_WIDTHS = {"A": 2, "B": 10, "C": 6, "D": 52, "E": 8, "F": 16, "G": 15, "H": 15, "I": 13, "J": 15,
                  "K": 11, "L": 22, "M": 4}
TAXCALC_WIDTHS = {"A": 44, "B": 18, "C": 18, "D": 13, "E": 70}
RATES_WIDTHS = {"A": 34, "B": 14, "C": 14, "D": 14, "E": 14}
SOURCES_WIDTHS = {"A": 8, "B": 46, "C": 11, "D": 13, "E": 12, "F": 10, "G": 7, "H": 14, "I": 8, "J": 22, "K": 16, "L": 60, "M": 40}
NOTES_WIDTHS = {"A": 5, "B": 9, "C": 30, "D": 80, "E": 13, "F": 11, "G": 12, "H": 34, "I": 20, "J": 40}
COVER_WIDTHS = {"A": 34, "B": 50}
