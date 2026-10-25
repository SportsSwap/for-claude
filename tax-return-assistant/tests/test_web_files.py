import json

import pytest
from webctx import ingest_demo, make_client, new_client

from tra.filing.index import DocumentIndex
from tra.ingest.classify import CATEGORIES
from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.services.files import add_folder, document_path, folders, move_document


def _setup(tmp_path, monkeypatch):
    app, client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    ingest_demo(settings, ws, "income_statement")
    return client, settings, ws, AuditLog(ws.audit_path)


def test_standard_and_custom_folders_listed(tmp_path, monkeypatch):
    client, _settings, ws, audit = _setup(tmp_path, monkeypatch)
    add_folder(ws, "Engagement", audit)
    listed = folders(ws)
    assert [f.name for f in listed] == list(CATEGORIES) + ["Engagement"]
    assert next(f for f in listed if f.name == "Income").count == 1
    assert next(f for f in listed if f.name == "Engagement").standard is False
    page = client.get("/c/TEST01/2026/files").get_data(as_text=True)
    assert "Engagement" in page and "TEST01 2026-06-30 Income statement" in page
    only_rental = client.get("/c/TEST01/2026/files?folder=Rental").get_data(as_text=True)
    assert "TEST01 2026-06-30 Income statement" not in only_rental


def test_add_folder_rejects_bad_names(tmp_path, monkeypatch, make_tfn):
    _client, _settings, ws, audit = _setup(tmp_path, monkeypatch)
    before = sorted(p.name for p in ws.clients_dir.iterdir())
    for bad in ("../x", "", "a" * 41, "Income", "a/b"):
        with pytest.raises(ValueError):
            add_folder(ws, bad, audit)
    with pytest.raises(SensitiveDataBlocked):
        add_folder(ws, f"TFN {make_tfn()}", audit)
    assert sorted(p.name for p in ws.clients_dir.iterdir()) == before


def test_add_folder_through_the_page(tmp_path, monkeypatch):
    client, _settings, ws, _audit = _setup(tmp_path, monkeypatch)
    resp = client.post("/c/TEST01/2026/folders", data={"name": "Correspondence"})
    assert resp.status_code == 302 and (ws.clients_dir / "Correspondence").is_dir()
    bad = client.post("/c/TEST01/2026/folders", data={"name": "../x"}, follow_redirects=True)
    assert "letters, numbers" in bad.get_data(as_text=True)


def test_view_document_by_id_only(tmp_path, monkeypatch):
    client, _settings, ws, _audit = _setup(tmp_path, monkeypatch)
    resp = client.get("/c/TEST01/2026/doc/D001")
    assert resp.status_code == 200 and resp.mimetype == "application/pdf" and resp.data.startswith(b"%PDF")
    assert document_path(ws, "D999") is None
    assert client.get("/c/TEST01/2026/doc/D999").status_code == 404
    assert client.get("/c/TEST01/2026/doc/..%2Findex.csv").status_code == 404


def test_move_document_updates_index_and_audit(tmp_path, monkeypatch):
    client, settings, ws, audit = _setup(tmp_path, monkeypatch)
    add_folder(ws, "Engagement", audit)
    old = document_path(ws, "D001")
    resp = client.post("/c/TEST01/2026/doc/D001/move", data={"folder": "Engagement"})
    assert resp.status_code == 302
    [doc] = DocumentIndex(ws.index_csv).load()
    assert doc.category == "Engagement" and doc.filed_name.startswith("TEST01 2026-06-30 Income statement")
    assert not old.exists() and document_path(ws, "D001").parent.name == "Engagement"
    actions = [json.loads(line)["action"] for line in ws.audit_path.read_text(encoding="utf-8").splitlines()]
    assert "document_moved" in actions
    with pytest.raises(ValueError):
        move_document(ws, "D001", "Nowhere", audit)


def test_bad_code_in_url_is_404(tmp_path, monkeypatch):
    client, _settings, _ws, _audit = _setup(tmp_path, monkeypatch)
    assert client.get("/c/test01/2026/files").status_code == 404
    assert client.get("/c/NOPE01/2026/files").status_code == 404
    assert client.get("/c/TEST01/2019/files").status_code == 404
    assert client.get("/c/..%2F..%2Fx/2026/files").status_code == 404
