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


# Share registries (Link/MUFG, Computershare) set the amounts out as a table. Invented companies and amounts.
REGISTRY_TABLE = [
    "Payment Advice",
    "All Registry communications to:",
    "SAMPLE MINING LIMITED",
    "DIVIDEND STATEMENT",
    "Payment Date: 20 March 2026",
    "Record Date: 20 February 2026",
    "Security Description Dividend Rate Participating Unfranked Franked Total Franking",
    "per Share Shares Amount Amount Payment Credit",
    "SMX - FULLY PAID ORDINARY SHARES $0.12 1,500 $30.00 $150.00 $180.00 $64.29",
    "Less Withholding Tax $0.00",
    "Net Amount AUD 180.00",
    "FRANKING INFORMATION Franked Rate per Share $0.10",
    "Franking Percentage 83.33%",
    "Company Tax Rate 30%",
]


def _dividends(lines):
    return get_extractor("DIVSTMT").extract(redact_pages(["\n".join(lines)]), "D001")


def test_dividends_registry_table():
    result = _dividends(REGISTRY_TABLE)
    assert _totals(result.figures) == {
        "income.div_unfranked": Decimal("30.00"),
        "income.div_franked": Decimal("150.00"),
        "income.franking_credit": Decimal("64.29"),
    }
    assert result.parse_status == "parsed"
    assert result.doc_date == date(2026, 3, 20)
    assert all(f.description.startswith("SAMPLE MINING LIMITED") for f in result.figures)


def test_dividends_table_columns_in_another_order():
    result = _dividends([
        "ACME RESOURCES LTD",
        "Dividend Statement",
        "Payment date 15 April 2026",
        "Class Description Amount per Security Number of Securities Franked Amount Unfranked Amount Gross Payment",
        "Ordinary Shares 50 cents 1,000 $500.00 $0.00 $500.00",
        "Net Payment $500.00",
        "Franking Credit $214.29",
    ])
    assert _totals(result.figures) == {
        "income.div_franked": Decimal("500.00"),
        "income.franking_credit": Decimal("214.29"),
    }
    assert result.parse_status == "parsed"


def test_dividends_table_that_does_not_add_up_is_left_for_manual_entry():
    lines = [line.replace("$180.00 $64.29", "$200.00 $64.29") for line in REGISTRY_TABLE]
    result = _dividends(lines)
    assert result.figures == []
    assert result.parse_status == "manual_needed"


def test_dividends_withholding_tax_is_flagged_to_confirm():
    lines = [line.replace("Less Withholding Tax $0.00", "Less Withholding Tax $47.00") for line in REGISTRY_TABLE]
    withheld = [f for f in _dividends(lines).figures if f.label_key == "income.div_tfn_withheld"]
    assert [f.amount for f in withheld] == [Decimal("47.00")]
    assert "confirm" in withheld[0].notes

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
