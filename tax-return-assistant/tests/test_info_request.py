"""Make info request: a Word checklist for this year's papers, built from last year's return. Made-up data only."""

import csv
import io
import zipfile
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

import pytest

from webctx import make_client, new_client

from tra.figures import CGT_COLUMNS, append_figures
from tra.info_request import build_request
from tra.docx_writer import write_docx
from tra.models import Figure
from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.client_names import set_name


def _fig(key, description, amount="100.00", confirmed=True):
    return Figure(figure_id="", label_key=key, description=description, amount=Decimal(amount), date=None,
                  doc_id="D001", page=1, method="parser", confirmed=confirmed, substantiated=None)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    from tra.settings import Settings

    return Settings.from_env()


def _last_year(settings, figures):
    last = new_client(settings, "TEST01", fy=2025)
    append_figures(last.figures_csv, figures)
    return last


def _text(req) -> str:
    return "\n".join([req.title, req.greeting, req.intro] + [h + "\n" + "\n".join(items) for h, items in req.sections]
                     + [req.closing])


def test_items_from_last_year(home):
    _last_year(home, [_fig("income.salary", "SAMPLE CO PTY LTD – gross payments", "60000.00"),
                      _fig("income.interest", "SAMPLE BANK – interest", "412.35"),
                      _fig("income.interest", "OTHER SAMPLE BANK – interest", "20.00"),
                      _fig("income.div_franked", "SAMPLE MINING LTD – franked amount", "700.00"),
                      _fig("ded.d5", "SAMPLE ASSOCIATION: membership", "250.00"),
                      _fig("ded.d9", "Sheet 1 row 2: Red Cross donation", "500.00")])
    req = build_request(new_client(home, "TEST01", fy=2026))
    assert req.from_last_year and req.year == 2026
    assert req.title == "Information request: 2026 income year (1 July 2025 – 30 June 2026)"
    headings = [h for h, _ in req.sections]
    assert headings == ["Income", "Interest", "Dividends", "Deductions you claimed last year", "Anything new this year?"]
    text = _text(req)
    for payer in ("SAMPLE CO PTY LTD", "SAMPLE BANK and OTHER SAMPLE BANK", "SAMPLE MINING LTD"):
        assert payer in text
    for amount in ("412", "60,000", "60000", "700.00", "$700", "250.00", "$250", "$500", "500.00"):
        assert amount not in text  # last year's amounts are never written (fixed wording like "$2 or more" is)
    assert "Sheet 1" not in text
    deductions = dict(req.sections)["Deductions you claimed last year"]
    assert len(deductions) == 2 and any("donation" in i.lower() for i in deductions)


def test_unconfirmed_last_year_ignored(home):
    _last_year(home, [_fig("income.interest", "SAMPLE BANK – interest", confirmed=False)])
    req = build_request(new_client(home, "TEST01", fy=2026))
    assert not req.from_last_year


def test_ai_read_payer_prefix_dropped(home):
    _last_year(home, [_fig("income.interest", "Claude: SAMPLE BANK – interest")])
    assert "SAMPLE BANK" in dict(build_request(new_client(home, "TEST01", fy=2026)).sections)["Interest"][0]


def test_cgt_last_year(home):
    last = _last_year(home, [])
    with last.cgt_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CGT_COLUMNS)
        writer.writerow(["C001", "SAMPLE MINING LTD shares", "2020-02-01", "2025-03-03", "3500", "2000", "", "",
                         "yes"])
    req = build_request(new_client(home, "TEST01", fy=2026))
    [item] = dict(req.sections)["Things you sold"]
    assert "SAMPLE MINING LTD shares" in item and "3500" not in item


def test_prior_year_csv_fallback(home):
    ws = new_client(home, "TEST01", fy=2026)
    ws.prior_year_csv.write_text("label_key,amount\nincome.interest,412.35\nded.d10,330\n", encoding="utf-8")
    req = build_request(ws)
    assert req.from_last_year
    assert [h for h, _ in req.sections] == ["Interest", "Deductions you claimed last year", "Anything new this year?"]
    assert "412" not in _text(req)


def test_no_last_year_standard_checklist(home):
    req = build_request(new_client(home, "TEST01", fy=2026))
    assert not req.from_last_year
    assert "standard list" in req.intro
    headings = [h for h, _ in req.sections]
    assert "Income" in headings and "Deductions" in headings and headings[-1] == "Anything new this year?"


