"""The AI reader never breaks an import, never sends more than it should, and never writes an identifier.
No network: every client is a stand-in, and every identifier is made up at test time."""

import base64
import io
import json
import random
from datetime import date
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from PIL import Image
from test_ai_reader import FakeClient, _odd_document, _rental_called_interest, _typed_answer
from webctx import make_client, new_client

from tra.figures import read_figures
from tra.filing.local_store import LocalStore
from tra.ingest import page_images
from tra.ingest.classify import load_doc_types
from tra.ingest.extractors.ai_reader import SYSTEM, AiReader, figures_from_items, ai_reader_from_settings
from tra.ingest.extractors.base import ExtractResult
from tra.ingest.page_images import MAX_IMAGE_BYTES, looks_garbled, render_pages
from tra.ingest.pipeline import ingest_file, issuer_of, read_document
from tra.ingest.readers import LoadedDocument
from tra.labels import load_labels
from tra.models import Figure
from tra.privacy.audit import AuditLog
from tra.privacy.detectors import find_sensitive
from tra.privacy.redact import redact_pages
from tra.reading_notes import load_reading_notes
from tra.web.app_settings import enable_ai_page_images, enable_ai_reader

TEXT = ["SAMPLE CREDIT UNION", "Yearly summary for members"]
ON = date(2026, 10, 25)
INTEREST = {"label_key": "income.interest", "description": "SAMPLE CREDIT UNION – interest", "amount": "123.45",
            "page": 1}
JPEG = b"\xff\xd8"


def _connection_error():
    return anthropic.APIConnectionError(request=httpx2.Request("POST", "https://example.invalid"))


class FlakyClient:
    """Raises an SDK error for every request (``always``) or only for requests carrying pictures."""

    def __init__(self, text, *, always=False):
        self.calls, self._text, self._always = [], text, always
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = kwargs["messages"][0]["content"]
        if self._always or isinstance(content, list):
            raise _connection_error()
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self._text)])


def _answer(*figures, doc_type="OTHER"):
    return json.dumps({"doc_type": doc_type, "figures": list(figures)})


def _setup(tmp_path, monkeypatch, client, *, images=True):
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    audit = AuditLog(tmp_path / "settings.jsonl")
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, audit)
    if images:
        enable_ai_page_images(settings.tra_home, "Privacy Officer", ON, audit)
    reader = ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}, client=client)
    return settings, new_client(settings), reader


def _ingest(settings, ws, path, reader):
    return ingest_file(path, ws, LocalStore(settings.tra_home), load_doc_types(), AuditLog(ws.audit_path),
                       ai_reader=reader)


def _has_images(call):
    content = call["messages"][0]["content"]
    return isinstance(content, list) and any(b["type"] == "image" for b in content)


# --- 2. an import never crashes because of the AI --------------------------------------------------------------

def test_an_api_error_files_the_document_with_notes(tmp_path, monkeypatch):
    client = FlakyClient(_answer(INTEREST), always=True)
    settings, ws, reader = _setup(tmp_path, monkeypatch, client, images=False)
    report = _ingest(settings, ws, _odd_document(tmp_path), reader)
    assert len(client.calls) == 1 and report.figures_added == 0
    assert report.doc.parse_status == "manual_needed"
    checks = [n.check_id for n in report.notes]
    assert "A3" in checks and "I1" in checks
    a3 = next(n for n in report.notes if n.check_id == "A3")
    assert a3.message.startswith("The AI reader couldn't give a usable answer")


def test_a_failed_request_with_pictures_is_retried_as_text(tmp_path, monkeypatch, make_pdf):
    client = FlakyClient(_answer({**INTEREST, "page": 3}))
    settings, ws, reader = _setup(tmp_path, monkeypatch, client)
    report = _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None, ["Interest credited this year 123.45"]]),
                     reader)
    assert [_has_images(c) for c in client.calls] == [True, False]
    assert isinstance(client.calls[1]["messages"][0]["content"], str)
    assert "picture" not in client.calls[1]["system"]
    assert report.figures_added == 1
    doubts = load_reading_notes(ws)[report.doc.doc_id]["doubts"]
    assert any("Page(s) 2" in d and "by hand" in d for d in doubts)


