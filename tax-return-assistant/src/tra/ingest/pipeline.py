"""Stages 1 and 2 for one file: read → redact → classify → extract → file → record.

Nothing about the original file except its bytes (copied unchanged into the
store) and its SHA-256 survives. The original filename is never recorded.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
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
from ..reading_notes import load_reading_notes, save_reading_notes
from ..workspace import Workspace
from .classify import DocType, classify
from .emails import EMAIL_TYPES, EmailLibraryMissing, read_email
from .extractors import ExtractResult, get_extractor
from .extractors.ai_reader import NOT_AI_TYPES
from .layouts import load_layouts, match_layout, read_with_layout
from .page_images import MAX_PAGE_IMAGES, pages_wanted, render_pages
from .readers import SUPPORTED, UnsupportedFile, load

# Areas the tool does not prepare. A mention in any document raises a High note (feeds spec check S12).
UNHANDLED_PHRASES = ("employee share scheme", "foreign income", "foreign tax", "personal services income",
                     "trust distribution", "partnership distribution", "distribution statement",
                     "medicare entitlement statement", "medicare levy exemption")


SHEET_TYPES = (".xlsx", ".csv")
STORE_ONLY_TYPES = (".docx", ".jpg", ".jpeg", ".png")  # kept with the client's files, never read
_PLAIN_SUFFIX = re.compile(r"[.][a-z][a-z0-9]{0,7}")  # .pdf, .xlsx: never digits that could be an identifier
EMAIL_DEPTH = 1  # an email attached to an email is read; an email inside that one is only stored


class IngestError(Exception):
    pass


@dataclass
class IngestReport:
    doc: Document | None
    figures_added: int
    notes: list[ReviewNote]
    duplicate: bool
    attachments: list[tuple[int, "IngestReport"]] = field(default_factory=list)  # (attachment number, report)


def file_document(source: Path, ws: Workspace, store: DocumentStore, *, doc_type: str, category: str,
                  doc_date: date | None, sha256: str, pages: int, redaction_counts: dict, parse_status: str,
                  audit: AuditLog, doc_id: str | None = None,
                  issuer: str | None = None) -> tuple[Document, list[ReviewNote]]:
    """File the original under the naming convention (filing/naming.py) and add it to the index."""
    from ..web.client_names import load_names

    index = DocumentIndex(ws.index_csv)
    doc_id = doc_id or index.next_doc_id()
    notes: list[ReviewNote] = []
    if doc_date is None:
        notes.append(ReviewNote("Low", "I2", "Document date not detected; the ingest date was used in the filename.",
                                None, "preparer", "confirm", doc_ids=(doc_id,)))
    when = doc_date or date.today()
    name = filed_name(ws.client_code, ws.income_year, doc_type, when, source.suffix, index.names(), issuer=issuer,
                      client_name=load_names(ws.tra_home).get(ws.client_code))
    ref = store.file(source, FilingRequest(ws.client_code, ws.income_year, category, name, doc_type, when))
    if ref.fell_back:
        notes.append(ReviewNote("Medium", "I3", f"{name} was filed locally because FYI was unavailable. "
                                "Run `tra fyi push` to file it in FYI.", None, "preparer", "confirm",
                                doc_ids=(doc_id,)))
    doc = Document(doc_id=doc_id, doc_type=doc_type, category=category, filed_name=name,
                   filed_location=ref.location, doc_date=when, date_detected=doc_date is not None, pages=pages,
                   sha256=sha256, ingested_at=datetime.now().astimezone(), redaction_counts=dict(redaction_counts),
                   parse_status=parse_status, store=ref.store)
    try:
        index.append(doc)  # the commit point: once indexed, a re-run treats the file as done
    except BaseException:
        if ref.store == "local":
            Path(ref.location).unlink(missing_ok=True)
        raise
    return doc, notes


@contextmanager
def restore_on_error(*paths: Path):
    """If anything fails, put these files back as they were, so a re-run starts clean."""
    saved = {p: p.read_bytes() if p.exists() else None for p in paths}
    try:
        yield
    except BaseException:
        for path, data in saved.items():
            try:
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(data)
            except OSError:
                pass
        raise


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_unreadable(path: Path, ws: Workspace, store: DocumentStore, doc_types: dict[str, DocType],
                     audit: AuditLog, from_email: str | None = None) -> IngestReport:
    """File a document whose text can't be read, so it isn't lost, and ask for manual entry."""
    sha256 = _sha256(path)
    index = DocumentIndex(ws.index_csv)
    duplicate = index.find_by_sha(sha256)
    if duplicate:
        audit.record("duplicate_skipped", client=ws.client_code, doc_id=duplicate.doc_id)
        return IngestReport(duplicate, 0, [], True)
    doc_id = index.next_doc_id()
    with restore_on_error(ws.reading_notes_json):
        if from_email:
            save_reading_notes(ws, doc_id, [], from_email)
        doc, notes = file_document(path, ws, store, doc_type="OTHER", category=doc_types["OTHER"].category,
                                   doc_date=None, sha256=sha256, pages=0, redaction_counts={},
                                   parse_status="manual_needed", audit=audit, doc_id=doc_id)
    notes.append(ReviewNote("Medium", "I1", f"{doc.filed_name} could not be read (damaged, password-protected or "
                            "not a real PDF). Open it, set its document type if needed, and enter its figures in "
                            f"figures.csv with doc_id {doc.doc_id}.", None, "preparer", "confirm",
                            doc_ids=(doc.doc_id,)))
    append_notes(ws.ingest_notes_json, notes)
    audit.record("document_ingested", client=ws.client_code, doc_id=doc.doc_id, doc_type="OTHER",
                 filed_name=doc.filed_name, redaction_counts={}, parse_status="manual_needed", figures=0,
                 store=doc.store)
    return IngestReport(doc, 0, notes, False)


def store_document(path: Path, ws: Workspace, store: DocumentStore, folder: str, audit: AuditLog, *,
                   from_email: str | None = None) -> IngestReport:
    """File a document unchanged, without reading it (Store only, and Word files or photos attached to an email)."""
    sha256 = _sha256(path)
    index = DocumentIndex(ws.index_csv)
    duplicate = index.find_by_sha(sha256)
    if duplicate:
        return IngestReport(duplicate, 0, [], True)
    doc_id = index.next_doc_id()
    with restore_on_error(ws.reading_notes_json):
        if from_email:
            save_reading_notes(ws, doc_id, [], from_email)
        doc, notes = file_document(path, ws, store, doc_type="OTHER", category=folder, doc_date=None, sha256=sha256,
                                   pages=0, redaction_counts={}, parse_status="stored", audit=audit, doc_id=doc_id)
    audit.record("document_stored", client=ws.client_code, doc_id=doc.doc_id, filed_name=doc.filed_name,
                 folder=folder, store=doc.store)
    return IngestReport(doc, 0, [n for n in notes if n.check_id != "I2"], False)


def _ingest_attachments(path: Path, ws: Workspace, store: DocumentStore, doc_types: dict[str, DocType],
                        audit: AuditLog, email_id: str, depth: int, ai_reader) -> list[tuple[int, IngestReport]]:
    """File and read each attachment as a document of its own, then note on the email what couldn't be used.

    Each is saved under a random name in the work folder and always deleted; its own name is never kept.
    One attachment failing doesn't undo the email or the others."""
    content = read_email(path)
    doubts, reports = list(content.skipped), []
    uploads = ws.work_dir / "_uploads"
    try:
        for n, attachment in enumerate(content.attachments, start=1):
            suffix = attachment.suffix
            # The type comes from the attachment's own name, so show it only if it's plainly a file type.
            kind = suffix if _PLAIN_SUFFIX.fullmatch(suffix) else "an unknown file type"
            nested_email = suffix in EMAIL_TYPES and depth >= EMAIL_DEPTH
            if suffix not in SUPPORTED + STORE_ONLY_TYPES:
                doubts.append(f"Attachment {n} ({kind}) wasn't filed: Sawnx can't use that kind of file. Save it from "
                              "the email and look at it.")
                continue
            uploads.mkdir(parents=True, exist_ok=True)
            temp = uploads / f"{secrets.token_hex(8)}{suffix}"
            try:
                temp.write_bytes(attachment.data)
                if suffix in STORE_ONLY_TYPES or nested_email:
                    report = store_document(temp, ws, store, "Other", audit, from_email=email_id)
                else:
                    report = ingest_file(temp, ws, store, doc_types, audit, ai_reader=ai_reader, from_email=email_id,
                                         _depth=depth + 1)
                reports.append((n, report))
            except Exception:  # whatever went wrong, the email and the other attachments are still filed
                doubts.append(f"Attachment {n} ({kind}) couldn't be filed. Save it from the email and import it on "
                              "its own.")
            finally:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:  # held by antivirus for a moment: left in _uploads rather than stopping the import
                    pass
    finally:
        if doubts:
            entry = load_reading_notes(ws).get(email_id, {})
            save_reading_notes(ws, email_id, entry.get("doubts", []) + doubts, entry.get("from_email"))
    return reports


