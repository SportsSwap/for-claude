"""Sawnx's own settings: TRA_HOME/sawnx.json. Today that's only the AI reader switch and who approved it."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value

LOCATION = "sawnx.json"


@dataclass
class SawnxSettings:
    ai_reader: bool = False
    approved_by: str | None = None
    approved_on: str | None = None


def _path(tra_home: Path) -> Path:
    return Path(tra_home) / "sawnx.json"


def load_app_settings(tra_home: Path) -> SawnxSettings:
    path = _path(tra_home)
    if not path.exists():
        return SawnxSettings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return SawnxSettings(ai_reader=data.get("ai_reader") is True, approved_by=data.get("approved_by"),
                         approved_on=data.get("approved_on"))


def _save(tra_home: Path, settings: SawnxSettings) -> None:
    data = asdict(settings)
    check_value(data, LOCATION)
    atomic_write_text(_path(tra_home), json.dumps(data, indent=2), LOCATION, prechecked=True)


def enable_ai_reader(tra_home: Path, approved_by: str, approved_on: date | None, audit: AuditLog) -> None:
    approved_by = (approved_by or "").strip()
    if not approved_by or approved_on is None:
        raise ValueError("Enter the approver's name and the date the privacy officer approved the AI reader.")
    _save(tra_home, SawnxSettings(True, approved_by, approved_on.isoformat()))
    audit.record("ai_reader_enabled", approved_by=approved_by, approved_on=approved_on.isoformat())


def disable_ai_reader(tra_home: Path, audit: AuditLog) -> None:
    _save(tra_home, SawnxSettings())
    audit.record("ai_reader_disabled")
