"""Rental properties: each property's share, private use and the firm's rental rows.

rental.json in the client's work folder holds the properties (a short name, the client's share, private use, weeks),
which property each rental document belongs to, and any figure moved to "This Taxpayer's Contribution Only".
compute() turns confirmed rental figures into the firm's rows A to X per property; the draft return, both tax
calculations and the workpaper all use it, so the return claims the client's share. Design:
docs/specs/2026-10-26-rental-properties-design.md. No owner names or addresses are ever kept here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .labels import LabelDef, return_key
from .privacy.guard import atomic_write_text, check_value

LOCATION = "rental.json"
TAB = "M25 Rental Property"
RETURN_KEYS = ("rent.gross", "rent.interest", "rent.capital_works", "rent.other")  # Item 21 P, Q, F, U
COLUMNS = ("agent", "owners", "taxpayer")
MAX_NAME = 18  # "M25 Rental " + the name fits Excel's 31-character tab names
CENT = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")
NOT_APPORTIONED = frozenset({"rent.advertising", "rent.agent_fees"})  # the firm's sheet leaves these unticked


@dataclass(frozen=True)
class Row:
    letter: str
    key: str | None  # None for a total row
    heading: str
    kind: str  # income | expense | total
    itemised: bool = False


ROWS = [
    Row("A", "rent.gross", "Rental Income", "income"),
    Row("B", "rent.other_income", "Other Income", "income"),
    Row("C", None, "Total Income", "total"),
    Row("D", "rent.advertising", "Advertising", "expense"),
    Row("E", "rent.body_corporate", "Body Corporate", "expense"),
    Row("F", "rent.borrowing", "Borrowing Expenses", "expense"),
    Row("G", "rent.cleaning", "Cleaning", "expense"),
    Row("H", "rent.council_rates", "Council Rates", "expense"),
    Row("I", "rent.capital_allowances", "Deductions for Decline in Value", "expense"),
    Row("J", "rent.gardening", "Gardening/Lawnmowing", "expense"),
    Row("K", "rent.insurance", "Insurance", "expense"),
    Row("L", "rent.interest", "Interest on Loans", "expense"),
    Row("M", "rent.land_tax", "Land Tax", "expense"),
    Row("N", "rent.legal", "Legal Expenses", "expense"),
    Row("O", "rent.pest_control", "Pest Control", "expense"),
    Row("P", "rent.agent_fees", "Agent Fees", "expense"),
    Row("Q", "rent.repairs", "Repairs and Maintenance", "expense", itemised=True),
    Row("R", "rent.capital_works", "Capital Works Deductions", "expense"),
    Row("S", "rent.stationery", "Office Supplies", "expense"),
    Row("T", "rent.travel", "Travel Expenses", "expense"),
    Row("U", "rent.water", "Water Charges", "expense"),
    Row("V", "rent.other", "Sundry Rental Expenses", "expense", itemised=True),
    Row("W", None, "Total Expenses", "total"),
    Row("X", None, "Net Income / (Loss)", "total"),
]
ROW_OF = {r.key: r for r in ROWS if r.key}


@dataclass
class Property:
    id: str
    name: str
    share: Decimal = HUNDRED  # the client's ownership share, as a percentage
    share_source: str = "default"  # default | suggested (read from a document) | person
    share_doc: str | None = None  # the document a suggested share was read from
    private_use: Decimal = ZERO  # percentage
    weeks_rented: int = 52
    weeks_available: int = 52
    first_income: str = ""  # date the property first earned rental income, as the preparer typed it
    apportion: dict[str, bool] = field(default_factory=dict)  # rows changed from the default tick

    def apportioned(self, key: str) -> bool:
        if ROW_OF[key].kind != "expense":
            return False
        return self.apportion.get(key, key not in NOT_APPORTIONED)


@dataclass
class RentalSetup:
    properties: list[Property]
    documents: dict[str, str] = field(default_factory=dict)  # doc_id -> property id
    columns: dict[str, str] = field(default_factory=dict)  # figure_id -> agent | owners | taxpayer (if changed)


def default_setup() -> RentalSetup:
    return RentalSetup(properties=[Property(id="P1", name="Property 1")])


# --- working it out ---------------------------------------------------------------------------------------------

def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def share_of(agent: Decimal, owners: Decimal, taxpayer: Decimal, prop: Property, key: str) -> Decimal:
    """ROUND(((agent + owners) x share + taxpayer only) x (1 - private use if ticked), 2): the workpaper's formula."""
    factor = (HUNDRED - prop.private_use) / HUNDRED if prop.apportioned(key) else Decimal(1)
    return _round(((agent + owners) * prop.share / HUNDRED + taxpayer) * factor)


@dataclass
class Line:
    """One figure on an itemised row (repairs, sundry)."""
    figure: object
    column: str
    share: Decimal


