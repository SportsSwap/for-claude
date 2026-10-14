"""figures.csv, cgt_events.csv, prefill.json and prior_year.csv.

figures.csv is the confirm step: the preparer opens it in Excel, corrects
figures, adds manual ones and marks them confirmed. Reading is forgiving of
what Excel does to a CSV (BOM, dd/mm/yyyy dates, $ and commas in amounts,
yes/no in place of Y/N). Writing always goes through the output guard.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from .dates import parse_date
from .labels import LabelDef, figure_allowed
from .models import Figure, PrefillLine
from .money import parse_amount
from .privacy.guard import atomic_write_text, check_rows, check_value

FIGURE_COLUMNS = ["figure_id", "label_key", "description", "amount", "date", "doc_id", "page", "method",
                  "confirmed", "substantiated", "notes"]
CGT_COLUMNS = ["event_id", "asset", "acquired", "disposed", "proceeds", "cost_base", "doc_id", "page", "confirmed"]
PRIOR_COLUMNS = ["label_key", "amount"]
METHODS = ("parser", "manual", "xero")

_TRUE = {"y", "yes", "true", "1"}
_FALSE = {"n", "no", "false", "0", ""}
_DOC_ID = re.compile(r"^D\d{3,}$")
_FIG_ID = re.compile(r"^F(\d+)$")


class FiguresError(Exception):
    pass


@dataclass(frozen=True)
class CgtEvent:
    event_id: str
    asset: str
    acquired: date
    disposed: date
    proceeds: Decimal
    cost_base: Decimal
    doc_id: str | None
    page: int | None
    confirmed: bool


# --- helpers -----------------------------------------------------------------------

def _yes_no(raw: str, *, blank: bool | None) -> bool | None:
    value = (raw or "").strip().lower()
    if value == "":
        return blank
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"expected Y or N, got {raw!r}")


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _blank(row: dict[str, str]) -> bool:
    return not any((v or "").strip() for v in row.values() if isinstance(v, str))


def _write_csv(path: Path, columns: list[str], rows: list[list[str]], location: str) -> None:
    check_rows(rows, location)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(columns)
    writer.writerows(rows)
    atomic_write_text(path, buf.getvalue(), location, prechecked=True)


def _fmt_bool(value: bool | None) -> str:
    return "" if value is None else ("Y" if value else "N")


def _figure_row(f: Figure) -> list[str]:
    return [f.figure_id, f.label_key, f.description, str(f.amount), f.date.isoformat() if f.date else "",
            f.doc_id or "", "" if f.page is None else str(f.page), f.method, _fmt_bool(f.confirmed),
            _fmt_bool(f.substantiated), f.notes]


# --- figures.csv --------------------------------------------------------------------

def _parse_figure(row: dict[str, str], labels: dict[str, LabelDef]) -> Figure:
    get = lambda k: (row.get(k) or "").strip()  # noqa: E731
    key = get("label_key")
    if key not in labels or not figure_allowed(labels[key]):
        raise ValueError(f"unknown label_key {key!r}")
    raw_date = get("date")
    when = parse_date(raw_date) if raw_date else None
    if raw_date and when is None:
        raise ValueError(f"bad date {raw_date!r}")
    doc_id = get("doc_id") or None
    if doc_id and not _DOC_ID.match(doc_id):
        raise ValueError(f"bad doc_id {doc_id!r} (expected D001 style)")
    raw_page = get("page")
    if raw_page and not raw_page.isdigit():
        raise ValueError(f"bad page {raw_page!r}")
    method = get("method").lower() or "manual"
    if method not in METHODS:
        raise ValueError(f"bad method {method!r}")
    try:
        amount = parse_amount(get("amount"))
    except ValueError:
        raise ValueError(f"bad amount {get('amount')!r}") from None
    return Figure(figure_id=get("figure_id"), label_key=key, description=get("description"), amount=amount,
                  date=when, doc_id=doc_id, page=int(raw_page) if raw_page else None, method=method,
                  confirmed=bool(_yes_no(get("confirmed"), blank=False)),
                  substantiated=_yes_no(get("substantiated"), blank=None), notes=get("notes"))


def _next_id(ids: list[str]) -> int:
    numbers = [int(m.group(1)) for i in ids if (m := _FIG_ID.match(i or ""))]
    return max(numbers, default=0) + 1


def read_figures(path: Path, labels: dict[str, LabelDef]) -> tuple[list[Figure], list[str]]:
    """Valid figures, plus one error per bad row ("row 7: ...", Excel row numbers)."""
    rows = _rows(path)
    if rows and set(FIGURE_COLUMNS) - set(rows[0].keys()):
        return [], [f"missing columns: {', '.join(sorted(set(FIGURE_COLUMNS) - set(rows[0].keys())))}"]
    figures, errors = [], []
    next_id = _next_id([r.get("figure_id", "") for r in rows])
    for excel_row, row in enumerate(rows, start=2):
        if _blank(row):
            continue
        try:
            fig = _parse_figure(row, labels)
        except ValueError as exc:
            errors.append(f"row {excel_row}: {exc}")
            continue
        if not fig.figure_id:
            fig.figure_id = f"F{next_id:04d}"
            next_id += 1
        figures.append(fig)
    return figures, errors


def write_figures(path: Path, figures: list[Figure]) -> None:
    _write_csv(path, FIGURE_COLUMNS, [_figure_row(f) for f in figures], path.name)


def append_figures(path: Path, new: list[Figure]) -> list[Figure]:
    """Append new figures with fresh ids. Existing rows are kept exactly as the user left them."""
    existing = _rows(path)
    next_id = _next_id([r.get("figure_id", "") for r in existing])
    assigned = []
    for f in new:
        f.figure_id = f"F{next_id:04d}"
        next_id += 1
        assigned.append(f)
    rows = [[r.get(c, "") or "" for c in FIGURE_COLUMNS] for r in existing] + [_figure_row(f) for f in assigned]
    _write_csv(path, FIGURE_COLUMNS, rows, path.name)
    return assigned


# --- cgt_events.csv ------------------------------------------------------------------

def read_cgt(path: Path) -> tuple[list[CgtEvent], list[str]]:
    events, errors = [], []
    for excel_row, row in enumerate(_rows(path), start=2):
        if _blank(row):
            continue
        get = lambda k: (row.get(k) or "").strip()  # noqa: E731
        try:
            acquired, disposed = parse_date(get("acquired")), parse_date(get("disposed"))
            if not acquired or not disposed:
                raise ValueError("acquired and disposed dates are required")
            page = get("page")
            events.append(CgtEvent(
                event_id=get("event_id") or f"C{excel_row - 1:03d}", asset=get("asset"), acquired=acquired,
                disposed=disposed, proceeds=parse_amount(get("proceeds")), cost_base=parse_amount(get("cost_base")),
                doc_id=get("doc_id") or None, page=int(page) if page.isdigit() else None,
                confirmed=bool(_yes_no(get("confirmed"), blank=False))))
        except ValueError as exc:
            errors.append(f"row {excel_row}: {exc}")
    return events, errors


# --- prefill.json and prior_year.csv -----------------------------------------------------

def read_prefill(path: Path) -> list[PrefillLine]:
    if not path.exists():
        return []
    return [PrefillLine(d["label_key"], d["payer"], Decimal(d["amount"]), d["doc_id"], int(d["page"]))
            for d in json.loads(path.read_text(encoding="utf-8"))]


def append_prefill(path: Path, lines: list[PrefillLine]) -> None:
    data = [{"label_key": p.label_key, "payer": p.payer, "amount": str(p.amount), "doc_id": p.doc_id, "page": p.page}
            for p in read_prefill(path) + list(lines)]
    check_value(data, path.name)
    atomic_write_text(path, json.dumps(data, indent=2), path.name, prechecked=True)


def read_prior_year(path: Path) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for row in _rows(path):
        key = (row.get("label_key") or "").strip()
        if key:
            out[key] = out.get(key, Decimal("0")) + parse_amount(row.get("amount") or "0")
    return out


def write_header_files(ws) -> None:
    """Empty figures.csv and cgt_events.csv with headers, for a new client."""
    if not ws.figures_csv.exists():
        _write_csv(ws.figures_csv, FIGURE_COLUMNS, [], "figures.csv")
    if not ws.cgt_csv.exists():
        _write_csv(ws.cgt_csv, CGT_COLUMNS, [], "cgt_events.csv")
