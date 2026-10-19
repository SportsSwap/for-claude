"""Claude reading documents in chat: `tra ai-text` shows only blanked-out text, `tra ai-add` adds unconfirmed figures."""

import csv
import json

import pytest
from click.testing import CliRunner

from tra.cli import main
from tra.demo import _write_pdf
from tra.filing.index import DocumentIndex
from tra.notes_store import read_notes
from tra.workspace import Workspace


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def _run(home, *args, input=None):
    return CliRunner().invoke(main, list(args), env={"TRA_HOME": str(home), "TRA_STORE": "local"}, input=input)


@pytest.fixture
def client(home, tmp_path, make_tfn):
    """TEST05 with one document the rules read and one they can't (with a TFN in it)."""
    tfn = make_tfn()
    readable, odd = tmp_path / "dividend.pdf", tmp_path / "odd.pdf"
    _write_pdf(readable, ["SAMPLE MINING LTD", "Dividend statement", "Payment date 20 March 2026",
                          "Unfranked amount 0.00", "Franked amount 700.00", "Franking credit 300.00"])
    _write_pdf(odd, ["SAMPLE CREDIT UNION", "Yearly summary for members", f"Member TFN {tfn}",
                     "Interest credited this year 123.45"])
    assert _run(home, "new", "TEST05").exit_code == 0
    assert _run(home, "ingest", "TEST05", str(readable), str(odd)).exit_code == 0
    ws = Workspace(home, "TEST05", 2026)
    docs = {d.doc_type: d for d in DocumentIndex(ws.index_csv).load()}
    return ws, docs["DIVSTMT"], docs["OTHER"], tfn


def _figures(ws):
    with ws.figures_csv.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _answer(*figures):
    return json.dumps({"figures": list(figures)})


INTEREST = {"label_key": "income.interest", "description": "SAMPLE CREDIT UNION interest", "amount": "123.45", "page": 1}


def test_ai_text_shows_only_unread_documents_blanked_out(home, client):
    ws, readable, odd, tfn = client
    result = _run(home, "ai-text", "TEST05")
    assert result.exit_code == 0, result.output
    assert odd.doc_id in result.output and "Interest credited this year 123.45" in result.output
    assert "[TFN REDACTED]" in result.output and tfn not in result.output.replace(" ", "")
    assert "Franked amount" not in result.output  # the rules already read that one
    assert "income.interest" in result.output  # the labels Claude may use
    assert "document_text_shown_to_claude" in ws.audit_path.read_text(encoding="utf-8")


def test_ai_add_adds_unconfirmed_figures(home, client):
    ws, _readable, odd, _tfn = client
    result = _run(home, "ai-add", "TEST05", odd.doc_id, _answer(INTEREST))
    assert result.exit_code == 0, result.output
    [row] = [r for r in _figures(ws) if r["doc_id"] == odd.doc_id]
    assert (row["label_key"], row["amount"], row["method"], row["confirmed"]) == ("income.interest", "123.45", "ai", "N")
    assert row["description"].startswith("Claude:") and row["page"] == "1"
    assert next(d for d in DocumentIndex(ws.index_csv).load() if d.doc_id == odd.doc_id).parse_status == "partial"
    assert not [n for n in read_notes(ws.ingest_notes_json) if n.check_id == "I1" and odd.doc_id in n.doc_ids]
    assert "Nothing to read" in _run(home, "ai-text", "TEST05").output
    again = _run(home, "ai-add", "TEST05", odd.doc_id, _answer(INTEREST))
    assert again.exit_code != 0 and "already" in again.output
    assert "claude_read_document" in ws.audit_path.read_text(encoding="utf-8")


def test_ai_add_reads_the_answer_from_stdin(home, client):
    ws, _readable, odd, _tfn = client
    assert _run(home, "ai-add", "TEST05", odd.doc_id, "-", input=_answer(INTEREST)).exit_code == 0
    assert [r["amount"] for r in _figures(ws) if r["doc_id"] == odd.doc_id] == ["123.45"]


@pytest.mark.parametrize("bad", [
    {**INTEREST, "label_key": "income.nonsense"},
    {**INTEREST, "amount": "about a hundred"},
    {**INTEREST, "page": 9},
    {**INTEREST, "label_key": "cgt.net_gain"},  # worked out by the tool, never typed in
])
def test_ai_add_rejects_a_bad_answer_whole(home, client, bad):
    ws, _readable, odd, _tfn = client
    before = _figures(ws)
    result = _run(home, "ai-add", "TEST05", odd.doc_id, _answer(INTEREST, bad))
    assert result.exit_code != 0
    assert _figures(ws) == before


def test_ai_add_only_for_documents_it_can_read(home, client):
    _ws, readable, _odd, _tfn = client
    assert _run(home, "ai-add", "TEST05", "D999", _answer(INTEREST)).exit_code != 0
    assert _run(home, "ai-add", "TEST05", "D001", "not json").exit_code != 0


def test_text_with_an_identifier_left_is_never_shown(home, client, monkeypatch):
    _ws, _readable, odd, _tfn = client
    monkeypatch.setattr("tra.claude_reads.find_sensitive", lambda text: ["something"])
    result = _run(home, "ai-text", "TEST05")
    assert "Interest credited" not in result.output and "privacy officer" in result.output


def test_output_never_crashes_on_an_old_text_encoding(home, tmp_path):
    """Windows pipes can use an encoding without characters such as the arrow in ingest's output."""
    doc = tmp_path / "statement.pdf"
    _write_pdf(doc, ["SAMPLE BANK", "Account statement", "Interest earned 5.00"])
    runner = CliRunner(charset="cp1252")
    env = {"TRA_HOME": str(home), "TRA_STORE": "local"}
    assert runner.invoke(main, ["new", "TEST06"], env=env).exit_code == 0
    result = runner.invoke(main, ["ingest", "TEST06", str(doc)], env=env)
    assert result.exit_code == 0, result.output