def test_both_requests_failing_still_files_the_document(tmp_path, monkeypatch, make_pdf):
    client = FlakyClient(_answer(INTEREST), always=True)
    settings, ws, reader = _setup(tmp_path, monkeypatch, client)
    report = _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None, ["Interest credited this year 123.45"]]),
                     reader)
    assert len(client.calls) == 2 and report.figures_added == 0
    assert {"A3", "I1"} <= {n.check_id for n in report.notes}
    assert report.doc.filed_location


def test_a_page_that_wont_draw_doesnt_stop_the_import(tmp_path, monkeypatch, make_pdf):
    def broken(*_args, **_kwargs):
        raise RuntimeError("Failed to load page.")

    monkeypatch.setattr("tra.ingest.pipeline.render_pages", broken)
    client = FakeClient(_answer({**INTEREST, "page": 3}))
    settings, ws, reader = _setup(tmp_path, monkeypatch, client)
    report = _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None, ["Interest credited this year 123.45"]]),
                     reader)
    [call] = client.calls
    assert isinstance(call["messages"][0]["content"], str) and report.figures_added == 1
    doubts = load_reading_notes(ws)[report.doc.doc_id]["doubts"]
    assert ("Page(s) 2 weren't sent as pictures (too many, or too large). Enter their figures by hand.") in doubts


# --- 3. small enough pictures ----------------------------------------------------------------------------------

def test_pictures_are_greyscale_jpegs(make_pdf):
    [(page, data)] = render_pages(make_pdf("scan.pdf", [TEXT, None]), [2])
    image = Image.open(io.BytesIO(data))
    assert page == 2 and data.startswith(JPEG) and image.format == "JPEG" and image.mode == "L"


def test_a_huge_page_is_scaled_down(tmp_path):
    from reportlab.pdfgen import canvas

    path = tmp_path / "plan.pdf"
    c = canvas.Canvas(str(path), pagesize=(3000, 1200))  # about 42 x 17 inches: 4600 pixels wide at 110 dpi
    c.drawString(50, 600, "SAMPLE PLAN 1,000.00")
    c.showPage()
    c.save()
    [(_page, data)] = render_pages(path, [1])
    width, height = Image.open(io.BytesIO(data)).size
    assert max(width, height) <= 2000 and width > height


def test_pictures_stop_at_the_size_budget(tmp_path, monkeypatch, make_pdf):
    assert MAX_IMAGE_BYTES == 20 * 1024 * 1024
    big = JPEG + b"\0" * (6 * 1024 * 1024)  # 8 MB once base64-encoded: two fit, the third doesn't
    monkeypatch.setattr(page_images, "_render_page", lambda *_args, **_kwargs: big)
    sent = render_pages(make_pdf("scan.pdf", [None, None, None, None]), [1, 2, 3, 4])
    assert [n for n, _ in sent] == [1, 2]
    assert sum(len(base64.b64encode(data)) for _, data in sent) <= MAX_IMAGE_BYTES


def test_pages_not_sent_get_a_doubt(tmp_path, monkeypatch, make_pdf):
    client = FakeClient(_answer({**INTEREST, "page": 2}))
    settings, ws, reader = _setup(tmp_path, monkeypatch, client)
    report = _ingest(settings, ws, make_pdf("long.pdf", [TEXT] + [None] * 22), reader)
    [call] = client.calls
    assert sum(b["type"] == "image" for b in call["messages"][0]["content"]) == 20
    assert all(b["source"]["media_type"] == "image/jpeg"
               for b in call["messages"][0]["content"] if b["type"] == "image")
    doubts = load_reading_notes(ws)[report.doc.doc_id]["doubts"]
    assert "Page(s) 22, 23 weren't sent as pictures (too many, or too large). Enter their figures by hand." in doubts


# --- 5. descriptions never carry an identifier -----------------------------------------------------------------