def test_docx_opens(tmp_path):
    paragraphs = [("title", "Information request"), ("heading", "Income"), ("item", "Statements from A & B <Ltd>"),
                  ("text", "Thank you.")]
    a, b = tmp_path / "a.docx", tmp_path / "b.docx"
    write_docx(a, paragraphs, "a.docx")
    write_docx(b, paragraphs, "b.docx")
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(io.BytesIO(a.read_bytes())) as z:
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
                "word/_rels/document.xml.rels"} <= set(z.namelist())
        document = z.read("word/document.xml").decode("utf-8")
        for name in z.namelist():
            ElementTree.fromstring(z.read(name))  # every part is well-formed XML
    assert "☐ Statements from A &amp; B &lt;Ltd&gt;" in document and "Thank you." in document


def test_guard_blocks_identifier(tmp_path, make_tfn):
    path = tmp_path / "a.docx"
    with pytest.raises(SensitiveDataBlocked):
        write_docx(path, [("text", f"Your TFN is {make_tfn()}")], "a.docx")
    assert not path.exists()


def test_route_files_in_correspondence_letters(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    last = new_client(settings, "TEST01", fy=2025)
    append_figures(last.figures_csv, [_fig("income.interest", "SAMPLE BANK – interest")])
    ws = new_client(settings, "TEST01", fy=2026)
    set_name(settings.tra_home, "TEST01", "Jane Citizen", AuditLog(ws.audit_path))
    resp = client.post("/c/TEST01/2026/info-request")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/files?cab=CORR&view=D001")
    folder = settings.tra_home / "Clients" / "TEST01" / "Correspondence" / "Letters"
    [filed] = list(folder.iterdir())
    assert filed.name == f"TEST01 {date.today().isoformat()} Information request.docx"
    with zipfile.ZipFile(filed) as z:
        document = z.read("word/document.xml").decode("utf-8")
    assert "SAMPLE BANK" in document and "Jane" not in document and "Citizen" not in document
    audit = ws.audit_path.read_text(encoding="utf-8")
    assert '"info_request_made"' in audit and "Jane" not in audit
    uploads = ws.work_dir / "_uploads"
    assert not uploads.exists() or not any(uploads.iterdir())
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Info request" in page and filed.name in page


def test_button_on_files_tab(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    page = client.get("/c/TEST01/2026/files").get_data(as_text=True)
    assert 'action="/c/TEST01/2026/info-request"' in page and "Make info request" in page
    assert 'action="/c/TEST01/2026/info-request"' not in client.get("/c/TEST01/2026/files?cab=CORR").get_data(
        as_text=True)


def test_client_name_and_blanked_text_never_named_as_payers(home):
    ws25 = _last_year(home, [_fig("income.interest", "JANE CITIZEN – interest"),
                             _fig("income.interest", "SAMPLE BANK [ACCOUNT REDACTED] – interest"),
                             _fig("income.interest", "SAMPLE BANK – interest")])
    set_name(home.tra_home, "TEST01", "Jane Citizen", AuditLog(ws25.audit_path))
    [item] = dict(build_request(new_client(home, "TEST01", fy=2026)).sections)["Interest"]
    assert "SAMPLE BANK" in item and "JANE" not in item.upper() and "REDACTED" not in item


def test_more_than_six_payers_say_and_others(home):
    _last_year(home, [_fig("income.div_franked", f"SAMPLE CO {n} LTD – franked amount") for n in range(8)])
    [item] = dict(build_request(new_client(home, "TEST01", fy=2026)).sections)["Dividends"]
    assert "SAMPLE CO 5 LTD" in item and "SAMPLE CO 6 LTD" not in item and "and others" in item


def test_control_characters_dropped(tmp_path):
    path = tmp_path / "a.docx"
    write_docx(path, [("item", "Statement from SAMPLE\x0bBANK\x00")], "a.docx")
    with zipfile.ZipFile(path) as z:
        ElementTree.fromstring(z.read("word/document.xml"))


def test_wording_mistake_is_a_plain_message(tmp_path, monkeypatch):
    import tra.info_request as info

    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    wording = info.load_wording()
    wording["title"] = "Information request {yeer}"
    monkeypatch.setattr(info, "load_wording", lambda path=None: wording)
    resp = client.post("/c/TEST01/2026/info-request")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/files")
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "info_request.yaml" in page and "{yeer}" in page
