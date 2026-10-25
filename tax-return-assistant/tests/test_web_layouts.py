"""Sawnx: the Layouts page (learned layouts, problems, what's waiting) and the Read again button."""

import dataclasses
import io

import pytest

from webctx import make_client, new_client

from tra.demo import _write_pdf
from tra.filing.index import DocumentIndex

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
"""


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr("tra.ingest.layouts.LAYOUTS_DIR", tmp_path / "layouts")
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    pdf = tmp_path / "a.pdf"
    _write_pdf(pdf, ["SAMPLE BANK", "Yearly interest", "Interest paid this financial year 321.00"])
    client.post("/c/TEST01/2026/import", data={"return_type": "individual", "mode_0": "read",
                                               "files": [(io.BytesIO(pdf.read_bytes()), "x.pdf")]},
                content_type="multipart/form-data")
    return client, ws, tmp_path


def _learn(tmp_path, text=LAYOUT, name="sample-bank-yearly"):
    (tmp_path / "layouts").mkdir(exist_ok=True)
    (tmp_path / "layouts" / f"{name}.yaml").write_text(text, encoding="utf-8")


def test_layouts_page_lists_waiting_documents(site):
    client, _ws, tmp_path = site
    _learn(tmp_path, "name: [unclosed", "broken")
    page = client.get("/layouts").get_data(as_text=True)
    assert 'href="/c/TEST01/2026/files?view=D001"' in page and "Not read yet" in page
    assert "broken.yaml" in page
    assert "Interest paid" not in page


def test_layouts_page_counts_what_each_layout_read(site):
    client, _ws, tmp_path = site
    _learn(tmp_path)
    client.post("/c/TEST01/2026/doc/D001/reread")
    page = client.get("/layouts").get_data(as_text=True)
    assert "SAMPLE BANK interest summary" in page and "1 document" in page
    assert 'href="/c/TEST01/2026/files?view=D001"' not in page  # read now, so not waiting


def test_settings_links_to_layouts(site):
    client, _ws, _tmp = site
    assert 'href="/layouts"' in client.get("/settings").get_data(as_text=True)


def test_read_again_button(site):
    client, _ws, tmp_path = site
    page = client.get("/c/TEST01/2026/files?view=D001").get_data(as_text=True)
    assert 'action="/c/TEST01/2026/doc/D001/reread"' in page
    _learn(tmp_path)
    resp = client.post("/c/TEST01/2026/doc/D001/reread")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/files?view=D001")
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "read again" in page and "1 figure added" in page


def test_read_again_refused_plainly(site):
    client, ws, _tmp = site
    [doc] = DocumentIndex(ws.index_csv).load()
    DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, parse_status="stored"))
    assert 'doc/D001/reread' not in client.get("/c/TEST01/2026/files?view=D001").get_data(as_text=True)
    resp = client.post("/c/TEST01/2026/doc/D001/reread")
    assert "stored only" in client.get(resp.headers["Location"]).get_data(as_text=True)


def test_read_again_says_when_a_file_kept_its_name(site, monkeypatch):
    from pathlib import Path

    client, _ws, tmp_path = site
    _learn(tmp_path)

    def locked(self, target):
        raise PermissionError(32, "in use")

    monkeypatch.setattr(Path, "rename", locked)
    resp = client.post("/c/TEST01/2026/doc/D001/reread")
    assert "keeps its old name" in client.get(resp.headers["Location"]).get_data(as_text=True)
