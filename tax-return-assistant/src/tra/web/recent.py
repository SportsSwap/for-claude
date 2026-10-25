"""Recent searches: the last clients each Windows user found with the search box.

TRA_HOME/sawnx_recent.json holds {user: [client codes]}, newest first. Only codes are kept, never what
was typed (that may be a client's name); names come from clients.json when the list is shown.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..privacy.guard import FileLockedError, SensitiveDataBlocked, atomic_write_text, check_value
from ..settings import DEFAULT_CLIENT_CODE_PATTERN, validate_client_code
from .client_names import load_names

LOCATION = "sawnx_recent.json"
log = logging.getLogger("tra.web")
MAX_RECENT = 5


def recent_path(tra_home: Path) -> Path:
    return Path(tra_home) / LOCATION


def _load(tra_home: Path) -> dict[str, list[str]]:
    """The file, or nothing if it's missing or damaged: recent searches must never stop a page showing."""
    try:
        data = json.loads(recent_path(tra_home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {user: [c for c in codes if isinstance(c, str) and re.fullmatch(DEFAULT_CLIENT_CODE_PATTERN, c)]
            for user, codes in data.items() if isinstance(codes, list)}


def recent_codes(tra_home: Path, user: str) -> list[str]:
    return _load(tra_home).get(user, [])


def remember(tra_home: Path, user: str, code: str, pattern: str = DEFAULT_CLIENT_CODE_PATTERN) -> None:
    validate_client_code(code, pattern)
    data = _load(tra_home)
    data[user] = ([code] + [c for c in data.get(user, []) if c != code])[:MAX_RECENT]
    check_value(data, LOCATION)
    atomic_write_text(recent_path(tra_home), json.dumps(data, indent=2), LOCATION, prechecked=True)


def remember_quietly(tra_home: Path, user: str, code: str, pattern: str = DEFAULT_CLIENT_CODE_PATTERN) -> None:
    """remember(), for a search: if the file can't be written just now (open elsewhere, say), the search still works."""
    try:
        remember(tra_home, user, code, pattern)
    except (OSError, ValueError, FileLockedError, SensitiveDataBlocked):
        log.warning("Recent searches weren't updated (%s)", LOCATION)


def latest_year(tra_home: Path, code: str) -> int | None:
    years = [int(p.parent.name[2:]) for p in (Path(tra_home) / "Work" / code).glob("FY*/state.json")
             if p.parent.name[2:].isdigit()]
    return max(years, default=None)


def recent_clients(tra_home: Path, user: str) -> list[dict]:
    """The user's recent clients that still exist: code, name (if Sawnx has one) and latest income year."""
    names, out = load_names(tra_home), []
    for code in recent_codes(tra_home, user):
        year = latest_year(tra_home, code)
        if year:
            out.append({"code": code, "name": names.get(code), "fy": year})
    return out
