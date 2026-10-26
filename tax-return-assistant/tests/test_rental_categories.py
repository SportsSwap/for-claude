"""Rental expense categories (the ATO rental property schedule): each is part of Item 21 U, so the return and both
tax calculations only ever see the one label, while the M25 tab shows the breakdown for review. Made-up data only."""

from decimal import Decimal

import pytest
from checkctx import fig, ids, make_ctx

from tra.checks.sanity import check_sanity
from tra.ingest.extractors import get_extractor
from tra.ingest.extractors.ai_reader import AiReader
from tra.labels import load_labels, return_key
from tra.models import Figure
from tra.privacy.redact import redact_pages
from tra.return_.prepare import build_draft
from tra.web.services.figures import label_choices

CATEGORIES = ["rent.advertising", "rent.body_corporate", "rent.borrowing", "rent.cleaning", "rent.council_rates",
              "rent.capital_allowances", "rent.gardening", "rent.insurance", "rent.land_tax", "rent.legal",
              "rent.pest_control", "rent.agent_fees", "rent.repairs", "rent.stationery", "rent.travel", "rent.water"]


def _fig(fid, key, amount, description="x"):
    return Figure(fid, key, description, Decimal(amount), None, "D001", 1, "parser", True, None, "")


# --- labels and the return ------------------------------------------------------------------------------------

def test_every_category_is_part_of_item_21_u():
    labels = load_labels()
    for key in CATEGORIES:
        d = labels[key]
        assert (d.item, d.label, d.role, d.part_of, d.tab) == ("21", "U", "rental_deduction", "rent.other",
                                                              "M25 Rental Property"), key
        assert return_key(labels, key) == "rent.other"
    assert return_key(labels, "rent.interest") == "rent.interest" and labels["rent.other"].part_of is None


def test_the_return_adds_the_categories_into_one_u_line():
    figures = [_fig("F1", "rent.gardening", "300"), _fig("F2", "rent.agent_fees", "1820"),
               _fig("F3", "rent.other", "40"), _fig("F4", "rent.interest", "8000")]
    draft = build_draft("TEST01", 2026, figures, [], load_labels())
    assert draft.amount("rent.other") == Decimal("2160") and draft.amount("rent.interest") == Decimal("8000")
    assert set(draft.lines["rent.other"].figure_ids) == {"F1", "F2", "F3"}
    assert "rent.gardening" not in draft.lines  # never a return line of its own


def test_labels_file_rejects_a_bad_part_of(tmp_path):
    path = tmp_path / "labels.yaml"
    path.write_text('rent.other: {item: "21", label: "U", description: "Other", role: rental_deduction, '
                    'tab: "M25 Rental Property", order: 1}\n'
                    'rent.x: {item: "21", label: "Q", description: "X", role: rental_deduction, '
                    'tab: "M25 Rental Property", order: 2, part_of: rent.other}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="rent.x"):
        load_labels(path)


def test_categories_can_be_chosen_on_the_figures_tab_and_by_the_ai():
    names = dict(label_choices())
    assert names["rent.gardening"] == "Item 21 U Gardening/lawnmowing"
    assert set(CATEGORIES) <= set(AiReader(object()).keys)


# --- reading a property manager's statement --------------------------------------------------------------------

def _rental(*expense_lines):
    rt = redact_pages(["Rental statement", "Property manager: SAMPLE REALTY", "Total rent received 26,000.00",
                       *expense_lines, "Total expenses 1.00", "Net to owner 1.00"])
    return get_extractor("RENTSTMT").extract(rt, "D001")


@pytest.mark.parametrize("line, key", [
    ("Management fees 1,820.00", "rent.agent_fees"),
    ("Letting fee 440.00", "rent.agent_fees"),
    ("Repairs - leaking tap 640.00", "rent.repairs"),
    ("Council rates 2,100.00", "rent.council_rates"),
    ("Water rates 780.00", "rent.water"),
    ("Lawn mowing 300.00", "rent.gardening"),
    ("Garden maintenance 120.00", "rent.gardening"),
    ("Strata levy 1,200.00", "rent.body_corporate"),
    ("Landlord insurance 950.00", "rent.insurance"),
    ("Insurance 950.00", "rent.insurance"),
    ("Pest control 180.00", "rent.pest_control"),
    ("Advertising 99.00", "rent.advertising"),
    ("Land tax 600.00", "rent.land_tax"),
    ("Cleaning 150.00", "rent.cleaning"),
    ("Smoke alarm service 89.00", "rent.other"),  # no category fits: sundry, as before
    ("Loan interest 3,000.00", "rent.interest"),
])
def test_statement_lines_go_to_their_category(line, key):
    [gross, expense] = _rental(line).figures
    assert gross.label_key == "rent.gross" and expense.label_key == key


def test_a_line_that_fits_two_categories_goes_to_sundry():
    [_gross, expense] = _rental("Cleaning and pest control 330.00").figures
    assert expense.label_key == "rent.other"


# --- review notes ---------------------------------------------------------------------------------------------

def _notes(*figures):
    return check_sanity(make_ctx([fig("F0", "rent.gross", 20000), *figures]))


def test_a_rental_repair_that_may_be_capital_is_still_flagged():
    [note] = ids(_notes(fig("F1", "rent.repairs", 4000, description="Replace hot water system")), "S7")
    assert note.label_key == "rent.repairs" and note.citation_id == "tr97_23"


def test_rental_travel_is_flagged():
    [note] = ids(_notes(fig("F1", "rent.travel", 250, description="Travel to inspect the property")), "S15")
    assert note.citation_id == "itaa97_s26_31" and note.risk == "Medium"


def test_borrowing_expenses_over_100_are_flagged():
    [note] = ids(_notes(fig("F1", "rent.borrowing", 900, description="Loan establishment fee")), "S16")
    assert note.citation_id == "itaa97_s25_25"
    assert ids(_notes(fig("F1", "rent.borrowing", 100, description="Loan establishment fee")), "S16") == []


def test_depreciation_is_flagged_for_second_hand_assets():
    [note] = ids(_notes(fig("F1", "rent.capital_allowances", 1500, description="Depreciation schedule")), "S17")
    assert note.citation_id == "itaa97_s40_27"


def test_the_new_citations_exist():
    from tra.checks import load_citations
    c = load_citations()
    assert c["itaa97_s25_25"]["ref"] == "ITAA 1997 s25-25" and c["itaa97_s25_25"]["verified"] is False


def test_rental_with_only_categories_isnt_one_sided():
    assert ids(_notes(fig("F1", "rent.gardening", 300)), "S3") == []


# --- the info request -----------------------------------------------------------------------------------------

def test_last_years_categories_ask_for_the_rental_papers(tmp_path, monkeypatch):
    from test_info_request import _fig as info_fig
    from webctx import new_client

    from tra.figures import append_figures
    from tra.info_request import build_request
    from tra.settings import Settings
    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    home = Settings.from_env()
    append_figures(new_client(home, "TEST01", fy=2025).figures_csv,
                   [info_fig("rent.gardening", "SAMPLE REALTY: Lawn mowing", "300.00")])
    req = build_request(new_client(home, "TEST01", fy=2026))
    assert "Rental property" in [h for h, _ in req.sections]
