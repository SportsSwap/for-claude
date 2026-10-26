"""The AI reader: Claude reads documents the built-in readers can't. OFF unless the firm switches it on.

It is only ever given RedactedText, and the text is scanned again before
anything is sent. Every figure it returns is unconfirmed, with method "ai",
so a person checks each one, and R6 flags them on the workpaper. Switching it
on (Sawnx Settings) needs the privacy officer's approval, because the
redacted text leaves the laptop. It also says what the document is (doc_type),
which the pipeline uses unless the type was forced or known for sure.

Pictures of scanned pages (ingest/page_images.py) are the one exception to
"redacted text only": they can't be blanked, so they're only passed in when
their own Settings switch is on, with its own approval.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from ...checks import label_name
from ...labels import figure_allowed, load_labels
from ...models import Figure, ReviewNote
from ...money import parse_amount
from ...privacy.detectors import find_sensitive
from ...privacy.redact import RedactedText, RedactionError, redact_text
from ..classify import load_doc_types
from .base import ExtractResult, require_redacted

# Claude Haiku 5.5: the owner chose it (25 Oct 2026) - fast and low-cost, and reading figures off a document is the
# extraction work it suits. It has no server-side fallback, so a declined document comes back as an A3 note.
DEFAULT_MODEL = "claude-haiku-5-5"
MODEL_NAMES = {"claude-haiku-5-5": "Claude Haiku 5.5", "claude-opus-5-5": "Claude Opus 5.5",
               "claude-sonnet-5-5": "Claude Sonnet 5.5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"})  # "fallbacks" accepted
MAX_FIGURES = 60
# A figure's note when its amount is also printed in the document's own text: two separate readings agree (the
# scanner's or PDF's text, and the AI reading the text or the picture). A figure without it needs a closer look.
TEXT_MATCH = "matches the document's text"
# Money in the text: with a $, thousands commas or cents (a bare 2000 could be a postcode or a year).
_MONEY = re.compile(r"(?<![\w.,])(?:\$\s?\d[\d,]*(?:\.\d{2})?|\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2})(?![\w,]|\.?\d)")
NOTHING_FOUND = ("The AI reader read this document but found no amounts it could match to a return item. Check the "
                 "document and enter any figures by hand.")

SYSTEM = """You read Australian tax source documents for a tax agent's draft workpaper.
Identifiers in the text have already been replaced with markers such as [TFN REDACTED].
Return only amounts that are printed in the text, exactly as printed. Never calculate, total, guess or infer an amount.
Give each figure the label key from the list that it belongs to, a short description of where it came from
(payer or issuer and what the amount is), and the page it is on. If nothing in the text matches a label, return
an empty list. Never copy account numbers, BSBs, TFNs, card or licence numbers into a description.
Also give doc_type: the code from the list of document types that describes the whole document (for example, a
property manager's statement is RENTSTMT). Use OTHER if none fits.
If the document shows the client's ownership share of a rental property (for example 50% when it is owned with a
spouse), give it as ownership_percent, a number from 0 to 100; otherwise null. Never give owners' names.{pictures}

Label keys:
{labels}

