"""Append-only audit log: what was accessed or written, when, and by whom.

Entries carry identifiers the tool assigns (client code, doc_id, filed name)
and counts. They never carry values from documents or original filenames.
"""

from __future__ import annotations

import getpass
import json
from datetime import datetime
from pathlib import Path

from .guard import SensitiveDataBlocked, check_value


class AuditLog:
    def __init__(self, path: Path):
        self.path = path

    def record(self, action: str, client: str | None = None, **fields: object) -> None:
        entry = {
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "user": getpass.getuser(),
            "action": action,
            "client": client,
            **fields,
        }
        try:
            check_value(entry, "audit log")
        except SensitiveDataBlocked as blocked:
            entry = {
                "ts": entry["ts"],
                "user": entry["user"],
                "action": "guard_blocked",
                "blocked_action": action,
                "client": client,
                "detector": blocked.detector_type,
            }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
