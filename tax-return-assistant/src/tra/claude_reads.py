"""Claude reading documents in chat, for a firm without an API key (`tra ai-text`, `tra ai-add`).

The same deal as the AI reader: Claude only ever sees a document's blanked-out text, scanned again
first; it's only for documents the built-in readers couldn't read; and every figure it gives arrives
unconfirmed, method "ai", for a person to check (R6 flags them). The difference is that it runs when
someone asks Claude in a chat session, under that person's Claude account, instead of automatically.
Each step is in the audit log by document number.
"""

from __future__ import annotations

import dataclasses
import json

from .figures import append_figures, read_figures
from .filing.index import DocumentIndex
from .ingest.extractors.ai_reader import figures_from_items
from .ingest.readers import load
from .labels import figure_allowed, load_labels
from .models import Document, Figure
from .privacy.audit import AuditLog
from .privacy.detectors import find_sensitive
from .privacy.guard import atomic_write_text, check_value
from .privacy.redact import RedactedText

LEFT_IN = ("An identifier was left in the blanked-out text, so it isn't shown. Enter this document's figures by "
           "hand and tell the privacy officer.")


def label_keys() -> list[str]:
    labels = load_labels()
    return [d.key for d in sorted(labels.values(), key=lambda d: d.order) if figure_allowed(d)]


def unread_documents(ws, doc_id: str | None = None) -> list[Document]:
    """Documents filed on this laptop whose figures the built-in readers couldn't read (or the one asked for)."""
    docs = [d for d in DocumentIndex(ws.index_csv).load() if d.store == "local" and d.parse_status != "stored"]
    if doc_id:
        found = [d for d in docs if d.doc_id == doc_id]
        if not found:
            raise ValueError(f"There's no document {doc_id} that can be read.")
        return found
    return [d for d in docs if d.parse_status == "manual_needed"]


def document_text(ws, doc: Document, audit: AuditLog) -> RedactedText:
    """The document's blanked-out text, scanned again. Raises ValueError rather than show anything doubtful."""
    from .web.services.files import document_path

    path = document_path(ws, doc.doc_id)
    if path is None:
        raise ValueError("The filed file isn't on this laptop.")
    rt = load(path).redacted
    if not rt.text.strip():
        raise ValueError("It has no text (a scan?), so enter its figures by hand.")
    if find_sensitive(rt.text):
        audit.record("claude_read_refused", client=ws.client_code, doc_id=doc.doc_id, reason="identifier left in text")
        raise ValueError(LEFT_IN)
    audit.record("document_text_shown_to_claude", client=ws.client_code, doc_id=doc.doc_id)
    return rt


def add_claude_figures(ws, doc_id: str, answer: str, audit: AuditLog) -> list[Figure]:
    """Add the figures Claude read from one document, unconfirmed. The whole answer is refused if any part is wrong."""
    [doc] = unread_documents(ws, doc_id)
    try:
        data = json.loads(answer)
    except ValueError:
        raise ValueError("The answer isn't JSON: give {\"figures\": [{\"label_key\", \"description\", \"amount\", "
                         "\"page\"}, ...]}.") from None
    items = data.get("figures") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise ValueError("The answer has no figures.")
    existing, _errors = read_figures(ws.figures_csv, load_labels())
    if any(f.doc_id == doc_id and f.method == "ai" for f in existing):
        raise ValueError(f"Claude has already read {doc_id}. Delete those figures on the Figures tab first.")
    figures, problems = figures_from_items(items, label_keys(), doc_id, max(doc.pages, 1), "Claude")
    if problems:
        raise ValueError("Nothing was added: " + "; ".join(problems))
    added = append_figures(ws.figures_csv, figures)
    DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, parse_status="partial"))
    _drop_manual_entry_note(ws, doc_id)
    audit.record("claude_read_document", client=ws.client_code, doc_id=doc_id, figures=len(added))
    return added


def _drop_manual_entry_note(ws, doc_id: str) -> None:
    path = ws.ingest_notes_json
    if not path.exists():
        return
    notes = json.loads(path.read_text(encoding="utf-8"))
    kept = [n for n in notes if not (n.get("check_id") == "I1" and n.get("doc_ids") == [doc_id])]
    if len(kept) != len(notes):
        check_value(kept, path.name)
        atomic_write_text(path, json.dumps(kept, indent=2), path.name, prechecked=True)