@dataclass
class RowResult:
    row: Row
    figures: list = field(default_factory=list)
    agent: Decimal = ZERO
    owners: Decimal = ZERO
    taxpayer: Decimal = ZERO
    share: Decimal = ZERO
    lines: list[Line] = field(default_factory=list)


@dataclass
class PropertyResult:
    prop: Property
    rows: list[RowResult]
    return_labels: dict[str, Decimal]
    unassigned_docs: list[str] = field(default_factory=list)

    def row(self, letter: str) -> RowResult:
        return next(r for r in self.rows if r.row.letter == letter)


def column_of(f, setup: RentalSetup, doc_types: dict[str, str]) -> str:
    """Agent Summary for the property manager's statement, Owners' Contribution for anything else, unless moved."""
    chosen = setup.columns.get(f.figure_id)
    if chosen in COLUMNS:
        return chosen
    return "agent" if doc_types.get(f.doc_id or "") == "RENTSTMT" else "owners"


def property_of(f, setup: RentalSetup) -> str:
    ids = [p.id for p in setup.properties]
    chosen = setup.documents.get(f.doc_id or "")
    return chosen if chosen in ids else ids[0]


def is_rental(f, labels: dict[str, LabelDef]) -> bool:
    return f.label_key in labels and return_key(labels, f.label_key) in RETURN_KEYS


def compute(figures, setup: RentalSetup, labels: dict[str, LabelDef],
            doc_types: dict[str, str] | None = None) -> list[PropertyResult]:
    """Each property's rows A to X from the rental figures given (callers pass confirmed ones). A property with no
    figures is still listed. Documents not assigned to a property (with two or more) count under the first."""
    doc_types = doc_types or {}
    rental = [f for f in figures if is_rental(f, labels)]
    ids = {p.id for p in setup.properties}
    results = []
    for n, prop in enumerate(setup.properties):
        mine = [f for f in rental if property_of(f, setup) == prop.id]
        rows = []
        for row in ROWS:
            r = RowResult(row)
            if row.key:
                r.figures = [f for f in mine if f.label_key == row.key]
                for f in r.figures:
                    col = column_of(f, setup, doc_types)
                    setattr(r, col, getattr(r, col) + f.amount)
                    if row.itemised:
                        parts = {c: (f.amount if c == col else ZERO) for c in COLUMNS}
                        r.lines.append(Line(f, col, share_of(parts["agent"], parts["owners"], parts["taxpayer"],
                                                             prop, row.key)))
                r.share = (sum((line.share for line in r.lines), ZERO) if row.itemised
                           else share_of(r.agent, r.owners, r.taxpayer, prop, row.key))
            rows.append(r)
        by = {r.row.letter: r for r in rows}
        income = [r for r in rows if r.row.kind == "income"]
        expenses = [r for r in rows if r.row.kind == "expense"]
        for letter, parts in (("C", income), ("W", expenses)):
            for attr in ("agent", "owners", "taxpayer", "share"):
                setattr(by[letter], attr, sum((getattr(r, attr) for r in parts), ZERO))
        for attr in ("agent", "owners", "taxpayer", "share"):
            setattr(by["X"], attr, getattr(by["C"], attr) - getattr(by["W"], attr))
        labels_out = {"rent.gross": by["C"].share, "rent.interest": by["L"].share,
                      "rent.capital_works": by["R"].share,
                      "rent.other": by["W"].share - by["L"].share - by["R"].share}
        unassigned = []
        if n == 0 and len(setup.properties) > 1:
            unassigned = sorted({f.doc_id for f in rental if f.doc_id and setup.documents.get(f.doc_id) not in ids})
        results.append(PropertyResult(prop, rows, labels_out, unassigned))
    return results


def rental_return_totals(figures, setup: RentalSetup, labels: dict[str, LabelDef]) -> dict[str, Decimal]:
    """Item 21 P, Q, F and U across every property, for the labels that have rental figures."""
    rental = [f for f in figures if is_rental(f, labels)]
    present = {return_key(labels, f.label_key) for f in rental}
    totals = {key: ZERO for key in present}
    for result in compute(rental, setup, labels):
        for key in present:
            totals[key] += result.return_labels[key]
    return totals


# --- saving -----------------------------------------------------------------------------------------------------

class RentalFileProblem(ValueError):
    """rental.json can't be read (damaged, or edited by hand)."""


_PLAIN = re.compile(r"\d+(?:\.\d+)?")  # 50, 33.33: never NaN, Infinity or 1E+2, which Decimal accepts


def _number(value, what: str, low: Decimal, high: Decimal) -> Decimal:
    text = str(value).strip().rstrip("%").strip()
    if not _PLAIN.fullmatch(text):
        raise ValueError(f"{what} must be a number, like 50.")
    number = Decimal(text)
    if not low <= number <= high:
        raise ValueError(f"{what} must be between {low} and {high}.")
    return number


