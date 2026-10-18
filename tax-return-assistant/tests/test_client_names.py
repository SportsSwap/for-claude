import html
import json
import os

import pytest
from webctx import make_client, new_client

from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.client_names import load_names, names_path, set_name, suggest_code


def test_suggest_code_from_surname():
    assert suggest_code("Jane Citizen", set()) == "CITI01"
    assert suggest_code("Jane Citizen", {"CITI01", "CITI02"}) == "CITI03"
    assert suggest_code("Bo Li", set()) == "LI01"
    assert suggest_code("  ", set()) == ""
    assert suggest_code("O'Brien-Smith", set()) == "OBRI01"


def test_set_and_load_names(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    audit = AuditLog(home / "audit" / "a.jsonl")
    set_name(home, "CITI01", "Jane Citizen", audit)
    assert load_names(home) == {"CITI01": "Jane Citizen"}
    set_name(home, "CITI01", "Jane Q Citizen", audit)
    assert load_names(home)["CITI01"] == "Jane Q Citizen"
    with pytest.raises(ValueError):
        set_name(home, "CITI01", "   ", audit)
    with pytest.raises(ValueError):
        set_name(home, "CITI01", "x" * 81, audit)


def test_name_with_tfn_refused(tmp_path, make_tfn):
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(SensitiveDataBlocked):
        set_name(home, "CITI01", f"Jane {make_tfn()}", AuditLog(home / "audit" / "a.jsonl"))
    assert not names_path(home).exists()


def test_new_client_by_name_and_name_only_in_one_file(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    resp = client.post("/clients/new", data={"name": "Jane Citizen", "code": "", "income_year": "2026"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/CITI01/2026/files")
    assert load_names(settings.tra_home) == {"CITI01": "Jane Citizen"}
    for root, _dirs, files in os.walk(settings.tra_home):
        for f in files:
            path = os.path.join(root, f)
            assert "Citizen" not in path
            if os.path.abspath(path) != os.path.abspath(names_path(settings.tra_home)):
                assert "Citizen" not in open(path, encoding="utf-8", errors="replace").read(), path


def test_list_sorted_and_searched_by_name(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    for name, code in (("Zoe Adams", "ADAM01"), ("Ben Young", "YOUN01"), ("Amy Brown", "BROW01")):
        client.post("/clients/new", data={"name": name, "code": code, "income_year": "2026"})
    page = client.get("/").get_data(as_text=True)
    assert page.index("Amy Brown") < page.index("Ben Young") < page.index("Zoe Adams")
    found = client.get("/?q=young").get_data(as_text=True)
    assert "Ben Young" in found and "Amy Brown" not in found
    by_code = client.get("/?q=brow").get_data(as_text=True)
    assert "Amy Brown" in by_code and "Ben Young" not in by_code


def test_client_page_title_and_rename(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    client.post("/clients/new", data={"name": "Jane Citizen", "code": "CITI01", "income_year": "2026"})
    assert "Jane Citizen" in client.get("/c/CITI01/2026/files").get_data(as_text=True)
    resp = client.post("/c/CITI01/name", data={"name": "Jane Q Citizen", "fy": "2026"})
    assert resp.status_code == 302
    assert load_names(settings.tra_home)["CITI01"] == "Jane Q Citizen"


def test_clients_without_names_still_listed(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, "DEMO01")
    assert "DEMO01" in client.get("/").get_data(as_text=True)


def test_new_client_needs_name_or_code(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    resp = client.post("/clients/new", data={"name": "", "code": "", "income_year": "2026"})
    assert resp.status_code == 200 and "client's name" in html.unescape(resp.get_data(as_text=True))
    assert json.loads("{}") == {}
