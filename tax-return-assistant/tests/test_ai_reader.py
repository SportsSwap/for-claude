"""The AI reader is built but off. These tests never call the network: the client is a stand-in."""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from webctx import make_client, new_client

from tra.checks.reconcile import check_reconcile
from tra.demo import _write_pdf
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.extractors.ai_reader import DEFAULT_MODEL, AiReader, ai_reader_from_settings
from tra.ingest.pipeline import ingest_file
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
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if self._fail:
            raise AssertionError("the AI reader must not be called here")
        self.calls.append(kwargs)
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
    assert ai_reader_from_settings(settings.tra_home, {}) is None  # on, but no key
    reader = ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}, client=FakeClient())
    assert isinstance(reader, AiReader) and reader.model == DEFAULT_MODEL == "claude-opus-5-5"


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
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in call["betas"]
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
