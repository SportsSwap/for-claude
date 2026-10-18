"""Client names, for Sawnx's screens only: TRA_HOME/clients.json, code -> name.

Names are shown, searched and sorted by in Sawnx. Everywhere else (folders,
filenames, logs, the audit log, workpapers) the client is still its code, so a
stray file never says who the client is. The audit log records that a client
was named, never the name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value

LOCATION = "clients.json"
MAX_NAME = 80


def names_path(tra_home: Path) -> Path:
    return Path(tra_home) / "clients.json"


def load_names(tra_home: Path) -> dict[str, str]:
    path = names_path(tra_home)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def set_name(tra_home: Path, code: str, name: str, audit: AuditLog) -> None:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("Enter the client's name.")
    if len(name) > MAX_NAME:
        raise ValueError(f"Keep the name to {MAX_NAME} characters.")
    names = load_names(tra_home)
    names[code] = name
    check_value(names, LOCATION)
    atomic_write_text(names_path(tra_home), json.dumps(names, indent=2, sort_keys=True), LOCATION, prechecked=True)
    audit.record("client_named", client=code)


def suggest_code(name: str, existing: set[str]) -> str:
    """'Jane Citizen' -> CITI01: up to four letters of the surname and the next free number."""
    words = [re.sub(r"[^A-Za-z]", "", w) for w in (name or "").split()]
    words = [w for w in words if w]
    if not words:
        return ""
    stem = words[-1][:4].upper()
    n = 1
    while f"{stem}{n:02d}" in existing:
        n += 1
    return f"{stem}{n:02d}"