def validate(setup: RentalSetup) -> None:
    if not setup.properties:
        raise ValueError("Keep at least one property.")
    seen, names = set(), set()
    for p in setup.properties:
        if not p.name.strip() or len(p.name.strip()) > MAX_NAME:
            raise ValueError(f"Give each property a short name (1 to {MAX_NAME} characters).")
        if p.name.strip().lower() in names:  # Excel's tab names ignore capitals
            raise ValueError("Give each property a different name.")
        names.add(p.name.strip().lower())
        if p.id in seen:
            raise ValueError("Two properties have the same id.")
        seen.add(p.id)
        _number(p.share, "The share", ZERO, HUNDRED)
        _number(p.private_use, "Private use", ZERO, HUNDRED)
        for weeks, what in ((p.weeks_rented, "Weeks rented"), (p.weeks_available, "Weeks available")):
            if not (isinstance(weeks, int) and 0 <= weeks <= 52):
                raise ValueError(f"{what} must be a whole number from 0 to 52.")
        if p.share_source not in ("default", "suggested", "person"):
            raise ValueError("Unknown share source.")
    if any(c not in COLUMNS for c in setup.columns.values()):
        raise ValueError("Unknown column.")


def _to_json(setup: RentalSetup) -> dict:
    return {"properties": [{"id": p.id, "name": p.name.strip(), "share": str(p.share),
                            "share_source": p.share_source, "share_doc": p.share_doc,
                            "private_use": str(p.private_use), "weeks_rented": p.weeks_rented,
                            "weeks_available": p.weeks_available, "first_income": p.first_income,
                            "apportion": dict(p.apportion)} for p in setup.properties],
            "documents": dict(setup.documents), "columns": dict(setup.columns)}


DAMAGED = ("rental.json (the Rental page's settings) is damaged, so Sawnx can't read the rental properties. Open "
           "it from the client's work folder and fix it, or delete it and set the properties again on the Rental page.")


def load_rental(ws) -> RentalSetup:
    """The saved properties, or one default property when there's no file. Raises RentalFileProblem if it's damaged."""
    path = ws.rental_json
    if not path.exists():
        return default_setup()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        props = [Property(id=str(p["id"]), name=str(p["name"]), share=_number(p["share"], "share", ZERO, HUNDRED),
                          share_source=p.get("share_source", "person"), share_doc=p.get("share_doc"),
                          private_use=_number(p.get("private_use", "0"), "private use", ZERO, HUNDRED),
                          weeks_rented=int(p.get("weeks_rented", 52)), weeks_available=int(p.get("weeks_available", 52)),
                          first_income=str(p.get("first_income", "")),
                          apportion={str(k): bool(v) for k, v in dict(p.get("apportion", {})).items()})
                 for p in raw.get("properties", [])]
        setup = (RentalSetup(properties=props, documents={str(k): str(v) for k, v in dict(raw.get("documents", {})).items()},
                             columns={str(k): str(v) for k, v in dict(raw.get("columns", {})).items()})
                 if props else default_setup())
        validate(setup)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        raise RentalFileProblem(DAMAGED) from None
    return setup


def _pct(value: Decimal) -> str:
    return f"{value.normalize():f}%"


def suggest_share(ws, doc_id: str, share: Decimal, audit) -> str:
    """A reader found the client's share on a document. It becomes the share of that document's property unless a
    person has set one; either way the document's Things to check says what was found."""
    try:
        setup = load_rental(ws)
    except RentalFileProblem:  # the import still goes ahead; the file is left for a person to fix
        return f"This document shows an ownership share of {_pct(share)}, but {DAMAGED}"
    ids = [p.id for p in setup.properties]
    assigned = setup.documents.get(doc_id)
    if len(ids) > 1 and assigned not in ids:
        return (f"This document shows an ownership share of {_pct(share)}. Pick its property on the Rental page, "
                "then check that property's share.")
    prop = next(p for p in setup.properties if p.id == (assigned if assigned in ids else ids[0]))
    if prop.share_source in ("person", "suggested"):
        where = "the Rental page says" if prop.share_source == "person" else f"{prop.share_doc} suggested"
        if prop.share == share:
            return f"Ownership share {_pct(share)} on this document matches the Rental page."
        return (f"This document shows an ownership share of {_pct(share)}, but {where} {_pct(prop.share)}. "
                "Check which is right on the Rental page.")
    prop.share, prop.share_source, prop.share_doc = share, "suggested", doc_id
    save_rental(ws, setup, audit, what="share suggested")
    return f"Ownership share {_pct(share)} read from this document: check it on the Rental page."


def save_rental(ws, setup: RentalSetup, audit, *, what: str = "properties") -> None:
    """Checked, then written through the output guard; the audit log gets what changed, never the names."""
    validate(setup)
    data = _to_json(setup)
    check_value(data, LOCATION)
    atomic_write_text(ws.rental_json, json.dumps(data, indent=2), LOCATION, prechecked=True)
    audit.record("rental_changed", client=ws.client_code, changed=what, properties=len(setup.properties))
