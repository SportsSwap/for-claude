"""Knowledge: the firm's own templates, policies and procedures (TRA_HOME/Knowledge), like FYI's knowledge cabinet.

Not for client documents. Files keep a readable name (cleaned, checked by the output
guard), because these are firm documents people look for by name.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import date, datetime
from pathlib import Path

from ..filing.index import DocumentIndex
from ..models import Document
from ..privacy.audit import AuditLog
from ..privacy.guard import check_text
from .services.imports import STORE_TYPES

KNOWLEDGE_FOLDERS = ("Templates", "Policies", "Procedures", "Other")
_SAFE = re.compile(r"[^A-Za-z0-9 ._()&,'-]")


def knowledge_dir(tra_home: Path) -> Path:
    return Path(tra_home) / "Knowledge"


def _index(tra_home: Path) -> DocumentIndex:
    return DocumentIndex(knowledge_dir(tra_home) / "index.csv")


def knowledge_docs(tra_home: Path, folder: str | None = None) -> list[Document]:
    return [d for d in _index(tra_home).load() if folder is None or d.category == folder]


def knowledge_path(tra_home: Path, doc_id: str) -> Path | None:
    doc = next((d for d in knowledge_docs(tra_home) if d.doc_id == doc_id), None)
    if doc is None:
        return None
    path = Path(doc.filed_location).resolve()
    return path if path.is_file() and path.is_relative_to(knowledge_dir(tra_home).resolve()) else None


def _clean_name(name: str, existing: set[str]) -> str:
    raw = Path(name or "").name
    if raw != (name or "") or not raw:
        raise ValueError("Give the document a plain file name.")
    suffix = Path(raw).suffix.lower()
    if suffix not in STORE_TYPES:
        raise ValueError(f"Can't use {suffix or 'files without an extension'} files. Supported: {', '.join(STORE_TYPES)}.")
    stem = " ".join(_SAFE.sub(" ", Path(raw).stem).split())[:80] or "Document"
    candidate, n = f"{stem}{suffix}", 2
    while candidate in existing:
        candidate, n = f"{stem}_{n:02d}{suffix}", n + 1
    check_text(candidate, "knowledge file name")
    return candidate


def store_knowledge(tra_home: Path, source: Path, name: str, folder: str, by: str, audit: AuditLog) -> Document:
    if folder not in KNOWLEDGE_FOLDERS:
        raise ValueError("Choose a folder from the list.")
    index = _index(tra_home)
    filed = _clean_name(name, index.names())  # checked first, even for a file that's already here
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    duplicate = index.find_by_sha(sha256)
    if duplicate:
        return duplicate
    target = knowledge_dir(tra_home) / folder / filed
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    doc = Document(doc_id=index.next_doc_id(), doc_type="KNOWLEDGE", category=folder, filed_name=filed,
                   filed_location=str(target), doc_date=date.today(), date_detected=False, pages=0, sha256=sha256,
                   ingested_at=datetime.now().astimezone(), redaction_counts={}, parse_status="stored", store="local")
    try:
        index.append(doc)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    audit.record("knowledge_added", doc_id=doc.doc_id, folder=folder, by=by)
    return doc
