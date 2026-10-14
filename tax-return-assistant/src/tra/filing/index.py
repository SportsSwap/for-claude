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


def _row(d: Document) -> list[str]:
    return [d.filed_name, d.doc_id, d.doc_type, d.category, d.doc_date.isoformat(), "Y" if d.date_detected else "N",
            str(d.pages), d.sha256, d.ingested_at.isoformat(timespec="seconds"), d.parse_status, d.store,
            d.filed_location, json.dumps(d.redaction_counts, sort_keys=True)]


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

    def next_doc_id(self) -> str:
        numbers = [int(m.group(1)) for d in self.load() if (m := re.match(r"^D(\d+)$", d.doc_id))]
        return f"D{max(numbers, default=0) + 1:03d}"

    def find_by_sha(self, sha256: str) -> Document | None:
        return next((d for d in self.load() if d.sha256 == sha256), None)

    def names(self) -> set[str]:
        return {d.filed_name for d in self.load()}