Document types:
{doc_types}"""
PICTURES = """
Some pages are also sent as pictures, each after a line naming its page. Read amounts printed in a picture the
same way, and give that page number. A picture is not blanked out: never copy account numbers, BSBs, TFNs, card
or licence numbers from it into a description."""
# Sawnx's own letter, the types the pipeline sets, and types with readers of their own whose figures mean something
# special (the ATO's pre-fill report and prior-year return, Xero's reports): the AI reader can't give any of them.
NOT_AI_TYPES = frozenset({"INFOREQ", "EMAIL", "CLIENTXLS", "PREFILL", "PRIOR", "XEROPL", "XEROBS", "XEROBANK",
                          "XEROCOA"})


def figures_from_items(items: list, keys: list[str], doc_id: str, page_count: int,
                       reader: str) -> tuple[list[Figure], list[str]]:
    """Unconfirmed figures from a reader's answer, and a line for each item that couldn't be used.
    A page outside the document is left blank by the AI reader; Claude in chat (strict) is told."""
    figures, problems = [], []
    for n, item in enumerate(items[:MAX_FIGURES], start=1):
        try:
            key = item["label_key"]
            if key not in keys:
                raise ValueError(f"{key!r} isn't a label a figure can have")
            amount: Decimal = parse_amount(str(item["amount"]))
            page = item.get("page")
            if not (isinstance(page, int) and 1 <= page <= page_count):
                if reader != "AI":
                    raise ValueError(f"page {page!r} isn't in the document (it has {page_count})")
                page = None
            description = str(item.get("description") or "").strip()[:120]
            if reader == "AI" and find_sensitive(description):
                description = _blanked(description)  # the model copied an identifier (from a picture, say)
        except (ValueError, TypeError, KeyError) as exc:
            problems.append(f"figure {n}: {exc}")
            continue
        figures.append(Figure(figure_id="", label_key=key, description=f"{reader}: {description}", amount=amount,
                              date=None, doc_id=doc_id, page=page, method="ai", confirmed=False, substantiated=None))
    return figures, problems


def printed_amounts(text: str) -> set[Decimal]:
    """Every amount of money written in the text, without its sign (a refund in brackets is still 45.00)."""
    found = set()
    for m in _MONEY.finditer(text):
        try:
            found.add(abs(parse_amount(m.group(0).replace(" ", ""))))
        except ValueError:
            continue
    return found


def _blanked(description: str) -> str:
    """The description with its identifiers replaced by markers, or nothing if that fails (it fails closed)."""
    try:
        return redact_text(description)
    except RedactionError:
        return ""


def _api_errors() -> tuple[type[BaseException], ...]:
    """The SDK's errors (a refused key, a timeout, no connection). Without the SDK only a stand-in client exists."""
    try:
        import anthropic
    except ImportError:
        return ()
    return (anthropic.APIError,)


def _pages(numbers) -> str:
    return ", ".join(map(str, numbers))


def _note(risk: str, check_id: str, message: str, doc_id: str) -> ReviewNote:
    return ReviewNote(risk, check_id, message, None, "preparer", "confirm", doc_ids=(doc_id,))


