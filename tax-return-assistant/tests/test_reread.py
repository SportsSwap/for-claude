"""Read again: a filed document is read with today's rules; confirmed and typed-in figures are never touched."""

import json
from decimal import Decimal

import pytest

from tra.demo import _write_pdf
from tra.figures import append_figures, read_figures, write_figures
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.pipeline import ingest_file
from tra.labels import load_labels
from tra.models import Figure
from tra.privacy.audit import AuditLog
from tra.reading_notes import load_reading_notes, save_reading_notes
from tra.reread import reread_document, reread_waiting

from webctx import new_client

LAYOUT = """
name: SAMPLE BANK interest summary
doc_type: INTSTMT
match:
  all: ["sample bank", "yearly interest"]
issuer: SAMPLE BANK
fields:
  - label: income.interest
    line: "Interest paid this financial year"
    description: interest
    required: true
"""
SAMPLE = ["SAMPLE BANK", "Yearly interest", "Statement date 15/07/2026", "Interest paid this financial year 321.00"]


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from tra.settings import Settings

    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    monkeypatch.setattr("tra.ingest.layouts.LAYOUTS_DIR", tmp_path / "layouts")
    return new_client(Settings.from_env())


def _learn(tmp_path):
    (tmp_path / "layouts").mkdir(exist_ok=True)
    (tmp_path / "layouts" / "sample-bank-yearly.yaml").write_text(LAYOUT, encoding="utf-8")


def _ingest(ws, tmp_path, lines=SAMPLE, name="a.pdf"):
    path = tmp_path / name
    _write_pdf(path, lines)
    return ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path)).doc


def _figures(ws):
    return read_figures(ws.figures_csv, load_labels())[0]


def _fig(doc_id, method, confirmed, amount="99.00", label="income.interest"):
    return Figure(figure_id="", label_key=label, description="x", amount=Decimal(amount), date=None, doc_id=doc_id,
                  page=1, method=method, confirmed=confirmed, substantiated=None)


def test_new_layout_reads_a_waiting_document(ws, tmp_path):
    doc = _ingest(ws, tmp_path)
    assert doc.parse_status == "manual_needed" and '"I1"' in ws.ingest_notes_json.read_text(encoding="utf-8")
    _learn(tmp_path)
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert (result.added, result.removed, result.status, result.layout) == (1, 0, "parsed", "sample-bank-yearly")
    [fig] = _figures(ws)
    assert (fig.label_key, fig.amount, fig.confirmed) == ("income.interest", Decimal("321.00"), False)
    [again] = DocumentIndex(ws.index_csv).load()
    assert (again.parse_status, again.doc_type, again.category) == ("parsed", "INTSTMT", doc.category)
    assert '"I1"' not in ws.ingest_notes_json.read_text(encoding="utf-8")
    assert load_reading_notes(ws)[doc.doc_id]["layout"] == "sample-bank-yearly"
    assert '"document_reread"' in ws.audit_path.read_text(encoding="utf-8")


def test_reading_again_twice_doesnt_duplicate(ws, tmp_path):
    _learn(tmp_path)
    doc = _ingest(ws, tmp_path)
    reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert (result.added, result.removed) == (1, 1) and len(_figures(ws)) == 1


def test_confirmed_and_typed_figures_are_kept(ws, tmp_path):
    _learn(tmp_path)
    doc = _ingest(ws, tmp_path)
    figures = _figures(ws)
    figures[0].confirmed = True
    write_figures(ws.figures_csv, figures)
    append_figures(ws.figures_csv, [_fig(doc.doc_id, "manual", False, "5.00", "income.interest_tfn_withheld")])
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert (result.added, result.removed) == (0, 0)  # the confirmed 321.00 is already there, so it isn't added twice
    assert sorted((f.method, f.amount, f.confirmed) for f in _figures(ws)) == [
        ("manual", Decimal("5.00"), False), ("parser", Decimal("321.00"), True)]


def test_ai_figures_replaced_only_when_rules_read_it(ws, tmp_path):
    doc = _ingest(ws, tmp_path)
    append_figures(ws.figures_csv, [_fig(doc.doc_id, "ai", False)])
    reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))  # no layout yet: nothing read, the AI's figure stays
    assert [f.method for f in _figures(ws)] == ["ai"]
    _learn(tmp_path)
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert result.removed == 1 and [f.method for f in _figures(ws)] == ["parser"]


def test_where_it_came_from_is_kept(ws, tmp_path):
    doc = _ingest(ws, tmp_path)
    save_reading_notes(ws, doc.doc_id, ["old doubt"], from_email="D009")
    _learn(tmp_path)
    reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    entry = load_reading_notes(ws)[doc.doc_id]
    assert entry["from_email"] == "D009" and entry["doubts"] == []


def test_a_type_set_by_hand_is_respected(ws, tmp_path):
    import dataclasses

    doc = _ingest(ws, tmp_path, ["SAMPLE MINING LTD", "Payment date 20 March 2026", "Franked amount 700.00",
                                 "Franking credit 300.00"])
    DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, doc_type="DIVSTMT"))
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert result.added == 2 and result.status == "partial"


