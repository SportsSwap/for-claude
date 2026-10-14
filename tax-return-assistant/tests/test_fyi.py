from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from tra.cli import main
from tra.demo import build_demo_documents
from tra.filing.fyi_store import FyiError, FyiStore, load_fyi_config, make_store
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.filing.store import FallbackStore, FilingRequest
from tra.ingest.classify import CATEGORIES, load_doc_types
from tra.ingest.pipeline import ingest_file
from tra.models import ClientState
from tra.notes_store import read_notes
from tra.privacy.audit import AuditLog
from tra.settings import Settings
from tra.workspace import Workspace

ENV = {"FYI_BASE_URL": "https://fyi.example/external", "FYI_ACCESS_ID": "id-1", "FYI_ACCESS_SECRET": "sec-1",
       "FYI_APP_ID": "app-1"}


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self.responses.pop(0)

    def post(self, url, **kw):
        self.calls.append(("POST", url, {**kw, "files": {k: v[0] for k, v in kw.get("files", {}).items()}}))
        return self.responses.pop(0)


def _store(session):
    return FyiStore(session, ENV["FYI_BASE_URL"], "id-1", "sec-1", "app-1", load_fyi_config())


REQ = FilingRequest("SMIT01", 2026, "Investments", "SMIT01_FY2026_DIVSTMT_2026-03-24.pdf", "DIVSTMT", date(2026, 3, 24))


def test_fyi_headers_and_upload(tmp_path):
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF")
    s = Session(Resp(data=[{"id": "c-77", "code": "SMIT01"}]), Resp(201, {"url": "https://fyi.example/d/9"}))
    ref = _store(s).file(source, REQ)
    assert ref.store == "fyi" and ref.location == "https://fyi.example/d/9"
    cfg = load_fyi_config()["headers"]
    for method, url, kw in s.calls:
        assert kw["headers"][cfg["access_id"]] == "id-1"
        assert kw["headers"][cfg["access_secret"]] == "sec-1"
        assert kw["headers"][cfg["app_id"]] == "app-1"
    assert s.calls[0][1] == "https://fyi.example/external/clients?code=SMIT01"
    post = s.calls[1][2]
    assert post["data"]["filename"] == REQ.filed_name and post["data"]["client_id"] == "c-77"
    assert post["data"]["cabinet"] == "Tax" and post["data"]["year"] == "FY2026"
    assert post["files"]["file"] == REQ.filed_name


def test_fyi_client_not_found(tmp_path):
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF")
    with pytest.raises(FyiError):
        _store(Session(Resp(data=[]))).file(source, REQ)
    with pytest.raises(FyiError):
        _store(Session(Resp(data=[{"id": 1}, {"id": 2}]))).file(source, REQ)
    with pytest.raises(FyiError) as err:
        _store(Session(Resp(500, {"detail": "secret server detail"}))).file(source, REQ)
    assert "secret server detail" not in str(err.value)
    with pytest.raises(FyiError):
        _store(Session(Resp(200, None))).file(source, REQ)


def test_make_store_selection(tmp_path):
    warnings = []
    local = Settings(tmp_path, "local", "^[A-Z0-9]{2,12}$")
    fyi = Settings(tmp_path, "fyi", "^[A-Z0-9]{2,12}$")
    assert isinstance(make_store(local, env=ENV, warn=warnings.append), LocalStore)
    assert isinstance(make_store(fyi, env=ENV, warn=warnings.append), FallbackStore)
    assert warnings == []
    assert isinstance(make_store(fyi, env={}, warn=warnings.append), LocalStore)
    assert warnings and "FYI_" in warnings[0]


class BrokenFyi:
    name = "fyi"

    def file(self, source, req):
        raise FyiError("HTTP 503")


def _client(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    ws = Workspace(home, "SMIT01", 2026)
    ws.create(list(CATEGORIES))
    ws.save_state(ClientState("SMIT01", 2026))
    return home, ws


def test_ingest_falls_back_when_fyi_down(tmp_path):
    home, ws = _client(tmp_path)
    demo = build_demo_documents(tmp_path / "inbox")
    report = ingest_file(demo.paths["dividend_bhp"], ws, FallbackStore(BrokenFyi(), LocalStore(home)),
                         load_doc_types(), AuditLog(ws.audit_path))
    assert report.doc.store == "local" and Path(report.doc.filed_location).exists()
    assert any(n.check_id == "I3" for n in read_notes(ws.ingest_notes_json))


def test_fyi_push_updates_index(tmp_path, monkeypatch):
    home, ws = _client(tmp_path)
    demo = build_demo_documents(tmp_path / "inbox")
    for stem in ("dividend_bhp", "bank_interest"):
        ingest_file(demo.paths[stem], ws, LocalStore(home), load_doc_types(), AuditLog(ws.audit_path))

    class FakeFyi:
        name = "fyi"

        def __init__(self, *a, **k):
            pass

        def file(self, source, req):
            from tra.filing.store import FiledRef
            assert Path(source).exists()
            return FiledRef(location=f"https://fyi.example/d/{req.filed_name}", store="fyi")

    monkeypatch.setattr("tra.cli.FyiStore", FakeFyi)
    env = {"TRA_HOME": str(home), "TRA_STORE": "fyi", **ENV}
    result = CliRunner().invoke(main, ["fyi", "push", "SMIT01"], env=env, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    docs = DocumentIndex(ws.index_csv).load()
    assert [d.store for d in docs] == ["fyi", "fyi"]
    assert all(d.filed_location.startswith("https://fyi.example/d/") for d in docs)
    assert "fyi_push" in ws.audit_path.read_text()
