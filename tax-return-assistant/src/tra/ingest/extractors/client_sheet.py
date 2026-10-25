"""Clients' own spreadsheets (.xlsx and .csv that aren't Xero exports or another known type).

Each sheet is one page of CSV text (readers.py). On each sheet: find the header row, the amount and
description columns (and a category and date column if there are any), then read every row with an
amount. A row whose words point to exactly one label (words.py) becomes an unconfirmed figure with a
suggested label; any other row is listed in Things to check rather than guessed. A sheet that looks
like a list of share sales gives no figures: those are CGT events, entered by hand.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime

from ...dates import parse_date
from ...labels import load_labels
from ...money import format_dollars, parse_amount, round_cents
from .base import ExtractResult, doc_date, figure, require_redacted
from .words import load_sheet_words, match_labels

MAX_FIGURES = 200
MAX_DOUBTS = 20
HEADER_ROWS = 10

_AMOUNT_HEADS = ("amount", "total", "cost", "paid", "value", "price", "$", "aud")
_DESC_HEADS = ("description", "item", "details", "detail", "expense", "payee", "supplier", "particulars", "what")
_CAT_HEADS = ("category", "type", "group")
_DATE_HEADS = ("date", "when")
_SALE_WORDS = re.compile(r"\b(?:bought|acquired|sold|disposed|units|cost base|proceeds)\b", re.I)
# A running balance, or debit and credit columns: a bank export, not a list the client made.
_BANK = re.compile(r"\bbalance\b|\bwithdrawals?\b|\bdeposits?\b", re.I)
# A total repeats the rows above it, wherever the word is ("Donations total").
_TOTAL = re.compile(r"\b(?:sub-?\s?totals?|grand totals?|totals?|sum|balance)\b", re.I)


def _amount(raw: str):
    raw = (raw or "").strip()
    try:
        return round_cents(parse_amount(raw[1:] if raw.startswith("+") else raw))  # banks write credits as +3.21
    except ValueError:
        return None


def _date(raw: str) -> date | None:
    raw = (raw or "").strip()
    try:
        return datetime.fromisoformat(raw).date() if re.match(r"^\d{4}-\d{2}-\d{2}", raw) else parse_date(raw)
    except ValueError:
        return None


def _is_text(cell: str) -> bool:
    return bool(cell) and _amount(cell) is None and _date(cell) is None


def _header_index(rows: list[list[str]]) -> int | None:
    for i, row in enumerate(rows[:HEADER_ROWS]):
        filled = [c for c in row if c]
        if len(filled) >= 2 and all(_is_text(c) for c in filled):
            return i
    return None


def _find(header: list[str], heads: tuple[str, ...], taken: set[int]) -> int | None:
    for head in heads:
        for i, cell in enumerate(header):
            words = cell.lower()
            if i not in taken and (head in re.findall(r"[a-z]+|\$", words) or (head == "$" and "$" in words)):
                return i
    return None


def _columns(rows: list[list[str]], header: list[str] | None) -> dict[str, int | None]:
    cols: dict[str, int | None] = {}
    taken: set[int] = set()
    for name, heads in (("amount", _AMOUNT_HEADS), ("date", _DATE_HEADS), ("cat", _CAT_HEADS), ("desc", _DESC_HEADS)):
        cols[name] = _find(header, heads, taken) if header else None
        if cols[name] is not None:
            taken.add(cols[name])
    width = max((len(r) for r in rows), default=0)

    def most(test, exclude):
        counts = [(sum(1 for r in rows if i < len(r) and test(r[i])), i) for i in range(width) if i not in exclude]
        best = max(counts, default=(0, None))
        return best[1] if best[0] else None

    if cols["amount"] is None:
        cols["amount"] = most(lambda c: _amount(c) is not None and _date(c) is None, taken)
        if cols["amount"] is not None:
            taken.add(cols["amount"])
    if cols["desc"] is None:
        cols["desc"] = most(_is_text, taken)
    return cols


def _money_columns(rows: list[list[str]]) -> int:
    """How many columns hold an amount in most of the rows that have anything in them."""
    filled = [r for r in rows if any(r)]
    width = max((len(r) for r in filled), default=0)
    return sum(1 for i in range(width)
               if sum(1 for r in filled if i < len(r) and _amount(r[i]) is not None and _date(r[i]) is None)
               > len(filled) / 2)


def _cell(row: list[str], i: int | None) -> str:
    return row[i].strip() if i is not None and i < len(row) else ""


def _could_be(keys: list[str], labels) -> str:
    names = [labels[k].description.lower() if k in labels else k for k in keys]
    return ", ".join(names[:-1]) + " or " + names[-1]


class ClientSheetExtractor:
    doc_types = frozenset({"CLIENTXLS"})

    def extract(self, rt, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        words, labels = load_sheet_words(), load_labels()
        result = ExtractResult(doc_date=doc_date(rt))
        not_added: list[str] = []
        capped = False
        for sheet, page in enumerate(rt.pages, start=1):
            try:
                rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(page))]
            except csv.Error:
                not_added.insert(0, f"Sheet {sheet} couldn't be read as a table (a cell is too long or a quote isn't "
                                    "closed). Open it and enter its figures by hand.")
                continue
            head = _header_index(rows)
            header = rows[head] if head is not None else None
            heading = " ".join(header or [])
            if header and len(_SALE_WORDS.findall(heading)) >= 2:
                not_added.insert(0, f"Sheet {sheet} looks like a list of share sales, so no figures were taken "
                                    "from it. Enter them as CGT events.")
                continue
            if header and (_BANK.search(heading) or re.search(r"\bdebit", heading, re.I) and re.search(
                    r"\bcredit", heading, re.I)):
                not_added.insert(0, f"Sheet {sheet} looks like a bank statement or transaction list, so no figures "
                                    "were taken from it. Pick out the rows that matter and enter them by hand.")
                continue
            body = rows[head + 1:] if head is not None else rows
            if header is None and _money_columns(body) >= 2:  # amount and running balance, no header row
                not_added.insert(0, f"Sheet {sheet} looks like a bank statement or transaction list, so no figures "
                                    "were taken from it. Pick out the rows that matter and enter them by hand.")
                continue
            cols = _columns(body, header)
            for n, row in enumerate(rows[(head + 1) if head is not None else 0:],
                                    start=(head + 2) if head is not None else 1):
                value = _amount(_cell(row, cols["amount"]))
                desc, cat = _cell(row, cols["desc"]), _cell(row, cols["cat"])
                if value is None or value == 0 or not (desc or cat) or _TOTAL.search(f"{cat} {desc}"):
                    continue
                text = f"{cat}: {desc}" if cat and desc else (desc or cat)
                where = f"Sheet {sheet} row {n}: {text}"
                keys = match_labels(f"{cat} {desc}", words)
                if len(keys) != 1:
                    why = "has no label" if not keys else f"could be {_could_be(keys, labels)}"
                    not_added.append(f"{where} {format_dollars(value)} {why}, so it wasn't added.")
                    continue
                if len(result.figures) >= MAX_FIGURES:
                    capped = True
                    continue
                result.figures.append(figure(keys[0], where[:120], value, doc_id, sheet,
                                             _date(_cell(row, cols["date"])), notes="suggested label"))
        if capped:
            result.doubts.append(f"Only the first {MAX_FIGURES} rows with amounts were read. Enter the rest by hand.")
        result.doubts += not_added[:MAX_DOUBTS]
        if len(not_added) > MAX_DOUBTS:
            result.doubts.append(f"And {len(not_added) - MAX_DOUBTS} more rows that weren't added.")
        result.parse_status = "partial" if result.figures else "manual_needed"
        return result
