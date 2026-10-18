import socket

from webctx import KEY, ORIGIN, make_app, make_client

from tra.web.security import SESSION_COOKIE
from tra.web.server import HOST, bind


def _plain(app):
    """A client that sends exactly what the test says, nothing added."""
    from flask.testing import FlaskClient

    app.test_client_class = FlaskClient
    return app.test_client()


def test_key_is_swapped_for_cookie(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    resp = _plain(app).get(f"/?key={KEY}", base_url=ORIGIN)
    assert resp.status_code == 302
    assert "key=" not in resp.headers["Location"]
    cookie = resp.headers["Set-Cookie"]
    assert f"{SESSION_COOKIE}={KEY}" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_no_cookie_is_403(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    assert _plain(app).get("/", base_url=ORIGIN).status_code == 403


def test_wrong_key_is_403(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    client = _plain(app)
    assert client.get("/?key=not-the-key", base_url=ORIGIN).status_code == 403
    client.set_cookie(SESSION_COOKIE, "not-the-key", domain="127.0.0.1")
    assert client.get("/", base_url=ORIGIN).status_code == 403


def test_wrong_host_is_403(tmp_path, monkeypatch):
    _app, client, _ = make_client(tmp_path, monkeypatch)
    assert client.get("/", headers={"Host": "evil.example:8766"}).status_code == 403
    assert client.get("/").status_code == 200


def test_post_needs_same_origin(tmp_path, monkeypatch):
    app, client, _ = make_client(tmp_path, monkeypatch)
    plain = _plain(app)
    plain.get(f"/?key={KEY}", base_url=ORIGIN)
    assert plain.post("/", base_url=ORIGIN).status_code == 403
    assert plain.post("/", base_url=ORIGIN, headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.post("/").status_code != 403


def test_security_headers(tmp_path, monkeypatch):
    _app, client, _ = make_client(tmp_path, monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    # Not "no-referrer": with it, Chromium sends "Origin: null" on same-site form posts, so every save was
    # refused in the real browser (found by hand on 18 Oct 2026). "same-origin" still sends nothing to other sites.
    assert resp.headers["Referrer-Policy"] == "same-origin"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def test_favicon_needs_no_cookie_and_logs_nothing(tmp_path, monkeypatch):
    app, settings = make_app(tmp_path, monkeypatch)
    resp = _plain(app).get("/favicon.ico", base_url=ORIGIN)
    assert resp.status_code == 204 and resp.data == b""
    log = settings.tra_home / "logs" / "tra.log"
    assert not log.exists() or "favicon" not in log.read_text(encoding="utf-8")


def test_refusals_are_logged_without_the_key(tmp_path, monkeypatch):
    app, settings = make_app(tmp_path, monkeypatch)
    _plain(app).get("/?key=not-the-key", base_url=ORIGIN)
    text = (settings.tra_home / "logs" / "tra.log").read_text(encoding="utf-8")
    assert "wrong key" in text and KEY not in text and "not-the-key" not in text


def test_bind_uses_loopback_only(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    server = bind(app, 0)
    try:
        assert server.server_address[0] == HOST == "127.0.0.1"
    finally:
        server.server_close()


def test_bind_falls_back_when_port_taken(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    holder = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        holder.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    holder.bind(("127.0.0.1", 0))
    holder.listen()
    taken = holder.getsockname()[1]
    try:
        server = bind(app, taken)
        try:
            assert server.server_port != taken
        finally:
            server.server_close()
    finally:
        holder.close()
