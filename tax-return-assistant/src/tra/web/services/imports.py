"""Import: each file is either read for the return (the normal ingest) or stored only.

The upload is saved under a random name inside the client's work folder, used,
and always deleted. Its original name is never written anywhere, and pages
call it "File 1", "File 2"...
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from werkzeug.datastructures import FileStorage

from ...filing.index import DocumentIndex
from ...filing.store import DocumentStore
from ...ingest.classify import DocType
from ...ingest.pipeline import IngestError, file_document, ingest_file
from ...models import Document, ReviewNote
from ...privacy.audit import AuditLog
from ...privacy.guard import FileLockedError, SensitiveDataBlocked
from ...workspace import Workspace
from ..messages import problem_text
from .files import folder_names

RETURN_TYPES = {"individual": "Individual", "company": "Company", "trust": "Trust"}
ENABLED_RETURN_TYPES = frozenset({"individual"})
READ_TYPES = (".pdf", ".csv", ".xlsx", ".json")
STORE_TYPES = READ_TYPES + (".docx", ".jpg", ".jpeg", ".png", ".eml", ".msg")
MODES = ("read", "store")


@dataclass
class ImportOutcome:
    label: str
    doc: Document | None = None
    figures_added: int = 0
    notes: list[ReviewNote] = field(default_factory=list)
    duplicate: bool = False
    error: str | None = None


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
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    duplicate = DocumentIndex(ws.index_csv).find_by_sha(sha256)
    if duplicate:
        outcome.doc, outcome.duplicate = duplicate, True
        return outcome
    doc, notes = file_document(path, ws, store, doc_type="OTHER", category=folder, doc_date=None, sha256=sha256,
                               pages=0, redaction_counts={}, parse_status="stored", audit=audit)
    audit.record("document_stored", client=ws.client_code, doc_id=doc.doc_id, filed_name=doc.filed_name,
                 folder=folder, store=doc.store)
    outcome.doc, outcome.notes = doc, [n for n in notes if n.check_id != "I2"]
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
        outcome.doc, outcome.figures_added = report.doc, report.figures_added
        outcome.notes, outcome.duplicate = report.notes, report.duplicate
        return outcome
    except (IngestError, SensitiveDataBlocked, FileLockedError, ValueError, OSError) as exc:
        outcome.error = problem_text(exc)
        return outcome
    finally:
        path.unlink(missing_ok=True)
