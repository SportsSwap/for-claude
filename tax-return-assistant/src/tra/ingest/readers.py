"""Turn a file into redacted pages.

Raw text exists only inside :func:`load` and goes straight to the redactor.
Nothing else in the tool ever sees it.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pdfplumber

from ..privacy.redact import RedactedText, redact_pages
from .emails import EMAIL_TYPES, email_page_text, read_email

SUPPORTED = (".pdf", ".csv", ".xlsx", ".json", ".eml", ".msg")


class UnsupportedFile(Exception):
    def __init__(self, suffix: str):
        self.suffix = suffix
        super().__init__(f"Can't read {suffix or 'files without an extension'} files. Supported: {', '.join(SUPPORTED)}")


@dataclass(frozen=True)
class LoadedDocument:
    redacted: RedactedText
    sha256: str
    page_count: int
    image_only_pages: tuple[int, ...]
    suffix: str


def _pdf_pages(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def _xlsx_pages(path: Path) -> list[str]:
    """One page per sheet. Rows are CSV (cells holding commas are quoted); empty rows stay as empty
    lines, so a line number is the row number Excel shows."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        pages = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(min_row=1, values_only=True):
                cells = ["" if v is None else str(v) for v in row]
                while cells and not cells[-1]:
                    cells.pop()
                rows.append(cells)
            while rows and not rows[-1]:
                rows.pop()
            out = io.StringIO()
            writer = csv.writer(out, lineterminator="\n")
            for cells in rows:
                if cells:
                    writer.writerow(cells)
                else:
                    out.write("\n")
            pages.append(out.getvalue())
        return pages or [""]
    finally:
        wb.close()


def _text_file(path: Path) -> str:
    """UTF-8 (with or without Excel's marker), else the Windows encoding older Excel saves CSV files in."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def load(path: Path) -> LoadedDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise UnsupportedFile(suffix)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if suffix == ".pdf":
        raw = _pdf_pages(path)
    elif suffix == ".xlsx":
        raw = _xlsx_pages(path)
    elif suffix in EMAIL_TYPES:
        raw = [email_page_text(read_email(path))]
    else:
        raw = [_text_file(path)]
    image_only = tuple(i for i, page in enumerate(raw, start=1) if not page.strip()) if suffix == ".pdf" else ()
    redacted = redact_pages(raw)
    del raw
    return LoadedDocument(redacted=redacted, sha256=sha256, page_count=len(redacted.pages),
                          image_only_pages=image_only, suffix=suffix)
