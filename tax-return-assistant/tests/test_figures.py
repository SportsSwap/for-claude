from datetime import date
from decimal import Decimal

import pytest

from tra import figures as figs
from tra.demo import build_demo_documents
from tra.figures import (
    FIGURE_COLUMNS,
    append_figures,
    append_prefill,
    read_cgt,
    read_figures,
    read_prefill,
    read_prior_year,
    write_figures,
)
from tra.ingest.extractors import get_extractor
from tra.ingest.readers import load
from tra.labels import load_labels
from tra.models import Figure, PrefillLine
from tra.privacy.guard import FileLockedError

LABELS = load_labels()


def _fig(fid, key="income.interest", amount="412.35", **kw):
    base = dict(figure_id=fid, label_key=key, description="CBA – interest", amount=Decimal(amount),
                date=date(2026, 6, 30), doc_id="D003", page=1, method="parser", confirmed=True,
                substantiated=None, notes="")
    base.update(kw)
    return Figure(**base)


def test_roundtrip(tmp_path):
    path = tmp_path / "figures.csv"
    original = [_fig("F0001"), _fig("F0002", "ded.d5", "520.00", substantiated=True, confirmed=False),
                _fig("F0003", "income.salary", "85000.00", date=None, doc_id=None, page=None, method="manual")]
    write_figures(path, original)
    loaded, errors = read_figures(path, LABELS)
    assert errors == []
    assert loaded == original


def test_excel_roundtrip_formats(tmp_path):
    path = tmp_path / "figures.csv"
    header = ",".join(FIGURE_COLUMNS)
    path.write_text(
        "﻿" + header + "\n"
        "F0001,income.interest,CBA interest,1234.5,24/03/2026,D003,1,parser,yes,,\n"
        'F0002,ded.d5,Union fees,"$1,234.50",2026-03-24,D007,1,parser,y,Y,\n'
        "F0003,ded.d5,Pens,12,,D007,1,parser,Yes,No,\n",
        encoding="utf-8")
    loaded, errors = read_figures(path, LABELS)
    assert errors == []
    assert [f.amount for f in loaded] == [Decimal("1234.5"), Decimal("1234.50"), Decimal("12")]
    assert loaded[0].date == date(2026, 3, 24)
    assert all(f.confirmed for f in loaded)
    assert [f.substantiated for f in loaded] == [None, True, False]


def test_errors_listed(tmp_path):
    path = tmp_path / "figures.csv"
    header = ",".join(FIGURE_COLUMNS)
    path.write_text(
        header + "\n"
        "F0001,income.interest,ok,10.00,,D001,1,parser,Y,,\n"
        "F0002,income.salry,typo,10.00,,D001,1,parser,Y,,\n"
        "F0003,income.interest,bad amount,abc,,D001,1,parser,Y,,\n"
        "F0004,income.interest,bad page,10.00,,D001,x,parser,Y,,\n"
        "F0005,income.interest,bad confirmed,10.00,,D001,1,parser,maybe,,\n"
        "F0006,income.interest,bad date,10.00,31/02/2026,D001,1,parser,Y,,\n",
        encoding="utf-8")
    loaded, errors = read_figures(path, LABELS)
    assert [f.figure_id for f in loaded] == ["F0001"]
    assert len(errors) == 5
    assert errors[0].startswith("row 3:") and "income.salry" in errors[0]
    assert errors[1].startswith("row 4:")
    assert errors[2].startswith("row 5:")
    assert errors[3].startswith("row 6:")
    assert errors[4].startswith("row 7:")


def test_blank_rows_and_blank_ids(tmp_path):
    path = tmp_path / "figures.csv"
    header = ",".join(FIGURE_COLUMNS)
    path.write_text(header + "\nF0004,income.interest,a,1.00,,D001,1,parser,Y,,\n,,,,,,,,,,\n"
                    ",ded.d9,Manual gift,50.00,,,,manual,Y,,\n", encoding="utf-8")
    loaded, errors = read_figures(path, LABELS)
    assert errors == []
    assert [f.figure_id for f in loaded] == ["F0004", "F0005"]
    assert loaded[1].method == "manual" and loaded[1].doc_id is None


def test_info_label_rejected(tmp_path):
    path = tmp_path / "figures.csv"
    path.write_text(",".join(FIGURE_COLUMNS) + "\nF0001,phi.premiums_total,x,1.00,,D001,1,parser,Y,,\n",
                    encoding="utf-8")
    _, errors = read_figures(path, LABELS)
    assert errors and "phi.premiums_total" in errors[0]


