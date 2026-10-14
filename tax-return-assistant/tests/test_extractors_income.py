from datetime import date
from decimal import Decimal

import pytest

from tra.demo import build_demo_documents
from tra.ingest.extractors import get_extractor
from tra.ingest.readers import load
from tra.privacy.redact import redact_pages


@pytest.fixture
def demo(tmp_path):
    return build_demo_documents(tmp_path / "inbox")


def _extract(doc_type, path, doc_id="D001"):
    return get_extractor(doc_type).extract(load(path).redacted, doc_id)


def _totals(figures):
    out = {}
    for f in figures:
        out[f.label_key] = out.get(f.label_key, Decimal("0")) + f.amount
    return out


def test_prefill_extracts_lines(demo):
    result = _extract("PREFILL", demo.paths["prefill"])
    assert {line.label_key: line.amount for line in result.prefill} == {
        "income.salary": Decimal("85000.00"),
        "income.salary_tax_withheld": Decimal("19000.00"),
        "income.interest": Decimal("412.35"),
        "income.div_franked": Decimal("1200.00"),
        "income.franking_credit": Decimal("514.29"),
        "phi.premiums_total": Decimal("2400.00"),
        "phi.rebate_total": Decimal("581.89"),
    }
    assert all(line.doc_id == "D001" and line.page == 1 for line in result.prefill)
    assert sorted(f.label_key for f in result.figures) == sorted(
        ["income.salary", "income.salary_tax_withheld", "income.interest", "income.div_franked", "income.franking_credit"])
    assert all(f.notes == "prefill" and not f.confirmed and f.method == "parser" for f in result.figures)
    assert result.parse_status == "parsed"
    assert result.doc_date == date(2026, 7, 15)


def test_prefill_help_indicator_yes():
    rt = redact_pages(["Individual pre-fill report", "HELP  Debt balance indicator  Yes"])
    result = get_extractor("PREFILL").extract(rt, "D009")
    assert [(p.label_key, p.amount) for p in result.prefill] == [("help.indicator", Decimal("1"))]
    assert result.figures == []


def test_income_statement(demo):
    result = _extract("INCSTMT", demo.paths["income_statement"], "D002")
    assert _totals(result.figures) == {
        "income.salary": Decimal("85000.00"),
        "income.salary_tax_withheld": Decimal("19000.00"),
        "income.allowances": Decimal("1200.00"),
    }
    assert result.parse_status == "parsed"
    assert all(f.page == 1 and f.doc_id == "D002" and f.figure_id == "" for f in result.figures)
    assert all("ACME PTY LTD" in f.description for f in result.figures)
    assert result.doc_date == date(2026, 6, 30)


def test_interest_and_doc_date(demo):
    result = _extract("BANKSTMT", demo.paths["bank_interest"])
    assert _totals(result.figures) == {"income.interest": Decimal("412.35")}
    assert result.doc_date == date(2026, 6, 30)
    assert result.parse_status == "parsed"
    assert get_extractor("INTSTMT") is get_extractor("BANKSTMT")


def test_dividends(demo):
    result = _extract("DIVSTMT", demo.paths["dividend_bhp"])
    assert _totals(result.figures) == {
        "income.div_franked": Decimal("1200.00"),
        "income.franking_credit": Decimal("514.29"),
    }
    assert result.doc_date == date(2026, 3, 24)
    assert result.parse_status == "parsed"
    assert all(f.date == date(2026, 3, 24) for f in result.figures)


def test_extractor_rejects_raw_str():
    with pytest.raises(TypeError):
        get_extractor("DIVSTMT").extract("raw", "D001")


def test_unparseable_is_manual_needed():
    rt = redact_pages(["Dividend statement", "Franking credit information enclosed"])
    result = get_extractor("DIVSTMT").extract(rt, "D001")
    assert result.parse_status == "manual_needed"
    assert result.figures == []


def test_partial_income_statement():
    rt = redact_pages(["Income statement", "Gross payments 50,000.00"])
    result = get_extractor("INCSTMT").extract(rt, "D001")
    assert result.parse_status == "partial"
    assert _totals(result.figures) == {"income.salary": Decimal("50000.00")}


def test_demo_documents_carry_identifiers(demo):
    """The demo must exercise redaction: identifiers are in the PDFs, not in the extracted text."""
    loaded = load(demo.paths["prefill"])
    assert loaded.redacted.counts["TFN"] == 1
    assert "123 456 789" not in loaded.redacted.text
    assert load(demo.paths["bank_interest"]).redacted.counts == {"BSB": 1, "ACCOUNT": 1}
    assert load(demo.paths["receipt_laptop"]).redacted.counts == {"CARD": 1}
    assert load(demo.paths["phi"]).redacted.counts == {"MEDICARE": 1}
