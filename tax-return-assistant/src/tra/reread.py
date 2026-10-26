"""Read again: read a filed document with today's rules, for instance after Sawnx has learned its layout.

Figures from the document that someone confirmed, or typed in, are never touched. Unconfirmed figures the readers
added are replaced; unconfirmed AI or Claude figures only for the labels the rules now read. A new figure equal to
one that's kept isn't added again (each kept figure stands for one new one, so two equal amounts stay two); a new
figure for a label whose kept figure differs (the preparer corrected it) isn't added but noted as a doubt. Pre-fill
reports aren't read again, because their lines would double.
"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .checks import label_name
from .figures import append_figures, read_figures, write_figures
from .filing.index import DocumentIndex
from .ingest.classify import load_doc_types
from .ingest.emails import EMAIL_TYPES, EMBEDDED_SKIPPED, RTF_SKIPPED
from .ingest.layouts import load_layouts, match_layout
from .ingest.pipeline import read_document, restore_on_error
from .ingest.readers import load
from .labels import load_labels
from .money import format_dollars
from .privacy.audit import AuditLog
from .privacy.guard import FileLockedError, atomic_write_text, check_value
from .reading_notes import load_reading_notes, save_reading_notes
from .rental import is_rental, suggest_share

# How the readers (and the learned layouts' required fields) begin a doubt about an amount they expected but didn't
# find. A document with one is waiting for a layout. Keep the readers' wording and this in step. ("Looks misread"
# doubts aren't waiting: they need a person, not a layout.)
MISSING_PREFIX = "Didn't find"

# An email's doubts that the import added about its attachments, not its reader: kept when it's read again.
EMAIL_DOUBTS = ("Attachment ", EMBEDDED_SKIPPED, RTF_SKIPPED, "Only the first")

RENAME_NOTE = ("It keeps its old name: Windows wouldn't rename it, usually because it's open in another program. "
               "Close it and read it again to rename it.")


@dataclass(frozen=True)
class RereadResult:
    doc_id: str
    added: int
    removed: int
    status: str
    doc_type: str
    layout: str | None
    note: str = ""  # anything the person should know, e.g. the file couldn't be renamed


def _drop_manual_entry_note(ws, doc_id: str) -> None:
    path = ws.ingest_notes_json
    if not path.exists():
        return
    notes = json.loads(path.read_text(encoding="utf-8"))
    kept = [n for n in notes if not (n.get("check_id") == "I1" and n.get("doc_ids") == [doc_id])]
    if len(kept) != len(notes):
        check_value(kept, path.name)
        atomic_write_text(path, json.dumps(kept, indent=2), path.name, prechecked=True)


def reread_document(ws, doc_id: str, audit: AuditLog) -> RereadResult:
    """Read one filed document again. Raises ValueError with a plain message if it can't be."""
    from .web.services.files import document_path, find_document

    doc = find_document(ws, doc_id)
    if doc is None:
        raise ValueError(f"There's no document {doc_id}.")
    if doc.parse_status == "stored":
        raise ValueError(f"{doc_id} is stored only, not read for the return, so it can't be read again.")
    if doc.doc_type == "PREFILL":
        raise ValueError("Pre-fill reports aren't read again, because their lines would be counted twice. Delete it "
                         "and import it again instead.")
    path = document_path(ws, doc_id)
    if path is None:
        raise ValueError(f"{doc_id} isn't filed on this laptop (FYI?), so it can't be read again here.")
    try:
        loaded = load(path)
    except Exception:
        raise ValueError(f"{doc_id} couldn't be read (damaged, password-protected or not a real PDF).") from None
    doc_types = load_doc_types()
    layouts, _problems = load_layouts()
    learned = loaded.suffix not in EMAIL_TYPES and match_layout(loaded.redacted, layouts) is not None
    # A type someone set by hand is kept, unless a learned layout now recognises the document.
    keep_type = None if learned or doc.doc_type in ("OTHER", "CLIENTXLS", "EMAIL") else doc.doc_type
    doc_type, result, layout = read_document(loaded, doc_types, doc_id, keep_type)

    labels = load_labels()
    figures, errors = read_figures(ws.figures_csv, labels)
    if errors:
        raise ValueError("figures.csv has rows to fix first: " + "; ".join(errors))
    read_labels = {f.label_key for f in result.figures}

    def replaced(f) -> bool:
        return f.doc_id == doc_id and not f.confirmed and (f.method == "parser" or (f.method == "ai"
                                                                                       and f.label_key in read_labels))

    kept = [f for f in figures if not replaced(f)]
    new, differ = _new_figures([f for f in kept if f.doc_id == doc_id], result.figures, labels)
    entry = load_reading_notes(ws).get(doc_id, {})
    is_email = loaded.suffix in EMAIL_TYPES or doc.doc_type == "EMAIL"
    carried = [d for d in entry.get("doubts", []) if d.startswith(EMAIL_DOUBTS)] if is_email else []
    doubts = carried + [d for d in result.doubts if d not in carried] + differ
    with restore_on_error(ws.figures_csv, ws.reading_notes_json, ws.index_csv, ws.ingest_notes_json, ws.rental_json):
        share = result.facts.get("ownership_share")  # as on import: a suggestion, never over a person's share
        if share is not None and (doc_type == "RENTSTMT" or any(is_rental(f, labels) for f in result.figures)):
            doubts.append(suggest_share(ws, doc_id, share, audit))
        write_figures(ws.figures_csv, kept)
        added = append_figures(ws.figures_csv, new) if new else []
        save_reading_notes(ws, doc_id, doubts, entry.get("from_email"), layout=layout)
        DocumentIndex(ws.index_csv).update(dataclasses.replace(doc, doc_type=doc_type, parse_status=result.parse_status))
        if result.parse_status != "manual_needed":
            _drop_manual_entry_note(ws, doc_id)
    note = ""
    try:
        _rename(ws, doc_id, doc_type, result.figures or [f for f in kept if f.doc_id == doc_id], layout)
    except (OSError, FileLockedError):  # open in a PDF viewer (Windows won't rename it), or the index is in Excel
        note = RENAME_NOTE
    audit.record("document_reread", client=ws.client_code, doc_id=doc_id, added=len(added),
                 removed=len(figures) - len(kept), layout=layout, parse_status=result.parse_status,
                 renamed=not note)
    return RereadResult(doc_id, len(added), len(figures) - len(kept), result.parse_status, doc_type, layout, note)


