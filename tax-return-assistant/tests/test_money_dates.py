from datetime import date
from decimal import Decimal

import pytest

from tra.dates import days_in_fy, find_doc_date, fy_bounds, fy_label, parse_date
from tra.money import parse_amount, round_cents, truncate_dollars


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1,234.56", "1234.56"),
        ("$1,234.56", "1234.56"),
        ("1234.5", "1234.5"),
        ("(1,234.56)", "-1234.56"),
        ("-1234.56", "-1234.56"),
        (" 85000 ", "85000"),
        ("$ 412.35", "412.35"),
    ],
)
def test_parse_amount_variants(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["abc", "", "1.2.3", "$"])
def test_parse_amount_rejects(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


def test_round_and_truncate():
    assert round_cents(Decimal("2.345")) == Decimal("2.35")
    assert round_cents(Decimal("2.344")) == Decimal("2.34")
    assert truncate_dollars(Decimal("45000.99")) == Decimal("45000")
    assert truncate_dollars(Decimal("-10.5")) == Decimal("-10")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-03-24", date(2026, 3, 24)),
        ("24/03/2026", date(2026, 3, 24)),
        ("4/3/26", date(2026, 3, 4)),
        ("24 March 2026", date(2026, 3, 24)),
        ("24 Mar 2026", date(2026, 3, 24)),
        ("nonsense", None),
        ("31/02/2026", None),
    ],
)
def test_parse_date_variants(raw, expected):
    assert parse_date(raw) == expected


def test_find_doc_date():
    assert find_doc_date("Statement date: 24/03/2026") == date(2026, 3, 24)
    assert find_doc_date("Period 1 July 2025 to 30 June 2026") == date(2026, 6, 30)
    assert find_doc_date("Payment date 24 March 2026\nPeriod 1 July 2025 to 30 June 2026") == date(2026, 3, 24)
    assert find_doc_date("Period ending 30/06/2026") == date(2026, 6, 30)
    assert find_doc_date("No dates here") is None


def test_fy():
    assert fy_label(2026) == "FY2026"
    assert fy_bounds(2026) == (date(2025, 7, 1), date(2026, 6, 30))
    assert days_in_fy(2026) == 365
    assert days_in_fy(2024) == 366
