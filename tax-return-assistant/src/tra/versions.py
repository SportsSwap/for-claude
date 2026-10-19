"""Versions: a newer copy of a document replaces the current file; older copies are kept.

Older copies live beside the document in <folder>/_versions/<name>_v<n><ext>, listed in
versions.json in the work folder. The filed name and doc_id don't change.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from .filing.index import DocumentIndex
from .privacy.audit import AuditLog
from .privacy.guard import atomic_write_text, check_value

LOCATION = "versions.json"


def _path(space) -> Path:
    return space.work_dir / "versions.json"


def _load(space) -> dict[str, list[dict]]:
    path = _path(space)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def list_versions(space, doc_id: str) -> list[dict]:
    """Older copies, oldest first: {"n", "file" (relative to the cabinet or year folder), "sha256", "at", "by"}."""
    return _load(space).get(doc_id, [])


def version_path(space, doc_id: str, n: int) -> Path | None:
    entry = next((v for v in list_versions(space, doc_id) if v["n"] == n), None)
    if entry is None:
        return None
    path = (space.clients_dir / entry["file"]).resolve()
    return path if path.is_file() and path.is_relative_to(space.clients_dir.resolve()) else None


def forget_versions(space, doc_id: str) -> int:
    """Delete a document's older copies for good (when the document itself is deleted forever)."""
    data = _load(space)
    older = data.pop(doc_id, [])
    for entry in older:
        path = (space.clients_dir / entry["file"]).resolve()
        if path.is_file() and path.is_relative_to(space.clients_dir.resolve()):
            path.unlink()
    if older:
        check_value(data, LOCATION)
        atomic_write_text(_path(space), json.dumps(data, indent=2), LOCATION, prechecked=True)
    return len(older)


def add_version(space, doc_id: str, source: Path, by: str, audit: AuditLog) -> list[str]:
    """Make ``source`` the current copy of the document. Returns warnings for the preparer."""
    from .web.services.files import document_path, find_document

    doc = find_document(space, doc_id)
    current = document_path(space, doc_id)
    if doc is None or current is None:
        raise ValueError("Only documents filed on this laptop can have new versions here.")
    if source.suffix.lower() != current.suffix.lower():
        raise ValueError(f"Upload the same kind of file ({current.suffix.lower()}).")
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    index = DocumentIndex(space.index_csv)
    if sha256 == doc.sha256:
        raise ValueError("That's the same file as the current version.")
    other = index.find_by_sha(sha256)
    if other is not None:
        raise ValueError(f"That file is already filed as {other.doc_id}.")
    data = _load(space)
    older = data.get(doc_id, [])
    n = len(older) + 1
    keep = current.parent / "_versions" / f"{current.stem}_v{n}{current.suffix}"
    keep.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(current), str(keep))
    try:
        shutil.copy2(source, current)
        index.update(dataclasses.replace(doc, sha256=sha256))
    except BaseException:
        current.unlink(missing_ok=True)
        shutil.move(str(keep), str(current))
        raise
    older.append({"n": n, "file": keep.relative_to(space.clients_dir).as_posix(), "sha256": doc.sha256,
                  "at": datetime.now().astimezone().isoformat(timespec="seconds"), "by": by})
    data[doc_id] = older
    check_value(data, LOCATION)
    atomic_write_text(_path(space), json.dumps(data, indent=2), LOCATION, prechecked=True)
    audit.record("document_version_added", client=space.client_code, doc_id=doc_id, version=n + 1)
    if doc.parse_status != "stored":
        return ["The new version isn't re-read. Check this document's figures against it on the Figures tab."]
    return []
