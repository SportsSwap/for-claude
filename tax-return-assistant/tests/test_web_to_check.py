"""Things to check in Sawnx: the document panel, the import results, the Figures tab and the document list."""

import io
from decimal import Decimal

from webctx import make_client, new_client

from tra.demo import _write_pdf
from tra.figures import append_figures
from tra.models import Figure

DIVIDEND_NO_CREDIT = ["SAMPLE MINING LTD", "Dividend statement", "Payment date 20 March 2026",
                      "Unfranked amount 0.00", "Franked amount 700.00", "Franked dividend paid"]
INCOME_STATEMENT = ["Income statement", "Payer: SAMPLE CO PTY LTD", "Period 1 July 2025 to 30 June 2026",
                    "Gross payments 60,000.00", "Total tax withheld 11,000.00"]


def _pdf(tmp_path, name, lines) -> bytes:
    path = tmp_path / f"{name}.pdf"
    _write_pdf(path, lines)
    return path.read_bytes()


def _import(client, data: bytes):
    return client.post("/c/TEST01/2026/import", data={"return_type": "individual", "mode_0": "read",
                                                      "files": [(io.BytesIO(data), "x.pdf")]},
                       content_type="multipart/form-data")


def _setup(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    return client, new_client(settings)


def test_doc_panel_shows_things_to_check(tmp_path, monkeypatch):
    client, _ws = _setup(tmp_path, monkeypatch)
    _import(client, _pdf(tmp_path, "div", DIVIDEND_NO_CREDIT))
    page = client.get("/c/TEST01/2026/files?view=D001").get_data(as_text=True)
    panel = page[page.index('aria-label="Document viewer"'):]
    assert "Things to check" in panel
    assert "Didn&#39;t find the franking credit." in panel
    assert panel.index("Things to check") < panel.index(">Open<")


def test_import_results_list_items(tmp_path, monkeypatch):
    client, _ws = _setup(tmp_path, monkeypatch)
    page = _import(client, _pdf(tmp_path, "div", DIVIDEND_NO_CREDIT)).get_data(as_text=True)
    results = page[page.index('aria-label="Import results"'):]
    assert "Didn&#39;t find the franking credit." in results


def test_import_results_keep_note_risk(tmp_path, monkeypatch):
    client, _ws = _setup(tmp_path, monkeypatch)
    lines = [line for line in DIVIDEND_NO_CREDIT if not line.startswith("Payment date")]
    page = _import(client, _pdf(tmp_path, "div", lines)).get_data(as_text=True)
    results = page[page.index('aria-label="Import results"'):]
    assert '<span class="risk Low">Low</span> Document date not detected' in results


def _suggested(ws):
    [fig] = append_figures(ws.figures_csv, [Figure(
        figure_id="", label_key="ded.d9", description="Sheet 1 row 2: Red Cross donation", amount=Decimal("500.00"),
        date=None, doc_id="D001", page=1, method="parser", confirmed=False, substantiated=None,
        notes="suggested label")])
    return fig


def test_figures_tab_line_under_figure(tmp_path, monkeypatch):
    client, ws = _setup(tmp_path, monkeypatch)
    _import(client, _pdf(tmp_path, "inc", INCOME_STATEMENT))
    fig = _suggested(ws)
    page = client.get("/c/TEST01/2026/figures").get_data(as_text=True)
    row = page[page.index(f'<tr id="{fig.figure_id}"'):]
    row = row[:row.index("</tr>")]
    assert 'class="small tocheck-line"' in row and "Label suggested (" in row


def test_doclist_count(tmp_path, monkeypatch):
    client, _ws = _setup(tmp_path, monkeypatch)
    _import(client, _pdf(tmp_path, "div", DIVIDEND_NO_CREDIT))
    page = client.get("/c/TEST01/2026/files").get_data(as_text=True)
    assert 'class="tocheck"' in page and "1 to check" in page


def test_nothing_to_check_shows_no_box(tmp_path, monkeypatch):
    client, _ws = _setup(tmp_path, monkeypatch)
    _import(client, _pdf(tmp_path, "inc", INCOME_STATEMENT))
    page = client.get("/c/TEST01/2026/files?view=D001").get_data(as_text=True)
    assert "Things to check" not in page
    assert 'class="tocheck"' not in page