# Readers whose issuer is a labelled line ("Payer:"), a company line or a receipt's shop. The bank statement reader
# takes the statement's first line, which is often the account holder, so that never names a file.
_ISSUER_TYPES = frozenset({"INCSTMT", "DIVSTMT", "RECEIPT"})
_NOT_ISSUERS = ("email", "ai", "claude", "employer", "company")  # readers' own words, not who issued it
_NEVER_LAYOUTS = ("PREFILL", "PRIOR")  # the ATO's reports keep their own readers
_AI_KEEPS_TYPE = ("EMAIL", "CLIENTXLS", *_NEVER_LAYOUTS)  # types the AI reader's own guess never replaces


def issuer_of(figures, doc_type: str, layout: str | None = None) -> str | None:
    """Who issued a document, from its figures' descriptions ("SAMPLE BANK – interest"), for its file name.

    Only from a learned layout (``layout`` is its name, from read_document) or a reader in _ISSUER_TYPES."""
    from ..doc_summary import _issuer
    from ..filing.naming import kind_name

    if layout is None and doc_type not in _ISSUER_TYPES:
        return None
    figures = [f for f in figures if f.method != "ai"]  # the AI reader's words are a model's, never a file's name
    who = _issuer(figures) if figures else None
    if who and who.lower() in (kind_name(doc_type).lower(), *_NOT_ISSUERS) or (who or "").startswith("Sheet "):
        return None
    return who


