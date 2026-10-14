"""OAuth 2.0 authorisation code flow with PKCE.

PKCE lets a desktop app sign in without a client secret, so there's nothing
secret to store on the laptop except the tokens Xero issues, which go in
Windows Credential Manager (via keyring), never in a file.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


class XeroSignInError(Exception):
    pass


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: datetime

    def expired(self, margin_seconds: int = 60) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at - timedelta(seconds=margin_seconds)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(client_id: str, redirect_uri: str, scopes: list[str], state: str, challenge: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "scope": " ".join(scopes),
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})


def _tokens(response) -> Tokens:
    if response.status_code != 200:
        raise XeroSignInError(f"Xero sign-in failed (HTTP {response.status_code}). Run 'tra xero connect' again.")
    data = response.json()
    return Tokens(data["access_token"], data["refresh_token"],
                  datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 1800))))


def exchange_code(session, client_id: str, code: str, verifier: str, redirect_uri: str) -> Tokens:
    return _tokens(session.post(TOKEN_URL, data={"grant_type": "authorization_code", "client_id": client_id,
                                                 "code": code, "redirect_uri": redirect_uri,
                                                 "code_verifier": verifier}, timeout=30))


def refresh_tokens(session, client_id: str, refresh_token: str) -> Tokens:
    return _tokens(session.post(TOKEN_URL, data={"grant_type": "refresh_token", "client_id": client_id,
                                                 "refresh_token": refresh_token}, timeout=30))


class TokenStore:
    """The Xero refresh token in the operating system's credential store (Windows Credential Manager).

    Only the refresh token is stored: Windows limits a stored credential to about 1,280
    characters and Xero access tokens can be longer. Each run swaps the refresh token
    for a fresh access token, which lives in memory only.
    """

    def __init__(self, service: str = "tra-xero", backend=None):
        if backend is None:
            import keyring as backend
        self.service, self.backend = service, backend

    def get(self) -> str | None:
        return self.backend.get_password(self.service, "refresh_token") or None

    def set(self, tokens: Tokens) -> None:
        self.backend.set_password(self.service, "refresh_token", tokens.refresh_token)


def wait_for_code(expected_state: str, port: int = REDIRECT_PORT, timeout: int = 300) -> str:
    """Run a one-shot local web server to catch Xero's redirect, and return the authorisation code."""
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            query = parse_qs(urlparse(self.path).query)
            result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Signed in to Xero. You can close this tab and return to the terminal.".encode())

        def log_message(self, *_args):  # keep the code out of any log
            return

    server = HTTPServer(("localhost", port), Handler)
    server.timeout = timeout
    try:
        server.handle_request()
    finally:
        server.server_close()
    if result.get("state") != expected_state or "code" not in result:
        raise XeroSignInError("Xero sign-in didn't complete (no code, or the state didn't match). Try again.")
    return result["code"]
