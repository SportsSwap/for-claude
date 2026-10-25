"""Layout files: one settings file per layout Sawnx has learned, read by one shared reader. Made-up data only."""

from decimal import Decimal

import pytest

from tra.ingest.layouts import amount_words, load_layouts, match_layout, read_with_layout
from tra.privacy.redact import redact_pages

GOOD = """
name: SAMPLE BANK interest summary
doc_type: INTSTMT
match:
  all: ["sample bank", "interest summary"]
issuer: SAMPLE BANK
fields:
  - label: income.interest
    line: "Interest paid this financial year"
    description: interest
    required: true
  - label: income.interest_tfn_withheld
    contains: "tfn withholding"
    amount: first
    description: TFN withheld
added: "test"
"""


def _write(folder, name, text):
    folder.mkdir(exist_ok=True)
    (folder / f"{name}.yaml").write_text(text, encoding="utf-8")


def _rt(*lines, pages=None):
    return redact_pages(pages or ["\n".join(lines)])


@pytest.fixture
def layouts(tmp_path):
    _write(tmp_path / "layouts", "sample-bank-interest", GOOD)
    found, problems = load_layouts(tmp_path / "layouts")
    assert problems == []
    return found


def test_loads_a_layout(layouts):
    [layout] = layouts
    assert (layout.slug, layout.name, layout.doc_type, layout.issuer) == (
        "sample-bank-interest", "SAMPLE BANK interest summary", "INTSTMT", "SAMPLE BANK")


def test_matches_on_all_words_any_case(layouts):
    assert match_layout(_rt("Sample Bank Ltd", "Interest Summary 2025-26"), layouts).slug == "sample-bank-interest"
    assert match_layout(_rt("Sample Bank Ltd", "Account statement"), layouts) is None


def test_any_words(tmp_path):
    _write(tmp_path / "l", "a", GOOD.replace('all: ["sample bank", "interest summary"]',
                                             'all: ["sample bank"]\n  any: ["interest summary", "interest statement"]'))
    found, _ = load_layouts(tmp_path / "l")
    assert match_layout(_rt("SAMPLE BANK", "Interest statement"), found)
    assert match_layout(_rt("SAMPLE BANK", "Account statement"), found) is None


def test_most_specific_layout_wins(tmp_path):
    _write(tmp_path / "l", "general", GOOD.replace('all: ["sample bank", "interest summary"]', 'all: ["sample bank"]')
           .replace("SAMPLE BANK interest summary", "SAMPLE BANK anything"))
    _write(tmp_path / "l", "specific", GOOD)
    found, _ = load_layouts(tmp_path / "l")
    assert match_layout(_rt("SAMPLE BANK", "Interest summary"), found).slug == "specific"


def test_reads_fields(layouts):
    rt = _rt(pages=["SAMPLE BANK\nInterest summary", "Interest paid this financial year $1,234.50 $9.00\n"
                                                      "Less TFN withholding 12.00 0.00"])
    result = read_with_layout(rt, layouts[0], "D007")
    assert [(f.label_key, f.amount, f.page, f.description, f.confirmed, f.method) for f in result.figures] == [
        ("income.interest", Decimal("9.00"), 2, "SAMPLE BANK – interest", False, "parser"),
        ("income.interest_tfn_withheld", Decimal("12.00"), 2, "SAMPLE BANK – TFN withheld", False, "parser")]
    assert result.parse_status == "parsed" and result.doubts == []


def test_line_match_ignores_spaces_and_case(layouts):
    rt = _rt("SAMPLE BANK", "Interest summary", "INTEREST   PAID this financial   year   400.00")
    assert [f.amount for f in read_with_layout(rt, layouts[0], "D1").figures] == [Decimal("400.00")]


def test_required_field_missing_is_a_doubt(layouts):
    result = read_with_layout(_rt("SAMPLE BANK", "Interest summary", "Nothing here"), layouts[0], "D1")
    assert result.figures == [] and result.doubts == ["Didn't find the interest."]
    assert result.parse_status == "manual_needed"


