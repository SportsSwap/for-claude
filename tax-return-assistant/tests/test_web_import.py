import html
import io
import os
import re
from datetime import date

from webctx import make_client, new_client

from tra.demo import build_demo_documents
from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.pipeline import IngestError, ingest_file
from tra.labels import load_labels
from tra.notes_store import read_notes
from tra.privacy.audit import AuditLog
from tra.web.services.files import add_folder


def _setup(tmp_path, monkeypatch):
    app, client, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    demo = build_demo_documents(tmp_path / "demo_src")
    return app, client, settings, ws, demo


def _post(client, files, **form):
    """files: list of (bytes, name, mode, folder)."""
    data = {"return_type": form.pop("return_type", "individual"), **form}
    data["files"] = [(io.BytesIO(b), name) for b, name, _m, _f in files]
    for i, (_b, _n, mode, folder) in enumerate(files):
        data[f"mode_{i}"] = mode
        if folder:
            data[f"folder_{i}"] = folder
    return client.post("/c/TEST01/2026/import", data=data, content_type="multipart/form-data")


def _uploads_empty(ws):
    folder = ws.work_dir / "_uploads"
    return not folder.exists() or not any(folder.iterdir())


def test_read_upload_matches_ingest_file(tmp_path, monkeypatch):
    _app, client, settings, ws, demo = _setup(tmp_path, monkeypatch)
    pdf = demo.paths["income_statement"].read_bytes()
    assert _post(client, [(pdf, "anything.pdf", "read", None)]).status_code == 200
    other = new_client(settings, "TEST02")
    ingest_file(demo.paths["income_statement"], other, LocalStore(settings.tra_home), load_doc_types(),
                AuditLog(other.audit_path))
    [a], [b] = DocumentIndex(ws.index_csv).load(), DocumentIndex(other.index_csv).load()
    assert (a.doc_type, a.category, a.parse_status, a.redaction_counts, a.filed_name.replace("TEST01", "X")) == \
           (b.doc_type, b.category, b.parse_status, b.redaction_counts, b.filed_name.replace("TEST02", "X"))
    fa, _ = read_figures(ws.figures_csv, load_labels())
    fb, _ = read_figures(other.figures_csv, load_labels())
    assert [(f.label_key, f.amount, f.description) for f in fa] == [(f.label_key, f.amount, f.description) for f in fb]
    assert _uploads_empty(ws)


def test_redaction_counts_shown(tmp_path, monkeypatch):
    _app, client, _settings, _ws, demo = _setup(tmp_path, monkeypatch)
    page = _post(client, [(demo.paths["income_statement"].read_bytes(), "x.pdf", "read", None)]).get_data(as_text=True)
    [count] = re.findall(r"(\d+) numbers? blanked out", page)
    assert int(count) > 0
    assert "123 456 789" not in page


def test_store_only_files_unread(tmp_path, monkeypatch):
    _app, client, _settings, ws, _demo = _setup(tmp_path, monkeypatch)
    add_folder(ws, "Engagement", AuditLog(ws.audit_path))
    resp = _post(client, [(os.urandom(500), "letter.docx", "store", "Engagement")])
    assert resp.status_code == 200
    [doc] = DocumentIndex(ws.index_csv).load()
    assert doc.filed_name == f"TEST01 {date.today().isoformat()} Document.docx"
    assert doc.parse_status == "stored" and doc.category == "Engagement" and doc.redaction_counts == {}
    assert read_figures(ws.figures_csv, load_labels())[0] == []
    assert not [n for n in read_notes(ws.ingest_notes_json) if n.check_id == "I2"]
    assert "stored only, not read" in resp.get_data(as_text=True)


def test_store_only_needs_a_real_folder(tmp_path, monkeypatch):
    _app, client, _settings, ws, _demo = _setup(tmp_path, monkeypatch)
    page = _post(client, [(b"hello", "a.docx", "store", "Nowhere")]).get_data(as_text=True)
    assert "Choose a folder" in page and DocumentIndex(ws.index_csv).load() == []


