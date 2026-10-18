"""Setting up a client for an income year. Shared by `tra new` and Sawnx."""

from __future__ import annotations

from pathlib import Path

from .figures import write_header_files
from .ingest.classify import CATEGORIES
from .models import ClientState
from .privacy.audit import AuditLog
from .workspace import Workspace


class ClientExists(Exception):
    pass


def create_client(tra_home: Path, code: str, income_year: int, state_options: dict, audit: AuditLog) -> Workspace:
    """The caller has already checked the client code. ``state_options`` are ClientState fields."""
    ws = Workspace(tra_home, code, income_year)
    if ws.state_json.exists():
        raise ClientExists(f"{code} FY{income_year} already exists.")
    ws.create(list(CATEGORIES))
    ws.save_state(ClientState(client_code=code, income_year=income_year, **state_options))
    write_header_files(ws)
    audit.record("client_created", client=code, income_year=income_year)
    return ws