def _bank_details():
    rng = random.Random()
    bsb = f"{rng.randint(100, 999)}-{rng.randint(100, 999)}"
    account = "".join(str(rng.randint(0, 9)) for _ in range(8))
    return f"SAMPLE BANK – interest, account {account} BSB {bsb}"


def test_the_prompt_says_never_copy_identifiers():
    rule = "Never copy account numbers, BSBs, TFNs, card or licence numbers into a description."
    assert rule in SYSTEM


def test_an_identifier_in_a_description_is_blanked(tmp_path, monkeypatch):
    description = _bank_details()
    assert find_sensitive(description)
    client = FakeClient(_answer({**INTEREST, "description": description}))
    settings, ws, reader = _setup(tmp_path, monkeypatch, client, images=False)
    report = _ingest(settings, ws, _odd_document(tmp_path), reader)
    assert report.figures_added == 1
    [f] = read_figures(ws.figures_csv, load_labels())[0]
    assert f.description.startswith("AI: SAMPLE BANK") and find_sensitive(f.description) == []
    assert "REDACTED" in f.description


def test_figures_from_items_blanks_identifiers_for_the_ai_reader():
    description = _bank_details()
    [f], problems = figures_from_items([{**INTEREST, "description": description}], ["income.interest"], "D001", 1,
                                       "AI")
    assert problems == [] and find_sensitive(f.description) == []


# --- 6. types with special meaning -----------------------------------------------------------------------------

SPECIAL = ["PREFILL", "PRIOR", "XEROPL", "XEROBS", "XEROBANK", "XEROCOA"]


def test_special_types_arent_offered():
    client = FakeClient(_answer())
    AiReader(client).extract(redact_pages(["SAMPLE CREDIT UNION interest 1.00"]), "D001")
    [call] = client.calls
    enum = call["output_config"]["format"]["schema"]["properties"]["doc_type"]["enum"]
    assert not set(SPECIAL) & set(enum)
    for code in SPECIAL:
        assert f"\n{code}:" not in call["system"]


@pytest.mark.parametrize("code", SPECIAL)
def test_a_special_type_from_the_ai_changes_nothing(tmp_path, monkeypatch, code):
    settings, ws, reader = _setup(tmp_path, monkeypatch, FakeClient(_typed_answer(code)), images=False)
    report = _ingest(settings, ws, _rental_called_interest(tmp_path), reader)
    assert report.doc.doc_type == "INTSTMT" and report.figures_added == 1


# --- 7. ordinary text isn't garbled ----------------------------------------------------------------------------

@pytest.mark.parametrize("line", [
    "01JUL25 TFR 12.00DR 1,222.56CR",
    "15AUG2025 DEP 1,234.56CR 30SEP25 FEE 2.50DR",
    "FY2025-26 Q1 12.5k Q2 3.1k",
    "José Müller and Zoë Ångström 1,000.00",
    "Müller-Lüdenscheidt O’Brien Ñúñez",
    "利息收入 年度汇总 123.45 存款账户 合计",
])
def test_ordinary_lines_arent_garbled(line):
    assert not looks_garbled(line)


@pytest.mark.parametrize("soup", [
    "Th3 qu!ck br0wn ~~ |||l1 %$#@ fx0x 9a9 ;;;; Int3r3st 1O0.0O",
    "~~~ |||| Int3r3st #@! 1O0.0O b4l4nc3 %%%",
])
def test_ocr_soup_is_still_garbled(soup):
    assert looks_garbled(soup)


# --- 8. the built-in reader's doubts are kept ------------------------------------------------------------------

def test_an_ai_type_keeps_the_built_in_readers_doubts(monkeypatch):
    class Doubtful:
        def extract(self, _rt, _doc_id):
            return ExtractResult(doubts=["The statement period wasn't clear."])

    monkeypatch.setattr("tra.ingest.pipeline.get_extractor", lambda _doc_type: Doubtful())
    loaded = LoadedDocument(redacted=redact_pages(["SAMPLE REALTY", "Interest summary", "Rent received 1,000.00"]),
                            sha256="0" * 64, page_count=1, image_only_pages=(), suffix=".pdf")
    doc_type, result, _layout = read_document(loaded, load_doc_types(), "D001",
                                              ai_reader=AiReader(FakeClient(_typed_answer("RENTSTMT"))))
    assert doc_type == "RENTSTMT"
    assert result.doubts[0] == "The statement period wasn't clear."
    assert result.doubts[1].startswith("Type set by the AI reader: Rental / property manager statement")


