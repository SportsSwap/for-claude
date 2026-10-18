"""Only this laptop, only this browser session.

The server binds to 127.0.0.1 (server.py). On top of that, every request must
carry the session cookie, whose value is a random key made each time Sawnx
starts and handed to the browser once in the address it opens. Requests for
another host name (DNS rebinding) and POSTs from another origin are refused.
"""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from flask import Flask, abort, redirect, request

SESSION_COOKIE = "sawnx_session"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
log = logging.getLogger("tra.web")
CSP = ("default-src 'self'; img-src 'self' data:; frame-src 'self'; object-src 'self'; "
       "frame-ancestors 'self'; base-uri 'none'; form-action 'self'")


def _same(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def install_security(app: Flask, session_key: str) -> None:
    """The port is read from app.config["SAWNX"]["port"] on each request, so a fallback port still works."""

    def allowed_hosts() -> set[str]:
        port = app.config["SAWNX"]["port"]
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def refuse(reason: str):
        log.warning("Sawnx refused %s %s: %s", request.method, request.path, reason)
        abort(403)

    @app.before_request
    def _check():
        if request.path == "/favicon.ico":  # browsers ask without the cookie; there is no icon
            return "", 204
        hosts = allowed_hosts()
        if request.host not in hosts:
            refuse(f"host {request.host!r}")
        key = request.args.get("key")
        if key is not None and request.method == "GET":
            if not _same(key, session_key):
                refuse("wrong key")
            rest = {k: v for k, v in request.args.lists() if k != "key"}
            resp = redirect(request.path + (f"?{urlencode(rest, doseq=True)}" if rest else ""))
            resp.set_cookie(SESSION_COOKIE, session_key, httponly=True, samesite="Strict", path="/")
            return resp
        if not _same(request.cookies.get(SESSION_COOKIE, ""), session_key):
            refuse("no session cookie")
        if request.method not in SAFE_METHODS and request.headers.get("Origin") not in {f"http://{h}" for h in hosts}:
            refuse(f"origin {request.headers.get('Origin')!r}")
        return None

    @app.after_request
    def _headers(resp):
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        # same-origin, not no-referrer: with no-referrer Chromium sends "Origin: null" on our own form posts.
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = CSP
        return resp
