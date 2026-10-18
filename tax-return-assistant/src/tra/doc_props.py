"""Editing a document's properties: type, folder, document date and status."""

from __future__ import annotations

import dataclasses
from datetime import date

from .doc_notes import STATUSES, set_doc_status
from .filing.index import DocumentIndex
from .ingest.classify import load_doc_types
from .models import Document
from .privacy.audit import AuditLog

__all__ = ["STATUSES", "set_properties"]


def set_properties(space, doc_id: str, *, doc_type: str, folder: str, doc_date: date | None, status: str, by: str,
                   audit: AuditLog) -> tuple[Document, list[str]]:
    """Returns the updated index entry and any warnings for the preparer. The filed name doesn't change."""
    from .web.services.files import find_document, move_document

    doc = find_document(space, doc_id)
    if doc is None:
        raise ValueError(f"There's no document {doc_id}.")
    if doc_type not in load_doc_types():
        raise ValueError("Choose a type from the list.")
    if status not in STATUSES:
        raise ValueError("Choose a status from the list.")
    warnings, changed = [], []
    if folder != doc.category:
        doc = move_document(space, doc_id, folder, audit)
        changed.append("folder")
    updated = doc
    if doc_type != doc.doc_type:
        updated = dataclasses.replace(updated, doc_type=doc_type)
        changed.append("type")
        if doc.parse_status != "stored":
            warnings.append("Changing the type doesn't re-read this document's figures. Check them on the Figures tab.")
    if doc_date is not None and doc_date != doc.doc_date:
        updated = dataclasses.replace(updated, doc_date=doc_date, date_detected=True)
        changed.append("date")
    if updated is not doc:
        DocumentIndex(space.index_csv).update(updated)
    set_doc_status(space, doc_id, status, by)
    if changed:
        audit.record("document_properties_changed", client=space.client_code, doc_id=doc_id, fields=changed)
    return updated, warnings