# --- 9. the I1 note says when pictures went out ----------------------------------------------------------------

def test_i1_says_the_scans_went_as_pictures(tmp_path, monkeypatch, make_pdf):
    client = FakeClient(_answer({**INTEREST, "page": 2}))
    settings, ws, reader = _setup(tmp_path, monkeypatch, client)
    report = _ingest(settings, ws, make_pdf("scan.pdf", [TEXT, None]), reader)
    [i1] = [n for n in report.notes if n.check_id == "I1"]
    assert ("Page(s) 2 had no text and were sent to the AI reader as pictures; check its figures against the "
            "document.") in i1.message
    assert "Add its figures" not in i1.message


def test_i1_without_pictures_still_asks_for_manual_entry(tmp_path, monkeypatch, make_pdf):
    client = FakeClient(_answer({**INTEREST, "page": 1}))
    settings, ws, reader = _setup(tmp_path, monkeypatch, client, images=False)
    report = _ingest(settings, ws, make_pdf("scan.pdf", [TEXT + ["Interest credited 123.45"], None]), reader)
    [i1] = [n for n in report.notes if n.check_id == "I1"]
    assert "have no text (scanned?)" in i1.message and "Add its figures" in i1.message
    assert "as pictures" not in i1.message


# --- 10. the AI's words never name a file ----------------------------------------------------------------------

def test_issuer_ignores_ai_figures():
    f = Figure(figure_id="", label_key="income.salary", description="AI: SAMPLE EMPLOYER PTY LTD – gross payments",
               amount=1, date=None, doc_id="D001", page=1, method="ai", confirmed=False, substantiated=None)
    assert issuer_of([f], "INCSTMT") is None


def test_an_ai_typed_income_statement_has_no_issuer_in_its_name(tmp_path, monkeypatch):
    answer = _answer({"label_key": "income.salary", "description": "SAMPLE EMPLOYER PTY LTD – gross payments",
                      "amount": "50000.00", "page": 1}, doc_type="INCSTMT")
    settings, ws, reader = _setup(tmp_path, monkeypatch, FakeClient(answer), images=False)
    report = _ingest(settings, ws, _odd_document(tmp_path), reader)
    assert report.doc.doc_type == "INCSTMT" and report.figures_added == 1
    name = report.doc.filed_name.upper()
    assert "SAMPLE" not in name and "EMPLOYER" not in name and "AI " not in name and "AI:" not in name


# --- 11. pictures only when the reader allows them -------------------------------------------------------------

def test_the_reader_drops_pictures_unless_allowed():
    client = FakeClient(_answer())
    sent = []
    AiReader(client).extract(redact_pages(["SAMPLE CREDIT UNION interest 1.00", ""]), "D001",
                             [(2, JPEG + b"picture")], on_send=sent.append)
    [call] = client.calls
    assert isinstance(call["messages"][0]["content"], str) and sent == []
    assert "picture" not in call["system"]


# --- 12. the client gives up in good time ----------------------------------------------------------------------

def test_the_client_has_a_timeout_and_one_retry(tmp_path, monkeypatch):
    made = []
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: made.append(kwargs) or FakeClient())
    _app, _web, settings = make_client(tmp_path, monkeypatch)
    enable_ai_reader(settings.tra_home, "Privacy Officer", ON, AuditLog(tmp_path / "a.jsonl"))
    assert isinstance(ai_reader_from_settings(settings.tra_home, {"ANTHROPIC_API_KEY": "x"}), AiReader)
    assert made == [{"api_key": "x", "timeout": 120, "max_retries": 1}]