@pytest.mark.parametrize("kind", ["stored", "prefill", "unknown"])
def test_refused_with_a_plain_message(ws, tmp_path, kind):
    import dataclasses

    doc = _ingest(ws, tmp_path)
    if kind == "stored":
        DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, parse_status="stored"))
    if kind == "prefill":
        DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, doc_type="PREFILL"))
    with pytest.raises(ValueError) as exc:
        reread_document(ws, "D999" if kind == "unknown" else doc.doc_id, AuditLog(ws.audit_path))
    assert {"stored": "stored only", "prefill": "Pre-fill", "unknown": "no document D999"}[kind] in str(exc.value)


def test_reread_waiting(ws, tmp_path):
    first = _ingest(ws, tmp_path, name="a.pdf")
    _ingest(ws, tmp_path, ["Income statement", "Payer: SAMPLE CO PTY LTD", "Period 1 July 2025 to 30 June 2026",
                           "Gross payments 60,000.00", "Total tax withheld 11,000.00"], name="b.pdf")
    _learn(tmp_path)
    results = reread_waiting(ws, AuditLog(ws.audit_path))
    assert [(r.doc_id, r.added) for r in results] == [(first.doc_id, 1)]  # the fully read one isn't touched


def test_cli_reread(ws, tmp_path):
    from click.testing import CliRunner

    from tra.cli import main

    doc = _ingest(ws, tmp_path)
    _learn(tmp_path)
    result = CliRunner().invoke(main, ["reread", "TEST01", "--waiting"],
                                env={"TRA_HOME": str(ws.tra_home), "TRA_STORE": "local"})
    assert result.exit_code == 0, result.output
    assert f"{doc.doc_id} read again by layout sample-bank-yearly: 1 figure added, 0 replaced" in result.output
    assert json.loads(ws.reading_notes_json.read_text(encoding="utf-8"))[doc.doc_id]["layout"] == "sample-bank-yearly"


def test_waiting_means_unread_or_missing_amounts(ws, tmp_path):
    from tra.reread import waiting_documents

    unread = _ingest(ws, tmp_path, name="a.pdf")
    receipt = _ingest(ws, tmp_path, ["SAMPLE SHOP", "TAX INVOICE", "Date: 14/09/2025", "Pens 4.00", "Total 4.00"],
                      name="b.pdf")
    missing = _ingest(ws, tmp_path, ["Income statement", "Payer: SAMPLE CO PTY LTD", "Gross payments 60,000.00"],
                      name="c.pdf")
    assert receipt.parse_status == "partial" and missing.parse_status == "partial"
    assert [d.doc_id for d in waiting_documents(ws)] == [unread.doc_id, missing.doc_id]


def test_read_again_gives_a_readable_name(ws, tmp_path):
    from pathlib import Path

    doc = _ingest(ws, tmp_path)
    _learn(tmp_path)
    reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    [again] = DocumentIndex(ws.index_csv).load()
    assert again.filed_name == "TEST01 2026-07-15 Interest statement - SAMPLE BANK.pdf"
    assert Path(again.filed_location).is_file() and Path(again.filed_location).parent == Path(doc.filed_location).parent
    assert not Path(doc.filed_location).exists()


def _reads(monkeypatch, figures, doubts=(), status="partial", doc_type="RECEIPT"):
    """Make Read again's reader return these figures (Figure(label, amount) pairs) and doubts."""
    from tra.ingest.extractors.base import ExtractResult, figure

    def fake(loaded, doc_types, doc_id, override_type=None, ai_reader=None):
        found = [figure(label, "SAMPLE SHOP", Decimal(amount), doc_id, 1, None) for label, amount in figures]
        return doc_type, ExtractResult(figures=found, parse_status=status, doubts=list(doubts)), None

    monkeypatch.setattr("tra.reread.read_document", fake)


def test_a_file_open_in_another_program_keeps_its_name(ws, tmp_path, monkeypatch):
    from pathlib import Path

    doc = _ingest(ws, tmp_path)
    _learn(tmp_path)

    def locked(self, target):
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(Path, "rename", locked)
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert (result.added, result.status) == (1, "parsed")
    assert "old name" in result.note
    [again] = DocumentIndex(ws.index_csv).load()
    assert again.filed_name == doc.filed_name and Path(again.filed_location).is_file()
    assert '"document_reread"' in ws.audit_path.read_text(encoding="utf-8")


def test_a_renamed_file_has_no_note(ws, tmp_path):
    doc = _ingest(ws, tmp_path)
    _learn(tmp_path)
    assert reread_document(ws, doc.doc_id, AuditLog(ws.audit_path)).note == ""


def test_equal_amounts_are_each_kept(ws, tmp_path, monkeypatch):
    doc = _ingest(ws, tmp_path)
    append_figures(ws.figures_csv, [_fig(doc.doc_id, "parser", True, "40.00", "ded.d5")])
    _reads(monkeypatch, [("ded.d5", "40.00"), ("ded.d5", "40.00")])
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert result.added == 1  # two $40.00 transactions; one was confirmed, so only the other is added
    assert sorted((f.amount, f.confirmed) for f in _figures(ws)) == [(Decimal("40.00"), False),
                                                                      (Decimal("40.00"), True)]