def test_every_line(tmp_path):
    _write(tmp_path / "l", "monthly", GOOD.replace('    line: "Interest paid this financial year"\n'
                                                   '    description: interest\n    required: true\n',
                                                   '    line: "Interest credit"\n    description: interest\n'
                                                   '    every: true\n'))
    [layout], _ = load_layouts(tmp_path / "l")
    rt = _rt("SAMPLE BANK", "Interest summary", "Interest credit 1.10", "Deposit 50.00", "Interest credit 2.20")
    assert [f.amount for f in read_with_layout(rt, layout, "D1").figures] == [Decimal("1.10"), Decimal("2.20")]


def test_zero_amount_not_added(layouts):
    rt = _rt("SAMPLE BANK", "Interest summary", "Interest paid this financial year 0.00")
    result = read_with_layout(rt, layouts[0], "D1")
    assert result.figures == [] and result.doubts == []


@pytest.mark.parametrize("broken, problem", [
    (GOOD.replace("doc_type: INTSTMT", "doc_type: NOPE"), "doc_type NOPE"),
    (GOOD.replace("label: income.interest\n", "label: income.nope\n"), "income.nope"),
    (GOOD.replace("label: income.interest\n", "label: phi.premiums_total\n"), "phi.premiums_total"),
    (GOOD.replace('    line: "Interest paid this financial year"\n', ""), "line or contains"),
    ("name: [unclosed", "isn't valid"),
    (GOOD.replace('  all: ["sample bank", "interest summary"]\n', "  all: []\n"), "match"),
])
def test_bad_files_are_reported_and_skipped(tmp_path, broken, problem):
    _write(tmp_path / "l", "good", GOOD)
    _write(tmp_path / "l", "bad", broken)
    found, problems = load_layouts(tmp_path / "l")
    assert [layout.slug for layout in found] == ["good"]
    [message] = problems
    assert message.startswith("bad.yaml: ") and problem in message


def test_no_layouts_folder(tmp_path):
    assert load_layouts(tmp_path / "missing") == ([], [])


# --- In the import pipeline ---------------------------------------------------------------------

@pytest.fixture
def ws(tmp_path, monkeypatch):
    from tra.settings import Settings
    from webctx import new_client

    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    _write(tmp_path / "layouts", "sample-bank-interest", GOOD)
    monkeypatch.setattr("tra.ingest.layouts.LAYOUTS_DIR", tmp_path / "layouts")
    return new_client(Settings.from_env())


def _ingest(ws, tmp_path, lines, override=None):
    from tra.demo import _write_pdf
    from tra.filing.local_store import LocalStore
    from tra.ingest.classify import load_doc_types
    from tra.ingest.pipeline import ingest_file
    from tra.privacy.audit import AuditLog

    path = tmp_path / f"doc{len(list(tmp_path.glob('doc*.pdf')))}.pdf"
    _write_pdf(path, lines)
    return ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path), override)


SAMPLE = ["SAMPLE BANK", "Interest summary", "Statement date 15/07/2026", "Interest paid this financial year 321.00"]


def test_layout_reads_on_import(ws, tmp_path):
    from tra.figures import read_figures
    from tra.labels import load_labels
    from tra.reading_notes import load_reading_notes

    report = _ingest(ws, tmp_path, SAMPLE)
    assert (report.doc.doc_type, report.doc.parse_status, report.figures_added) == ("INTSTMT", "parsed", 1)
    [fig] = read_figures(ws.figures_csv, load_labels())[0]
    assert (fig.label_key, fig.amount, fig.description) == ("income.interest", Decimal("321.00"),
                                                            "SAMPLE BANK – interest")
    assert load_reading_notes(ws)[report.doc.doc_id]["layout"] == "sample-bank-interest"


def test_forced_type_skips_layouts(ws, tmp_path):
    report = _ingest(ws, tmp_path, SAMPLE, override="OTHER")
    assert report.doc.doc_type == "OTHER" and report.figures_added == 0


def test_no_layout_reads_as_before(ws, tmp_path):
    report = _ingest(ws, tmp_path, ["Income statement", "Payer: SAMPLE CO PTY LTD", "Period 1 July 2025 to 30 June 2026",
                                    "Gross payments 60,000.00", "Total tax withheld 11,000.00"])
    assert (report.doc.doc_type, report.figures_added) == ("INCSTMT", 2)


