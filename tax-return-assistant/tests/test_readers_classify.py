import pytest

from tra.ingest.classify import CATEGORIES, classify, load_doc_types
from tra.ingest.readers import UnsupportedFile, load
from tra.privacy.redact import redact_pages


def test_load_pdf_redacts_before_return(make_pdf):
    path = make_pdf("doc.pdf", [["Income statement", "TFN 123 456 789", "Gross payments 85,000.00"]])
    loaded = load(path)
    assert "[TFN REDACTED]" in loaded.redacted.text
    assert "123 456 789" not in loaded.redacted.text
    assert loaded.redacted.counts["TFN"] == 1
    assert loaded.page_count == 1
    assert loaded.suffix == ".pdf"


def test_load_image_only_page(make_pdf):
    path = make_pdf("scan.pdf", [["Page one text"], None])
    loaded = load(path)
    assert loaded.image_only_pages == (2,)
    assert loaded.page_count == 2


def test_load_csv_and_unsupported(tmp_path):
    csv = tmp_path / "pl.csv"
    csv.write_text("﻿Profit and Loss,Xero\nSales,1000.00\n", encoding="utf-8")
    loaded = load(csv)
    assert loaded.page_count == 1
    assert "Sales,1000.00" in loaded.redacted.text
    docx = tmp_path / "letter.docx"
    docx.write_bytes(b"x")
    with pytest.raises(UnsupportedFile):
        load(docx)


def test_sha256_stable(make_pdf):
    path = make_pdf("a.pdf", [["hello"]])
    assert load(path).sha256 == load(path).sha256
    assert len(load(path).sha256) == 64


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Individual pre-fill report Income year 2026", "PREFILL"),
        ("Tax return for individuals 2025 Return summary", "PRIOR"),
        ("Income statement 2026 Gross payments", "INCSTMT"),
        ("Dividend statement Franking credit 514.29", "DIVSTMT"),
        ("AMIT member annual statement interest 12.00", "MFUND"),
        ("Interest summary for the year", "INTSTMT"),
        ("Account statement Opening balance 10.00", "BANKSTMT"),
        ("Capital gains report 2026", "CGT"),
        ("Rental statement from your property manager", "RENTSTMT"),
        ("Private health insurance statement 2025-26", "PHI"),
        ("Profit and Loss Xero Demo Company", "XEROPL"),
        ("Balance Sheet Account code 200", "XEROBS"),
        ("Bank transactions export", "XEROBANK"),
        ("Chart of accounts", "XEROCOA"),
        ("TAX INVOICE Officeworks", "RECEIPT"),
        ("Something unrecognisable", "OTHER"),
    ],
)
def test_classify_examples(text, expected):
    assert classify(redact_pages([text]), load_doc_types()) == expected


def test_doc_types_categories_known():
    for doc_type in load_doc_types().values():
        assert doc_type.category in CATEGORIES


def test_classify_rejects_raw_text():
    with pytest.raises(TypeError):
        classify("Income statement", load_doc_types())
