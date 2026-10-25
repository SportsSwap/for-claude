"""Deleting documents: Deleted items, Restore and Delete forever.

A deleted document goes to Deleted items with everything that came from it: the file moves to a
hidden _Deleted folder, and its figures, pre-fill and CGT lines and its manual-entry notes come out
of the return. Restore puts it all back as it was. Delete forever removes the file, its older
versions, description, star and comments for good. Its document number is never handed out again.

Deleted items are listed in deleted.json beside the cabinet's index.csv. Only documents filed on this
laptop can be deleted here; FYI documents are deleted in FYI.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .figures import CGT_COLUMNS, FIGURE_COLUMNS, put_back_rows, take_rows
from .filing.index import DELETED_JSON, DocumentIndex, from_dict, to_dict
from .ingest.pipeline import restore_on_error
from .models import Document
from .privacy.audit import AuditLog
from .privacy.guard import atomic_write_text, check_value

TRASH_DIR = "_Deleted"
_LOCKED = "Close the document first (it's open in another program), then try again."


@dataclass(frozen=True)
class DeletedItem:
    doc: Document
    deleted_at: str
    by: str
    figures: int


def _path(space) -> Path:
    return space.index_csv.with_name(DELETED_JSON)


def _load(space) -> dict:
    path = _path(space)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {"items": data.get("items", []), "retired": data.get("retired", [])}


def _save(space, data: dict) -> None:
    check_value(data, DELETED_JSON)
    atomic_write_text(_path(space), json.dumps(data, indent=2), DELETED_JSON, prechecked=True)


def _item(data: dict, doc_id: str) -> dict | None:
    return next((i for i in data["items"] if i["doc"]["doc_id"] == doc_id), None)


def _doc_key(space, doc_id: str) -> str:
    return f"{space.client_code}/{getattr(space, 'code', None) or space.income_year}/{doc_id}"


def _work_files(space) -> list[Path]:
    """The return's files a document can have lines in (a Permanent or Correspondence cabinet has none)."""
    return [getattr(space, a) for a in ("figures_csv", "cgt_csv", "prefill_json", "ingest_notes_json") if hasattr(space, a)]


def _inside(space, path: Path) -> bool:
    return path.resolve().is_relative_to(space.clients_dir.resolve())


def _take_json(path: Path | None, belongs) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    taken = [d for d in data if belongs(d)]
    if taken:
        kept = [d for d in data if not belongs(d)]
        check_value(kept, path.name)
        atomic_write_text(path, json.dumps(kept, indent=2), path.name, prechecked=True)
    return taken


def _put_json(path: Path | None, rows: list[dict]) -> None:
    if path is None or not rows:
        return
    data = (json.loads(path.read_text(encoding="utf-8")) if path.exists() else []) + rows
    check_value(data, path.name)
    atomic_write_text(path, json.dumps(data, indent=2), path.name, prechecked=True)


def _move(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(source), str(target))
    except PermissionError:
        raise ValueError(_LOCKED) from None


def deleted_documents(space) -> list[DeletedItem]:
    """What's in Deleted items, most recently deleted first."""
    items = sorted(_load(space)["items"], key=lambda i: i["deleted_at"], reverse=True)
    return [DeletedItem(from_dict(i["doc"]), i["deleted_at"], i["by"], len(i["figures"])) for i in items]


