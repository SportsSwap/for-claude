"""Shared fixtures.

Fake identifiers are generated in memory at test time and never committed. The
generators below are written from the published check-digit rules, separately
from ``tra.privacy.validators``, so they can catch a bug in either.
"""

import random

import pytest

_TFN_WEIGHTS = {9: (1, 4, 3, 7, 5, 8, 6, 9, 10), 8: (10, 7, 8, 4, 6, 3, 5, 1)}
_MEDICARE_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9)


def _tfn(rng: random.Random, length: int) -> str:
    weights = _TFN_WEIGHTS[length]
    while True:
        digits = [rng.randint(0, 9) for _ in range(length)]
        if sum(d * w for d, w in zip(digits, weights)) % 11 == 0:
            return "".join(map(str, digits))


def _medicare(rng: random.Random, irn: bool = False) -> str:
    first8 = [rng.randint(2, 6)] + [rng.randint(0, 9) for _ in range(7)]
    check = sum(d * w for d, w in zip(first8, _MEDICARE_WEIGHTS)) % 10
    issue = rng.randint(1, 9)
    tail = [check, issue] + ([rng.randint(1, 9)] if irn else [])
    return "".join(map(str, first8 + tail))


def _card(rng: random.Random, length: int = 16) -> str:
    body = [4] + [rng.randint(0, 9) for _ in range(length - 2)]
    total = 0
    for i, d in enumerate(reversed(body)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return "".join(map(str, body + [(10 - total % 10) % 10]))


@pytest.fixture
def rng() -> random.Random:
    return random.Random(20260630)


@pytest.fixture
def make_tfn(rng):
    return lambda length=9: _tfn(rng, length)


@pytest.fixture
def make_medicare(rng):
    return lambda irn=False: _medicare(rng, irn)


@pytest.fixture
def make_card(rng):
    return lambda length=16: _card(rng, length)


@pytest.fixture
def make_pdf(tmp_path):
    """Write a simple PDF: one list of text lines per page (None = image-only page)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    def build(name: str, pages: list[list[str] | None]):
        path = tmp_path / name
        c = canvas.Canvas(str(path), pagesize=A4)
        for lines in pages:
            if lines is None:
                c.rect(100, 100, 200, 200, fill=1)
            else:
                y = 800
                for line in lines:
                    c.drawString(50, y, line)
                    y -= 16
            c.showPage()
        c.save()
        return path

    return build