def test_a_corrected_figure_isnt_added_back(ws, tmp_path, monkeypatch):
    from tra.checks import label_name

    doc = _ingest(ws, tmp_path)
    append_figures(ws.figures_csv, [_fig(doc.doc_id, "parser", True, "40100.00")])  # the preparer fixed 40,100.50
    _reads(monkeypatch, [("income.interest", "40100.50")], doubts=["new doubt"])
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert result.added == 0 and [f.amount for f in _figures(ws)] == [Decimal("40100.00")]
    name = label_name(load_labels(), "income.interest")
    assert load_reading_notes(ws)[doc.doc_id]["doubts"] == [
        "new doubt", f"Read again found {name} $40,100.50 but you already have $40,100.00 from this document; check "
                     "which is right."]


def test_a_typed_in_figure_isnt_doubled_either(ws, tmp_path, monkeypatch):
    doc = _ingest(ws, tmp_path)
    append_figures(ws.figures_csv, [_fig(doc.doc_id, "manual", False, "300.00")])
    _reads(monkeypatch, [("income.interest", "321.00"), ("income.interest_tfn_withheld", "5.00")])
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert result.added == 1
    assert sorted((f.label_key, f.amount) for f in _figures(ws)) == [
        ("income.interest", Decimal("300.00")), ("income.interest_tfn_withheld", Decimal("5.00"))]
    assert "but you already have $300.00" in load_reading_notes(ws)[doc.doc_id]["doubts"][0]


def test_ai_figures_for_labels_the_rules_dont_read_are_kept(ws, tmp_path):
    doc = _ingest(ws, tmp_path)
    append_figures(ws.figures_csv, [_fig(doc.doc_id, "ai", False),
                                    _fig(doc.doc_id, "ai", False, "5.00", "income.interest_tfn_withheld")])
    _learn(tmp_path)
    result = reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert result.removed == 1
    assert sorted((f.method, f.label_key, f.amount) for f in _figures(ws)) == [
        ("ai", "income.interest_tfn_withheld", Decimal("5.00")), ("parser", "income.interest", Decimal("321.00"))]


def test_an_emails_attachment_notes_are_kept(ws, tmp_path, monkeypatch):
    import dataclasses

    from tra.ingest.emails import EMBEDDED_SKIPPED

    doc = _ingest(ws, tmp_path)
    DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, doc_type="EMAIL"))
    attachment = "Attachment 2 (.zip) wasn't filed: Sawnx can't use that kind of file. Save it from the email."
    save_reading_notes(ws, doc.doc_id, [attachment, EMBEDDED_SKIPPED, "Only the first 20 attachments were read; 1 "
                                        "more weren't.", "an old reader doubt"])
    _reads(monkeypatch, [], doubts=["new doubt"], doc_type="EMAIL")
    reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))
    assert load_reading_notes(ws)[doc.doc_id]["doubts"] == [
        attachment, EMBEDDED_SKIPPED, "Only the first 20 attachments were read; 1 more weren't.", "new doubt"]


def test_a_documents_old_doubts_are_replaced(ws, tmp_path, monkeypatch):
    doc = _ingest(ws, tmp_path)
    save_reading_notes(ws, doc.doc_id, ["Attachment 1 looks like an email note", "old"])
    _reads(monkeypatch, [], doubts=["new doubt"])
    reread_document(ws, doc.doc_id, AuditLog(ws.audit_path))  # not an email: nothing is carried over
    assert load_reading_notes(ws)[doc.doc_id]["doubts"] == ["new doubt"]


def test_a_layouts_missing_amount_is_waiting(ws, tmp_path):
    from tra.reread import MISSING_PREFIX, waiting_documents

    _learn(tmp_path)
    doc = _ingest(ws, tmp_path, SAMPLE[:3])  # the layout knows it, but the required amount isn't there
    doubts = load_reading_notes(ws)[doc.doc_id]["doubts"]
    assert doubts and doubts[0].startswith(MISSING_PREFIX)
    assert [d.doc_id for d in waiting_documents(ws)] == [doc.doc_id]


def test_a_damaged_reading_notes_file_is_skipped(ws, tmp_path):
    from tra.reread import all_waiting, layout_counts
    from tra.settings import Settings

    _learn(tmp_path)
    _ingest(ws, tmp_path)  # read by the layout
    waiting = _ingest(ws, tmp_path, ["SAMPLE SHOP", "unknown paper"], name="b.pdf")
    other = new_client(Settings.from_env(), code="TEST02")
    other.reading_notes_json.parent.mkdir(parents=True, exist_ok=True)
    other.reading_notes_json.write_text("{not json", encoding="utf-8")
    assert layout_counts(ws.tra_home) == {"sample-bank-yearly": 1}
    assert [(w.client_code, d.doc_id) for w, d in all_waiting(ws.tra_home)] == [("TEST01", waiting.doc_id)]
