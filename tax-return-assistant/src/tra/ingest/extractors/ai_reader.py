"""The AI reader: Claude reads documents the built-in readers can't. OFF unless the firm switches it on.

It is only ever given RedactedText, and the text is scanned again before
anything is sent. Every figure it returns is unconfirmed, with method "ai",
so a person checks each one, and R6 flags them on the workpaper. Switching it
on (Sawnx Settings) needs the privacy officer's approval, because the
redacted text leaves the laptop.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from ...checks import label_name
from ...labels import figure_allowed, load_labels
from ...models import Figure, ReviewNote
from ...money import parse_amount
from ...privacy.detectors import find_sensitive
from ...privacy.redact import RedactedText
from .base import ExtractResult, require_redacted

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_FIGURES = 60

SYSTEM = """You read Australian tax source documents for a tax agent's draft workpaper.
Identifiers in the text have already been replaced with markers such as [TFN REDACTED].
Return only amounts that are printed in the text, exactly as printed. Never calculate, total, guess or infer an amount.
Give each figure the label key from the list that it belongs to, a short description of where it came from
(payer or issuer and what the amount is), and the page it is on. If nothing in the text matches a label, return
an empty list.

Label keys:
{labels}"""


def _note(risk: str, check_id: str, message: str, doc_id: str) -> ReviewNote:
    return ReviewNote(risk, check_id, message, None, "preparer", "confirm", doc_ids=(doc_id,))


class AiReader:
    doc_types: frozenset[str] = frozenset()

    def __init__(self, client, *, model: str = DEFAULT_MODEL, labels=None):
        self.client = client
        self.model = model
        self.labels = labels or load_labels()
        self.keys = [d.key for d in sorted(self.labels.values(), key=lambda d: d.order) if figure_allowed(d)]

    def _schema(self) -> dict:
        item = {"type": "object", "additionalProperties": False,
                "required": ["label_key", "description", "amount", "page"],
                "properties": {"label_key": {"type": "string", "enum": self.keys},
                               "description": {"type": "string"}, "amount": {"type": "string"},
                               "page": {"type": "integer"}}}
        return {"type": "object", "additionalProperties": False, "required": ["figures"],
                "properties": {"figures": {"type": "array", "items": item}}}

    def _ask(self, rt: RedactedText) -> str | None:
        text = "\n\n".join(f"--- Page {i} ---\n{page}" for i, page in enumerate(rt.pages, start=1))
        labels = "\n".join(f"{k}: {label_name(self.labels, k)}" for k in self.keys)
        response = self.client.beta.messages.create(
            model=self.model, max_tokens=16000, betas=[FALLBACK_BETA], fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": self._schema()}},
            system=SYSTEM.format(labels=labels), messages=[{"role": "user", "content": text}])
        if response.stop_reason == "refusal":
            return None
        return next((b.text for b in response.content if b.type == "text"), None)

    def extract(self, rt: RedactedText, doc_id: str) -> ExtractResult:
        rt = require_redacted(rt)
        result = ExtractResult()
        if find_sensitive(rt.text):
            result.notes.append(_note("High", "A2", "The AI reader found an identifier left in the text and sent "
                                      "nothing. Enter this document's figures by hand and tell the privacy "
                                      "officer.", doc_id))
            return result
        raw = self._ask(rt)
        try:
            items = json.loads(raw)["figures"] if raw else None
        except (ValueError, TypeError, KeyError):
            items = None
        unusable = items is None
        for item in (items or [])[:MAX_FIGURES]:
            try:
                key = item["label_key"]
                if key not in self.keys:
                    raise ValueError(key)
                amount: Decimal = parse_amount(str(item["amount"]))
                page = item.get("page")
                page = page if isinstance(page, int) and 1 <= page <= len(rt.pages) else None
                description = str(item.get("description") or "").strip()[:120]
            except (ValueError, TypeError, KeyError):
                unusable = True
                continue
            result.figures.append(Figure(figure_id="", label_key=key, description=f"AI: {description}",
                                         amount=amount, date=None, doc_id=doc_id, page=page, method="ai",
                                         confirmed=False, substantiated=None))
        if unusable:
            result.notes.append(_note("Medium", "A3", "The AI reader couldn't give a usable answer for some or all "
                                      "of this document. Enter anything missing by hand.", doc_id))
        result.parse_status = "partial" if result.figures else "manual_needed"
        return result


class AiReaderUnavailable(Exception):
    pass


def ai_reader_from_settings(tra_home: Path, env: Mapping[str, str], client=None) -> AiReader | None:
    """An AiReader only when Sawnx's setting is on and ANTHROPIC_API_KEY is set; otherwise None."""
    from ...web.app_settings import load_app_settings

    key = (env.get("ANTHROPIC_API_KEY") or "").strip()
    if not load_app_settings(tra_home).ai_reader or not key:
        return None
    if client is None:
        try:
            import anthropic
        except ImportError:
            raise AiReaderUnavailable("The AI reader is switched on but its library isn't installed. Run: "
                                      ".venv\\Scripts\\pip install -e \".[ai]\"") from None
        client = anthropic.Anthropic(api_key=key)
    return AiReader(client)
