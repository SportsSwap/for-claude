"""The In Tray: documents waiting to be filed, each with Sawnx's suggestion of where it goes.

Files wait in TRA_HOME/InTray under random names; tray.json holds, per item, the
suggestion and a short preview of the *redacted* text. Original file names are
never kept. Nothing is filed until the preparer confirms; discarding deletes only
Sawnx's copy. Suggestions need no AI: the client comes from finding a client's
name (or code) in the text, the type and folder from the classifier, the year
from the document's date.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from ..cabinets import CABINETS, CODES, CabinetSpace, store_in_cabinet
from ..dates import find_doc_date
from ..filing.fyi_store import make_store
from ..ingest.classify import classify, load_doc_types
from ..ingest.pipeline import IngestError, ingest_file
from ..ingest.readers import load
from ..privacy.audit import AuditLog
from ..privacy.guard import atomic_write_text, check_value
from ..settings import Settings, validate_client_code
from ..workspace import Workspace
from .client_names import load_names
from .rules import match_rule
from .services.imports import READ_TYPES, STORE_TYPES, ImportOutcome, _store_only

LOCATION = "tray.json"
PREVIEW_LINES = 4


@dataclass
class TrayItem:
    id: str
    ext: str
    sha256: str
    added_at: str
    by: str
    readable: bool
    preview: list[str] = field(default_factory=list)
    suggestion: dict = field(default_factory=dict)


def tray_dir(tra_home: Path) -> Path:
    return Path(tra_home) / "InTray"


def _load(tra_home: Path) -> list[TrayItem]:
    path = tray_dir(tra_home) / "tray.json"
    return [TrayItem(**d) for d in json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []


def _save(tra_home: Path, items: list[TrayItem]) -> None:
    data = [asdict(i) for i in items]
    check_value(data, LOCATION)
    atomic_write_text(tray_dir(tra_home) / "tray.json", json.dumps(data, indent=2), LOCATION, prechecked=True)


def list_tray(tra_home: Path) -> list[TrayItem]:
    return _load(tra_home)


def tray_file_path(tra_home: Path, item_id: str) -> Path | None:
    item = next((i for i in _load(tra_home) if i.id == item_id), None)
    if item is None:
        return None
    path = tray_dir(tra_home) / f"{item.id}{item.ext}"
    return path if path.is_file() else None


def _client_years(tra_home: Path) -> dict[str, list[int]]:
    years: dict[str, list[int]] = {}
    for state in (Path(tra_home) / "Work").glob("*/FY*/state.json"):
        code, fy = state.parent.parent.name, state.parent.name[2:]
        if fy.isdigit():
            years.setdefault(code, []).append(int(fy))
    return {k: sorted(v, reverse=True) for k, v in years.items()}


def _match_client(text: str, tra_home: Path) -> str:
    lowered, best, best_score = text.lower(), "", 0
    names = load_names(tra_home)
    for code in _client_years(tra_home):
        words = [w for w in (names.get(code) or "").lower().split() if len(w) > 1]
        score = len(words) if words and all(w in lowered for w in words) else 0
        if code.lower() in lowered.split():
            score = max(score, 1)
        if score > best_score:
            best, best_score = code, score
        elif score and score == best_score:
            best = ""  # two clients match equally: don't guess
    return best


def _income_year(when: date | None) -> int | None:
    if when is None:
        return None
    return when.year + 1 if when.month >= 7 else when.year


def _suggest(path: Path, tra_home: Path) -> tuple[bool, list[str], dict]:
    ext = path.suffix.lower()
    years = _client_years(tra_home)
    if ext not in READ_TYPES:
        cabinet, folder = ("Correspondence", "Emails") if ext in (".eml", ".msg") else ("Tax return", "Other")
        return False, [], {"code": "", "cabinet": cabinet, "year": None, "folder": folder, "doc_type": "OTHER",
                           "mode": "store"}
    try:
        loaded = load(path)
    except Exception:  # damaged or password-protected: still filable, just no suggestion
        return False, [], {"code": "", "cabinet": "Tax return", "year": None, "folder": "Other", "doc_type": "OTHER",
                           "mode": "store"}
    doc_types = load_doc_types()
    doc_type = classify(loaded.redacted, doc_types)
    text = loaded.redacted.text
    code = _match_client(text, tra_home)
    year = _income_year(find_doc_date(text))
    if year is None and code:
        year = years[code][0]
    preview = [line.strip()[:120] for line in text.splitlines() if line.strip()][:PREVIEW_LINES]
    suggestion = {"code": code, "cabinet": "Tax return", "year": year, "folder": doc_types[doc_type].category,
                  "doc_type": doc_type, "mode": "store" if doc_type == "OTHER" else "read"}
    rule = match_rule(tra_home, text)
    if rule:
        suggestion.update(code=rule["code"], cabinet=rule["cabinet"], folder=rule["folder"])
        if rule["cabinet"] != "Tax return":
            suggestion["mode"] = "store"
        elif suggestion["year"] is None:
            suggestion["year"] = years.get(rule["code"], [None])[0]
    return True, preview, suggestion


def add_to_tray(tra_home: Path, source: Path, by: str, audit: AuditLog) -> TrayItem:
    """Copy ``source`` into the In Tray (the caller deletes its own temporary copy)."""
    ext = source.suffix.lower()
    if ext not in STORE_TYPES:
        raise ValueError(f"Can't use {ext or 'files without an extension'} files. Supported: {', '.join(STORE_TYPES)}.")
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    items = _load(tra_home)
    existing = next((i for i in items if i.sha256 == sha256), None)
    if existing:
        return existing
    item_id = secrets.token_hex(8)
    target = tray_dir(tra_home) / f"{item_id}{ext}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    try:
        readable, preview, suggestion = _suggest(target, tra_home)
        item = TrayItem(id=item_id, ext=ext, sha256=sha256, by=by, readable=readable, preview=preview,
                        added_at=datetime.now().astimezone().isoformat(timespec="seconds"), suggestion=suggestion)
        _save(tra_home, items + [item])
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    audit.record("intray_added", item=item_id)
    return item


def _remove(tra_home: Path, item_id: str) -> None:
    items = _load(tra_home)
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise ValueError("That document is no longer in the In Tray.")
    _save(tra_home, [i for i in items if i.id != item_id])
    (tray_dir(tra_home) / f"{item.id}{item.ext}").unlink(missing_ok=True)


def discard_item(tra_home: Path, item_id: str, audit: AuditLog) -> None:
    _remove(tra_home, item_id)
    audit.record("intray_discarded", item=item_id)


def file_item(settings: Settings, item_id: str, *, code: str, cabinet: str, year: int | None, folder: str, mode: str,
              audit: AuditLog) -> ImportOutcome:
    """File one In Tray document where the preparer chose. Raises ValueError with a plain message if it can't."""
    tra_home = settings.tra_home
    path = tray_file_path(tra_home, item_id)
    if path is None:
        raise ValueError("That document is no longer in the In Tray.")
    validate_client_code(code, settings.client_code_pattern)
    years = _client_years(tra_home)
    if code not in years:
        raise ValueError("Choose a client from the list.")
    if cabinet not in CABINETS:
        raise ValueError("Choose a cabinet from the list.")
    outcome = ImportOutcome(label="This document")
    if cabinet in CODES:
        outcome.doc = store_in_cabinet(CabinetSpace(tra_home, code, cabinet), path, folder, audit)
    else:
        if year not in years[code]:
            raise ValueError(f"FY{year} isn't set up for this client yet. Add it with New client (same code), "
                             "then file this document." if year else "Choose an income year.")
        ws = Workspace(tra_home, code, year)
        if mode == "read":
            if path.suffix.lower() not in READ_TYPES:
                raise ValueError("Only PDF, Excel, CSV and JSON files can be read for the return. Choose Store only.")
            try:
                report = ingest_file(path, ws, make_store(settings), load_doc_types(), audit)
            except IngestError as exc:
                raise ValueError(str(exc)) from None
            outcome.doc, outcome.figures_added = report.doc, report.figures_added
            outcome.notes, outcome.duplicate = report.notes, report.duplicate
        else:
            from .services.files import folder_names

            if folder not in folder_names(ws):
                raise ValueError("Choose a folder to store it in.")
            outcome = _store_only(path, ws, make_store(settings), folder, audit, outcome)
    _remove(tra_home, item_id)
    audit.record("intray_filed", client=code, item=item_id, doc_id=outcome.doc.doc_id if outcome.doc else None)
    return outcome
