import io
import os
from datetime import date

import pytest
from webctx import make_client, new_client

from tra.cabinets import CABINETS, CabinetSpace, store_in_cabinet
from tra.filing.index import DocumentIndex
from tra.privacy.audit import AuditLog
from tra.web.services.doclist import all_documents, resolve
from tra.web.services.files import add_folder, document_path, folder_names, move_document


def _space(settings, cab="Permanent"):
    return CabinetSpace(settings.tra_home, "TEST01", cab)


def test_cabinet_names_and_default_folders(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    assert CABINETS == ("Tax return", "Permanent", "Correspondence")
    assert folder_names(_space(settings)) == ["Identity", "Engagement", "Trust deeds", "Other"]
    assert folder_names(_space(settings, "Correspondence")) == ["Emails", "Letters", "Other"]
    with pytest.raises(ValueError):
        CabinetSpace(settings.tra_home, "TEST01", "Tax return")


def test_store_in_permanent(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    space = _space(settings)
    src = tmp_path / "upload.pdf"
    src.write_bytes(b"%PDF-1.4 engagement letter")
    doc = store_in_cabinet(space, src, "Engagement", AuditLog(space.audit_path))
    assert doc.filed_name == f"TEST01 {date.today().isoformat()} Document.pdf"
    assert doc.category == "Engagement" and doc.parse_status == "stored"
    assert document_path(space, doc.doc_id) == (space.clients_dir / "Engagement" / doc.filed_name).resolve()
    assert space.clients_dir == settings.tra_home / "Clients" / "TEST01" / "Permanent"
    again = store_in_cabinet(space, src, "Other", AuditLog(space.audit_path))
    assert again.doc_id == doc.doc_id  # the same file is not filed twice
    with pytest.raises(ValueError):
        store_in_cabinet(space, src, "Nowhere", AuditLog(space.audit_path))


def test_cabinet_folders_and_moves(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    space = _space(settings, "Correspondence")
    audit = AuditLog(space.audit_path)
    add_folder(space, "ATO letters", audit)
    src = tmp_path / "a.eml"
    src.write_bytes(b"From: someone")
    doc = store_in_cabinet(space, src, "Emails", audit)
    move_document(space, doc.doc_id, "ATO letters", audit)
    [moved] = DocumentIndex(space.index_csv).load()
    assert moved.category == "ATO letters" and os.path.exists(moved.filed_location)


def test_cabinet_documents_in_lists_and_keys(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    space = _space(settings)
    src = tmp_path / "id.png"
    src.write_bytes(b"\x89PNG fake")
    doc = store_in_cabinet(space, src, "Identity", AuditLog(space.audit_path))
    [row] = all_documents(settings.tra_home)
    assert row.cabinet == "Permanent" and row.income_year is None and row.key == f"TEST01/PERM/{doc.doc_id}"
    ws, found = resolve(settings, row.key)
    assert found.doc_id == doc.doc_id and ws.clients_dir == space.clients_dir


def test_files_tab_cabinet_switch_and_upload(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    page = client.get("/c/TEST01/2026/files?cab=PERM").get_data(as_text=True)
    assert "Identity" in page and "Trust deeds" in page and "Permanent" in page
    resp = client.post("/c/TEST01/2026/import?cab=PERM", content_type="multipart/form-data",
                       data={"cab": "PERM", "return_type": "individual", "files": [(io.BytesIO(b"hello"), "x.docx")],
                             "mode_0": "read", "folder_0": "Engagement"})
    assert resp.status_code == 200
    [doc] = DocumentIndex(_space(settings).index_csv).load()
    assert doc.category == "Engagement" and doc.parse_status == "stored"  # cabinets never read for the return
    assert client.get(f"/c/TEST01/2026/doc/{doc.doc_id}?cab=PERM").status_code == 200
    assert client.get("/c/TEST01/2026/files?cab=XYZ").status_code == 404
