"""Filing rules: "if a document mentions X, suggest client Y, cabinet Z, folder W" (TRA_HOME/sawnx_rules.json).

Rules only change In Tray *suggestions*; the preparer still confirms every filing.
They are matched against the redacted text, case-insensitively; the first match wins.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..cabinets import CABINETS, DEFAULT_FOLDERS
from ..ingest.classify import CATEGORIES
from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value
from .ids import new_id
from .jobs import client_years

LOCATION = "sawnx_rules.json"


def _path(tra_home: Path) -> Path:
    return Path(tra_home) / "sawnx_rules.json"


def load_rules(tra_home: Path) -> list[dict]:
    path = _path(tra_home)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _save(tra_home: Path, rules: list[dict]) -> None:
    check_value(rules, LOCATION)
    atomic_write_text(_path(tra_home), json.dumps(rules, indent=2), LOCATION, prechecked=True)


def folders_for(cabinet: str) -> tuple[str, ...]:
    return tuple(CATEGORIES) if cabinet == "Tax return" else DEFAULT_FOLDERS.get(cabinet, ())


def add_rule(tra_home: Path, phrase: str, code: str, cabinet: str, folder: str, audit: AuditLog) -> dict:
    phrase = " ".join((phrase or "").split())
    if len(phrase) < 3 or len(phrase) > 100:
        raise ValueError("The words to look for need 3 to 100 characters.")
    if code not in client_years(tra_home):
        raise ValueError("Choose a client from the list.")
    if cabinet not in CABINETS or folder not in folders_for(cabinet):
        raise ValueError("Choose a cabinet and one of its folders.")
    rule = {"id": new_id(10), "phrase": phrase, "code": code, "cabinet": cabinet, "folder": folder}
    _save(tra_home, load_rules(tra_home) + [rule])
    audit.record("rule_added", client=code, rule=rule["id"])
    return rule


def delete_rule(tra_home: Path, rule_id: str, audit: AuditLog) -> None:
    rules = load_rules(tra_home)
    kept = [r for r in rules if r["id"] != rule_id]
    if len(kept) == len(rules):
        raise ValueError("That rule no longer exists.")
    _save(tra_home, kept)
    audit.record("rule_deleted", rule=rule_id)


def match_rule(tra_home: Path, text: str) -> dict | None:
    lowered = (text or "").lower()
    return next((r for r in load_rules(tra_home) if r["phrase"].lower() in lowered), None)
