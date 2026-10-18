"""The FYI-style document list: every filed document across clients, with sorting, filters and stars."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from werkzeug.exceptions import NotFound

from ...doc_notes import load_doc_notes
from ...doc_summary import summaries
from ...filing.index import DocumentIndex
from ...ingest.classify import load_doc_types
from ...models import Document
from ...settings import Settings
from ...workspace import Workspace
from ..client_names import load_names
from ..stars import KEY, load_stars
from .clients import workspace_for

_FY = re.compile(r"^FY(\d{4})$")
SORTS = {"name": "filed_name", "client": "client_sort", "year": "income_year", "folder": "folder",
         "changed": "last_change", "kind": "kind"}


@dataclass
class DocRow:
    code: str
    client: str
    income_year: int
    doc_id: str
    filed_name: str
    folder: str
    doc_type: str
    kind: str
    summary: str
    description: str
    last_change: datetime
    starred: bool
    store: str

    @property
    def key(self) -> str:
        return f"{self.code}/{self.income_year}/{self.doc_id}"

    @property
    def client_sort(self) -> str:
        return self.client.lower()

    @property
    def ext(self) -> str:
        return Path(self.filed_name).suffix.lower().lstrip(".")


def _workspaces(tra_home: Path) -> list[Workspace]:
    work = Path(tra_home) / "Work"
    out = []
    for state in sorted(work.glob("*/FY*/state.json")) if work.is_dir() else []:
        m = _FY.match(state.parent.name)
        if m:
            out.append(Workspace(tra_home, state.parent.parent.name, int(m.group(1))))
    return out


def _rows_for(ws: Workspace, names: dict[str, str], stars: set[str], doc_types) -> list[DocRow]:
    docs = DocumentIndex(ws.index_csv).load()
    if not docs:
        return []
    sums, notes = summaries(ws), load_doc_notes(ws)
    rows = []
    for d in docs:
        note = notes.get(d.doc_id, {})
        changed = d.ingested_at
        if note.get("at"):
            changed = max(changed, datetime.fromisoformat(note["at"]))
        kind = "Stored only" if d.parse_status == "stored" else (
            doc_types[d.doc_type].description if d.doc_type in doc_types else d.doc_type)
        key = f"{ws.client_code}/{ws.income_year}/{d.doc_id}"
        rows.append(DocRow(code=ws.client_code, client=names.get(ws.client_code, ws.client_code),
                           income_year=ws.income_year, doc_id=d.doc_id, filed_name=d.filed_name, folder=d.category,
                           doc_type=d.doc_type, kind=kind, summary=sums.get(d.doc_id, ""),
                           description=note.get("text", ""), last_change=changed, starred=key in stars,
                           store=d.store))
    return rows


def all_documents(tra_home: Path, *, code: str | None = None, income_year: int | None = None) -> list[DocRow]:
    names, stars, doc_types = load_names(tra_home), load_stars(tra_home), load_doc_types()
    rows = []
    for ws in _workspaces(tra_home):
        if (code is None or ws.client_code == code) and (income_year is None or ws.income_year == income_year):
            rows += _rows_for(ws, names, stars, doc_types)
    return rows


def query(rows: list[DocRow], *, q: str = "", client: str = "", year: str | int = "", folder: str = "",
          kind: str = "", starred: bool = False, sort: str = "changed", desc: bool | None = None) -> list[DocRow]:
    needle = (q or "").strip().lower()
    out = [r for r in rows
           if (not needle or needle in f"{r.filed_name} {r.client} {r.summary} {r.description} {r.kind}".lower())
           and (not client or r.code == client) and (not year or str(r.income_year) == str(year))
           and (not folder or r.folder == folder) and (not kind or r.kind == kind) and (not starred or r.starred)]
    attr = SORTS.get(sort, "last_change")
    reverse = (attr == "last_change") if desc is None else desc
    return sorted(out, key=lambda r: getattr(r, attr), reverse=reverse)


def resolve(settings: Settings, key: str) -> tuple[Workspace, Document]:
    """A document key from the browser -> its workspace and index entry. Raises ValueError if unknown."""
    m = KEY.match(key or "")
    if not m:
        raise ValueError("That isn't a document Sawnx knows.")
    try:
        ws = workspace_for(settings, m.group(1), int(m.group(2)))
    except NotFound:
        raise ValueError("That isn't a document Sawnx knows.") from None
    doc = next((d for d in DocumentIndex(ws.index_csv).load() if d.doc_id == m.group(3)), None)
    if doc is None:
        raise ValueError("That isn't a document Sawnx knows.")
    return ws, doc
