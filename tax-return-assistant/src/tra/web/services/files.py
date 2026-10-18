"""A client's folders and filed documents. Documents are always found by doc_id through index.csv."""

from __future__ import annotations

import dataclasses
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ...filing.index import DocumentIndex
from ...ingest.classify import CATEGORIES
from ...models import Document
from ...privacy.audit import AuditLog
from ...privacy.guard import check_text
from ...workspace import Workspace

FOLDER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{0,39}$")


@dataclass(frozen=True)
class Folder:
    name: str
    count: int
    standard: bool


def documents(ws: Workspace, folder: str | None = None) -> list[Document]:
    docs = DocumentIndex(ws.index_csv).load()
    return [d for d in docs if folder is None or d.category == folder]


def folders(ws: Workspace) -> list[Folder]:
    docs = documents(ws)
    standard = set(getattr(ws, "standard_folders", CATEGORIES))
    custom = {d.category for d in docs} - standard
    if ws.clients_dir.is_dir():
        custom |= {p.name for p in ws.clients_dir.iterdir()
                   if p.is_dir() and p.name not in standard and FOLDER_NAME.match(p.name)}
    standard = list(getattr(ws, "standard_folders", CATEGORIES))
    custom -= set(standard)
    names = standard + sorted(custom, key=str.lower)
    return [Folder(n, sum(d.category == n for d in docs), n in standard) for n in names]


def folder_names(ws: Workspace) -> list[str]:
    return [f.name for f in folders(ws)]


def add_folder(ws: Workspace, name: str, audit: AuditLog) -> None:
    name = (name or "").strip()
    if not FOLDER_NAME.match(name):
        raise ValueError("Folder names use letters, numbers, spaces and hyphens, up to 40 characters.")
    if name.lower() in {n.lower() for n in folder_names(ws)}:
        raise ValueError(f"There's already a folder called {name}.")
    check_text(name, "folder name")
    (ws.clients_dir / name).mkdir(parents=True, exist_ok=False)
    audit.record("folder_added", client=ws.client_code, income_year=ws.income_year, folder=name)


def find_document(ws: Workspace, doc_id: str) -> Document | None:
    return next((d for d in documents(ws) if d.doc_id == doc_id), None)


def document_path(ws: Workspace, doc_id: str) -> Path | None:
    """The filed original on this laptop, or None (unknown, filed in FYI, or outside the client's folder)."""
    doc = find_document(ws, doc_id)
    if doc is None or doc.store != "local":
        return None
    path = Path(doc.filed_location).resolve()
    if not path.is_file() or not path.is_relative_to(ws.clients_dir.resolve()):
        return None
    return path


def move_document(ws: Workspace, doc_id: str, folder: str, audit: AuditLog) -> Document:
    doc = find_document(ws, doc_id)
    if doc is None:
        raise ValueError(f"There's no document {doc_id}.")
    if folder not in folder_names(ws):
        raise ValueError("Choose a folder from the list.")
    source = document_path(ws, doc_id)
    if source is None:
        raise ValueError("Only documents filed on this laptop can be moved here. Move FYI documents in FYI.")
    if folder == doc.category:
        return doc
    target = ws.clients_dir / folder / doc.filed_name
    if target.exists():
        raise ValueError(f"{folder} already has a file called {doc.filed_name}.")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    moved = dataclasses.replace(doc, category=folder, filed_location=str(target))
    try:
        DocumentIndex(ws.index_csv).update(moved)
    except BaseException:
        shutil.move(str(target), str(source))
        raise
    audit.record("document_moved", client=ws.client_code, doc_id=doc_id, from_folder=doc.category, to_folder=folder)
    return moved
