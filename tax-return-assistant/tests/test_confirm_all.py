"""Confirm all figures from one document: the service, the route, the button and the Figures tab card."""

import io
import json
import re

import pytest
from webctx import ingest_demo, make_client, new_client

from tra.privacy.audit import AuditLog
from tra.privacy.guard import FileLockedError
from tra.web.services.figures import (FiguresFileProblem, add_figure, confirm_document_figures, figure_rows,
                                      set_figure)

BASE = "/c/TEST01/2026"


def _setup(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ingest_demo(settings, ws, "income_statement", "prefill", "phi")
    return client, ws, AuditLog(ws.audit_path)


def _doc_of(ws, label_key, prefill=False):
    return next(f.doc_id for f in figure_rows(ws)
                if f.label_key == label_key and (f.notes == "prefill") == prefill)


def _waiting(ws, doc_id):
    return [f for f in figure_rows(ws) if f.doc_id == doc_id and not f.confirmed and f.notes != "prefill"]


def _ids(ws, doc_id):
    return [f.figure_id for f in _waiting(ws, doc_id)]


def _form_ids(page, doc_id):
    """The figure ids a Confirm all form for this document posts."""
    [form] = re.findall(rf'action="{BASE}/doc/{doc_id}/confirm-all">(.*?)</form>', page, re.S)
    return re.findall(r'name="figure_id" value="([^"]+)"', form)


def _late_figure(ws, doc_id, audit):
    """A figure that arrives after the page was opened (Excel, Read again or tra ai-add)."""
    return add_figure(ws, label_key="income.salary", description="Late row", amount="123.45", doc_id=doc_id,
                      page=None, audit=audit)


def test_confirms_only_that_documents_figures(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    income, phi = _doc_of(ws, "income.salary"), _doc_of(ws, "phi.premiums_p1")
    before = {f.figure_id: f for f in figure_rows(ws)}
    expected = len(_waiting(ws, income))
    assert expected >= 2
    assert confirm_document_figures(ws, income, audit, figure_ids=_ids(ws, income)) == (expected, 0)
    after = {f.figure_id: f for f in figure_rows(ws)}
    for fid, f in after.items():
        old = before[fid]
        if f.doc_id == income and f.notes != "prefill":
            assert f.confirmed is True
        else:
            assert f.confirmed == old.confirmed  # other documents and pre-fill rows untouched
        assert (f.amount, f.label_key, f.description) == (old.amount, old.label_key, old.description)
    assert _waiting(ws, phi) and not _waiting(ws, income)
    assert confirm_document_figures(ws, income, audit, figure_ids=list(before)) == (0, 0)  # nothing left


def test_only_the_figures_shown_are_confirmed(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    shown = _ids(ws, income)
    late = _late_figure(ws, income, audit)
    assert confirm_document_figures(ws, income, audit, figure_ids=shown) == (len(shown), 1)
    assert [f.figure_id for f in _waiting(ws, income)] == [late.figure_id]


def test_ids_from_another_document_or_prefill_ignored(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    income, phi = _doc_of(ws, "income.salary"), _doc_of(ws, "phi.premiums_p1")
    prefill = _doc_of(ws, "income.salary", prefill=True)
    prefill_ids = [f.figure_id for f in figure_rows(ws) if f.notes == "prefill"]
    before = ws.figures_csv.read_bytes()
    tampered = _ids(ws, phi) + prefill_ids + ["F9876"]
    not_shown = len(_ids(ws, income))
    assert confirm_document_figures(ws, income, audit, figure_ids=tampered) == (0, not_shown)
    assert confirm_document_figures(ws, prefill, audit, figure_ids=prefill_ids) == (0, 0)
    assert ws.figures_csv.read_bytes() == before


def test_figure_ids_required(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    with pytest.raises(TypeError):
        confirm_document_figures(ws, income, audit)  # the ids that were shown are required


def test_prefill_rows_never_confirmed(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    prefill = _doc_of(ws, "income.salary", prefill=True)
    every_id = [f.figure_id for f in figure_rows(ws)]
    assert confirm_document_figures(ws, prefill, audit, figure_ids=every_id) == (0, 0)
    assert all(not f.confirmed for f in figure_rows(ws) if f.notes == "prefill")


def test_audit_has_count_not_amounts(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    waiting = _waiting(ws, income)
    n, _newer = confirm_document_figures(ws, income, audit, figure_ids=_ids(ws, income))
    entries = [json.loads(line) for line in ws.audit_path.read_text(encoding="utf-8").splitlines()]
    [entry] = [e for e in entries if e["action"] == "figures_confirmed_bulk"]
    assert (entry["client"], entry["doc_id"], entry["count"]) == ("TEST01", income, n)
    text = json.dumps(entry)
    for f in waiting:
        assert str(f.amount) not in text and f.description not in text


def test_unknown_document_and_bad_rows(tmp_path, monkeypatch):
    _client, ws, audit = _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="There's no document D099."):
        confirm_document_figures(ws, "D099", audit, figure_ids=[])
    income = _doc_of(ws, "income.salary")
    shown = _ids(ws, income)
    text = ws.figures_csv.read_text(encoding="utf-8-sig")
    ws.figures_csv.write_text(text + "F0099,income.interest,Bad row,abc,,,,manual,N,,\r\n", encoding="utf-8-sig")
    with pytest.raises(FiguresFileProblem):
        confirm_document_figures(ws, income, audit, figure_ids=shown)


def test_route_flashes_and_goes_back_to_next(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    shown = _ids(ws, income)
    n = len(shown)
    resp = client.post(f"{BASE}/doc/{income}/confirm-all", data={"next": f"{BASE}/figures", "figure_id": shown})
    assert resp.status_code == 302 and resp.headers["Location"].endswith(f"{BASE}/figures")
    page = client.get(f"{BASE}/figures").get_data(as_text=True)
    assert (f"{n} figures from {income} confirmed. They&#39;ll be in the return the next time you prepare it."
            in page)
    resp = client.post(f"{BASE}/doc/{income}/confirm-all", data={"next": f"{BASE}/figures", "figure_id": shown},
                       follow_redirects=True)
    assert f"Nothing to confirm in {income}." in resp.get_data(as_text=True)


def test_route_singular(tmp_path, monkeypatch):
    client, ws, audit = _setup(tmp_path, monkeypatch)
    phi = _doc_of(ws, "phi.premiums_p1")
    for f in _waiting(ws, phi)[1:]:
        set_figure(ws, f.figure_id, confirmed=True, audit=audit)
    resp = client.post(f"{BASE}/doc/{phi}/confirm-all",
                       data={"next": f"{BASE}/files?view={phi}", "figure_id": _ids(ws, phi)}, follow_redirects=True)
    assert f"1 figure from {phi} confirmed. They&#39;ll be in the return" in resp.get_data(as_text=True)


def test_route_figure_arrived_after_page_opened(tmp_path, monkeypatch):
    client, ws, audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    page = client.get(f"{BASE}/files?view={income}").get_data(as_text=True)
    shown = _form_ids(page, income)
    assert shown == _ids(ws, income)
    late = _late_figure(ws, income, audit)
    resp = client.post(f"{BASE}/doc/{income}/confirm-all",
                       data={"next": f"{BASE}/files?view={income}", "figure_id": shown}, follow_redirects=True)
    text = resp.get_data(as_text=True)
    assert (f"{len(shown)} figures confirmed. 1 more from {income} arrived since you opened the page; check them "
            "before confirming." in text)
    assert [f.figure_id for f in _waiting(ws, income)] == [late.figure_id]
    assert all(f.confirmed for f in figure_rows(ws) if f.figure_id in shown)


def test_route_nothing_shown_still_waiting(tmp_path, monkeypatch):
    client, ws, audit = _setup(tmp_path, monkeypatch)
    income, phi = _doc_of(ws, "income.salary"), _doc_of(ws, "phi.premiums_p1")
    prefill_ids = [f.figure_id for f in figure_rows(ws) if f.notes == "prefill"]
    before = ws.figures_csv.read_bytes()
    for data in ({"figure_id": _ids(ws, phi) + prefill_ids}, {}):  # tampered ids, then no ids at all
        resp = client.post(f"{BASE}/doc/{income}/confirm-all", data={"next": f"{BASE}/figures", **data},
                           follow_redirects=True)
        assert f"Nothing to confirm in {income}." in resp.get_data(as_text=True)
    assert ws.figures_csv.read_bytes() == before


@pytest.mark.parametrize("unsafe", ["//evil.example/x", "/\\evil.example/x", "/\\/evil.example", "\\\\evil.example",
                                    "https://evil.example/x", "", "figures"])
def test_unsafe_next_ignored(tmp_path, monkeypatch, unsafe):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    resp = client.post(f"{BASE}/doc/{income}/confirm-all", data={"next": unsafe})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"{BASE}/files?view={income}")


def test_safe_next_rejects_backslash_tricks():
    from tra.web.home_routes import _safe_next

    for unsafe in ("//evil.example", "/\\evil.example", "/\\", "\\/evil.example", "https://evil.example"):
        assert _safe_next(unsafe, "/home") == "/home", unsafe
    for ok in ("/", "/figures", "/c/TEST01/2026/files?view=D001", "/?tab=tasks"):
        assert _safe_next(ok, "/home") == ok


def test_button_on_document_panel(tmp_path, monkeypatch):
    client, ws, audit = _setup(tmp_path, monkeypatch)
    income, prefill = _doc_of(ws, "income.salary"), _doc_of(ws, "income.salary", prefill=True)
    n = len(_waiting(ws, income))
    page = client.get(f"{BASE}/files?view={income}").get_data(as_text=True)
    assert f"Confirm all {n} figures" in page
    assert (f'data-confirm="Confirm all {n} figures from {income}? Only do this after you\'ve checked each one '
            'against the document."' in page)
    assert f'action="{BASE}/doc/{income}/confirm-all"' in page
    assert f'value="{BASE}/files?view={income}"' in page
    assert _form_ids(page, income) == _ids(ws, income)
    # A pre-fill only document has nothing to confirm in bulk.
    assert "/confirm-all" not in client.get(f"{BASE}/files?view={prefill}").get_data(as_text=True)
    confirm_document_figures(ws, income, audit, figure_ids=_ids(ws, income))
    assert "/confirm-all" not in client.get(f"{BASE}/files?view={income}").get_data(as_text=True)


def test_no_button_in_a_cabinet(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    client.post(f"{BASE}/import?cab=PERM", content_type="multipart/form-data",
                data={"cab": "PERM", "return_type": "individual", "files": [(io.BytesIO(b"hello"), "x.docx")],
                      "mode_0": "read", "folder_0": "Engagement"})
    from tra.cabinets import CABINET_BY_CODE, CabinetSpace
    from tra.filing.index import DocumentIndex

    space = CabinetSpace(ws.tra_home, "TEST01", CABINET_BY_CODE["PERM"])
    [doc] = DocumentIndex(space.index_csv).load()
    assert _waiting(ws, doc.doc_id)  # the same id has figures waiting in the Tax return cabinet
    page = client.get(f"{BASE}/files?cab=PERM&view={doc.doc_id}").get_data(as_text=True)
    assert "Document viewer" in page and "/confirm-all" not in page


def test_figures_tab_by_document_card(tmp_path, monkeypatch):
    client, ws, audit = _setup(tmp_path, monkeypatch)
    income, phi = _doc_of(ws, "income.salary"), _doc_of(ws, "phi.premiums_p1")
    prefill = _doc_of(ws, "income.salary", prefill=True)
    page = client.get(f"{BASE}/figures").get_data(as_text=True)
    assert "By document" in page
    for doc in (income, phi):
        assert f"{len(_waiting(ws, doc))} to confirm" in page
        assert f'action="{BASE}/doc/{doc}/confirm-all"' in page
        assert _form_ids(page, doc) == _ids(ws, doc)
    assert "Private health insurance statement" in page
    assert f'action="{BASE}/doc/{prefill}/confirm-all"' not in page
    assert f'name="next" value="{BASE}/figures"' in page
    confirm_document_figures(ws, income, audit, figure_ids=_ids(ws, income))
    confirm_document_figures(ws, phi, audit, figure_ids=_ids(ws, phi))
    page = client.get(f"{BASE}/figures").get_data(as_text=True)
    assert "By document" not in page and "/confirm-all" not in page


def test_locked_figures_file(tmp_path, monkeypatch):
    client, ws, _audit = _setup(tmp_path, monkeypatch)
    income = _doc_of(ws, "income.salary")
    shown = _ids(ws, income)
    before = ws.figures_csv.read_bytes()

    def locked(path, *_a, **_k):
        raise FileLockedError(path)

    monkeypatch.setattr("tra.figures.atomic_write_text", locked)
    resp = client.post(f"{BASE}/doc/{income}/confirm-all", data={"next": f"{BASE}/figures", "figure_id": shown},
                       follow_redirects=True)
    assert "figures.csv is open in Excel. Close it and try again." in resp.get_data(as_text=True)
    assert ws.figures_csv.read_bytes() == before
