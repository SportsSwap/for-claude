"""The progress bar sends files one at a time and asks for just that file's results (fragment=1)."""

import io

from webctx import make_client, new_client

from tra.demo import _write_pdf

INCOME_STATEMENT = ["Income statement", "Payer: SAMPLE CO PTY LTD", "Period 1 July 2025 to 30 June 2026",
                    "Gross payments 60,000.00", "Total tax withheld 11,000.00"]


def _setup(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    pdf = tmp_path / "inc.pdf"
    _write_pdf(pdf, INCOME_STATEMENT)
    return client, pdf.read_bytes()


def _post(client, data, name, **form):
    fields = {"return_type": "individual", "mode_0": "read", "files": [(io.BytesIO(data), name)], **form}
    return client.post("/c/TEST01/2026/import", data=fields, content_type="multipart/form-data")


def test_fragment_returns_results_only(tmp_path, monkeypatch):
    client, pdf = _setup(tmp_path, monkeypatch)
    resp = _post(client, pdf, "x.pdf", fragment="1", first_position="3")
    page = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "<html" not in page and 'aria-label="Import results"' in page
    assert "<strong>File 3</strong>" in page and "2 figures found" in page


def test_fragment_error_still_200(tmp_path, monkeypatch):
    client, _pdf = _setup(tmp_path, monkeypatch)
    resp = _post(client, b"MZ", "tool.exe", fragment="1", first_position="2")
    page = resp.get_data(as_text=True)
    assert resp.status_code == 200 and "<html" not in page
    assert "<strong>File 2</strong>" in page and "Can&#39;t use .exe files" in page


def test_fragment_cabinet_store(tmp_path, monkeypatch):
    client, pdf = _setup(tmp_path, monkeypatch)
    page = _post(client, pdf, "x.pdf", fragment="1", first_position="1", cab="CORR",
                 folder_0="Letters").get_data(as_text=True)
    assert "<html" not in page and " Document.pdf" in page and "TEST01 20" in page


def test_plain_post_unchanged(tmp_path, monkeypatch):
    client, pdf = _setup(tmp_path, monkeypatch)
    page = _post(client, pdf, "x.pdf").get_data(as_text=True)
    assert "<html" in page and "<strong>File 1</strong>" in page


def test_files_page_has_progress_area(tmp_path, monkeypatch):
    client, _pdf = _setup(tmp_path, monkeypatch)
    page = client.get("/c/TEST01/2026/files").get_data(as_text=True)
    assert 'id="progress"' in page and 'aria-live="polite"' in page and "<progress" in page


def test_hidden_wins_over_card_layout():
    """The progress panel is a flex card; without this rule its `hidden` attribute is ignored and it shows empty."""
    from pathlib import Path

    import tra.web

    css = (Path(tra.web.__file__).parent / "static" / "sawnx.css").read_text(encoding="utf-8")
    assert "[hidden] { display: none !important; }" in css