def delete_document(space, doc_id: str, by: str, audit: AuditLog) -> int:
    """Move a document and everything that came from it to Deleted items. Returns how many figures came out."""
    from .web.services.files import document_path, find_document

    doc = find_document(space, doc_id)
    if doc is None:
        raise ValueError(f"There's no document {doc_id}.")
    if doc.store != "local":
        raise ValueError("Documents filed in FYI are deleted in FYI.")
    source = document_path(space, doc_id)  # None if the file is already gone
    trash = space.clients_dir / TRASH_DIR / f"{doc_id}_{doc.filed_name}"
    with restore_on_error(space.index_csv, _path(space), *_work_files(space)):
        figures = take_rows(space.figures_csv, FIGURE_COLUMNS, doc_id)
        cgt = take_rows(space.cgt_csv, CGT_COLUMNS, doc_id) if hasattr(space, "cgt_csv") else []
        prefill = _take_json(getattr(space, "prefill_json", None), lambda d: d.get("doc_id") == doc_id)
        notes = _take_json(getattr(space, "ingest_notes_json", None), lambda d: d.get("doc_ids") == [doc_id])
        data = _load(space)
        data["items"].append({"doc": to_dict(doc), "file": trash.relative_to(space.clients_dir).as_posix() if source else "",
                              "deleted_at": datetime.now().astimezone().isoformat(timespec="seconds"), "by": by,
                              "figures": figures, "cgt": cgt, "prefill": prefill, "notes": notes})
        _save(space, data)
        DocumentIndex(space.index_csv).remove(doc_id)
        if source:
            _move(source, trash)
    audit.record("document_deleted", client=space.client_code, doc_id=doc_id, figures=len(figures))
    return len(figures)


def restore_document(space, doc_id: str, by: str, audit: AuditLog) -> int:
    """Put a deleted document back where it was, with its figures. Returns how many figures came back."""
    data = _load(space)
    item = _item(data, doc_id)
    if item is None:
        raise ValueError(f"{doc_id} isn't in Deleted items.")
    doc = from_dict(item["doc"])
    index = DocumentIndex(space.index_csv)
    again = index.find_by_sha(doc.sha256)
    if again is not None:
        raise ValueError(f"The same file has been imported again since, as {again.doc_id}. "
                         f"Delete {again.doc_id} first if you want this one back.")
    target = Path(doc.filed_location)
    trash = space.clients_dir / item["file"] if item["file"] else None
    if trash is not None:
        if not (trash.is_file() and _inside(space, trash)):
            raise ValueError("The deleted file is no longer in Deleted items.")
        if not _inside(space, target):
            raise ValueError("That document was filed outside this client's folder, so it can't be put back here.")
        if target.exists():
            raise ValueError(f"There's already a file called {doc.filed_name} in {doc.category}.")
    with restore_on_error(space.index_csv, _path(space), *_work_files(space)):
        put_back_rows(space.figures_csv, FIGURE_COLUMNS, item["figures"], "figure_id", "F")
        if hasattr(space, "cgt_csv"):
            put_back_rows(space.cgt_csv, CGT_COLUMNS, item["cgt"], "event_id", "C")
        _put_json(getattr(space, "prefill_json", None), item["prefill"])
        _put_json(getattr(space, "ingest_notes_json", None), item["notes"])
        index.append(doc)
        data["items"].remove(item)
        _save(space, data)
        if trash is not None:
            _move(trash, target)
    audit.record("document_restored", client=space.client_code, doc_id=doc_id, figures=len(item["figures"]), by=by)
    return len(item["figures"])


def purge_document(space, doc_id: str, audit: AuditLog) -> None:
    """Delete a document in Deleted items for good, with its older versions, description, star and comments."""
    from .doc_notes import forget_doc_note
    from .reading_notes import forget_reading_notes
    from .versions import forget_versions
    from .web.comments import forget_comments
    from .web.stars import set_stars

    data = _load(space)
    item = _item(data, doc_id)
    if item is None:
        raise ValueError("Only documents in Deleted items can be deleted forever.")
    if item["file"]:
        trash = space.clients_dir / item["file"]
        if trash.is_file() and _inside(space, trash):
            try:
                trash.unlink()
            except PermissionError:
                raise ValueError(_LOCKED) from None
    data["items"].remove(item)
    data["retired"] = sorted(set(data["retired"]) | {doc_id})
    _save(space, data)
    forget_versions(space, doc_id)
    forget_doc_note(space, doc_id)
    forget_reading_notes(space, doc_id)
    key = _doc_key(space, doc_id)
    set_stars(space.tra_home, [key], False)
    forget_comments(space.tra_home, space.client_code, f"doc:{key}")
    audit.record("document_deleted_forever", client=space.client_code, doc_id=doc_id)
