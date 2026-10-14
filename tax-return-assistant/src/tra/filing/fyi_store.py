"""FYI Docs as the document store (stage 6). Built against FYI's documented
header-credential scheme; header names and endpoint paths come from
config/fyi.yaml and must be confirmed with FYI before first use."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Mapping

import yaml

from ..dates import fy_label
from ..paths import CONFIG_DIR
from ..settings import Settings
from .local_store import LocalStore
from .store import DocumentStore, FallbackStore, FiledRef, FilingRequest

FYI_ENV = ("FYI_BASE_URL", "FYI_ACCESS_ID", "FYI_ACCESS_SECRET", "FYI_APP_ID")


class FyiError(Exception):
    """FYI refused or failed. The message never includes FYI's response body."""


def load_fyi_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or CONFIG_DIR / "fyi.yaml").read_text(encoding="utf-8"))


class FyiStore:
    name = "fyi"

    def __init__(self, session, base_url: str, access_id: str, access_secret: str, app_id: str, cfg: dict):
        self.session, self.base_url, self.cfg = session, base_url.rstrip("/"), cfg
        h = cfg["headers"]
        self.headers = {h["access_id"]: access_id, h["access_secret"]: access_secret, h["app_id"]: app_id}

    def _json(self, response, what: str):
        if response.status_code not in (200, 201):
            raise FyiError(f"FYI returned HTTP {response.status_code} when {what}")
        try:
            return response.json()
        except ValueError:
            raise FyiError(f"FYI sent a response the tool doesn't understand when {what}") from None

    def _client_id(self, client_code: str) -> str:
        url = self.base_url + self.cfg["endpoints"]["find_client"].format(code=client_code)
        data = self._json(self.session.get(url, headers=self.headers, timeout=30), "looking up the client")
        clients = data if isinstance(data, list) else data.get("clients") or data.get("items") or []
        if len(clients) != 1:
            raise FyiError(f"FYI has {len(clients)} clients with code {client_code}; expected exactly one")
        return str(clients[0]["id"])

    def file(self, source: Path, req: FilingRequest) -> FiledRef:
        client_id = self._client_id(req.client_code)
        cabinet = self.cfg["cabinet_map"].get(req.category, "Tax")
        with Path(source).open("rb") as fh:
            response = self.session.post(
                self.base_url + self.cfg["endpoints"]["upload"], headers=self.headers, timeout=120,
                data={"client_id": client_id, "cabinet": cabinet, "filename": req.filed_name,
                      "year": fy_label(req.income_year)},
                files={"file": (req.filed_name, fh, "application/octet-stream")})
        body = self._json(response, "uploading")
        location = body.get("url") or body.get("id") if isinstance(body, dict) else None
        return FiledRef(location=str(location or f"FYI:{req.filed_name}"), store="fyi")


def fyi_from_env(env: Mapping[str, str], session=None) -> FyiStore | None:
    if not all(env.get(name) for name in FYI_ENV):
        return None
    if session is None:
        import requests
        session = requests.Session()
    return FyiStore(session, env["FYI_BASE_URL"], env["FYI_ACCESS_ID"], env["FYI_ACCESS_SECRET"], env["FYI_APP_ID"],
                    load_fyi_config())


def make_store(settings: Settings, session=None, env: Mapping[str, str] | None = None,
               warn: Callable[[str], None] = lambda _m: None) -> DocumentStore:
    local = LocalStore(settings.tra_home)
    if settings.store != "fyi":
        return local
    fyi = fyi_from_env(os.environ if env is None else env, session)
    if fyi is None:
        warn("TRA_STORE is 'fyi' but FYI_BASE_URL, FYI_ACCESS_ID, FYI_ACCESS_SECRET and FYI_APP_ID are not all set; "
             "filing locally.")
        return local
    return FallbackStore(fyi, local)
