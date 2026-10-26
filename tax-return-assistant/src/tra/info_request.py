"""Make info request: a Word checklist asking a client for this year's papers, based on last year's return.

Last year comes from the previous income year's confirmed figures (who paid what, from their
descriptions) and share sales, or, failing those, prior_year.csv / last_return.json (items only).
No amounts are written, and never the client's name. The wording is in config/info_request.yaml.
With nothing from last year, it is the firm's standard list and says so.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

import yaml

from .cabinets import CabinetSpace, store_in_cabinet
from .checks.prior_year import load_prior_year
from .dates import fy_bounds
from .docx_writer import write_docx
from .figures import read_cgt, read_figures
from .labels import load_labels, return_key
from .models import Document
from .paths import CONFIG_DIR
from .privacy.audit import AuditLog
from .workspace import Workspace

MAX_PAYERS = 6
_READER = re.compile(r"^(?:AI|Claude|Email|Sheet \d+ row \d+):\s*")


@dataclass
class InfoRequest:
    year: int
    from_last_year: bool
    title: str
    greeting: str
    intro: str
    sections: list[tuple[str, list[str]]]
    closing: str


def load_wording(path: Path | None = None) -> dict:
    return yaml.safe_load((path or CONFIG_DIR / "info_request.yaml").read_text(encoding="utf-8"))


def payer(description: str) -> str | None:
    """Who issued a figure's document: the part of its description before " – " or ": "."""
    text = _READER.sub("", description or "")
    for sep in (" – ", ": "):
        if sep in text:
            return text.split(sep, 1)[0].strip() or None
    return None


def _join(names: list[str]) -> str:
    if len(names) > MAX_PAYERS:
        names = names[:MAX_PAYERS] + ["others"]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _is_the_client(who: str, name: str | None) -> bool:
    """A statement's first line is sometimes the account holder: never put the client's name in the letter."""
    if not name:
        return False
    words = set(re.findall(r"[a-z]+", who.lower()))
    return set(re.findall(r"[a-z]+", name.lower())) <= words


def _last_year(ws: Workspace) -> tuple[dict[str, list[str]], list[str]]:
    """Label key -> payers, from last year's confirmed figures (or prior_year.csv); and assets sold last year."""
    from .web.client_names import load_names

    last = ws.for_year(ws.income_year - 1)
    labels = load_labels()
    figures, _errors = read_figures(last.figures_csv, labels) if last.figures_csv.exists() else ([], [])
    client = load_names(ws.tra_home).get(ws.client_code)
    keys: dict[str, list[str]] = {}
    for f in figures:
        if f.confirmed and f.amount:
            names = keys.setdefault(return_key(labels, f.label_key), [])  # gardening asks for the rental papers
            who = payer(f.description)
            if who and "redacted" not in who.lower() and not _is_the_client(who, client) and who not in names:
                names.append(who)
    if not keys:
        keys = {k: [] for k, amount in load_prior_year(ws).items() if amount}
    events, _errors = read_cgt(last.cgt_csv) if last.cgt_csv.exists() else ([], [])
    assets = list(dict.fromkeys(e.asset for e in events if e.confirmed and e.asset))
    return keys, assets


def build_request(ws: Workspace, wording: dict | None = None) -> InfoRequest:
    try:
        return _build(ws, wording or load_wording())
    except (KeyError, IndexError) as exc:
        raise ValueError(f"config/info_request.yaml has a mistake: {{{exc.args[0]}}} isn't something Sawnx fills in "
                         "(use {year}, {start}, {end} or {payers}), or a section is missing a line. Fix it and try "
                         "again.") from None


def _build(ws: Workspace, words: dict) -> InfoRequest:
    start, end = fy_bounds(ws.income_year)
    fill = {"year": ws.income_year, "start": f"{start.day} {start:%B %Y}", "end": f"{end.day} {end:%B %Y}"}
    keys, assets = _last_year(ws)
    from_last_year = bool(keys or assets)
    sections: list[tuple[str, list[str]]] = []
    for s in words["sections"]:
        if not from_last_year:
            if s.get("standard_items"):
                sections.append((s.get("standard_heading", s["heading"]), list(s["standard_items"])))
            elif s.get("standard"):
                sections.append((s["heading"], [s["item_no_payers"].format(**fill)]))
            continue
        if s.get("per_label"):
            items = [text for key, text in s["per_label"].items() if key in keys]
        elif s.get("cgt"):
            items = [s["item"].format(**fill, payers=_join(assets))] if assets else []
        elif any(k in keys for k in s.get("labels", [])):
            names = [n for k in s["labels"] for n in keys.get(k, [])]
            names = list(dict.fromkeys(names))
            if s.get("items"):
                items = list(s["items"])
            else:
                items = [s["item"].format(**fill, payers=_join(names)) if names else s["item_no_payers"].format(**fill)]
        else:
            items = []
        if items:
            sections.append((s["heading"], items))
    sections.append((words["new_this_year"]["heading"], list(words["new_this_year"]["items"])))
    return InfoRequest(year=ws.income_year, from_last_year=from_last_year, title=words["title"].format(**fill),
                       greeting=words["greeting"], intro=words["intro" if from_last_year else "intro_standard"]
                       .format(**fill), sections=sections, closing=words["closing"])


def paragraphs(req: InfoRequest) -> list[tuple[str, str]]:
    out = [("title", req.title), ("text", req.greeting), ("text", req.intro)]
    for heading, items in req.sections:
        out.append(("heading", heading))
        out += [("item", item) for item in items]
    out.append(("text", req.closing))
    return out


def make_info_request(ws: Workspace, audit: AuditLog) -> Document:
    """Build the request, file it in the client's Correspondence cabinet (Letters), and return its entry."""
    req = build_request(ws)
    uploads = ws.work_dir / "_uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    path = uploads / f"{secrets.token_hex(8)}.docx"
    try:
        write_docx(path, paragraphs(req), "info request")
        doc = store_in_cabinet(CabinetSpace(ws.tra_home, ws.client_code, "Correspondence"), path, "Letters", audit,
                               doc_type="INFOREQ")
    finally:
        path.unlink(missing_ok=True)
    audit.record("info_request_made", client=ws.client_code, income_year=ws.income_year, doc_id=doc.doc_id,
                 from_last_year=req.from_last_year)
    return doc