class AiReader:
    doc_types: frozenset[str] = frozenset()

    def __init__(self, client, *, model: str = DEFAULT_MODEL, labels=None, doc_types=None,
                 page_images: bool = False):
        """``page_images`` (its own Settings switch) lets the pipeline send pictures of a PDF's scanned pages."""
        self.client = client
        self.model = model
        self.page_images = page_images
        self.labels = labels or load_labels()
        self.keys = [d.key for d in sorted(self.labels.values(), key=lambda d: d.order) if figure_allowed(d)]
        self.type_choices = {code: t for code, t in (doc_types or load_doc_types()).items() if code not in NOT_AI_TYPES}

    def _schema(self) -> dict:
        item = {"type": "object", "additionalProperties": False,
                "required": ["label_key", "description", "amount", "page"],
                "properties": {"label_key": {"type": "string", "enum": self.keys},
                               "description": {"type": "string"}, "amount": {"type": "string"},
                               "page": {"type": "integer"}}}
        return {"type": "object", "additionalProperties": False,
                "required": ["doc_type", "figures", "ownership_percent"],
                "properties": {"doc_type": {"type": "string", "enum": list(self.type_choices)},
                               "figures": {"type": "array", "items": item},
                               "ownership_percent": {"anyOf": [{"type": "number"}, {"type": "null"}]}}}

    def _ask(self, rt: RedactedText, images) -> str | None:
        text = "\n\n".join(f"--- Page {i} ---\n{page}" for i, page in enumerate(rt.pages, start=1))
        labels = "\n".join(f"{k}: {label_name(self.labels, k)}" for k in self.keys)
        types = "\n".join(f"{code}: {t.description}" for code, t in self.type_choices.items())
        content: str | list = text
        if images:  # each picture after a line naming its page, and the blanked-out text last
            content = []
            for page, jpeg in images:
                content.append({"type": "text", "text": f"--- Page {page} (picture; not blanked) ---"})
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                            "data": base64.b64encode(jpeg).decode("ascii")}})
            content.append({"type": "text", "text": text})
        request = dict(model=self.model, max_tokens=16000,
                       output_config={"effort": "medium", "format": {"type": "json_schema", "schema": self._schema()}},
                       system=SYSTEM.format(labels=labels, doc_types=types, pictures=PICTURES if images else ""),
                       messages=[{"role": "user", "content": content}])
        if self.model in FALLBACK_MODELS:  # re-run on another model if this one declines
            response = self.client.beta.messages.create(**request, betas=[FALLBACK_BETA], fallbacks="default")
        else:
            response = self.client.messages.create(**request)
        if response.stop_reason == "refusal":
            return None
        return next((b.text for b in response.content if b.type == "text"), None)

    def extract(self, rt: RedactedText, doc_id: str, images: list[tuple[int, bytes]] | None = None, *,
                on_send=None) -> ExtractResult:
        """``images`` are (page number, JPEG bytes) of scanned pages, only when Settings allows them; they can't be
        blanked out, so they're dropped unless this reader was made with ``page_images``. ``on_send`` is called with
        their page numbers just before they are sent (for the audit log).

        The AI never stops an import: if the request with pictures fails it asks again with the text only, and if
        that fails too the document is left for entering by hand (A3). ``facts["ai_picture_pages"]`` lists the
        pages it read as pictures."""
        rt = require_redacted(rt)
        result = ExtractResult()
        if find_sensitive(rt.text):
            result.notes.append(_note("High", "A2", "The AI reader found an identifier left in the text and sent "
                                      "nothing. Enter this document's figures by hand and tell the privacy "
                                      "officer.", doc_id))
            return result
        if not self.page_images:
            images = None  # defence in depth: the switch is checked here as well as in the pipeline
        pictures = [page for page, _jpeg in images] if images else []
        if pictures and on_send is not None:
            on_send(pictures)
        raw, errors = None, _api_errors()
        try:
            raw = self._ask(rt, images)
        except errors:
            if pictures:
                result.doubts.append(f"Page(s) {_pages(pictures)} went to the AI reader as pictures, but it couldn't "
                                     "take them, so it read the text only. Enter those pages' figures by hand.")
                pictures = []
                try:
                    raw = self._ask(rt, None)
                except errors:
                    raw = None
        if pictures:
            result.facts["ai_picture_pages"] = pictures
        try:
            answer = json.loads(raw) if raw else None
            items = answer["figures"] if answer is not None else None
        except (ValueError, TypeError, KeyError):
            answer, items = None, None
        doc_type = answer.get("doc_type") if isinstance(answer, dict) else None
        if isinstance(doc_type, str) and doc_type in self.type_choices:
            result.facts["ai_doc_type"] = doc_type
        share = answer.get("ownership_percent") if isinstance(answer, dict) else None
        if isinstance(share, (int, float)) and not isinstance(share, bool) and 0 < share <= 100:
            share = Decimal(str(share)).quantize(Decimal("0.01")).normalize()  # 50, 33.33: never 1E-7
            if share > 0:
                result.facts["ownership_share"] = Decimal(f"{share:f}")  # a suggestion for the Rental page
        figures, problems = figures_from_items(items or [], self.keys, doc_id, len(rt.pages), "AI")
        printed = printed_amounts(rt.text)
        for f in figures:
            if abs(f.amount) in printed:
                f.notes = TEXT_MATCH
        result.figures.extend(figures)
        if items is None or problems:
            result.notes.append(_note("Medium", "A3", "The AI reader couldn't give a usable answer for some or all "
                                      "of this document. Enter anything missing by hand.", doc_id))
        elif not items:  # said plainly, so the document doesn't look as if the AI was never asked
            result.doubts.append(NOTHING_FOUND)
        result.parse_status = "partial" if result.figures else "manual_needed"
        return result


class AiReaderUnavailable(Exception):
    pass


def ai_reader_from_settings(tra_home: Path, env: Mapping[str, str], client=None) -> AiReader | None:
    """An AiReader when Sawnx's setting is on, otherwise None. The key comes from the environment or, like
    TRA_HOME, from the value saved for the Windows account; switched on without a key says so."""
    from ... import settings as tra_settings
    from ...web.app_settings import load_app_settings

    app = load_app_settings(tra_home)
    if not app.ai_reader:
        return None
    key = (env.get("ANTHROPIC_API_KEY") or "").strip() or tra_settings.saved_user_variable("ANTHROPIC_API_KEY").strip()
    if not key:
        raise AiReaderUnavailable("The AI reader is switched on, but there's no ANTHROPIC_API_KEY saved for this "
                                  "Windows account, so it didn't read anything. Set it (see the README), then import "
                                  "again.")
    if client is None:
        try:
            import anthropic
        except ImportError:
            raise AiReaderUnavailable("The AI reader is switched on but its library isn't installed. Run: "
                                      ".venv\\Scripts\\pip install -e \".[ai]\"") from None
        # Two minutes a request and one retry, so a slow or unreachable service holds an import up only briefly.
        client = anthropic.Anthropic(api_key=key, timeout=120, max_retries=1)
    return AiReader(client, page_images=app.page_images_in_use)
