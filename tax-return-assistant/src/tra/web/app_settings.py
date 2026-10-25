"""Sawnx's own settings: TRA_HOME/sawnx.json. The AI reader switch and, separately, the switch that lets it send
pictures of scanned pages, each with who approved it."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
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
    # Pictures of scanned pages can't be blanked out, so they need their own approval. Only used while the AI
    # reader is on; switching the AI reader off switches these off and clears their approval too.
    ai_page_images: bool = False
    images_approved_by: str | None = None
    images_approved_on: str | None = None

    @property
    def page_images_in_use(self) -> bool:
        return self.ai_reader and self.ai_page_images


def _path(tra_home: Path) -> Path:
    return Path(tra_home) / "sawnx.json"


def load_app_settings(tra_home: Path) -> SawnxSettings:
    path = _path(tra_home)
    if not path.exists():
        return SawnxSettings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return SawnxSettings(ai_reader=data.get("ai_reader") is True, approved_by=data.get("approved_by"),
                         approved_on=data.get("approved_on"), ai_page_images=data.get("ai_page_images") is True,
                         images_approved_by=data.get("images_approved_by"),
                         images_approved_on=data.get("images_approved_on"))


def _save(tra_home: Path, settings: SawnxSettings) -> None:
    data = asdict(settings)
    check_value(data, LOCATION)
    atomic_write_text(_path(tra_home), json.dumps(data, indent=2), LOCATION, prechecked=True)


def _approver(approved_by: str, approved_on: date | None, what: str) -> str:
    approved_by = (approved_by or "").strip()
    if not approved_by or approved_on is None:
        raise ValueError(f"Enter the approver's name and the date the privacy officer approved {what}.")
    return approved_by


def enable_ai_reader(tra_home: Path, approved_by: str, approved_on: date | None, audit: AuditLog) -> None:
    approved_by = _approver(approved_by, approved_on, "the AI reader")
    _save(tra_home, replace(load_app_settings(tra_home), ai_reader=True, approved_by=approved_by,
                            approved_on=approved_on.isoformat()))
    audit.record("ai_reader_enabled", approved_by=approved_by, approved_on=approved_on.isoformat())


def disable_ai_reader(tra_home: Path, audit: AuditLog) -> None:
    """Page images go off with it, so switching the AI reader back on never quietly resumes sending pictures:
    they need their own approval again."""
    current = load_app_settings(tra_home)
    _save(tra_home, replace(current, ai_reader=False, approved_by=None, approved_on=None, ai_page_images=False,
                            images_approved_by=None, images_approved_on=None))
    if current.ai_page_images:
        audit.record("ai_page_images_disabled", reason="ai_reader_disabled")
    audit.record("ai_reader_disabled")


def enable_ai_page_images(tra_home: Path, approved_by: str, approved_on: date | None, audit: AuditLog) -> None:
    current = load_app_settings(tra_home)
    if not current.ai_reader:
        raise ValueError("Switch the AI reader on first: page images are only sent by the AI reader.")
    approved_by = _approver(approved_by, approved_on, "sending page images")
    _save(tra_home, replace(current, ai_page_images=True, images_approved_by=approved_by,
                            images_approved_on=approved_on.isoformat()))
    audit.record("ai_page_images_enabled", approved_by=approved_by, approved_on=approved_on.isoformat())


def disable_ai_page_images(tra_home: Path, audit: AuditLog) -> None:
    _save(tra_home, replace(load_app_settings(tra_home), ai_page_images=False, images_approved_by=None,
                            images_approved_on=None))
    audit.record("ai_page_images_disabled")
