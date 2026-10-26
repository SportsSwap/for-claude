from decimal import Decimal

import pytest
from webctx import ingest_demo, make_client, new_client

from tra.figures import read_figures, write_figures
from tra.labels import load_labels
from tra.privacy.audit import AuditLog
from tra.privacy.guard import FileLockedError
from tra.web.services.figures import add_figure, figure_rows, label_choices, set_figure


def _setup(tmp_path, monkeypatch, *stems):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ingest_demo(settings, ws, *(stems or ("income_statement",)))
    return client, ws, AuditLog(ws.audit_path)


def test_tick_writes_same_csv_as_excel_edit(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    expected_path = tmp_path / "expected.csv"
    figures, _ = read_figures(ws.figures_csv, load_labels())
    figures[0].confirmed = True
    write_figures(expected_path, figures)
    set_figure(ws, figures[0].figure_id, confirmed=True, audit=audit)
    assert ws.figures_csv.read_bytes() == expected_path.read_bytes()


def test_tick_through_the_page(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    first = figure_rows(ws)[0]
    resp = client.post(f"/c/TEST01/2026/figures/{first.figure_id}",
                       data={"confirmed": "on", "substantiated": "on", "label_key": first.label_key,
                             "amount": str(first.amount)})
    assert resp.status_code == 302
    changed = figure_rows(ws)[0]
    assert changed.confirmed is True and changed.substantiated is True
    client.post(f"/c/TEST01/2026/figures/{first.figure_id}", data={"label_key": first.label_key,
                                                                    "amount": str(first.amount)})
    again = figure_rows(ws)[0]
    assert again.confirmed is False and again.substantiated is False


def test_label_and_amount_validated(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    before = ws.figures_csv.read_bytes()
    fid = figure_rows(ws)[0].figure_id
    with pytest.raises(ValueError):
        set_figure(ws, fid, amount="abc", audit=audit)
    with pytest.raises(ValueError):
        set_figure(ws, fid, label_key="nope.nothing", audit=audit)
    with pytest.raises(ValueError):
        set_figure(ws, "F9999", confirmed=True, audit=audit)
    assert ws.figures_csv.read_bytes() == before
    set_figure(ws, fid, amount="$85,100.50", audit=audit)
    assert figure_rows(ws)[0].amount == Decimal("85100.50")


def test_add_manual_figure(tmp_path, monkeypatch):
    client, ws, audit = _setup(tmp_path, monkeypatch)
    count = len(figure_rows(ws))
    new = add_figure(ws, label_key="ded.d5", description="Union fees", amount="520.5", doc_id="D001", page=1,
                     audit=audit)
    rows = figure_rows(ws)
    assert len(rows) == count + 1 and rows[-1].figure_id == new.figure_id
    assert (new.method, new.confirmed, new.amount) == ("manual", False, Decimal("520.5"))
    with pytest.raises(ValueError):
        add_figure(ws, label_key="ded.d5", description="x", amount="1", doc_id="D099", page=None, audit=audit)
    resp = client.post("/c/TEST01/2026/figures/new", data={"label_key": "ded.d9", "description": "Gift",
                                                           "amount": "50", "doc_id": "", "page": ""})
    assert resp.status_code == 302 and figure_rows(ws)[-1].doc_id is None


def test_label_choices_are_figure_labels():
    keys = [k for k, _name in label_choices()]
    assert "income.salary" in keys and "ded.d5" in keys
    assert all(not load_labels()[k].computed for k in keys)


def test_prefill_row_shows_warning(tmp_path, monkeypatch):
    client, _ws, _audit = _setup(tmp_path, monkeypatch, "income_statement", "prefill")
    page = client.get("/c/TEST01/2026/figures").get_data(as_text=True)
    assert "Leave unconfirmed if another document supports this" in page


def _ai_figures(ws):
    """The first two figures as if the AI reader read them: the first found in the document's text, the second not."""
    from tra.ingest.extractors.ai_reader import TEXT_MATCH
    figures = figure_rows(ws)
    for f, notes in zip(figures, (TEXT_MATCH, "")):
        f.method, f.notes = "ai", notes
    write_figures(ws.figures_csv, figures)
    return figures


def test_ai_figures_show_whether_the_text_agrees(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    _ai_figures(ws)
    page = client.get("/c/TEST01/2026/figures").get_data(as_text=True).replace("&#39;", "'")
    assert page.count("Same amount in the document's own text") == 1
    assert page.count("Not found in the document's own text") == 1


def test_changing_the_amount_clears_the_match(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    first = _ai_figures(ws)[0]
    set_figure(ws, first.figure_id, confirmed=True, audit=audit)
    assert figure_rows(ws)[0].notes != ""  # confirming keeps it
    set_figure(ws, first.figure_id, amount=str(first.amount + 1), audit=audit)
    assert figure_rows(ws)[0].notes == ""  # the new amount wasn't the one found in the text


def test_excel_lock_message(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    before = ws.figures_csv.read_bytes()
    first = figure_rows(ws)[0]

    def locked(path, *_a, **_k):
        raise FileLockedError(path)

    monkeypatch.setattr("tra.figures.atomic_write_text", locked)
    resp = client.post(f"/c/TEST01/2026/figures/{first.figure_id}",
                       data={"confirmed": "on", "label_key": first.label_key, "amount": str(first.amount)},
                       follow_redirects=True)
    assert "figures.csv is open in Excel. Close it and try again." in resp.get_data(as_text=True)
    assert ws.figures_csv.read_bytes() == before


def test_bad_rows_reported(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    text = ws.figures_csv.read_text(encoding="utf-8-sig")
    ws.figures_csv.write_text(text + "F0099,income.interest,Bad row,abc,,,,manual,N,,\r\n", encoding="utf-8-sig")
    page = client.get("/c/TEST01/2026/figures").get_data(as_text=True)
    assert "bad amount" in page
