import dataclasses
from pathlib import Path

import pytest
from webctx import build_test01, ingest_demo, make_client

from tra.cabinets import CabinetSpace, store_in_cabinet
from tra.doc_notes import load_doc_notes, save_doc_note
from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.pipeline import ingest_file
from tra.labels import load_labels
from tra.notes_store import read_notes
from tra.privacy.audit import AuditLog
from tra.trash import delete_document, deleted_documents, purge_document, restore_document
from tra.versions import add_version, list_versions
from tra.web.comments import add_comment, list_comments
from tra.web.stars import load_stars, set_stars


def _audit(space):
    return AuditLog(space.audit_path)


def _figures(ws):
    figures, errors = read_figures(ws.figures_csv, load_labels())
    assert not errors
    return figures


def _doc(ws, doc_type):
    return next(d for d in DocumentIndex(ws.index_csv).load() if d.doc_type == doc_type)


def test_delete_takes_the_document_and_its_figures_out(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    doc = _doc(ws, "DIVSTMT")
    assert delete_document(ws, doc.doc_id, "tester", _audit(ws)) == 2
    assert doc.doc_id not in {d.doc_id for d in DocumentIndex(ws.index_csv).load()}
    assert all(f.doc_id != doc.doc_id for f in _figures(ws)) and len(_figures(ws)) == 4
    assert not Path(doc.filed_location).exists()
    [item] = deleted_documents(ws)
    assert (item.doc.doc_id, item.figures, item.by) == (doc.doc_id, 2, "tester")
    [entry] = [line for line in ws.audit_path.read_text(encoding="utf-8").splitlines() if "document_deleted" in line]
    assert doc.doc_id in entry and doc.filed_name not in entry


def test_restore_puts_everything_back(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    doc = _doc(ws, "DIVSTMT")
    before = sorted((f.figure_id, f.amount, f.confirmed) for f in _figures(ws))
    delete_document(ws, doc.doc_id, "tester", _audit(ws))
    assert restore_document(ws, doc.doc_id, "tester", _audit(ws)) == 2
    assert Path(doc.filed_location).is_file()
    assert sorted((f.figure_id, f.amount, f.confirmed) for f in _figures(ws)) == before
    assert _doc(ws, "DIVSTMT") == doc
    assert deleted_documents(ws) == []


def test_ids_are_not_reused_and_clashing_figures_are_renumbered(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    receipt = _doc(ws, "RECEIPT")
    [receipt_figure] = [f for f in _figures(ws) if f.doc_id == receipt.doc_id]
    delete_document(ws, receipt.doc_id, "tester", _audit(ws))
    [report] = ingest_demo(settings, ws, "receipt_union")
    assert report.doc.doc_id != receipt.doc_id  # a deleted document keeps its number
    restore_document(ws, receipt.doc_id, "tester", _audit(ws))
    ids = [f.figure_id for f in _figures(ws)]
    assert len(ids) == len(set(ids))
    [back] = [f for f in _figures(ws) if f.doc_id == receipt.doc_id]
    assert (back.amount, back.confirmed) == (receipt_figure.amount, True)


def test_restore_refused_when_the_same_file_was_imported_again(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    doc = _doc(ws, "DIVSTMT")
    delete_document(ws, doc.doc_id, "tester", _audit(ws))
    again = ingest_file(settings.tra_home.parent / "TEST01_src" / "dividend.pdf", ws, LocalStore(settings.tra_home),
                        load_doc_types(), _audit(ws))
    assert not again.duplicate  # deleting it lets the same file be read again
    with pytest.raises(ValueError, match=again.doc.doc_id):
        restore_document(ws, doc.doc_id, "tester", _audit(ws))


def test_its_manual_entry_note_goes_with_it(tmp_path, monkeypatch):
    from tra.demo import _write_pdf

    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    _write_pdf(tmp_path / "odd.pdf", ["Dividend statement", "Franking credit information enclosed"])
    report = ingest_file(tmp_path / "odd.pdf", ws, LocalStore(settings.tra_home), load_doc_types(), _audit(ws))
    mine = lambda: [n for n in read_notes(ws.ingest_notes_json) if report.doc.doc_id in n.doc_ids]  # noqa: E731
    assert mine()
    delete_document(ws, report.doc.doc_id, "tester", _audit(ws))
    assert mine() == []
    restore_document(ws, report.doc.doc_id, "tester", _audit(ws))
    assert mine()


def test_delete_forever(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    doc = _doc(ws, "RECEIPT")
    key = f"TEST01/2026/{doc.doc_id}"
    save_doc_note(ws, doc.doc_id, "Membership", "tester")
    set_stars(settings.tra_home, [key], True)
    add_comment(settings.tra_home, "TEST01", f"doc:{key}", "Check this", "tester", _audit(ws))
    newer = tmp_path / "newer.pdf"
    newer.write_bytes(Path(doc.filed_location).read_bytes() + b"\n% newer copy")
    add_version(ws, doc.doc_id, newer, "tester", _audit(ws))
    old_copy = ws.clients_dir / list_versions(ws, doc.doc_id)[0]["file"]
    assert old_copy.is_file()

    delete_document(ws, doc.doc_id, "tester", _audit(ws))
    purge_document(ws, doc.doc_id, _audit(ws))
    assert deleted_documents(ws) == []
    assert not list((ws.clients_dir / "_Deleted").glob("*"))
    assert not old_copy.exists() and list_versions(ws, doc.doc_id) == []
    assert doc.doc_id not in load_doc_notes(ws)
    assert key not in load_stars(settings.tra_home)
    assert list_comments(settings.tra_home, "TEST01", f"doc:{key}") == []
    assert DocumentIndex(ws.index_csv).next_doc_id() != doc.doc_id  # never handed out again
    with pytest.raises(ValueError):
        restore_document(ws, doc.doc_id, "tester", _audit(ws))
    assert "document_deleted_forever" in ws.audit_path.read_text(encoding="utf-8")


def test_unknown_and_fyi_documents(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    with pytest.raises(ValueError):
        delete_document(ws, "D999", "tester", _audit(ws))
    doc = _doc(ws, "RECEIPT")
    DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, store="fyi"))
    with pytest.raises(ValueError, match="FYI"):
        delete_document(ws, doc.doc_id, "tester", _audit(ws))
    with pytest.raises(ValueError):
        purge_document(ws, doc.doc_id, _audit(ws))  # only deleted items can be deleted forever


def test_cabinet_documents(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    build_test01(settings)
    space = CabinetSpace(settings.tra_home, "TEST01", "Permanent")
    src = tmp_path / "letter.pdf"
    src.write_bytes(b"%PDF-1.4 engagement letter")
    doc = store_in_cabinet(space, src, "Engagement", _audit(space))
    assert delete_document(space, doc.doc_id, "tester", _audit(space)) == 0
    assert [i.doc.doc_id for i in deleted_documents(space)] == [doc.doc_id]
    restore_document(space, doc.doc_id, "tester", _audit(space))
    assert Path(doc.filed_location).is_file()


def test_pages(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    doc, receipt = _doc(ws, "DIVSTMT"), _doc(ws, "RECEIPT")
    page = client.get(f"/c/TEST01/2026/files?view={doc.doc_id}").get_data(as_text=True)
    assert "Deleted items" in page and "data-confirm" in page
    resp = client.post(f"/c/TEST01/2026/doc/{doc.doc_id}/delete")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/files")
    page = client.get("/c/TEST01/2026/deleted").get_data(as_text=True)
    assert doc.filed_name in page and "Restore" in page and "Delete forever" in page
    resp = client.post(f"/c/TEST01/2026/deleted/{doc.doc_id}/restore")
    assert resp.status_code == 302 and _doc(ws, "DIVSTMT") == doc

    resp = client.post("/delete", data={"key": [f"TEST01/2026/{doc.doc_id}", f"TEST01/2026/{receipt.doc_id}"],
                                        "next": "/c/TEST01/2026/files"})
    assert resp.status_code == 302
    assert {i.doc.doc_id for i in deleted_documents(ws)} == {doc.doc_id, receipt.doc_id}
    assert "2 documents deleted" in client.get("/c/TEST01/2026/files").get_data(as_text=True)
    client.post(f"/c/TEST01/2026/deleted/{receipt.doc_id}/forever")
    assert [i.doc.doc_id for i in deleted_documents(ws)] == [doc.doc_id]
    assert client.post("/c/TEST01/2026/deleted/D999/restore").status_code == 302  # a message, not a crash
    assert client.get("/c/TEST01/2026/deleted?cab=PERM").status_code == 200