def test_append_assigns_ids(tmp_path):
    path = tmp_path / "figures.csv"
    first = append_figures(path, [_fig("")])
    second = append_figures(path, [_fig(""), _fig("", "ded.d5", "1.00")])
    assert [f.figure_id for f in first + second] == ["F0001", "F0002", "F0003"]
    loaded, errors = read_figures(path, LABELS)
    assert errors == [] and len(loaded) == 3


def test_append_preserves_user_rows_even_if_invalid(tmp_path):
    path = tmp_path / "figures.csv"
    write_figures(path, [_fig("F0001")])
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "F0009,income.salry,user typo,5.00,,,,manual,Y,,\n", encoding="utf-8")
    append_figures(path, [_fig("")])
    content = path.read_text(encoding="utf-8")
    assert "income.salry" in content
    assert "F0010" in content


def test_write_locked_file(tmp_path, monkeypatch):
    path = tmp_path / "figures.csv"
    write_figures(path, [_fig("F0001")])
    before = path.read_text(encoding="utf-8")

    def locked(*_args):
        raise PermissionError("locked")

    monkeypatch.setattr("tra.privacy.guard.os.replace", locked)
    with pytest.raises(FileLockedError):
        write_figures(path, [_fig("F0001"), _fig("F0002")])
    assert path.read_text(encoding="utf-8") == before


def test_cgt_and_prior_year_missing_ok(tmp_path):
    assert read_cgt(tmp_path / "cgt_events.csv") == ([], [])
    assert read_prior_year(tmp_path / "prior_year.csv") == {}
    assert read_prefill(tmp_path / "prefill.json") == []


def test_cgt_and_prior_year_read(tmp_path):
    cgt = tmp_path / "cgt_events.csv"
    cgt.write_text(",".join(figs.CGT_COLUMNS) + "\nC001,BHP shares,2020-01-10,24/03/2026,15000.00,9000.00,D008,1,Y\n",
                   encoding="utf-8")
    events, errors = read_cgt(cgt)
    assert errors == []
    assert events[0].proceeds == Decimal("15000.00") and events[0].confirmed
    prior = tmp_path / "prior_year.csv"
    prior.write_text("label_key,amount\nincome.interest,300.00\n", encoding="utf-8")
    assert read_prior_year(prior) == {"income.interest": Decimal("300.00")}


def test_prefill_roundtrip(tmp_path):
    path = tmp_path / "prefill.json"
    lines = [PrefillLine("income.interest", "CBA", Decimal("412.35"), "D001", 1)]
    append_prefill(path, lines)
    append_prefill(path, lines)
    assert read_prefill(path) == lines * 2


def test_labels_cover_extractor_keys(tmp_path):
    demo = build_demo_documents(tmp_path)
    keys = set()
    for stem, doc_type in [("prefill", "PREFILL"), ("income_statement", "INCSTMT"), ("bank_interest", "BANKSTMT"),
                           ("dividend_bhp", "DIVSTMT"), ("rental", "RENTSTMT"), ("phi", "PHI"),
                           ("receipt_laptop", "RECEIPT")]:
        result = get_extractor(doc_type).extract(load(demo.paths[stem]).redacted, "D001")
        keys |= {f.label_key for f in result.figures} | {p.label_key for p in result.prefill}
    keys |= {"income.div_unfranked", "income.interest_tfn_withheld", "income.div_tfn_withheld", "it.rfb",
             "it.resc", "income.business_income", "income.business_expenses", "rent.interest", "help.indicator"}
    assert keys <= set(LABELS)


def test_labels_ordered_and_have_tabs():
    orders = [d.order for d in LABELS.values()]
    assert orders == sorted(orders)
    assert all(d.tab for d in LABELS.values())
    assert LABELS["income.interest"].item == "10" and LABELS["income.interest"].label == "L"
    assert LABELS["cgt.net_gain"].computed is True


def test_prior_capital_losses_can_be_a_figure(tmp_path):
    path = tmp_path / "figures.csv"
    path.write_text(",".join(FIGURE_COLUMNS) + "\nF0001,cgt.prior_losses,2025 NOA losses c/f,3000.00,,D002,1,manual,Y,,\n",
                    encoding="utf-8")
    loaded, errors = read_figures(path, LABELS)
    assert errors == [] and loaded[0].label_key == "cgt.prior_losses"
