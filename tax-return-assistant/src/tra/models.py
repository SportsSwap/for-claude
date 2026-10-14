"""Records passed between stages. See spec §5."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

RISKS = ("High", "Medium", "Low")


@dataclass(frozen=True)
class Document:
    doc_id: str
    doc_type: str
    category: str
    filed_name: str
    filed_location: str
    doc_date: date
    date_detected: bool
    pages: int
    sha256: str
    ingested_at: datetime
    redaction_counts: dict[str, int]
    parse_status: str  # parsed | partial | manual_needed
    store: str  # local | fyi


@dataclass
class Figure:
    figure_id: str
    label_key: str
    description: str
    amount: Decimal
    date: date | None
    doc_id: str | None
    page: int | None
    method: str  # parser | manual | xero
    confirmed: bool
    substantiated: bool | None
    notes: str = ""


@dataclass(frozen=True)
class PrefillLine:
    label_key: str
    payer: str
    amount: Decimal
    doc_id: str
    page: int


@dataclass(frozen=True)
class ReviewNote:
    risk: str  # High | Medium | Low
    check_id: str
    message: str
    dollar_impact: Decimal | None
    audience: str  # client | reviewer | preparer
    action: str  # question | confirm | assumption
    label_key: str | None = None
    citation_id: str | None = None
    figure_ids: tuple[str, ...] = ()
    doc_ids: tuple[str, ...] = ()


@dataclass
class ClientState:
    client_code: str
    income_year: int
    resident: bool = True
    age_band: str = "under65"  # under65 | 65to69 | 70plus
    sapto_status: str = "none"  # none | single | couple | illness_separated
    has_spouse: bool = False
    dependants: int = 0
    help_debt: bool = False
    hospital_cover_days: int | None = None
    sole_trader: bool = False
    xero_tenant_id: str | None = None
    extra: dict = field(default_factory=dict)
