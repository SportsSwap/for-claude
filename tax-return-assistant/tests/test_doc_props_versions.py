import io
from datetime import date

import pytest
from webctx import build_test01, make_client, new_client

from tra.cabinets import CabinetSpace, store_in_cabinet
from tra.doc_notes import load_doc_notes, save_doc_note, set_doc_status
from tra.doc_props import STATUSES, set_properties
from tra.filing.index import DocumentIndex
from tra.privacy.audit import AuditLog
from tra.versions import add_version, list_versions, version_path
from tra.web.services.files import document_path


def _perm_doc(tmp_path, settings, body=b"%PDF-1.4 v1"):
    space = CabinetSpace(settings.tra_home, "TEST01", "Permanent")
    src = tmp_path / "v1.pdf"
    src.write_bytes(body)
    return space, store_in_cabinet(space, src, "Engagement", AuditLog(space.audit_path))


def test_status_and_description_kept_together(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    set_doc_status(ws, "D001", "Final", "tester")
    save_doc_note(ws, "D001", "Bank statement", "tester")
    save_doc_note(ws, "D001", "", "tester")
    assert load_doc_notes(ws)["D001"]["status"] == "Final"
    with pytest.raises(ValueError):
        set_doc_status(ws, "D001", "Lost", "tester")
    assert STATUSES == ("", "To review", "Final", "Superseded")


def test_set_properties_type_date_folder(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    audit = AuditLog(ws.audit_path)
    doc, warnings = set_properties(ws, "D004", doc_type="RECEIPT", folder="Other", doc_date=date(2025, 9, 20),
                                   status="To review", by="tester", audit=audit)
    assert (doc.category, doc.doc_date, doc.date_detected) == ("Other", date(2025, 9, 20), True)
    assert warnings == []
    doc, warnings = set_properties(ws, "D004", doc_type="OTHER", folder="Other", doc_date=None, status="",
                                   by="tester", audit=audit)
    assert doc.doc_type == "OTHER" and warnings and "figures" in warnings[0]
    with pytest.raises(ValueError):
        set_properties(ws, "D004", doc_type="NOPE", folder="Other", doc_date=None, status="", by="t", audit=audit)


def test_versions_keep_older_copies(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    space, doc = _perm_doc(tmp_path, settings)
    newer = tmp_path / "v2.pdf"
    newer.write_bytes(b"%PDF-1.4 v2")
    audit = AuditLog(space.audit_path)
    warnings = add_version(space, doc.doc_id, newer, "tester", audit)
    assert warnings == []
    assert document_path(space, doc.doc_id).read_bytes() == b"%PDF-1.4 v2"
    [old] = list_versions(space, doc.doc_id)
    assert old["n"] == 1 and version_path(space, doc.doc_id, 1).read_bytes() == b"%PDF-1.4 v1"
    [entry] = DocumentIndex(space.index_csv).load()
    assert entry.filed_name == doc.filed_name and entry.sha256 != doc.sha256
    with pytest.raises(ValueError):
        add_version(space, doc.doc_id, newer, "tester", audit)  # same as current
    other = tmp_path / "v3.docx"
    other.write_bytes(b"PK word")
    with pytest.raises(ValueError):
        add_version(space, doc.doc_id, other, "tester", audit)  # different kind of file
    assert version_path(space, doc.doc_id, 9) is None


def test_new_version_of_a_read_document_warns(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    newer = tmp_path / "bank2.pdf"
    newer.write_bytes(b"%PDF-1.4 corrected statement")
    warnings = add_version(ws, "D001", newer, "tester", AuditLog(ws.audit_path))
    assert warnings and "figures" in warnings[0]


def test_properties_and_versions_through_the_page(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    space, doc = _perm_doc(tmp_path, settings)
    resp = client.post(f"/c/TEST01/2026/doc/{doc.doc_id}/properties",
                       data={"cab": "PERM", "doc_type": "OTHER", "folder": "Identity", "doc_date": "2026-07-01",
                             "status": "Final"})
    assert resp.status_code == 302 and "cab=PERM" in resp.headers["Location"]
    assert load_doc_notes(space)[doc.doc_id]["status"] == "Final"
    resp = client.post(f"/c/TEST01/2026/doc/{doc.doc_id}/version", content_type="multipart/form-data",
                       data={"cab": "PERM", "file": (io.BytesIO(b"%PDF-1.4 newer"), "anything.pdf")})
    assert resp.status_code == 302
    assert client.get(f"/c/TEST01/2026/doc/{doc.doc_id}/v/1?cab=PERM").data == b"%PDF-1.4 v1"
    page = client.get(f"/c/TEST01/2026/files?cab=PERM&view={doc.doc_id}").get_data(as_text=True)
    assert "Version 1" in page and "Final" in page
    assert client.get(f"/c/TEST01/2026/doc/{doc.doc_id}/v/5?cab=PERM").status_code == 404
