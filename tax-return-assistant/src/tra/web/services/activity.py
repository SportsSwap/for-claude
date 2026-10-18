"""A client's activity, in plain words, from the audit log (which already records every action)."""

from __future__ import annotations

import json
from datetime import datetime

from ...workspace import Workspace


def _plural(n, word: str) -> str:
    n = int(n or 0)
    return f"{n} {word}{'' if n == 1 else 's'}"


def _sentence(e: dict) -> str | None:
    action = e.get("action")
    if action == "client_created":
        return f"Client set up for FY{e.get('income_year')}"
    if action == "document_ingested":
        blanked = sum((e.get("redaction_counts") or {}).values())
        return f"{e.get('filed_name')} read · {_plural(e.get('figures'), 'figure')} · {_plural(blanked, 'number')} blanked out"
    if action == "document_stored":
        where = f"{e.get('cabinet')} › " if e.get("cabinet") else ""
        return f"{e.get('filed_name')} stored in {where}{e.get('folder')}"
    if action == "duplicate_skipped":
        return f"A file already filed as {e.get('doc_id')} was skipped"
    if action == "document_moved":
        return f"{e.get('doc_id')} moved from {e.get('from_folder')} to {e.get('to_folder')}"
    if action == "folder_added":
        return f"Folder {e.get('folder')} added"
    if action == "figure_changed":
        return f"{e.get('figure_id')} changed ({', '.join(e.get('fields') or [])})"
    if action == "figure_added":
        return f"{e.get('figure_id')} added by hand"
    if action == "workpaper_generated":
        return f"{e.get('file')} prepared · {_plural(e.get('notes_high'), 'High note')}"
    if action == "review_marked":
        return f"Marked reviewed by {e.get('reviewer')}"
    if action == "document_properties_changed":
        return f"{e.get('doc_id')} properties changed ({', '.join(e.get('fields') or [])})"
    if action == "document_version_added":
        return f"{e.get('doc_id')} new version (version {e.get('version')})"
    if action == "intray_filed":
        return f"Filed from the In Tray as {e.get('doc_id')}"
    if action == "client_named":
        return "Client name set"
    if action == "guard_blocked":
        return "The privacy guard refused to save something (tell the privacy officer)"
    return None


def _when(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %H:%M")
    except (TypeError, ValueError):
        return ""


def activity(ws: Workspace, limit: int = 50) -> list[tuple[str, str]]:
    """Newest first: (time, sentence)."""
    entries = []
    for path in sorted((ws.tra_home / "audit").glob("audit-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("client") == ws.client_code and (text := _sentence(e)):
                entries.append((e.get("ts", ""), text))
    entries.sort(key=lambda x: x[0], reverse=True)
    return [(_when(ts), text) for ts, text in entries[:limit]]