def test_broken_layout_file_never_stops_an_import(ws, tmp_path):
    _write(tmp_path / "layouts", "broken", "name: [unclosed")
    assert _ingest(ws, tmp_path, SAMPLE).figures_added == 1


# --- Table rows, codes and suggested labels -----------------------------------------------------

ROWS = """
name: SAMPLE FUND health statement
doc_type: PHI
match:
  all: ["sample fund", "benefit code"]
issuer: SAMPLE FUND
fields:
  - label: phi.premiums_p1
    line: "SMP"
    also: ["30", "35", "40"]
    amount: 1
    description: premiums 1 Jul–31 Mar
  - label: phi.rebate_p1
    line: "SMP"
    also: ["30", "35", "40"]
    amount: 2
    description: rebate 1 Jul–31 Mar
  - label: phi.premiums_p2
    line: "SMP"
    also: ["31", "36", "41"]
    amount: 1
    description: premiums 1 Apr–30 Jun
"""


def test_nth_dollar_amount_and_row_codes(tmp_path):
    _write(tmp_path / "l", "fund", ROWS)
    [layout], problems = load_layouts(tmp_path / "l")
    assert problems == []
    rt = _rt("SAMPLE FUND", "Insurer ID Premiums Rebate Benefit code",
             "SMP 12345 $1,200 $290 31 Sam Sample", "SMP 12345 $3,600 $870 30 Sam Sample")
    result = read_with_layout(rt, layout, "D1")
    assert [(f.label_key, f.amount) for f in result.figures] == [
        ("phi.premiums_p1", Decimal("3600.00")), ("phi.rebate_p1", Decimal("870.00")),
        ("phi.premiums_p2", Decimal("1200.00"))]


def test_suggested_label(tmp_path):
    _write(tmp_path / "l", "shop", GOOD.replace("description: interest\n", "description: interest\n    suggested: true\n"))
    [layout], _ = load_layouts(tmp_path / "l")
    rt = _rt("SAMPLE BANK", "Interest summary", "Interest paid this financial year 5.00")
    [fig] = read_with_layout(rt, layout, "D1").figures
    assert fig.notes == "suggested label"


def test_amount_number_must_be_sensible(tmp_path):
    _write(tmp_path / "l", "bad", ROWS.replace("amount: 2", "amount: 0"))
    assert "amount" in load_layouts(tmp_path / "l")[1][0]


def test_misread_amount_is_never_used(tmp_path):
    _write(tmp_path / "l", "fund", ROWS)
    [layout], _ = load_layouts(tmp_path / "l")
    rt = _rt("SAMPLE FUND", "Benefit code", "SMP 12345 $3,600 $87s 30 Sam Sample")
    result = read_with_layout(rt, layout, "D1")
    assert [(f.label_key, f.amount) for f in result.figures] == [("phi.premiums_p1", Decimal("3600.00"))]
    assert result.doubts == ['The rebate 1 Jul–31 Mar looks misread in the scan ("$87s"), so it wasn\'t added. '
                             "Check it on the document."]
    assert result.parse_status == "partial"


def test_misread_amount_on_a_line(layouts):
    rt = _rt("SAMPLE BANK", "Interest summary", "Interest paid this financial year $1,2O4.50")
    result = read_with_layout(rt, layouts[0], "D1")
    assert result.figures == [] and "looks misread" in result.doubts[0]


# --- Misread amounts are never used or dropped silently -----------------------------------------

def _misread(desc, word):
    return f'The {desc} looks misread in the scan ("{word}"), so it wasn\'t added. Check it on the document.'


@pytest.fixture
def fund(tmp_path):
    _write(tmp_path / "l", "fund", ROWS)
    [layout], problems = load_layouts(tmp_path / "l")
    assert problems == []
    return layout


def test_misread_first_column_keeps_its_place(fund):
    result = read_with_layout(_rt("SAMPLE FUND", "Benefit code", "SMP 12345 s1500 $360 30"), fund, "D1")
    assert [(f.label_key, f.amount) for f in result.figures] == [("phi.rebate_p1", Decimal("360.00"))]
    assert result.doubts == [_misread("premiums 1 Jul–31 Mar", "s1500")]
    assert result.parse_status == "partial"