def _new_figures(kept, found, labels) -> tuple[list, list[str]]:
    """(figures to add, doubts) from what the new read found, given the document's kept figures.

    Each kept figure stands for one found figure with the same label and amount, so two equal amounts stay two.
    A found figure for a label whose confirmed or typed-in figure the read doesn't match (the preparer probably
    corrected it) isn't added, because it would be counted twice; it becomes a doubt instead."""
    have = Counter((f.label_key, f.amount) for f in kept)
    unmatched = have - Counter((f.label_key, f.amount) for f in found)
    held = {(f.label_key, f.amount) for f in kept if f.confirmed or f.method == "manual"}
    differs: dict[str, list] = {}
    for (label, amount), n in unmatched.items():
        if (label, amount) in held:
            differs.setdefault(label, []).extend([amount] * n)
    new, doubts = [], []
    for f in found:
        key = (f.label_key, f.amount)
        if have[key]:
            have[key] -= 1
        elif f.label_key in differs:
            doubts.append(f"Read again found {label_name(labels, f.label_key)} {format_dollars(f.amount)} but you "
                          f"already have {', '.join(format_dollars(a) for a in differs[f.label_key])} from this "
                          "document; check which is right.")
        else:
            new.append(f)
    return new, doubts


def _rename(ws, doc_id: str, doc_type: str, figures, layout: str | None = None) -> None:
    """Give the document the readable name its new reading supports (same folder). Skipped if that name is taken."""
    from .filing.naming import filed_name
    from .ingest.pipeline import issuer_of
    from .web.client_names import load_names
    from .web.services.files import document_path, find_document

    doc, path = find_document(ws, doc_id), document_path(ws, doc_id)
    if doc is None or path is None:
        return
    index = DocumentIndex(ws.index_csv)
    name = filed_name(ws.client_code, ws.income_year, doc_type, doc.doc_date, path.suffix,
                      index.names() - {doc.filed_name}, issuer=issuer_of(figures, doc_type, layout),
                      client_name=load_names(ws.tra_home).get(ws.client_code))
    target = path.with_name(name)
    if name == doc.filed_name or target.exists():
        return
    path.rename(target)
    try:
        index.update(dataclasses.replace(doc, filed_name=name, filed_location=str(target)))
    except BaseException:
        target.rename(path)
        raise


def waiting_documents(ws) -> list:
    """What a teaching session works on: documents the readers couldn't read, or read only partly because an
    amount they expected wasn't found. (Receipts, emails and client lists are 'partial' because their labels are
    suggestions; that alone isn't waiting.)"""
    notes = load_reading_notes(ws)

    def missing(doc_id: str) -> bool:
        return any(d.startswith(MISSING_PREFIX) for d in notes.get(doc_id, {}).get("doubts", []))

    return [d for d in DocumentIndex(ws.index_csv).load() if d.store == "local" and d.doc_type != "PREFILL"
            and (d.parse_status == "manual_needed" or (d.parse_status == "partial" and missing(d.doc_id)))]


def reread_waiting(ws, audit: AuditLog) -> list[RereadResult]:
    return [reread_document(ws, d.doc_id, audit) for d in waiting_documents(ws)]


def workspaces(tra_home, code: str | None = None) -> list:
    """Every client's (or one client's) income-year workspaces."""
    from .workspace import Workspace

    out = []
    for state in sorted((Path(tra_home) / "Work").glob("*/FY*/state.json")):
        client, year = state.parent.parent.name, state.parent.name[2:]
        if year.isdigit() and (code is None or client == code):
            out.append(Workspace(tra_home, client, int(year)))
    return out


def _readable_notes(ws) -> bool:
    """False if the workspace's reading_notes.json is damaged (hand-edited, half-copied), so a list across every
    client skips that one rather than failing for all of them."""
    try:
        notes = load_reading_notes(ws)
    except (OSError, ValueError):
        return False
    return isinstance(notes, dict) and all(isinstance(entry, dict) for entry in notes.values())


def all_waiting(tra_home, code: str | None = None) -> list[tuple]:
    """(workspace, document) for every waiting document, for every client (or one) and year."""
    return [(ws, d) for ws in workspaces(tra_home, code) if _readable_notes(ws) for d in waiting_documents(ws)]


def layout_counts(tra_home) -> dict[str, int]:
    """How many filed documents each learned layout has read."""
    counts: dict[str, int] = {}
    for ws in workspaces(tra_home):
        if not _readable_notes(ws):
            continue
        for entry in load_reading_notes(ws).values():
            if entry.get("layout"):
                counts[entry["layout"]] = counts.get(entry["layout"], 0) + 1
    return counts
