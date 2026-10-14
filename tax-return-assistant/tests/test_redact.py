import pytest

from tra.privacy import detectors
from tra.privacy.redact import RedactedText, RedactionError, redact_pages, redact_text


def test_tfn_checksum_spaced_and_hyphenated(make_tfn):
    t = make_tfn()
    for sep in (" ", "-"):
        result = redact_pages([f"TFN: {t[:3]}{sep}{t[3:6]}{sep}{t[6:]}"])
        assert result.pages[0] == "TFN: [TFN REDACTED]"
        assert result.counts["TFN"] == 1


def test_tfn_checksum_without_context(make_tfn):
    t = make_tfn()
    out = redact_text(f"Please quote {t[:3]} {t[3:6]} {t[6:]} on all correspondence")
    assert out == "Please quote [TFN REDACTED] on all correspondence"


def test_tfn_eight_digit(make_tfn):
    t = make_tfn(8)
    assert redact_text(f"Old number {t} here") == "Old number [TFN REDACTED] here"


def test_tfn_context_bad_checksum():
    assert redact_text("Tax file number 123 456 789") == "Tax file number [TFN REDACTED]"


def test_tfn_split_across_line(make_tfn):
    t = make_tfn()
    out = redact_text(f"TFN {t[:3]} {t[3:6]}\n{t[6:]}")
    assert out == "TFN [TFN REDACTED]"
    assert t[6:] not in out


def test_medicare_with_irn_and_line_break(make_medicare):
    m = make_medicare()
    out = redact_text(f"Medicare card {m[:4]} {m[4:9]}\n{m[9]}")
    assert out == "Medicare card [MEDICARE REDACTED]"


def test_medicare_context_bad_checksum():
    assert redact_text("Medicare no. 1234 56789 0") == "Medicare no. [MEDICARE REDACTED]"


def test_card_luhn():
    assert redact_text("Card 4111 1111 1111 1111") == "Card [CARD REDACTED]"
    assert redact_text("Card XXXX XXXX XXXX 1234") == "Card XXXX XXXX XXXX 1234"


def test_bsb_and_account():
    out = redact_text("BSB 062-000 Account number 1234 5678")
    assert out == "BSB [BSB REDACTED] Account number [ACCOUNT REDACTED]"


def test_bsb_without_keyword():
    assert redact_text("Paid to 062-000 12345678") .startswith("Paid to [BSB REDACTED]")


def test_licence_and_passport():
    assert redact_text("Driver licence no. 12345678") == "Driver licence no. [LICENCE REDACTED]"
    assert redact_text("Passport PA1234567") == "Passport [PASSPORT REDACTED]"


@pytest.mark.parametrize(
    "text",
    [
        "$123,456.78",
        "Total 85,000.00",
        "Phone 02 9876 5432",
        "Mobile 0412 345 678",
        "24/03/2026",
        "ABN 51 824 753 556",
        "Invoice INV-2026-0042",
        "Date 2026-03-24",
        "Ingested 2026-10-14T05:49:00+10:00",
        "Interest 412.35",
    ],
)
def test_not_redacted(text):
    assert redact_text(text) == text


def test_abn_inside_text_not_split_into_tfn():
    text = "Supplier 51824753556 tax invoice"
    assert redact_text(text) == text


def test_counts_by_type(make_tfn):
    t = make_tfn()
    result = redact_pages([f"TFN {t}", "Card 4111 1111 1111 1111 and TFN 123 456 789"])
    assert dict(result.counts) == {"TFN": 2, "CARD": 1}
    assert result.text == f"TFN [TFN REDACTED]\n\f\nCard [CARD REDACTED] and TFN [TFN REDACTED]"


def test_redacted_text_cannot_be_built_directly():
    with pytest.raises(TypeError):
        RedactedText(pages=("x",), counts={})


def test_detector_exception_fails_closed(monkeypatch, make_tfn):
    def boom(*_args, **_kwargs):
        raise ValueError("secret 123 456 789 leaked into an error")

    monkeypatch.setattr(detectors, "_numeric_matches", boom)
    t = make_tfn()
    with pytest.raises(RedactionError) as err:
        redact_pages([f"TFN {t} client SMITH"])
    assert t not in str(err.value)
    assert "SMITH" not in str(err.value)
    assert "123 456 789" not in str(err.value)
    assert err.value.__cause__ is None


def test_context_false_only_checksum(make_tfn):
    t = make_tfn()
    matches = detectors.find_sensitive(f"TFN 123 456 789 and {t} and BSB 062-000", context=False)
    assert [m.type for m in matches] == ["TFN"]


def test_two_labelled_tfns_on_one_page():
    out = redact_text("Your TFN 123 456 789\nSpouse TFN 987 654 321")
    assert out == "Your TFN [TFN REDACTED]\nSpouse TFN [TFN REDACTED]"


def test_identifiers_joined_by_underscores(make_tfn):
    t = make_tfn()
    assert redact_text(f"scan_{t}_final.pdf") == "scan_[TFN REDACTED]_final.pdf"
    assert redact_text("OTHER_4111111111111111_x") == "OTHER_[CARD REDACTED]_x"
    assert redact_text("SMIT01_FY2026_DIVSTMT_2026-03-24.pdf") == "SMIT01_FY2026_DIVSTMT_2026-03-24.pdf"
