"""The Rental page: properties, which property each rental document is, and each figure's column.

Every change goes through tra.rental.save_rental (checked, guarded, audited without names). Saving a property's
form is a person setting its share, so a suggested or assumed share stops being flagged (S18).
"""

from __future__ import annotations

import re
from decimal import Decimal

from ...filing.index import DocumentIndex
from ...labels import load_labels
from ...rental import (COLUMNS, ROWS, Property, RentalFileProblem, RentalSetup, column_of, compute, default_setup,
                       is_rental, load_rental, property_of, save_rental)

_PLAIN = re.compile(r"\d+(?:\.\d+)?")


def _plain_number(text: str, what: str) -> str:
    if not _PLAIN.fullmatch(text):  # Decimal would also take NaN, Infinity and 1e2
        raise ValueError(f"{what} must be a number, like 50.")
    return text
from ...workspace import Workspace
from .figures import FiguresFileProblem, figure_rows

COLUMN_NAMES = {"agent": "Agent Summary", "owners": "Owners' Contribution", "taxpayer": "This taxpayer only"}
EXPENSE_KEYS = [r.key for r in ROWS if r.kind == "expense"]


def _rental_figures(ws: Workspace) -> list:
    try:
        figures = figure_rows(ws)
    except FiguresFileProblem:
        return []
    labels = load_labels()
    return [f for f in figures if is_rental(f, labels)]


def has_rental(ws: Workspace) -> bool:
    """Show the Rental tab: the year has rental figures, or someone has set up a property."""
    return ws.rental_json.exists() or bool(_rental_figures(ws))


def _doc_types(ws: Workspace) -> dict:
    return {d.doc_id: d for d in DocumentIndex(ws.index_csv).load()} if ws.index_csv.exists() else {}


def rental_page(ws: Workspace) -> dict:
    try:
        setup = load_rental(ws)
    except RentalFileProblem as exc:  # say so, rather than an error page
        return {"problem": str(exc), "setup": default_setup(), "results": [], "documents": [], "figures": [],
                "unconfirmed": 0, "rows": ROWS, "expense_keys": EXPENSE_KEYS, "column_names": COLUMN_NAMES}
    figures = _rental_figures(ws)
    docs = _doc_types(ws)
    doc_types = {k: d.doc_type for k, d in docs.items()}
    results = compute(figures, setup, load_labels(), doc_types)
    rental_docs = sorted({f.doc_id for f in figures if f.doc_id} |
                         {k for k, d in docs.items() if d.doc_type == "RENTSTMT"})
    return {
        "setup": setup, "results": results, "expense_keys": EXPENSE_KEYS, "rows": ROWS,
        "unconfirmed": sum(not f.confirmed for f in figures),
        "documents": [{"doc_id": k, "name": docs[k].filed_name if k in docs else k,
                       "property": setup.documents.get(k, "")} for k in rental_docs],
        "figures": [{"f": f, "column": column_of(f, setup, doc_types), "property": property_of(f, setup)}
                    for f in figures],
        "column_names": COLUMN_NAMES,
    }


def _decimal(raw: str, what: str, *, blank: str | None = None) -> Decimal:
    """A percentage typed on the form. A blank is ``blank`` if given (private use: 0), otherwise refused."""
    text = (raw or "").strip().rstrip("%").strip()
    if not text and blank is not None:
        text = blank
    if not text:
        raise ValueError(f"Type {what.lower()}, like 50.")
    return Decimal(_plain_number(text, what))


def _weeks(raw: str, what: str) -> int:
    try:
        return int((raw or "").strip() or "52")
    except ValueError:
        raise ValueError(f"{what} must be a whole number of weeks, from 0 to 52.") from None


def save_property(ws: Workspace, pid: str, form, audit) -> Property:
    setup = load_rental(ws)
    prop = next((p for p in setup.properties if p.id == pid), None)
    if prop is None:
        raise ValueError(f"There's no property {pid}.")
    prop.name = (form.get("name") or "").strip()
    prop.share = _decimal(form.get("share", ""), "The client's share")
    prop.private_use = _decimal(form.get("private_use", ""), "Private use", blank="0")
    prop.weeks_rented = _weeks(form.get("weeks_rented", ""), "Weeks rented")
    prop.weeks_available = _weeks(form.get("weeks_available", ""), "Weeks available")
    prop.first_income = (form.get("first_income") or "").strip()[:20]
    ticked = set(form.getlist("apportion")) if hasattr(form, "getlist") else set(form.get("apportion", []))
    prop.apportion = {key: key in ticked for key in EXPENSE_KEYS}
    prop.share_source, prop.share_doc = "person", None
    save_rental(ws, setup, audit, what="property")
    return prop


def add_property(ws: Workspace, name: str, audit) -> Property:
    setup = load_rental(ws)
    used = {p.id for p in setup.properties}
    pid = next(f"P{n}" for n in range(1, len(used) + 2) if f"P{n}" not in used)
    prop = Property(id=pid, name=(name or "").strip() or f"Property {len(used) + 1}")
    setup.properties.append(prop)
    save_rental(ws, setup, audit, what="property added")
    return prop


def remove_property(ws: Workspace, pid: str, audit) -> None:
    setup = load_rental(ws)
    if len(setup.properties) == 1:
        raise ValueError("Keep at least one property.")
    if pid in setup.documents.values():
        raise ValueError("That property still has documents. Move them to another property first.")
    setup.properties = [p for p in setup.properties if p.id != pid]
    save_rental(ws, setup, audit, what="property removed")


def set_documents(ws: Workspace, form, audit) -> int:
    setup = load_rental(ws)
    ids = {p.id for p in setup.properties}
    changed = 0
    for field_name, value in form.items():
        if field_name.startswith("doc-") and value in ids and setup.documents.get(field_name[4:]) != value:
            setup.documents[field_name[4:]] = value
            changed += 1
    if changed:
        save_rental(ws, setup, audit, what="documents")
    return changed


def set_columns(ws: Workspace, form, audit) -> int:
    """Only a column different from the document's usual one is kept, so a figure left alone still follows its
    document (Agent Summary for the agent's statement); one moved back to its usual column is forgotten."""
    setup = load_rental(ws)
    doc_types = {k: d.doc_type for k, d in _doc_types(ws).items()}
    plain = RentalSetup(properties=setup.properties)
    figures = {f.figure_id: f for f in _rental_figures(ws)}
    changed = 0
    for field_name, value in form.items():
        f = figures.get(field_name[4:]) if field_name.startswith("col-") else None
        if f is None or value not in COLUMNS or column_of(f, setup, doc_types) == value:
            continue
        if column_of(f, plain, doc_types) == value:
            setup.columns.pop(f.figure_id, None)
        else:
            setup.columns[f.figure_id] = value
        changed += 1
    if changed:
        save_rental(ws, setup, audit, what="columns")
    return changed