def test_misread_second_column_is_a_doubt(fund):
    result = read_with_layout(_rt("SAMPLE FUND", "Benefit code", "SMP 12345 $1500 s360 30"), fund, "D1")
    assert [(f.label_key, f.amount) for f in result.figures] == [("phi.premiums_p1", Decimal("1500.00"))]
    assert result.doubts == [_misread("rebate 1 Jul–31 Mar", "s360")]
    assert result.parse_status == "partial"


def _one_field(tmp_path, field, name="x"):
    _write(tmp_path / "l", name, "name: SAMPLE BANK\ndoc_type: INTSTMT\nmatch:\n  all: [\"sample bank\"]\n"
                                 "issuer: SAMPLE BANK\nfields:\n" + field)
    found, problems = load_layouts(tmp_path / "l")
    assert problems == []
    return found[0]


def test_s_for_dollar_is_a_doubt(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Overtime"\n    description: overtime\n')
    result = read_with_layout(_rt("SAMPLE BANK", "Overtime S120.00"), layout, "D1")
    assert result.figures == [] and result.doubts == [_misread("overtime", "S120.00")]
    assert result.parse_status == "manual_needed"


def test_thousands_split_by_a_space_is_a_doubt(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Gross amount"\n    description: gross\n')
    result = read_with_layout(_rt("SAMPLE BANK", "Gross amount $41 720.75"), layout, "D1")
    assert result.figures == [] and result.doubts == [_misread("gross", "$41 720.75")]


@pytest.mark.parametrize("text, expected", [
    ("(-$5.00)", [("(-$5.00)", Decimal("-5.00"))]),
    ("($5.00)", [("($5.00)", Decimal("-5.00"))]),
    ("-$5.00", [("-$5.00", Decimal("-5.00"))]),
    ("$1,234.50 12.00", [("$1,234.50", Decimal("1234.50")), ("12.00", Decimal("12.00"))]),
    ("30/06/2026 2026-06-30 01t07t2026 2025-26 10% 02:15pm R12345 FY2025-26", []),
    ("$1,2O4.50 12O.00 l20.00 S5 1.2.3", [("$1,2O4.50", None), ("12O.00", None), ("l20.00", None), ("S5", None),
                                          ("1.2.3", None)]),
    ("$41 720.75 then 3", [("$41 720.75", None), ("3", Decimal("3.00"))]),
])
def test_amount_words(text, expected):
    assert amount_words(text) == expected


def test_amount_words_dollars_only():
    assert amount_words("12345 $1500 120.00 s360 30 $0.00", dollars_only=True) == [
        ("$1500", Decimal("1500.00")), ("120.00", None), ("s360", None), ("$0.00", Decimal("0.00"))]


def test_negative_amount_is_read(layouts):
    rt = _rt("SAMPLE BANK", "Interest summary", "Interest paid this financial year (-$5.00)")
    assert [f.amount for f in read_with_layout(rt, layouts[0], "D1").figures] == [Decimal("-5.00")]


def test_dollars_option(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Gross amount"\n    description: gross\n'
                                  "    dollars: true\n")
    result = read_with_layout(_rt("SAMPLE BANK", "Gross amount 41,720.75"), layout, "D1")
    assert result.figures == [] and result.doubts == [_misread("gross", "41,720.75")]
    assert [f.amount for f in read_with_layout(_rt("SAMPLE BANK", "Gross amount 2 $41,720.75"), layout,
                                               "D1").figures] == [Decimal("41720.75")]


def test_numbered_amounts_count_dollars_unless_told_otherwise(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Gross amount"\n    description: gross\n'
                                  "    amount: 1\n    dollars: false\n")
    assert [f.amount for f in read_with_layout(_rt("SAMPLE BANK", "Gross amount 7.00 $9.00"), layout,
                                               "D1").figures] == [Decimal("7.00")]


def test_amounts_option_checks_the_row(tmp_path):
    _write(tmp_path / "l", "fund", ROWS.replace("    amount: 1\n", "    amount: 1\n    amounts: 2\n"))
    [layout], problems = load_layouts(tmp_path / "l")
    assert problems == []
    result = read_with_layout(_rt("SAMPLE FUND", "Benefit code", "SMP 12345 1500 $360 30"), layout, "D1")
    assert result.figures == []
    assert result.doubts[0] == ("The premiums 1 Jul–31 Mar row doesn't look like the others (it has 1 amount, "
                                "not 2), so it wasn't added. Check it on the document.")
    assert result.parse_status == "manual_needed"


def test_row_without_the_column_is_a_doubt(fund):
    result = read_with_layout(_rt("SAMPLE FUND", "Benefit code", "SMP 12345 $1500 30"), fund, "D1")
    assert [(f.label_key, f.amount) for f in result.figures] == [("phi.premiums_p1", Decimal("1500.00"))]
    assert result.doubts == ["The rebate 1 Jul–31 Mar row doesn't look like the others (it has 1 amount, not 2), "
                             "so it wasn't added. Check it on the document."]


# --- More than one line, unread fields, nothing found -------------------------------------------

def test_second_matching_line_is_a_doubt(layouts):
    rt = _rt("SAMPLE BANK", "Interest summary", "Interest paid this financial year 5.00",
             "Interest paid this financial year 7.00")
    result = read_with_layout(rt, layouts[0], "D1")
    assert [f.amount for f in result.figures] == [Decimal("5.00")]
    assert result.doubts == ["There's more than one interest line; only the first was read. Check the document."]


def test_unread_field(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Gross amount"\n    description: gross\n'
                                  '  - unread: true\n    line: "Lump sum payment A"\n    description: lump sum A\n')
    result = read_with_layout(_rt("SAMPLE BANK", "Gross amount 100.00", "Lump sum payment A $1,500.00"), layout, "D1")
    assert [f.amount for f in result.figures] == [Decimal("100.00")]
    assert result.doubts == ["The document shows lump sum A ($1,500.00), which this layout doesn't read. "
                             "Enter it by hand."]
    assert result.parse_status == "partial"
    quiet = read_with_layout(_rt("SAMPLE BANK", "Gross amount 100.00", "Lump sum payment A $0.00"), layout, "D1")
    assert quiet.doubts == [] and quiet.parse_status == "parsed"


@pytest.mark.parametrize("field, problem", [
    ('  - unread: true\n    description: lump sum A\n', "line or contains"),
    ('  - unread: true\n    line: "Lump sum payment A"\n', "description"),
])
def test_unread_field_needs_a_line_and_description(tmp_path, field, problem):
    _write(tmp_path / "l", "x", "name: SAMPLE BANK\ndoc_type: INTSTMT\nmatch:\n  all: [\"sample bank\"]\nfields:\n"
           "  - label: income.salary\n    line: \"Gross amount\"\n" + field)
    found, [message] = load_layouts(tmp_path / "l")
    assert found == [] and problem in message


def test_nothing_found_needs_manual_entry(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Gross amount"\n    description: gross\n')
    result = read_with_layout(_rt("SAMPLE BANK", "Nothing here"), layout, "D1")
    assert result.figures == [] and result.doubts == [] and result.parse_status == "manual_needed"


# --- Stricter checks on layout files ------------------------------------------------------------

@pytest.mark.parametrize("broken, problem", [
    (GOOD.replace('all: ["sample bank", "interest summary"]', 'all: "zq"'), "all"),
    (GOOD.replace('all: ["sample bank", "interest summary"]', 'all: ["sample bank", 12345]'), "all"),
    (GOOD.replace('all: ["sample bank", "interest summary"]', 'all: ["sample bank"]\n  any: "interest"'), "any"),
    (GOOD.replace('all: ["sample bank", "interest summary"]', 'all: ["sample bank", "abc"]'), "4"),
    (GOOD.replace('    line: "Interest paid this financial year"\n', "    line: 1234\n"), "line"),
    (GOOD.replace('    contains: "tfn withholding"\n', "    contains: [tfn]\n"), "contains"),
    (GOOD.replace("    amount: first\n", "    amount: middle\n"), "amount"),
    (GOOD.replace("    amount: first\n", "    amount: 21\n"), "amount"),
    (GOOD.replace("    required: true\n", "    required: yes please\n"), "required"),
    (GOOD.replace("    required: true\n", "    every: 1\n"), "every"),
    (GOOD.replace("    required: true\n", "    suggested: \"true\"\n"), "suggested"),
    (GOOD.replace("    required: true\n", "    dollars: maybe\n"), "dollars"),
    (GOOD.replace("    required: true\n", "    unread: 0\n"), "unread"),
    (GOOD.replace("    required: true\n", "    amounts: 0\n"), "amounts"),
    (GOOD.replace("    required: true\n", '    also: "30"\n'), "also"),
    (GOOD.replace("    required: true\n", "    also: [30]\n"), "also"),
    (GOOD.replace("match:\n", "match: sample bank\nx:\n"), "match"),
])
def test_stricter_checks(tmp_path, broken, problem):
    _write(tmp_path / "l", "good", GOOD)
    _write(tmp_path / "l", "bad", broken)
    found, problems = load_layouts(tmp_path / "l")
    assert [layout.slug for layout in found] == ["good"]
    [message] = problems
    assert message.startswith("bad.yaml: ") and problem in message


def test_a_file_that_cant_be_opened_is_reported(tmp_path):
    _write(tmp_path / "l", "good", GOOD)
    (tmp_path / "l" / "folder.yaml").mkdir()
    found, [message] = load_layouts(tmp_path / "l")
    assert [layout.slug for layout in found] == ["good"]
    assert message.startswith("folder.yaml: ") and "couldn't be opened" in message


# --- Whole words only ---------------------------------------------------------------------------

def test_line_words_are_whole_words(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Overtime"\n    description: overtime\n')
    assert read_with_layout(_rt("SAMPLE BANK", "Overtimemeal allowance $9.00"), layout, "D1").figures == []
    assert [f.amount for f in read_with_layout(_rt("SAMPLE BANK", "Overtime $42.16"), layout, "D1").figures] == [
        Decimal("42.16")]


def test_line_bup_is_not_bupa(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "BUP"\n    description: row\n')
    assert read_with_layout(_rt("SAMPLE BANK", "Bupa HI Pty Ltd 2026"), layout, "D1").figures == []


def test_contains_words_are_whole_words(tmp_path):
    layout = _one_field(tmp_path, '  - label: it.resc\n    contains: "super contribution"\n    description: resc\n')
    assert read_with_layout(_rt("SAMPLE BANK", "Employer superannuation contribution $9.00",
                                "Ultrasuper contribution $8.00"), layout, "D1").figures == []


def test_match_words_are_whole_words(tmp_path):
    _write(tmp_path / "l", "z", GOOD.replace('all: ["sample bank", "interest summary"]', 'all: ["zebra"]'))
    found, _ = load_layouts(tmp_path / "l")
    assert match_layout(_rt("Zebras and more"), found) is None
    assert match_layout(_rt("A zebra, striped"), found)


def test_also_words_whole_and_phrases(tmp_path):
    layout = _one_field(tmp_path, '  - label: income.salary\n    line: "Row"\n    also: ["30", "code b"]\n'
                                  "    description: row\n")
    assert read_with_layout(_rt("SAMPLE BANK", "Row $3.30 $7.00"), layout, "D1").figures == []
    assert [f.amount for f in read_with_layout(_rt("SAMPLE BANK", "Row $7.00 code B"), layout, "D1").figures] == [
        Decimal("7.00")]
    assert read_with_layout(_rt("SAMPLE BANK", "Row $7.00 code Bx"), layout, "D1").figures == []


# --- Picking a layout ---------------------------------------------------------------------------

def test_tie_goes_to_the_first_name(tmp_path):
    from tra.ingest.layouts import matching_layouts

    _write(tmp_path / "l", "beta", GOOD)
    _write(tmp_path / "l", "alpha", GOOD)
    found, _ = load_layouts(tmp_path / "l")
    rt = _rt("SAMPLE BANK", "Interest summary")
    assert match_layout(rt, found).slug == "alpha"
    assert match_layout(rt, list(reversed(found))).slug == "alpha"
    assert [lay.slug for lay in matching_layouts(rt, found)] == ["alpha", "beta"]
    assert matching_layouts(_rt("Nothing"), found) == []
