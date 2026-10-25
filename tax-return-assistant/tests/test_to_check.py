"""Things to check: what a reader wasn't sure about, gathered per document. All data is made up here."""

import json
from decimal import Decimal

import pytest

from tra.demo import _write_pdf
from tra.figures import append_figures, read_figures, write_figures
from tra.filing.local_store import LocalStore
from tra.ingest import pipeline
from tra.ingest.classify import load_doc_types
from tra.ingest.extractors import get_extractor
from tra.ingest.pipeline import ingest_file
from tra.checks import label_name
from tra.labels import load_labels
from tra.models import Figure
from tra.privacy.audit import AuditLog
from tra.privacy.redact import redact_pages
from tra.reading_notes import load_reading_notes, save_reading_notes
from tra.to_check import things_to_check, to_check_by_figure, to_check_counts

from webctx import new_client

D9 = label_name(load_labels(), "ded.d9")


def _extract(doc_type, lines):
    return get_extractor(doc_type).extract(redact_pages(["\n".join(lines)]), "D001")


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    from tra.settings import Settings

    return new_client(Settings.from_env())


def _ingest(ws, tmp_path, name, lines):
    path = tmp_path / f"{name}.pdf"
    _write_pdf(path, lines)
    return ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path))


DIVIDEND_NO_CREDIT = ["SAMPLE MINING LTD", "Dividend statement", "Payment date 20 March 2026",
                      "Unfranked amount 0.00", "Franked amount 700.00", "Franked dividend paid"]


def test_dividend_missing_credit_is_a_doubt():
    result = _extract("DIVSTMT", DIVIDEND_NO_CREDIT)
    assert "Didn't find the franking credit." in result.doubts


def test_income_statement_missing_tax_withheld_is_a_doubt():
    result = _extract("INCSTMT", ["Income statement", "Payer: SAMPLE CO PTY LTD", "Gross payments 60,000.00"])
    assert "Didn't find the tax withheld." in result.doubts


def test_phi_missing_period_is_a_doubt():
    result = _extract("PHI", ["Private health insurance statement", "SAMPLE HEALTH FUND",
                              "Premiums eligible for rebate 1 July - 31 March 1,800.00",
                              "Rebate received 1 July - 31 March 436.50"])
    assert "Didn't find the premiums for 1 Apr–30 Jun." in result.doubts
    assert "Didn't find the rebate received for 1 Apr–30 Jun." in result.doubts


def test_interest_not_found_is_a_doubt():
    result = _extract("INTSTMT", ["SAMPLE BANK", "Interest summary", "Account summary only"])
    assert "Didn't find the interest earned." in result.doubts


def test_full_statement_has_no_doubts():
    result = _extract("INCSTMT", ["Income statement", "Payer: SAMPLE CO PTY LTD", "Gross payments 60,000.00",
                                  "Total tax withheld 11,000.00"])
    assert result.doubts == []


def test_withholding_wording_is_a_doubt():
    result = _extract("DIVSTMT", ["SAMPLE MINING LTD", "Dividend statement", "Unfranked amount 0.00",
                                  "Franked amount 700.00", "Franking credit 300.00", "Withholding tax 50.00"])
    assert any("TFN withholding" in d for d in result.doubts)


def test_ingest_saves_doubts(ws, tmp_path):
    report = _ingest(ws, tmp_path, "div", DIVIDEND_NO_CREDIT)
    notes = load_reading_notes(ws)
    assert "Didn't find the franking credit." in notes[report.doc.doc_id]["doubts"]
    assert notes[report.doc.doc_id]["from_email"] is None


def test_no_doubts_writes_nothing(ws, tmp_path):
    _ingest(ws, tmp_path, "inc", ["Income statement", "Payer: SAMPLE CO PTY LTD", "Period 1 July 2025 to 30 June 2026",
                                  "Gross payments 60,000.00", "Total tax withheld 11,000.00"])
    assert load_reading_notes(ws) == {}


def _figure(**kw):
    base = dict(figure_id="", label_key="ded.d9", description="Red Cross donation", amount=Decimal("500.00"),
                date=None, doc_id="D001", page=1, method="parser", confirmed=False, substantiated=None,
                notes="suggested label")
    base.update(kw)
    return Figure(**base)


def _note(ws, check_id, risk, doc_id, message):
    ws.ingest_notes_json.write_text(json.dumps([{"risk": risk, "check_id": check_id, "message": message,
                                                 "dollar_impact": None, "audience": "preparer",
                                                 "action": "confirm", "label_key": None, "citation_id": None,
                                                 "figure_ids": [], "doc_ids": [doc_id]}]), encoding="utf-8")


def test_things_to_check_collects_sources(ws):
    save_reading_notes(ws, "D001", ["Didn't find the franking credit."])
    _note(ws, "I2", "Low", "D001", "Document date not detected.")
    [fig] = append_figures(ws.figures_csv, [_figure()])
    items = things_to_check(ws, "D001")
    assert [i.text for i in items][0] == "Didn't find the franking credit."
    assert any(i.risk == "Low" and i.text == "Document date not detected." for i in items)
    [fig_item] = [i for i in items if i.figure_id]
    assert fig_item.figure_id == fig.figure_id
    assert fig_item.text == f"{fig.figure_id}: label suggested ({D9}). Check it before confirming."
    assert len(items) == 3


