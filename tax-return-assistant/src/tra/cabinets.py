"""Cabinets, like FYI's top-level drawers.

"Tax return" is the per-year Workspace that already exists (Clients/<code>/FY<year>/...).
"Permanent" and "Correspondence" belong to the client, not a year:
Clients/<code>/<Cabinet>/<folder>/<filed name>, with their own index.csv. Documents there
are stored only, never read for the return, and named by client code like everything else.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import date, datetime
from pathlib import Path

from .filing.index import DocumentIndex
from .models import Document
from .privacy.audit import AuditLog
from .privacy.guard import check_text

CABINETS = ("Tax return", "Permanent", "Correspondence")
CODES = {"Permanent": "PERM", "Correspondence": "CORR"}
CABINET_BY_CODE = {v: k for k, v in CODES.items()}
DEFAULT_FOLDERS = {"Permanent": ("Identity", "Engagement", "Trust deeds", "Other"),
                   "Correspondence": ("Emails", "Letters", "Other")}


class CabinetSpace:
    """A client's Permanent or Correspondence cabinet. Quacks like a Workspace where the filing code needs it."""

    income_year = None

    def __init__(self, tra_home: Path, client_code: str, cabinet: str):
        if cabinet not in CODES:
            raise ValueError(f"{cabinet!r} isn't a client cabinet.")
        self.tra_home = Path(tra_home)
        self.client_code = client_code
        self.cabinet = cabinet
        self.code = CODES[cabinet]
        self.standard_folders = DEFAULT_FOLDERS[cabinet]

    @property
    def clients_dir(self) -> Path:
        return self.tra_home / "Clients" / self.client_code / self.cabinet

    @property
    def work_dir(self) -> Path:
        return self.tra_home / "Work" / self.client_code / self.cabinet

    @property
    def index_csv(self) -> Path:
        return self.clients_dir / "index.csv"

    @property
    def figures_csv(self) -> Path:
        return self.work_dir / "figures.csv"  # never written: cabinets aren't read for the return

    @property
    def audit_path(self) -> Path:
        return self.tra_home / "audit" / f"audit-{date.today().year}.jsonl"


def cabinet_filed_name(space: CabinetSpace, doc_type: str, when: date, suffix: str, existing: set[str]) -> str:
    stem = f"{space.client_code}_{space.code}_{doc_type}_{when.isoformat()}"
    name, n = f"{stem}{suffix.lower()}", 2
    while name in existing:
        name, n = f"{stem}_{n:02d}{suffix.lower()}", n + 1
    check_text(name, "filename")
    return name


def store_in_cabinet(space: CabinetSpace, source: Path, folder: str, audit: AuditLog,
                     doc_type: str = "OTHER") -> Document:
    """File a copy of ``source`` unchanged. Returns the existing entry if the same file is already there."""
    from .web.services.files import folder_names  # folders include ones the preparer added

    if folder not in folder_names(space):
        raise ValueError("Choose a folder to store it in.")
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    index = DocumentIndex(space.index_csv)
    duplicate = index.find_by_sha(sha256)
    if duplicate:
        return duplicate
    today = date.today()
    name = cabinet_filed_name(space, doc_type, today, source.suffix, index.names())
    target = space.clients_dir / folder / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    doc = Document(doc_id=index.next_doc_id(), doc_type=doc_type, category=folder, filed_name=name,
                   filed_location=str(target), doc_date=today, date_detected=False, pages=0, sha256=sha256,
                   ingested_at=datetime.now().astimezone(), redaction_counts={}, parse_status="stored", store="local")
    try:
        index.append(doc)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    audit.record("document_stored", client=space.client_code, doc_id=doc.doc_id, filed_name=name,
                 folder=folder, cabinet=space.cabinet, store="local")
    return doc
