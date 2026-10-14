from datetime import date
from decimal import Decimal

import pytest

from tra.demo import build_demo_documents
from tra.ingest.extractors import get_extractor
from tra.ingest.readers import load


@pytest.fixture
def demo(tmp_path):
    return build_demo_documents(tmp_path / "inbox")


def _extract(doc_type, path, doc_id="D001"):
    return get_extractor(doc_type).extract(load(path).redacted, doc_id)


def test_rental(demo):
    result = _extract("RENTSTMT", demo.paths["rental"])
    gross = [f for f in result.figures if f.label_key == "rent.gross"]
    other = [f for f in result.figures if f.label_key == "rent.other"]
    assert [f.amount for f in gross] == [Decimal("26000.00")]
    assert len(other) == 4
    assert sum(f.amount for f in other) == Decimal("5340.00")
    assert {f.description for f in other} >= {"Management fees", "Council rates"}
    assert result.parse_status == "parsed"
    assert result.doc_date == date(2026, 6, 30)


def test_rental_interest_line(tmp_path):
    from tra.privacy.redact import redact_pages
    rt = redact_pages(["Rental statement", "Total rent received 10,000.00", "Loan interest 3,000.00",
                       "Total expenses 3,000.00"])
    result = get_extractor("RENTSTMT").extract(rt, "D001")
    assert [(f.label_key, f.amount) for f in result.figures] == [
        ("rent.gross", Decimal("10000.00")), ("rent.interest", Decimal("3000.00"))]


def test_phi_periods(demo):
    result = _extract("PHI", demo.paths["phi"])
    assert {f.label_key: f.amount for f in result.figures} == {
        "phi.premiums_p1": Decimal("1800.00"),
        "phi.rebate_p1": Decimal("437.18"),
        "phi.premiums_p2": Decimal("600.00"),
        "phi.rebate_p2": Decimal("144.71"),
    }
    assert all("Medicare" not in f.description and "REDACTED" not in f.description for f in result.figures)
    assert all("benefit code 30" in f.notes for f in result.figures)
    assert result.parse_status == "parsed"


def test_receipt_substantiated(demo):
    result = _extract("RECEIPT", demo.paths["receipt_laptop"])
    [fig] = result.figures
    assert fig.amount == Decimal("1499.00")
    assert fig.label_key == "ded.d5"
    assert fig.substantiated is True
    assert fig.date == date(2025, 8, 12)
    assert fig.description == "OFFICEWORKS: Laptop computer"
    assert result.parse_status == "partial"


def test_receipt_without_date_not_substantiated(demo):
    result = _extract("RECEIPT", demo.paths["receipt_union"])
    [fig] = result.figures
    assert fig.amount == Decimal("520.00")
    assert fig.substantiated is None
    assert fig.date is None


def test_xero_pl_csv(tmp_path):
    csv = tmp_path / "pl.csv"
    csv.write_text(
        "Profit and Loss\nDemo Plumbing\nFor the year ended 30 June 2026\n"
        "Income\nSales,120000.00\nInterest Income,150.00\nTotal Income,120150.00\n"
        "Less Operating Expenses\nAdvertising,1200.00\nMotor Vehicle Expenses,3400.50\nRent,24000.00\n"
        "Total Operating Expenses,28600.50\nNet Profit,91549.50\n", encoding="utf-8")
    result = _extract("XEROPL", csv)
    assert [(f.label_key, f.description, f.amount) for f in result.figures] == [
        ("income.business_income", "Sales", Decimal("120000.00")),
        ("income.business_income", "Interest Income", Decimal("150.00")),
        ("income.business_expenses", "Advertising", Decimal("1200.00")),
        ("income.business_expenses", "Motor Vehicle Expenses", Decimal("3400.50")),
        ("income.business_expenses", "Rent", Decimal("24000.00")),
    ]
    assert result.parse_status == "parsed"


def test_xero_pl_unknown_section_partial(tmp_path):
    csv = tmp_path / "pl.csv"
    csv.write_text("Profit and Loss\nIncome\nSales,100.00\nMystery Section\nThing,5.00\n", encoding="utf-8")
    result = _extract("XEROPL", csv)
    assert result.parse_status == "partial"
    assert [f.description for f in result.figures] == ["Sales"]


def test_xero_other_exports_file_only(tmp_path):
    csv = tmp_path / "bs.csv"
    csv.write_text("Balance Sheet\nAccount code,Amount\n", encoding="utf-8")
    result = _extract("XEROBS", csv)
    assert result.figures == [] and result.parse_status == "parsed"


def test_other_document_not_marked_substantiated():
    from tra.privacy.redact import redact_pages
    rt = redact_pages(["CITY COUNCIL", "Rates notice", "Date: 01/02/2026", "Total 150.00"])
    [fig] = get_extractor("OTHER").extract(rt, "D001").figures
    assert fig.substantiated is None
