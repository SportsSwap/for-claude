"""index.csv: one row per filed document. Never holds an original filename."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from pathlib import Path

from ..models import Document
from ..privacy.guard import atomic_write_text, check_rows

INDEX_COLUMNS = ["filed_name", "doc_id", "doc_type", "category", "doc_date", "date_detected", "pages", "sha256",
                 "ingested_at", "parse_status", "store", "filed_location", "redaction_counts"]
DELETED_JSON = "deleted.json"  # beside index.csv: deleted documents (trash.py), whose numbers are never reused


def _row(d: Document) -> list[str]:
    return [d.filed_name, d.doc_id, d.doc_type, d.category, d.doc_date.isoformat(), "Y" if d.date_detected else "N",
            str(d.pages), d.sha256, d.ingested_at.isoformat(timespec="seconds"), d.parse_status, d.store,
            d.filed_location, json.dumps(d.redaction_counts, sort_keys=True)]


def to_dict(d: Document) -> dict[str, str]:
    return dict(zip(INDEX_COLUMNS, _row(d)))


def from_dict(r: dict[str, str]) -> Document:
    return _doc(r)


def _doc(r: dict[str, str]) -> Document:
    return Document(doc_id=r["doc_id"], doc_type=r["doc_type"], category=r["category"], filed_name=r["filed_name"],
                    filed_location=r["filed_location"], doc_date=date.fromisoformat(r["doc_date"]),
                    date_detected=r["date_detected"] == "Y", pages=int(r["pages"]), sha256=r["sha256"],
                    ingested_at=datetime.fromisoformat(r["ingested_at"]), redaction_counts=json.loads(r["redaction_counts"]),
                    parse_status=r["parse_status"], store=r["store"])


class DocumentIndex:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[Document]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8-sig", newline="") as fh:
            return [_doc(r) for r in csv.DictReader(fh)]

    def _save(self, docs: list[Document]) -> None:
        rows = [_row(d) for d in docs]
        check_rows(rows, "index.csv")
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(INDEX_COLUMNS)
        writer.writerows(rows)
        atomic_write_text(self.path, buf.getvalue(), "index.csv", prechecked=True)

    def append(self, doc: Document) -> None:
        self._save(self.load() + [doc])

    def update(self, doc: Document) -> None:
        self._save([doc if d.doc_id == doc.doc_id else d for d in self.load()])

    def remove(self, doc_id: str) -> None:
        self._save([d for d in self.load() if d.doc_id != doc_id])

    def next_doc_id(self) -> str:
        ids = [d.doc_id for d in self.load()] + sorted(self._deleted_ids())
        numbers = [int(m.group(1)) for doc_id in ids if (m := re.match(r"^D(\d+)$", doc_id))]
        return f"D{max(numbers, default=0) + 1:03d}"

    def _deleted_ids(self) -> set[str]:
        path = self.path.with_name(DELETED_JSON)
        if not path.exists():
            return set()
        data = json.loads(path.read_text(encoding="utf-8"))
        return {i["doc"]["doc_id"] for i in data.get("items", [])} | set(data.get("retired", []))

    def find_by_sha(self, sha256: str) -> Document | None:
        return next((d for d in self.load() if d.sha256 == sha256), None)

    def names(self) -> set[str]:
        return {d.filed_name for d in self.load()}