def _page_images(loaded, ai_reader, source: Path | None) -> tuple[list[tuple[int, bytes]], list[int]]:
    """Pictures of a PDF's scanned or garbled pages, only when Settings allows the AI reader to send them, and the
    pages that wanted one but won't get one (past MAX_PAGE_IMAGES or the size budget, or a page that won't draw)."""
    if not getattr(ai_reader, "page_images", False) or loaded.suffix != ".pdf" or source is None:
        return [], []
    wanted = pages_wanted(loaded.redacted.pages, loaded.image_only_pages)
    try:
        images = render_pages(source, wanted[:MAX_PAGE_IMAGES]) if wanted else []
    except Exception:  # a page pdfium can't draw (RuntimeError) never stops the import: the text is still read
        images = []
    drawn = {page for page, _jpeg in images}
    return images, [n for n in wanted if n not in drawn]


def read_document(loaded, doc_types: dict[str, DocType], doc_id: str, override_type: str | None = None,
                  ai_reader=None, *, source: Path | None = None,
                  on_images_sent=None) -> tuple[str, ExtractResult, str | None]:
    """Work out what a loaded document is and read its figures: (doc type, result, the layout's name if one read it).

    A learned layout (config/layouts) comes before the general readers, except for emails, spreadsheets (the
    client-spreadsheet reader) and the ATO's pre-fill reports and prior-year returns. Shared by the import and
    Read again, so both read a document the same way. ``source`` is the original PDF, for page images (off unless
    Settings allows them); ``on_images_sent`` gets their page numbers just before they're sent."""
    doc_type = override_type or classify(loaded.redacted, doc_types)
    layout = None
    if not override_type and loaded.suffix not in EMAIL_TYPES + SHEET_TYPES and doc_type not in _NEVER_LAYOUTS:
        layouts, _problems = load_layouts()  # a file with a mistake is skipped (the Layouts page lists it)
        layout = match_layout(loaded.redacted, layouts)
    if layout is not None:
        doc_type, result = layout.doc_type, read_with_layout(loaded.redacted, layout, doc_id)
    else:
        if not override_type and loaded.suffix in EMAIL_TYPES:
            doc_type = "EMAIL"  # never keyword-classified: a client's email can mention anything
        if not override_type and loaded.suffix in SHEET_TYPES and doc_type in ("OTHER", "RECEIPT"):
            doc_type = "CLIENTXLS"  # a client's own list; Xero exports and other known types keep their readers
        extractor = get_extractor(doc_type)
        result = extractor.extract(loaded.redacted, doc_id) if extractor else ExtractResult()
    # The AI reader isn't asked when the built-in reader found nothing to read (an email that's just a covering note).
    # A document that is all scans is asked about only when its pages can be sent as pictures.
    wanted = ai_reader is not None and not result.figures and result.parse_status != "parsed"
    images, unsent = _page_images(loaded, ai_reader, source) if wanted else ([], [])
    if wanted and (images or len(loaded.image_only_pages) < loaded.page_count):
        read = (ai_reader.extract(loaded.redacted, doc_id, images, on_send=on_images_sent) if images
                else ai_reader.extract(loaded.redacted, doc_id))
        result.figures, result.parse_status, result.notes = read.figures, read.parse_status, result.notes + read.notes
        result.doubts = list(result.doubts) + list(read.doubts)
        if read.facts.get("ai_picture_pages"):
            result.facts["ai_picture_pages"] = read.facts["ai_picture_pages"]
        ai_type = read.facts.get("ai_doc_type")
        if (ai_type in doc_types and ai_type not in NOT_AI_TYPES and ai_type != doc_type and not override_type
                and layout is None and doc_type not in _AI_KEEPS_TYPE):
            # The built-in reader's doubts are kept: they may still matter under the new type.
            result.doubts.append(f"Type set by the AI reader: {doc_types[ai_type].description} (Sawnx guessed "
                                 f"{doc_types[doc_type].description}). Change it on the document if that's wrong.")
            doc_type = ai_type
    if unsent:
        result.doubts = list(result.doubts) + [f"Page(s) {', '.join(map(str, unsent))} weren't sent as pictures "
                                               "(too many, or too large). Enter their figures by hand."]
    if loaded.image_only_pages and not result.figures:
        result.parse_status = "manual_needed"
    return doc_type, result, layout.slug if layout is not None else None


