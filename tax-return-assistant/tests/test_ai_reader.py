"""The AI reader is built but off. These tests never call the network: the client is a stand-in."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from webctx import make_client, new_client

from tra.checks.reconcile import check_reconcile
from tra.demo import _write_pdf
from tra.filing.local_store import LocalStore
from tra.ingest.classify import classify, load_doc_types
from tra.ingest.extractors.ai_reader import DEFAULT_MODEL, AiReader, AiReaderUnavailable, ai_reader_from_settings
from tra.ingest.pipeline import ingest_file, read_document
from tra.ingest.readers import LoadedDocument, load
from tra.reading_notes import load_reading_notes
from tra.privacy.audit import AuditLog
from tra.privacy.detectors import find_sensitive
from tra.privacy.redact import _KEY, RedactedText, redact_pages
from tra.web.app_settings import enable_ai_reader

from checkctx import fig, ids, make_ctx


class FakeClient:
    """Records each request and answers with the given text (or raises if told to)."""

    def __init__(self, text="", stop_reason="end_turn", fail=False):
        self.calls = []
        self._text, self._stop, self._fail = text, stop_reason, fail
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: self._create(beta=True, **kw)))
        self.messages = SimpleNamespace(create=lambda **kw: self._create(beta=False, **kw))

    def _create(self, beta, **kwargs):
        if self._fail:
            raise AssertionError("the AI reader must not be called here")
        self.calls.append({**kwargs, "_beta": beta})
        return SimpleNamespace(stop_reason=self._stop, content=[SimpleNamespace(type="text", text=self._text)])


def _answer(*figures):
    return json.dumps({"figures": list(figures)})


def _odd_document(tmp_path):
    """A layout no built-in reader knows: classified OTHER, so it has no figures of its own."""
    path = tmp_path / "odd.pdf"
    _write_pdf(path, ["SAMPLE CREDIT UNION", "Yearly summary for members", "Interest credited this year 123.45"])
    return path


def test_off_by_default(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    assert ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}) is None
    enable_ai_reader(settings.tra_home, "Privacy Officer", date(2026, 10, 20), AuditLog(tmp_path / "a.jsonl"))
    with pytest.raises(AiReaderUnavailable, match="ANTHROPIC_API_KEY"):
        ai_reader_from_settings(settings.tra_home, {})  # on, but no key: say so rather than skip it quietly
    reader = ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}, client=FakeClient())
    assert isinstance(reader, AiReader) and reader.model == DEFAULT_MODEL == "claude-haiku-5-5"


def test_key_saved_for_the_windows_account_is_used(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    enable_ai_reader(settings.tra_home, "Privacy Officer", date(2026, 10, 20), AuditLog(tmp_path / "a.jsonl"))
    monkeypatch.setattr("tra.settings.saved_user_variable", lambda name: "x" if name == "ANTHROPIC_API_KEY" else "")
    assert isinstance(ai_reader_from_settings(settings.tra_home, {}, client=FakeClient()), AiReader)


def test_never_called_when_off(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    report = ingest_file(_odd_document(tmp_path), ws, LocalStore(settings.tra_home), load_doc_types(),
                         AuditLog(ws.audit_path))
    assert report.figures_added == 0 and report.doc.parse_status == "manual_needed"


def test_refuses_unredacted_text(make_tfn):
    client = FakeClient(_answer())
    leaked = RedactedText(pages=(f"Member TFN {make_tfn()} interest 10.00",), counts={}, _key=_KEY)
    result = AiReader(client).extract(leaked, "D001")
    assert client.calls == [] and result.figures == []
    assert [n.check_id for n in result.notes] == ["A2"]


def test_rejects_non_redacted_object():
    with pytest.raises(TypeError):
        AiReader(FakeClient(_answer())).extract("plain text", "D001")


def test_mock_response_becomes_unconfirmed_ai_figures(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    client = FakeClient(_answer({"label_key": "income.interest", "description": "Interest credited",
                                 "amount": "123.45", "page": 1}))
    report = ingest_file(_odd_document(tmp_path), ws, LocalStore(settings.tra_home), load_doc_types(),
                         AuditLog(ws.audit_path), ai_reader=AiReader(client))
    assert report.figures_added == 1
    [call] = client.calls
    # Claude Haiku 5.5 has no server-side fallback, so the plain endpoint is used, without fallbacks.
    assert call["model"] == "claude-haiku-5-5" and not call["_beta"]
    assert "fallbacks" not in call and "betas" not in call
    sent = json.dumps(call["messages"]) + call["system"]
    assert "123.45" in sent and find_sensitive(sent) == []
    from tra.figures import read_figures
    from tra.labels import load_labels
    [f] = read_figures(ws.figures_csv, load_labels())[0]
    assert (f.method, f.confirmed, f.amount, f.doc_id, f.page) == ("ai", False, Decimal("123.45"), "D001", 1)


@pytest.mark.parametrize("text", ["not json", _answer({"label_key": "nope.nothing", "description": "x",
                                                         "amount": "1", "page": 1}),
                                  _answer({"label_key": "income.interest", "description": "x", "amount": "abc",
                                           "page": 1})])
def test_bad_response_adds_nothing(text):
    rt = redact_pages(["Interest credited this year 123.45"])
    result = AiReader(FakeClient(text)).extract(rt, "D001")
    assert result.figures == [] and [n.check_id for n in result.notes] == ["A3"]


def test_refusal_adds_nothing():
    rt = redact_pages(["Interest credited this year 123.45"])
    result = AiReader(FakeClient("", stop_reason="refusal")).extract(rt, "D001")
    assert result.figures == [] and [n.check_id for n in result.notes] == ["A3"]


def test_r6_raised_for_ai_figures():
    f = fig("F1", "income.interest", 100)
    f.method = "ai"
    [note] = ids(check_reconcile(make_ctx([f])), "R6")
    assert note.risk == "Medium" and "AI reader" in note.message
    assert ids(check_reconcile(make_ctx([fig("F1", "income.interest", 100)])), "R6") == []


def test_a_model_with_fallbacks_still_asks_for_them(tmp_path):
    client = FakeClient(_answer())
    AiReader(client, model="claude-opus-5-5").extract(redact_pages(["SAMPLE CREDIT UNION interest 1.00"]), "D001")
    [call] = client.calls
    assert call["_beta"] and call["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in call["betas"]


def _typed_answer(doc_type):
    return json.dumps({"doc_type": doc_type, "figures": [{"label_key": "rent.gross", "description": "Rent received",
                                                         "amount": "1000.00", "page": 1}]})


def _rental_called_interest(tmp_path):
    """A property manager's statement whose words make Sawnx's classifier guess an interest summary."""
    path = tmp_path / "rental.pdf"
    _write_pdf(path, ["SAMPLE REALTY", "Interest summary of the trust account", "Rent received 1,000.00"])
    return path


def test_the_schema_lists_the_document_types():
    client = FakeClient(_answer())
    AiReader(client).extract(redact_pages(["SAMPLE CREDIT UNION interest 1.00"]), "D001")
    [call] = client.calls
    schema = call["output_config"]["format"]["schema"]
    enum = schema["properties"]["doc_type"]["enum"]
    assert "doc_type" in schema["required"]
    assert {"RENTSTMT", "INTSTMT", "OTHER"} <= set(enum)
    assert not {"INFOREQ", "EMAIL", "CLIENTXLS"} & set(enum)
    assert "RENTSTMT" in call["system"] and "OTHER" in call["system"]


def test_ai_type_moves_the_document_to_its_folder(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    path = _rental_called_interest(tmp_path)
    assert classify(load(path).redacted, load_doc_types()) == "INTSTMT"  # what Sawnx would guess on its own
    report = ingest_file(path, ws, LocalStore(settings.tra_home), load_doc_types(), AuditLog(ws.audit_path),
                         ai_reader=AiReader(FakeClient(_typed_answer("RENTSTMT"))))
    assert report.doc.doc_type == "RENTSTMT" and report.doc.category == "Rental"
    assert "Rental" in Path(report.doc.filed_location).parts
    doubts = load_reading_notes(ws)[report.doc.doc_id]["doubts"]
    assert ("Type set by the AI reader: Rental / property manager statement (Sawnx guessed Interest summary). "
            "Change it on the document if that's wrong.") in doubts


@pytest.mark.parametrize("bad", ["NOPE", "EMAIL", "INFOREQ", None, 7])
def test_an_invalid_ai_type_changes_nothing(tmp_path, monkeypatch, bad):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    report = ingest_file(_rental_called_interest(tmp_path), ws, LocalStore(settings.tra_home), load_doc_types(),
                         AuditLog(ws.audit_path), ai_reader=AiReader(FakeClient(_typed_answer(bad))))
    assert report.doc.doc_type == "INTSTMT" and report.figures_added == 1
    assert not any("Type set" in d for d in load_reading_notes(ws).get(report.doc.doc_id, {}).get("doubts", []))


def test_a_forced_type_is_kept(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    report = ingest_file(_odd_document(tmp_path), ws, LocalStore(settings.tra_home), load_doc_types(),
                         AuditLog(ws.audit_path), override_type="INTSTMT",
                         ai_reader=AiReader(FakeClient(_typed_answer("RENTSTMT"))))
    assert report.doc.doc_type == "INTSTMT" and report.figures_added == 1  # the AI read it, but the type stays


def test_an_email_keeps_its_type():
    loaded = LoadedDocument(redacted=redact_pages(["Subject: figures\n\nThe two amounts are 1,000.00 and 2,000.00"]), sha256="0" * 64,
                            page_count=1, image_only_pages=(), suffix=".eml")
    client = FakeClient(_typed_answer("RENTSTMT"))
    doc_type, _result, _layout = read_document(loaded, load_doc_types(), "D001", ai_reader=AiReader(client))
    assert client.calls and doc_type == "EMAIL"


def test_settings_show_the_model_and_find_a_saved_key(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    enable_ai_reader(settings.tra_home, "Privacy Officer", date(2026, 10, 25), AuditLog(tmp_path / "a.jsonl"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("tra.settings.saved_user_variable",
                        lambda name: "saved-for-this-account" if name == "ANTHROPIC_API_KEY" else "")
    page = client.get("/settings").get_data(as_text=True)
    assert "Claude Haiku 5.5" in page
    assert "isn&#39;t set for this Windows account" not in page and "isn't set for this Windows account" not in page
