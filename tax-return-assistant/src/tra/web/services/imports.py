"""Import: each file is either read for the return (the normal ingest) or stored only.

The upload is saved under a random name inside the client's work folder, used,
and always deleted. Its original name is never written anywhere, and pages
call it "File 1", "File 2"...
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path

from werkzeug.datastructures import FileStorage

from ...filing.index import DocumentIndex
from ...filing.store import DocumentStore
from ...ingest.classify import DocType
from ...ingest.pipeline import STORE_ONLY_TYPES, IngestError, IngestReport, ingest_file, store_document
from ...models import Document, ReviewNote
from ...privacy.audit import AuditLog
from ...privacy.guard import FileLockedError, SensitiveDataBlocked
from ...to_check import CheckItem, things_to_check
from ...workspace import Workspace
from ..messages import problem_text
from .files import folder_names

RETURN_TYPES = {"individual": "Individual", "company": "Company", "trust": "Trust"}
ENABLED_RETURN_TYPES = frozenset({"individual"})
READ_TYPES = (".pdf", ".csv", ".xlsx", ".json", ".eml", ".msg")
STORE_TYPES = READ_TYPES + STORE_ONLY_TYPES
MODES = ("read", "store")


@dataclass
class ImportOutcome:
    label: str
    doc: Document | None = None
    figures_added: int = 0
    notes: list[ReviewNote] = field(default_factory=list)
    duplicate: bool = False
    error: str | None = None
    to_check: list[CheckItem] = field(default_factory=list)
    attachments: list["ImportOutcome"] = field(default_factory=list)  # an email's attachments, each read on its own


def _outcome(ws: Workspace, label: str, report: IngestReport) -> ImportOutcome:
    outcome = ImportOutcome(label=label, doc=report.doc, figures_added=report.figures_added, notes=report.notes,
                            duplicate=report.duplicate)
    if not report.duplicate:
        outcome.to_check = things_to_check(ws, report.doc.doc_id)
    outcome.attachments = [_outcome(ws, f"Attachment {n}", a) for n, a in report.attachments]
    return outcome


def _check(suffix: str, mode: str, folder: str | None, return_type: str, ws: Workspace) -> str | None:
    if return_type not in ENABLED_RETURN_TYPES:
        return "Company and trust returns are coming later. Only individual returns can be prepared for now."
    if mode not in MODES:
        return "Choose Read for the return or Store only."
    if suffix not in STORE_TYPES:
        return (f"Can't use {suffix or 'files without an extension'} files. "
                f"Supported: {', '.join(STORE_TYPES)}.")
    if mode == "read" and suffix not in READ_TYPES:
        return (f"Can't read {suffix} files for the return (only {', '.join(READ_TYPES)}). "
                "Choose Store only to keep it with the client's files.")
    if mode == "store" and folder not in folder_names(ws):
        return "Choose a folder to store it in."
    return None


def _store_only(path: Path, ws: Workspace, store: DocumentStore, folder: str, audit: AuditLog,
                outcome: ImportOutcome) -> ImportOutcome:
    report = store_document(path, ws, store, folder, audit)
    outcome.doc, outcome.notes, outcome.duplicate = report.doc, report.notes, report.duplicate
    return outcome


def import_file(ws: Workspace, store: DocumentStore, doc_types: dict[str, DocType], audit: AuditLog,
                upload: FileStorage, *, mode: str, folder: str | None, return_type: str, position: int,
                ai_reader=None) -> ImportOutcome:
    outcome = ImportOutcome(label=f"File {position}")
    suffix = Path(upload.filename or "").suffix.lower()
    outcome.error = _check(suffix, mode, folder, return_type, ws)
    if outcome.error:
        return outcome
    uploads = ws.work_dir / "_uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    path = uploads / f"{secrets.token_hex(8)}{suffix}"
    try:
        upload.save(path)
        if mode == "store":
            return _store_only(path, ws, store, folder, audit, outcome)
        extra = {"ai_reader": ai_reader} if ai_reader is not None else {}
        report = ingest_file(path, ws, store, doc_types, audit, **extra)
        return _outcome(ws, outcome.label, report)
    except (IngestError, SensitiveDataBlocked, FileLockedError, ValueError, OSError) as exc:
        outcome.error = problem_text(exc)
        return outcome
    finally:
        path.unlink(missing_ok=True)


def store_upload_in_cabinet(space, upload: FileStorage, *, folder: str, audit: AuditLog, position: int) -> ImportOutcome:
    """Permanent and Correspondence: always stored unchanged, never read for the return."""
    from ...cabinets import store_in_cabinet

    outcome = ImportOutcome(label=f"File {position}")
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in STORE_TYPES:
        outcome.error = f"Can't use {suffix or 'files without an extension'} files. Supported: {', '.join(STORE_TYPES)}."
        return outcome
    uploads = space.work_dir / "_uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    path = uploads / f"{secrets.token_hex(8)}{suffix}"
    try:
        upload.save(path)
        before = {d.doc_id for d in DocumentIndex(space.index_csv).load()}
        outcome.doc = store_in_cabinet(space, path, folder, audit)
        outcome.duplicate = outcome.doc.doc_id in before
        return outcome
    except (SensitiveDataBlocked, FileLockedError, ValueError, OSError) as exc:
        outcome.error = problem_text(exc)
        return outcome
    finally:
        path.unlink(missing_ok=True)
