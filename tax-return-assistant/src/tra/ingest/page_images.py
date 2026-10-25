"""Pictures of a PDF's scanned pages, for the AI reader. OFF unless the privacy officer approves them in Settings.

A picture can't be blanked out first, so TFNs, account numbers and names on those pages reach Anthropic too.
That's why it has its own switch, separate from the AI reader's. The pictures exist only in memory, on the way
to the AI reader: they are never written to any file.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pdfplumber

MAX_PAGE_IMAGES = 20  # a long scanned document sends its first 20 pages; the rest are entered by hand
RESOLUTION = 110  # dots per inch: an A4 page is about 910 x 1290 pixels, enough to read printed amounts
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # all of a document's pictures together, base64-encoded as they are sent
MAX_EDGE = 2000  # pixels on a picture's long side: a bigger page (a plan, an A3 sheet) is drawn smaller
JPEG_QUALITY = 70  # greyscale JPEG: printed amounts stay sharp at a fraction of a PNG's size

# A token is "ordinary" once the punctuation around it is stripped if it is a word (letters in any language, with
# an apostrophe or hyphen inside: tenant's, year-end, José, Müller), an amount or number ($1,234.56, -50.00, 5%,
# 1,234.56CR, 12.5k), a date (30/06/2026, or a bank's 01JUL25) or a short form (FY2025-26, Q1). A token that's only
# punctuation is left out of the count when it's one character (a dash, an ampersand) and counts as not ordinary
# when it's longer (~~, %$#@). OCR soup mixes letters, digits and symbols (Th3, br0wn).
_STRIP = "\"'()[]{}<>.,:;!?*"
_JOINS = re.compile(r"['’-]")
_NUMBER = re.compile(r"[-+]?\$?[-+]?\d[\d,]*(?:\.\d+)?(?:%|CR|DR|cr|dr|[kKmM])?")
_DATE = re.compile(r"\d{1,4}(?:[/.-]\d{1,4}){1,2}|\d{1,2}[A-Za-z]{3}\d{2,4}")
_SHORT = re.compile(r"(?:FY|fy)\d{2,4}(?:[-/]\d{2,4})?|[Qq][1-4]")


def _is_word(core: str) -> bool:
    return all(part.isalpha() for part in _JOINS.split(core))


def _ordinary(token: str) -> bool | None:
    """True for a word, amount, date or short form; False for anything else; None for a lone punctuation mark."""
    core = token.strip(_STRIP)
    if not core:
        return None if len(token) == 1 else False
    if len(core) == 1 and not core.isalnum():
        return None
    return bool(_is_word(core) or _NUMBER.fullmatch(core) or _DATE.fullmatch(core) or _SHORT.fullmatch(core))


def looks_garbled(text: str) -> bool:
    """Fewer than half of the page's tokens (split on whitespace) are ordinary words, amounts or dates."""
    marks = [m for m in (_ordinary(t) for t in text.split()) if m is not None]
    return bool(marks) and sum(marks) * 2 < len(marks)


def pages_wanted(loaded_text_pages, image_only_pages) -> list[int]:
    """Page numbers (from 1) with no text or garbled text, in page order: every page a picture would help."""
    scans = set(image_only_pages)
    return [n for n, text in enumerate(loaded_text_pages, start=1)
            if n in scans or not text.strip() or looks_garbled(text)]


def pages_to_send(loaded_text_pages, image_only_pages) -> list[int]:
    """The pages wanted, at most MAX_PAGE_IMAGES of them."""
    return pages_wanted(loaded_text_pages, image_only_pages)[:MAX_PAGE_IMAGES]


def _render_page(page, resolution: int) -> bytes:
    """One page as greyscale JPEG bytes, its long edge at most MAX_EDGE pixels."""
    longest = max(float(page.width), float(page.height)) / 72  # inches
    image = page.to_image(resolution=min(resolution, MAX_EDGE / longest) if longest else resolution).original
    image = image.convert("L")
    if max(image.size) > MAX_EDGE:  # rounding can leave a pixel over
        image.thumbnail((MAX_EDGE, MAX_EDGE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _base64_size(data: bytes) -> int:
    return 4 * ((len(data) + 2) // 3)


def render_pages(pdf_path: Path, pages, resolution: int = RESOLUTION) -> list[tuple[int, bytes]]:
    """(page number, JPEG bytes) for each page asked for, drawn in memory, until the pictures would come to more
    than MAX_IMAGE_BYTES once encoded; the pages after that aren't drawn."""
    out, total = [], 0
    with pdfplumber.open(pdf_path) as pdf:
        for n in pages:
            if not 1 <= n <= len(pdf.pages):
                continue
            data = _render_page(pdf.pages[n - 1], resolution)
            total += _base64_size(data)
            if total > MAX_IMAGE_BYTES:
                break
            out.append((n, data))
    return out