def test_company_return_type_refused(tmp_path, monkeypatch):
    _app, client, _settings, ws, demo = _setup(tmp_path, monkeypatch)
    page = _post(client, [(demo.paths["income_statement"].read_bytes(), "x.pdf", "read", None)],
                 return_type="company").get_data(as_text=True)
    assert "coming later" in page and DocumentIndex(ws.index_csv).load() == []


def test_unsupported_type_refused_before_saving(tmp_path, monkeypatch):
    _app, client, _settings, ws, _demo = _setup(tmp_path, monkeypatch)
    page = _post(client, [(b"MZ...", "virus.exe", "read", None), (b"MZ...", "virus.exe", "store", "Other"),
                          (b"PK..", "letter.docx", "read", None)]).get_data(as_text=True)
    page = html.unescape(page)
    assert page.count("Can't use .exe files") == 2
    assert "Can't read .docx files for the return" in page and "Store only" in page
    assert DocumentIndex(ws.index_csv).load() == [] and _uploads_empty(ws)


def test_duplicate_upload_reported(tmp_path, monkeypatch):
    _app, client, _settings, ws, demo = _setup(tmp_path, monkeypatch)
    pdf = demo.paths["bank_interest"].read_bytes()
    _post(client, [(pdf, "a.pdf", "read", None)])
    page = _post(client, [(pdf, "a.pdf", "read", None)]).get_data(as_text=True)
    assert "already filed as" in page and len(DocumentIndex(ws.index_csv).load()) == 1
    store_dup = _post(client, [(pdf, "a.pdf", "store", "Other")]).get_data(as_text=True)
    assert "already filed as" in store_dup and len(DocumentIndex(ws.index_csv).load()) == 1


def test_original_filename_never_written(tmp_path, monkeypatch, make_tfn):
    _app, client, settings, _ws, demo = _setup(tmp_path, monkeypatch)
    tfn = make_tfn()
    name = f"Jane_Citizen_{tfn}.pdf"
    page = _post(client, [(demo.paths["income_statement"].read_bytes(), name, "read", None),
                          (b"plain", f"Jane_Citizen_{tfn}.docx", "store", "Other")]).get_data(as_text=True)
    assert "Jane_Citizen" not in page and tfn not in page
    for root, _dirs, files in os.walk(settings.tra_home):
        for f in files:
            path = os.path.join(root, f)
            assert "Jane_Citizen" not in path and tfn not in path
            text = open(path, "rb").read().decode("latin-1")
            assert "Jane_Citizen" not in text and tfn not in text


def test_too_large_upload_refused(tmp_path, monkeypatch):
    app, client, _settings, ws, _demo = _setup(tmp_path, monkeypatch)
    app.config["MAX_CONTENT_LENGTH"] = 1000
    resp = _post(client, [(b"x" * 5000, "big.pdf", "read", None)])
    assert resp.status_code == 413 and "over 50 MB" in resp.get_data(as_text=True)
    assert DocumentIndex(ws.index_csv).load() == [] and _uploads_empty(ws)


def test_uploads_folder_emptied_even_on_error(tmp_path, monkeypatch):
    _app, client, _settings, ws, demo = _setup(tmp_path, monkeypatch)

    def broken(*_a, **_k):
        raise IngestError("redaction failed; document not processed")

    monkeypatch.setattr("tra.web.services.imports.ingest_file", broken)
    page = _post(client, [(demo.paths["income_statement"].read_bytes(), "x.pdf", "read", None)]).get_data(as_text=True)
    assert "redaction failed" in page and _uploads_empty(ws)


def test_no_files_chosen(tmp_path, monkeypatch):
    _app, client, _settings, _ws, _demo = _setup(tmp_path, monkeypatch)
    resp = client.post("/c/TEST01/2026/import", data={"return_type": "individual"}, content_type="multipart/form-data",
                       follow_redirects=True)
    assert "Choose at least one file" in resp.get_data(as_text=True)