def ingest_file(path: Path, ws: Workspace, store: DocumentStore, doc_types: dict[str, DocType], audit: AuditLog,
                override_type: str | None = None, ai_reader=None, *, from_email: str | None = None,
                _depth: int = 0) -> IngestReport:
    """``ai_reader`` (off unless Sawnx's setting is on) reads redacted text the built-in readers found nothing in,
    and pictures of a PDF's scanned pages if that separate setting is on (audited as ai_page_images_sent).
    An email's attachments are filed and read too; ``from_email`` is the email an attachment came in."""
    try:
        loaded = load(path)
    except RedactionError:
        audit.record("redaction_failed", client=ws.client_code, sha256=_sha256(path))
        raise IngestError("redaction failed; document not processed") from None
    except (UnsupportedFile, EmailLibraryMissing) as exc:
        raise IngestError(str(exc)) from None
    except Exception:  # damaged, password-protected, or not really the file type its name says
        return _file_unreadable(path, ws, store, doc_types, audit, from_email)

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
    doc_id = index.next_doc_id()
    def images_sent(pages: list[int]) -> None:  # page numbers only: what the pictures show is never recorded
        # The file's sha256 (not identifying) says which file it was, even if its doc id is used again later.
        audit.record("ai_page_images_sent", client=ws.client_code, doc_id=doc_id, sha256=loaded.sha256, pages=pages)

    doc_type, result, layout = read_document(loaded, doc_types, doc_id, override_type, ai_reader, source=path,
                                             on_images_sent=images_sent)

    # Figures first, the index row last: if any step fails, everything is rolled back and
    # the file is not marked as ingested, so running the command again does the whole job.
    with restore_on_error(ws.figures_csv, ws.prefill_json, ws.reading_notes_json):
        added = append_figures(ws.figures_csv, result.figures) if result.figures else []
        if result.prefill:
            append_prefill(ws.prefill_json, result.prefill)
        if result.doubts or from_email or layout:
            save_reading_notes(ws, doc_id, result.doubts, from_email, layout=layout)
        doc, notes = file_document(
            path, ws, store, doc_type=doc_type, category=doc_types[doc_type].category,
            doc_date=result.doc_date or find_doc_date(loaded.redacted.text), sha256=loaded.sha256,
            pages=loaded.page_count, redaction_counts=dict(loaded.redacted.counts),
            parse_status=result.parse_status, audit=audit, doc_id=doc_id,
            issuer=issuer_of(result.figures, doc_type, layout))
    notes = list(result.notes) + notes

    if result.parse_status == "manual_needed" or loaded.image_only_pages:
        # Scanned pages the AI reader read as pictures (and found figures in) are checked, not typed in.
        read_as_pictures = set(result.facts.get("ai_picture_pages", ())) if result.figures else set()
        pictured = [n for n in loaded.image_only_pages if n in read_as_pictures]
        scanned = [n for n in loaded.image_only_pages if n not in read_as_pictures]
        sent = (f" Page(s) {', '.join(map(str, pictured))} had no text and were sent to the AI reader as pictures; "
                "check its figures against the document." if pictured else "")
        detail = f" Page(s) {', '.join(map(str, scanned))} have no text (scanned?)." if scanned else ""
        if result.parse_status == "manual_needed" or scanned:
            message = (f"Manual entry needed for {doc.filed_name} ({doc_type}).{sent}{detail} "
                       f"Add its figures to figures.csv with doc_id {doc_id}.")
        else:
            message = f"Check {doc.filed_name} ({doc_type}).{sent}"
        notes.append(ReviewNote("Medium", "I1", message, None, "preparer", "confirm", doc_ids=(doc_id,)))
    cover_days = result.facts.get("hospital_cover_days")
    if cover_days is not None:
        state = ws.load_state()
        if state.hospital_cover_days is None:
            state.hospital_cover_days = cover_days
            ws.save_state(state)
            notes.append(ReviewNote("Low", "I7", f"Private hospital cover days ({cover_days}) taken from "
                                    f"{doc.filed_name}. Check them; they drive the Medicare levy surcharge.", None,
                                    "preparer", "confirm", doc_ids=(doc_id,)))
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
    report = IngestReport(doc, len(added), notes, False)
    if loaded.suffix in EMAIL_TYPES:
        report.attachments = _ingest_attachments(path, ws, store, doc_types, audit, doc_id, _depth, ai_reader)
    return report
