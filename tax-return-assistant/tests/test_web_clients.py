import json

from webctx import KEY, make_app, make_client

from tra.clients import ClientExists, create_client
from tra.privacy.audit import AuditLog


def test_empty_home_renders(tmp_path, monkeypatch):
    _app, client, _ = make_client(tmp_path, monkeypatch)
    resp = client.get("/clients")
    assert resp.status_code == 200
    assert "No clients yet" in resp.get_data(as_text=True)


def test_new_client_form_creates_state(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    resp = client.post("/clients/new", data={"code": "TEST09", "income_year": "2026", "help_debt": "on",
                                             "hospital_days": "365", "age_band": "under65", "sapto": "none",
                                             "dependants": "0"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/c/TEST09/2026/files")
    state = json.loads((settings.tra_home / "Work" / "TEST09" / "FY2026" / "state.json").read_text(encoding="utf-8"))
    assert state["help_debt"] is True and state["hospital_cover_days"] == 365 and state["resident"] is True


def test_new_client_rejects_bad_codes(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    for bad in ("test09", "TE ST", "../X", ""):
        resp = client.post("/clients/new", data={"code": bad, "income_year": "2026"})
        assert resp.status_code == 200
        assert "client code" in resp.get_data(as_text=True).lower()
    assert not (settings.tra_home / "Work").exists() or not any((settings.tra_home / "Work").iterdir())


def test_new_client_rejects_bad_numbers(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    resp = client.post("/clients/new", data={"code": "TEST09", "income_year": "2026", "hospital_days": "400"})
    assert resp.status_code == 200 and "hospital" in resp.get_data(as_text=True).lower()
    assert not (settings.tra_home / "Work" / "TEST09").exists()


def test_duplicate_client_is_refused(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    data = {"code": "TEST09", "income_year": "2026"}
    assert client.post("/clients/new", data=data).status_code == 302
    resp = client.post("/clients/new", data=data)
    assert resp.status_code == 200 and "already exists" in resp.get_data(as_text=True)
    try:
        create_client(settings.tra_home, "TEST09", 2026, {}, AuditLog(tmp_path / "a.jsonl"))
        raise AssertionError("expected ClientExists")
    except ClientExists:
        pass


def test_list_shows_status_and_search(tmp_path, monkeypatch):
    _app, client, _ = make_client(tmp_path, monkeypatch)
    for code in ("TEST09", "SAMP01"):
        client.post("/clients/new", data={"code": code, "income_year": "2026"})
    page = client.get("/clients").get_data(as_text=True)
    assert "TEST09" in page and "SAMP01" in page and "New" in page
    filtered = client.get("/clients?q=sam").get_data(as_text=True)
    assert "SAMP01" in filtered and "TEST09" not in filtered
    by_status = client.get("/clients?status=Prepared").get_data(as_text=True)
    assert "TEST09" not in by_status


def test_unknown_page_is_friendly_404(tmp_path, monkeypatch):
    _app, client, _ = make_client(tmp_path, monkeypatch)
    resp = client.get("/no/such/page")
    assert resp.status_code == 404 and "Sawnx" in resp.get_data(as_text=True)


def test_unexpected_error_page_has_no_detail(tmp_path, monkeypatch):
    app, settings = make_app(tmp_path, monkeypatch)

    @app.route("/boom")
    def boom():
        raise RuntimeError("secret detail")

    client = app.test_client()
    client.get(f"/?key={KEY}")
    resp = client.get("/boom")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 500 and "secret detail" not in body and "Reference" in body
    assert "secret detail" in (settings.tra_home / "logs" / "tra.log").read_text(encoding="utf-8")