def test_duplicate_note_not_listed(ws):
    _note(ws, "I4", "Low", "D001", "The same file was ingested again.")
    assert things_to_check(ws, "D001") == []


def test_other_documents_not_listed(ws):
    save_reading_notes(ws, "D002", ["Didn't find the tax withheld."])
    _note(ws, "I2", "Low", "D002", "Document date not detected.")
    append_figures(ws.figures_csv, [_figure(doc_id="D002")])
    assert things_to_check(ws, "D001") == []


def test_confirmed_figure_drops_off(ws):
    save_reading_notes(ws, "D001", ["Didn't find the franking credit."])
    append_figures(ws.figures_csv, [_figure()])
    figures, _ = read_figures(ws.figures_csv, load_labels())
    figures[0].confirmed = True
    write_figures(ws.figures_csv, figures)
    assert [i.text for i in things_to_check(ws, "D001")] == ["Didn't find the franking credit."]


def test_ai_figure_and_missing_page(ws):
    [fig] = append_figures(ws.figures_csv, [_figure(method="ai", page=None, notes="",
                                                    description="Claude: SAMPLE BANK interest")])
    [item] = things_to_check(ws, "D001")
    assert item.figure_id == fig.figure_id
    assert "read by the AI reader or Claude" in item.text
    assert "page isn't known" in item.text


def test_plain_parser_figure_not_listed(ws):
    append_figures(ws.figures_csv, [_figure(notes="", label_key="income.salary")])
    assert things_to_check(ws, "D001") == []


def test_email_parent_listed(ws):
    save_reading_notes(ws, "D003", [], from_email="D002")
    assert [i.text for i in things_to_check(ws, "D003")] == ["Came attached to email D002."]


def test_by_figure(ws):
    [fig] = append_figures(ws.figures_csv, [_figure()])
    assert to_check_by_figure(ws) == {fig.figure_id: [f"Label suggested ({D9}). Check it before confirming."]}


def test_counts(ws):
    save_reading_notes(ws, "D001", ["Didn't find the franking credit."])
    _note(ws, "I2", "Low", "D002", "Document date not detected.")
    append_figures(ws.figures_csv, [_figure(), _figure(doc_id="D002", description="Union fees")])
    counts = to_check_counts(ws)
    assert counts == {"D001": len(things_to_check(ws, "D001")), "D002": len(things_to_check(ws, "D002"))}
    assert counts == {"D001": 2, "D002": 2}


def test_reading_notes_go_through_the_guard(ws, make_tfn):
    from tra.privacy.guard import SensitiveDataBlocked

    with pytest.raises(SensitiveDataBlocked):
        save_reading_notes(ws, "D001", [f"Row 3: {make_tfn()}"])
    assert not ws.reading_notes_json.exists()


def test_failed_import_leaves_no_reading_notes(ws, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pipeline, "file_document", boom)
    with pytest.raises(OSError):
        _ingest(ws, tmp_path, "div", DIVIDEND_NO_CREDIT)
    assert not ws.reading_notes_json.exists()


def test_delete_forever_forgets_reading_notes(ws, tmp_path):
    from tra.trash import delete_document, purge_document

    report = _ingest(ws, tmp_path, "div", DIVIDEND_NO_CREDIT)
    doc_id, audit = report.doc.doc_id, AuditLog(ws.audit_path)
    delete_document(ws, doc_id, "tester", audit)
    assert doc_id in load_reading_notes(ws)  # kept while it can still be restored
    purge_document(ws, doc_id, audit)
    assert doc_id not in load_reading_notes(ws)


def test_receipt_without_total_is_a_doubt():
    assert "Didn't find a total." in _extract("RECEIPT", ["SAMPLE SHOP", "TAX INVOICE", "Pens 4.00"]).doubts


def test_unrecognised_document_has_no_total_doubt():
    assert _extract("OTHER", ["Dear client", "Thanks for your letter."]).doubts == []


def test_where_it_came_from_is_shown_but_not_counted(ws):
    save_reading_notes(ws, "D003", [], from_email="D002")
    assert [i.text for i in things_to_check(ws, "D003")] == ["Came attached to email D002."]
    assert to_check_counts(ws) == {}


def test_labels_and_doc_types_read_once(monkeypatch):
    from tra import labels as labels_mod
    from tra.ingest import classify as classify_mod

    labels_mod.load_labels.cache_clear()
    classify_mod.load_doc_types.cache_clear()
    calls = []
    real = labels_mod.yaml.safe_load
    monkeypatch.setattr(labels_mod.yaml, "safe_load", lambda text: calls.append(1) or real(text))
    a, b = labels_mod.load_labels(), labels_mod.load_labels()
    assert a == b and a is not b and len(calls) == 1  # each caller gets its own copy
    classify_mod.load_doc_types()
    classify_mod.load_doc_types()
    assert len(calls) == 2
