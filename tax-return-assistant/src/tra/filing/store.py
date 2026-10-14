"""Where filed documents go. FYI when configured, local folders otherwise."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

log = logging.getLogger("tra.filing")


@dataclass(frozen=True)
class FilingRequest:
    client_code: str
    income_year: int
    category: str
    filed_name: str
    doc_type: str
    doc_date: date


@dataclass(frozen=True)
class FiledRef:
    location: str
    store: str  # local | fyi
    fell_back: bool = False


class DocumentStore(Protocol):
    name: str

    def file(self, source: Path, req: FilingRequest) -> FiledRef: ...


class FallbackStore:
    """Try the primary store; if it fails for any reason, file locally and say so."""

    def __init__(self, primary: DocumentStore, fallback: DocumentStore):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name

    def file(self, source: Path, req: FilingRequest) -> FiledRef:
        try:
            return self.primary.file(source, req)
        except Exception as exc:  # any failure: network, auth, HTTP, unexpected response
            log.warning("%s store failed (%s); filed locally instead", self.primary.name, type(exc).__name__)
            ref = self.fallback.file(source, req)
            return FiledRef(location=ref.location, store=ref.store, fell_back=True)
