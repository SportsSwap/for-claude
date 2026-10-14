"""Stages 1 and 2 for one file: read → redact → classify → extract → file → record.

Nothing about the original file except its bytes (copied unchanged into the
store) and its SHA-256 survives. The original filename is never recorded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ..dates import find_doc_date
from ..figures import append_figures, append_prefill
from ..filing.index import DocumentIndex
from ..filing.naming import filed_name
from ..filing.store import DocumentStore, FilingRequest
from ..models import Document, ReviewNote
from ..notes_store import append_notes
from ..privacy.audit import AuditLog
from ..privacy.redact import RedactionError
from ..workspace import Workspace
from .classify import DocType, classify
from .extractors import ExtractResult, get_extractor
from .readers import UnsupportedFile, load

# Areas the tool does not prepare. A mention in any document raises a High note (feeds spec check S12).
UNHANDLED_PHRASES = ("employee share scheme", "foreign income", "foreign tax", "personal services income")


class IngestError(Exception):
    pass


@dataclass
class IngestReport:
    doc: Document | None
    figures_added: int
    notes: list[ReviewNote]
    duplicate: bool


def file_document(source: Path, ws: Workspace, store: DocumentStore, *, doc_type: str, category: str,
                  doc_date: date | None, sha256: str, pages: int, redaction_counts: dict, parse_status: str,
                  audit: AuditLog, doc_id: str | None = None) -> tuple[Document, list[ReviewNote]]:
    """File the original under the naming convention and add it to the index."""
    index = DocumentIndex(ws.index_csv)
    doc_id = doc_id or index.next_doc_id()
    notes: list[ReviewNote] = []
    if doc_date is None:
        notes.append(ReviewNote("Low", "I2", "Document date not detected; the ingest date was used in the filename.",
                                None, "preparer", "confirm", doc_ids=(doc_id,)))
    when = doc_date or date.today()
    name = filed_name(ws.client_code, ws.income_year, doc_type, when, source.suffix, index.names())
    ref = store.file(source, FilingRequest(ws.client_code, ws.income_year, category, name, doc_type, when))
    if ref.fell_back:
        notes.append(ReviewNote("Medium", "I3", f"{name} was filed locally because FYI was unavailable. "
                                "Run `tra fyi push` to file it in FYI.", None, "preparer", "confirm",
                                doc_ids=(doc_id,)))
    doc = Document(doc_id=doc_id, doc_type=doc_type, category=category, filed_name=name,
                   filed_location=ref.location, doc_date=when, date_detected=doc_date is not None, pages=pages,
                   sha256=sha256, ingested_at=datetime.now().astimezone(), redaction_counts=dict(redaction_counts),
                   parse_status=parse_status, store=ref.store)
    index.append(doc)
    return doc, notes


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_file(path: Path, ws: Workspace, store: DocumentStore, doc_types: dict[str, DocType], audit: AuditLog,
                override_type: str | None = None) -> IngestReport:
    try:
        loaded = load(path)
    except RedactionError:
        audit.record("redaction_failed", client=ws.client_code, sha256=_sha256(path))
        raise IngestError("redaction failed; document not processed") from None
    except UnsupportedFile as exc:
        raise IngestError(str(exc)) from None

    index = DocumentIndex(ws.index_csv)
    duplicate = index.find_by_sha(loaded.sha256)
    if duplicate:
        note = ReviewNote("Low", "I4", f"The same file was ingested again; it is already filed as {duplicate.doc_id}.",
                          None, "preparer", "confirm", doc_ids=(duplicate.doc_id,))
        append_notes(ws.ingest_notes_json, [note])
        audit.record("duplicate_skipped", client=ws.client_code, doc_id=duplicate.doc_id)
        return IngestReport(duplicate, 0, [note], True)

    if override_type and override_type not in doc_types:
        raise IngestError(f"unknown document type {override_type!r}; see config/doc_types.yaml")
    doc_type = override_type or classify(loaded.redacted, doc_types)
    doc_id = index.next_doc_id()
    extractor = get_extractor(doc_type)
    result = extractor.extract(loaded.redacted, doc_id) if extractor else ExtractResult()
    if loaded.image_only_pages and not result.figures:
        result.parse_status = "manual_needed"

    doc, notes = file_document(
        path, ws, store, doc_type=doc_type, category=doc_types[doc_type].category,
        doc_date=result.doc_date or find_doc_date(loaded.redacted.text), sha256=loaded.sha256,
        pages=loaded.page_count, redaction_counts=dict(loaded.redacted.counts), parse_status=result.parse_status,
        audit=audit, doc_id=doc_id)

    added = append_figures(ws.figures_csv, result.figures) if result.figures else []
    if result.prefill:
        append_prefill(ws.prefill_json, result.prefill)

    if result.parse_status == "manual_needed" or loaded.image_only_pages:
        detail = (f" Page(s) {', '.join(map(str, loaded.image_only_pages))} have no text (scanned?)."
                  if loaded.image_only_pages else "")
        notes.append(ReviewNote("Medium", "I1", f"Manual entry needed for {doc.filed_name} ({doc_type}).{detail} "
                                f"Add its figures to figures.csv with doc_id {doc_id}.", None, "preparer", "confirm",
                                doc_ids=(doc_id,)))
    text = loaded.redacted.text.lower()
    for phrase in UNHANDLED_PHRASES:
        if phrase in text:
            notes.append(ReviewNote("High", "I6", f"Area not handled by the tool: {phrase} (mentioned in {doc_id}). "
                                    "The reviewer needs to prepare this part manually.", None, "reviewer", "confirm",
                                    doc_ids=(doc_id,)))
    append_notes(ws.ingest_notes_json, notes)
    audit.record("document_ingested", client=ws.client_code, doc_id=doc_id, doc_type=doc_type,
                 filed_name=doc.filed_name, redaction_counts=dict(loaded.redacted.counts),
                 parse_status=result.parse_status, figures=len(added), store=doc.store)
    return IngestReport(doc, len(added), notes, False)
