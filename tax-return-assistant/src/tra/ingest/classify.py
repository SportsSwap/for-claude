"""Work out what kind of document this is, from its redacted text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..paths import CONFIG_DIR
from ..privacy.redact import RedactedText

CATEGORIES = ("ATO", "Income", "Investments", "Rental", "Deductions", "Business", "Health", "Other")


@dataclass(frozen=True)
class DocType:
    code: str
    category: str
    description: str
    all: tuple[str, ...]
    any: tuple[str, ...]


def load_doc_types(path: Path | None = None) -> dict[str, DocType]:
    raw = yaml.safe_load((path or CONFIG_DIR / "doc_types.yaml").read_text(encoding="utf-8"))
    return {
        code: DocType(
            code=code,
            category=spec["category"],
            description=spec.get("description", ""),
            all=tuple(k.lower() for k in spec.get("all", [])),
            any=tuple(k.lower() for k in spec.get("any", [])),
        )
        for code, spec in raw.items()
    }


def classify(rt: RedactedText, doc_types: dict[str, DocType]) -> str:
    if not isinstance(rt, RedactedText):
        raise TypeError("classify() accepts redacted text only")
    text = rt.text.lower()
    for doc_type in doc_types.values():
        if not doc_type.all and not doc_type.any:
            continue
        if all(k in text for k in doc_type.all) and (not doc_type.any or any(k in text for k in doc_type.any)):
            return doc_type.code
    return "OTHER"
