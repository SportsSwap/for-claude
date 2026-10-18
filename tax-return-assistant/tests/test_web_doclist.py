import html
import io
import zipfile

from webctx import build_test01, ingest_demo, make_client, new_client

from tra.privacy.audit import AuditLog
from tra.web.client_names import set_name
from tra.web.services.doclist import all_documents, query
from tra.web.stars import load_stars, set_stars


def _two_clients(tmp_path, monkeypatch):
    app, client, settings = make_client(tmp_path, monkeypatch)
    ws1 = build_test01(settings)
    set_name(settings.tra_home, "TEST01", "Sam Sample", AuditLog(ws1.audit_path))
    ws2 = new_client(settings, "DEMO01")
    ingest_demo(settings, ws2, "rental", "bank_interest")
    return client, settings


def test_all_documents_across_clients_with_names(tmp_path, monkeypatch):
    _client, settings = _two_clients(tmp_path, monkeypatch)
    rows = all_documents(settings.tra_home)
    assert len(rows) == 6
    sam = [r for r in rows if r.code == "TEST01"]
    assert {r.client for r in sam} == {"Sam Sample"} and all(r.summary for r in sam)
    assert {r.client for r in rows if r.code == "DEMO01"} == {"DEMO01"}


def test_sort_filter_and_search(tmp_path, monkeypatch):
    _client, settings = _two_clients(tmp_path, monkeypatch)
    rows = all_documents(settings.tra_home)
    by_name = query(rows, sort="name")
    assert [r.filed_name for r in by_name] == sorted(r.filed_name for r in rows)
    assert query(rows, sort="name", desc=True)[0].filed_name == max(r.filed_name for r in rows)
    assert {r.code for r in query(rows, client="TEST01")} == {"TEST01"}
    assert {r.folder for r in query(rows, folder="Investments")} == {"Investments"}
    found = query(rows, q="sample mining")
    assert [r.doc_type for r in found] == ["DIVSTMT"]
    recent = query(rows, sort="changed", desc=True)
    assert recent[0].last_change >= recent[-1].last_change


def test_home_shows_recent_documents_and_counts(tmp_path, monkeypatch):
    client, _settings = _two_clients(tmp_path, monkeypatch)
    page = html.unescape(client.get("/").get_data(as_text=True))
    assert "My Recent" in page and "My Starred" in page and "6 rows" in page
    assert "Sam Sample" in page and "TEST01_FY2026_INCSTMT_2026-06-30.pdf" in page


def test_star_and_starred_tab(tmp_path, monkeypatch):
    client, settings = _two_clients(tmp_path, monkeypatch)
    [row] = [r for r in all_documents(settings.tra_home) if r.doc_type == "INCSTMT"]
    resp = client.post("/stars", data={"key": [row.key], "action": "star", "next": "/?tab=starred"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/?tab=starred")
    assert load_stars(settings.tra_home) == {row.key}
    page = client.get("/?tab=starred").get_data(as_text=True)
    assert "INCSTMT" in page and "1 row" in page and "6 rows" not in page
    set_stars(settings.tra_home, [row.key], False)
    assert load_stars(settings.tra_home) == set()
    assert client.post("/stars", data={"key": ["../../x"], "action": "star", "next": "/"}).status_code == 400


def test_documents_page_filters_by_query_string(tmp_path, monkeypatch):
    client, _settings = _two_clients(tmp_path, monkeypatch)
    page = client.get("/documents?client=DEMO01&sort=name").get_data(as_text=True)
    assert "DEMO01_FY2026_RENTSTMT" in page and "TEST01_FY2026_INCSTMT" not in page


def test_bulk_download_zip(tmp_path, monkeypatch):
    client, settings = _two_clients(tmp_path, monkeypatch)
    keys = [r.key for r in all_documents(settings.tra_home) if r.code == "TEST01"][:2]
    resp = client.post("/download", data={"key": keys})
    assert resp.status_code == 200 and resp.mimetype == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(resp.data)).namelist()
    assert len(names) == 2 and all(n.startswith("TEST01_FY2026_") for n in names)
    assert client.post("/download", data={"key": ["TEST01/2026/D999"]}).status_code == 400


def test_bulk_move_same_client_only(tmp_path, monkeypatch):
    client, settings = _two_clients(tmp_path, monkeypatch)
    rows = all_documents(settings.tra_home)
    mixed = [rows[0].key, next(r.key for r in rows if r.code != rows[0].code)]
    page = client.post("/move", data={"key": mixed, "folder": "Other", "next": "/documents"},
                       follow_redirects=True).get_data(as_text=True)
    assert "one client" in page
    same = [r.key for r in rows if r.code == "TEST01"][:2]
    client.post("/move", data={"key": same, "folder": "Other", "next": "/documents"})
    moved = {r.key: r.folder for r in all_documents(settings.tra_home)}
    assert all(moved[k] == "Other" for k in same)


def test_search_finds_clients_and_documents(tmp_path, monkeypatch):
    client, _settings = _two_clients(tmp_path, monkeypatch)
    page = html.unescape(client.get("/search?q=sam").get_data(as_text=True))
    assert "Sam Sample" in page and "SAMPLE MINING LTD" in page


def test_top_bar_and_pages(tmp_path, monkeypatch):
    client, _settings = _two_clients(tmp_path, monkeypatch)
    page = client.get("/").get_data(as_text=True)
    for link in ('href="/"', 'href="/clients"', 'href="/documents"', 'href="/settings"', 'href="/help"',
                 'href="/clients/new"'):
        assert link in page
    assert client.get("/help").status_code == 200
    assert "Sam Sample" in client.get("/clients").get_data(as_text=True)
