"""Recent searches: the last 5 clients found by search, per Windows user, stored as client codes only."""

import getpass
import json

from webctx import make_client, new_client

from tra.privacy.audit import AuditLog
from tra.web.client_names import set_name
from tra.web.recent import MAX_RECENT, recent_codes, recent_path, remember

USER = getpass.getuser()


def _named(settings, code="TEST01", name="Jane Citizen"):
    ws = new_client(settings, code)
    set_name(settings.tra_home, code, name, AuditLog(ws.audit_path))
    return ws


def test_open_from_search_remembers_and_redirects(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    resp = client.get("/search/open/TEST01")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/files")
    assert recent_codes(settings.tra_home, USER) == ["TEST01"]


def test_search_links_go_through_open(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, "TEST01")
    new_client(settings, "TEST02")
    page = client.get("/search?q=TEST0").get_data(as_text=True)
    assert 'href="/search/open/TEST01"' in page and 'href="/search/open/TEST02"' in page


def test_single_match_remembered(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, "TEST01")
    new_client(settings, "TEST02")
    client.get("/search?q=TEST02")
    assert recent_codes(settings.tra_home, USER) == ["TEST02"]


def test_two_matches_not_remembered(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, "TEST01")
    new_client(settings, "TEST02")
    client.get("/search?q=TEST0")
    assert recent_codes(settings.tra_home, USER) == []


def test_keeps_five_newest_no_repeats(tmp_path):
    for n in range(1, 8):
        remember(tmp_path, USER, f"TEST0{n}")
    assert recent_codes(tmp_path, USER) == ["TEST07", "TEST06", "TEST05", "TEST04", "TEST03"]
    remember(tmp_path, USER, "TEST05")
    assert recent_codes(tmp_path, USER) == ["TEST05", "TEST07", "TEST06", "TEST04", "TEST03"]
    assert MAX_RECENT == 5


def test_each_user_has_their_own(tmp_path):
    remember(tmp_path, "alex", "TEST01")
    remember(tmp_path, "sam", "TEST02")
    assert recent_codes(tmp_path, "alex") == ["TEST01"] and recent_codes(tmp_path, "sam") == ["TEST02"]


def test_only_codes_stored(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    _named(settings)
    client.get("/search?q=jane")
    raw = recent_path(settings.tra_home).read_text(encoding="utf-8")
    assert json.loads(raw) == {USER: ["TEST01"]}
    assert "jane" not in raw.lower() and "citizen" not in raw.lower()


def test_bad_code_refused(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        remember(tmp_path, USER, "Jane Citizen")


def test_menu_and_empty_search_page(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    _named(settings)
    client.get("/search/open/TEST01")
    home = client.get("/").get_data(as_text=True)
    menu = home[home.index('class="recent-menu"'):]
    assert "Jane Citizen" in menu[:menu.index("</div>")] and 'href="/c/TEST01/2026/files"' in menu
    page = client.get("/search").get_data(as_text=True)
    assert "Recent searches" in page and page.count("Jane Citizen") >= 2  # the menu and the page's own list


def test_no_recent_no_menu(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    assert 'class="recent-menu"' not in client.get("/").get_data(as_text=True)


def test_deleted_client_dropped(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    _named(settings)
    remember(settings.tra_home, USER, "GONE01")
    remember(settings.tra_home, USER, "TEST01")
    home = client.get("/").get_data(as_text=True)
    assert "GONE01" not in home and "Jane Citizen" in home


def test_open_unknown_client_404(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    assert client.get("/search/open/NOPE01").status_code == 404
    assert client.get("/search/open/not-a-code").status_code == 404
    assert recent_codes(settings.tra_home, USER) == []


def test_damaged_recent_file_never_breaks_a_page(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    for broken in ("[", '["TEST01"]', json.dumps({USER: "TEST01"}), json.dumps({USER: ["../../x", "TEST01"]})):
        recent_path(settings.tra_home).write_text(broken, encoding="utf-8")
        assert client.get("/").status_code == 200, broken
        assert client.get("/search?q=TEST01").status_code == 200, broken
    assert 'href="/c/../../x' not in client.get("/").get_data(as_text=True)


def test_search_works_when_recent_file_is_locked(tmp_path, monkeypatch):
    from tra.privacy.guard import FileLockedError
    import tra.web.recent as recent

    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)

    def locked(*args, **kwargs):
        raise FileLockedError(recent_path(settings.tra_home))

    monkeypatch.setattr(recent, "atomic_write_text", locked)
    assert client.get("/search?q=TEST01").status_code == 200
    assert client.get("/search/open/TEST01").status_code == 302
