"""Layouts Sawnx has learned: one settings file each in config/layouts/, read by this one shared reader.

A layout file says how to recognise a layout (words that appear in it) and which line holds which amount. It is
written in a teaching session (see .claude/skills/teach-layouts) from a document's blanked-out text, and proved
by a made-up copy in tests/layout_samples/. A file with a mistake is skipped and reported, never trusted.
Layouts run before the general readers; documents no layout recognises are read exactly as before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from ..labels import figure_allowed, load_labels
from ..paths import CONFIG_DIR
from ..privacy.redact import RedactedText
from .classify import load_doc_types
from ..money import format_dollars, round_cents
from .extractors.base import ExtractResult, doc_date, figure, lines, require_redacted

LAYOUTS_DIR = CONFIG_DIR / "layouts"
MIN_MATCH_WORD = 4  # shorter match words ("zq") would recognise almost any document

# A clean amount: optional brackets and minus, optional $, digits (with , thousands) and up to 2 decimals.
_CLEAN = re.compile(r"(\()?(-)?(\$)?(-)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?(\))?")
# Not amounts: dates (also misread ones like 01t07t2026), year ranges, percentages and times.
_NOT_AMOUNT = re.compile(r"\d{1,2}[^\d\s]\d{1,2}[^\d\s]\d{2,4}|\d{4}[^\d\s]\d{1,2}[^\d\s]\d{1,2}"
                         r"|\d{4}[-/–]\d{2}(?:\d{2})?|\(?[\d.,]+%\)?|\d{1,2}:\d{2}(?::\d{2})?(?:am|pm)?", re.I)
# The rest of a thousands figure split by a scan ("$41 720.75").
_THOUSANDS_TAIL = re.compile(r"\d{3}(?:,\d{3})*(?:\.\d{1,2})?\)?")


def _money_like_misread(word: str) -> bool:
    """A word with letters that still looks like money: a scan misreading ("$24s", "S120.00", "1,2O4.50")."""
    bare = word.lstrip("(-")
    return (bare.startswith("$") or bool(re.match(r"[sS]\d", bare))
            or (bool(re.fullmatch(r"[\d,.OolI$()-]+", word)) and bool(re.search(r"[OolI]", word)))
            or bool(re.search(r"\d[,.]\d", word)))


def _value(match: re.Match) -> Decimal:
    opened, minus1, _dollar, minus2, digits, cents, closed = match.groups()
    if minus1 and minus2:
        raise ValueError("two minus signs")
    value = round_cents(Decimal(digits.replace(",", "") + (cents or "")))
    return -value if (opened and closed) or minus1 or minus2 else value


def amount_words(text: str, dollars_only: bool = False) -> list[tuple[str, object]]:
    """(word, amount) for each amount-like word, in order. A word that looks like money but can't be read
    ("$24s", "S120.00", "$41 720.75") comes back with None, keeping its place so the next column can't move into
    it. Dates, ranges, percentages, times and codes aren't amounts. With dollars_only, only amounts written with a
    $ count: other money-like words come back with None, and plain whole numbers (codes) are left out."""
    words = [w.strip(",;:*").rstrip(".") for w in text.split()]
    out, i = [], 0
    while i < len(words):
        word, i = words[i], i + 1
        if not any(c.isdigit() for c in word) or _NOT_AMOUNT.fullmatch(word):
            continue
        clean = _CLEAN.fullmatch(word)
        if clean is None:
            if any(c.isalpha() for c in word) and not _money_like_misread(word):
                continue  # a code or a word, not an amount
            out.append((word, None))
            continue
        dollar = clean.group(3) is not None
        if not (clean.group(5).count(",") or clean.group(6)) and len(clean.group(5)) <= 3 and not clean.group(7):
            split = i
            while split < len(words) and _THOUSANDS_TAIL.fullmatch(words[split]) and (
                    dollar or "." in words[split]):
                split += 1
            if split > i:
                out.append((" ".join(words[i - 1:split]), None))
                i = split
                continue
        if dollars_only and not dollar:
            if clean.group(5).count(",") or clean.group(6):
                out.append((word, None))  # money without its $: perhaps the $ was misread
            continue  # a plain whole number: a code, not a $ amount
        try:
            out.append((word, _value(clean)))
        except ValueError:
            out.append((word, None))
    return out


@dataclass(frozen=True)
class Field:
    label: str  # "" for an unread field
    line: str  # the line starts with these words ("" when contains is used)
    contains: str  # or these words appear anywhere in it
    amount: str | int  # first | last, or N: the Nth amount on the line (a table row)
    description: str
    required: bool
    every: bool
    also: tuple[str, ...] = ()  # one of these words must also be on the line (e.g. a benefit code in a row)
    suggested: bool = False  # the label is only a suggestion (a receipt): Things to check asks for a look
    dollars: bool = False  # only amounts written with a $ count (the default for a numbered amount)
    amounts: int | None = None  # the row must have exactly this many amounts, or it's flagged
    unread: bool = False  # a line this layout doesn't read: an amount on it is flagged for entry by hand


@dataclass(frozen=True)
class Layout:
    slug: str
    name: str
    doc_type: str
    issuer: str
    match_all: tuple[str, ...]
    match_any: tuple[str, ...]
    fields: tuple[Field, ...]
    added: str


def _words(text) -> str:
    return " ".join(str(text or "").lower().split())


def _text(spec: dict, key: str) -> str:
    value = spec.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{key} must be words in quotes, not {value!r}")
    return _words(value)


def _word_list(spec: dict, key: str, where: str) -> tuple[str, ...]:
    value = spec.get(key)
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(w, str) for w in value):
        raise ValueError(f"{where}{key} must be a list of words in quotes, like [\"sample bank\"], not {value!r}")
    return tuple(_words(w) for w in value if _words(w))


def _flag(spec: dict, key: str) -> bool | None:
    value = spec.get(key)
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false, not {value!r}")
    return value


def _number(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 20


def _field(spec: dict, labels) -> Field:
    if not isinstance(spec, dict):
        raise ValueError(f"each field must be a list of settings, not {spec!r}")
    unread = bool(_flag(spec, "unread"))
    label = spec.get("label")
    if not (unread and label is None) and (label not in labels or not figure_allowed(labels[label])):
        raise ValueError(f"{label!r} isn't a label a figure can have")
    line, contains = _text(spec, "line"), _text(spec, "contains")
    name = label or spec.get("description") or "an unread field"
    if bool(line) == bool(contains):
        raise ValueError(f"the field for {name} needs either line or contains (one of them)")
    description = spec.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"description must be words in quotes, not {description!r}")
    if unread and not str(description or "").strip():
        raise ValueError(f"the unread field for {line or contains!r} needs a description")
    amount = spec.get("amount", "last")
    if amount not in ("first", "last") and not _number(amount):
        raise ValueError(f"amount must be first, last or a number from 1 to 20 (the Nth amount), not {amount!r}")
    amounts = spec.get("amounts")
    if amounts is not None and not _number(amounts):
        raise ValueError(f"amounts must be a number from 1 to 20 (how many amounts the row has), not {amounts!r}")
    dollars = _flag(spec, "dollars")
    flags = {key: bool(_flag(spec, key)) for key in ("required", "every", "suggested")}
    return Field(label or "", line, contains, amount,
                 str(description or labels[label].description).strip(), flags["required"], flags["every"],
                 _word_list(spec, "also", ""), flags["suggested"],
                 isinstance(amount, int) if dollars is None else dollars, amounts, unread)


def _layout(path: Path, doc_types, labels) -> Layout:
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise ValueError("isn't valid YAML (check the indenting and quotes)") from None
    except UnicodeDecodeError:
        raise ValueError("isn't saved as plain (UTF-8) text") from None
    if not isinstance(spec, dict):
        raise ValueError("isn't valid YAML (it should be a list of settings)")
    if spec.get("doc_type") not in doc_types:
        raise ValueError(f"doc_type {spec.get('doc_type')} isn't in config/doc_types.yaml")
    match = spec.get("match") or {}
    if not isinstance(match, dict):
        raise ValueError("match must hold all (and optionally any), each a list of words in quotes")
    match_all, match_any = _word_list(match, "all", "match "), _word_list(match, "any", "match ")
    if not match_all:
        raise ValueError("match needs at least one word in all, so it only recognises this layout")
    short = [w for w in match_all + match_any if len(w) < MIN_MATCH_WORD]
    if short:
        raise ValueError(f"match words must be at least {MIN_MATCH_WORD} letters long, not {short[0]!r}")
    fields = spec.get("fields") or []
    if not isinstance(fields, list):
        raise ValueError("fields must be a list")
    fields = tuple(_field(f, labels) for f in fields)
    if not any(not f.unread for f in fields):
        raise ValueError("has no fields")
    return Layout(path.stem, str(spec.get("name") or path.stem), spec["doc_type"], str(spec.get("issuer") or "").strip(),
                  match_all, match_any, fields, str(spec.get("added") or ""))


def _read_layout(path: Path, doc_types, labels) -> Layout:
    try:
        return _layout(path, doc_types, labels)
    except OSError:
        raise ValueError("couldn't be opened (is it a folder, or open in another program?)") from None


def load_layouts(folder: Path | None = None) -> tuple[list[Layout], list[str]]:
    """Every good layout, and a line for each file with a mistake (that file is skipped)."""
    folder = Path(folder or LAYOUTS_DIR)
    if not folder.is_dir():
        return [], []
    doc_types, labels = load_doc_types(), load_labels()
    layouts, problems = [], []
    for path in sorted(folder.glob("*.yaml")):
        try:
            layouts.append(_read_layout(path, doc_types, labels))
        except (ValueError, TypeError, AttributeError) as exc:
            problems.append(f"{path.name}: {exc}")
    return layouts, problems


@lru_cache(maxsize=512)
def _phrase(words: str) -> re.Pattern:
    """Words as whole words: 'bup' isn't in 'bupa', 'overtime' isn't in 'overtimemeal'."""
    return re.compile(r"(?<!\w)" + re.escape(words) + r"(?!\w)")


def matching_layouts(rt: RedactedText, layouts: list[Layout]) -> list[Layout]:
    """Every layout this document matches: all its words appear (and one of its 'any' words), as whole words."""
    text = _words(require_redacted(rt).text)
    return [lay for lay in layouts if all(_phrase(w).search(text) for w in lay.match_all)
            and (not lay.match_any or any(_phrase(w).search(text) for w in lay.match_any))]


def match_layout(rt: RedactedText, layouts: list[Layout]) -> Layout | None:
    """The layout this document is, if any. Most match words wins; a tie goes to the first name (slug)."""
    found = matching_layouts(rt, layouts)
    return min(found, key=lambda lay: (-(len(lay.match_all) + len(lay.match_any)), lay.slug), default=None)


def _rest(line: str, f: Field) -> str | None:
    """The part of the line after the field's words, or None if the line isn't this field's."""
    low = line.lower()
    found = _phrase(f.line or f.contains).search(low)
    if found is None or (f.line and found.start() != 0):
        return None
    if f.also and not any(re.search(r"(?<!\S)" + re.escape(w) + r"(?!\S)", low) for w in f.also):
        return None
    return line[found.end():]


def _pick(words: list, f: Field) -> tuple[tuple[str, object] | None, str]:
    """The field's (word, amount) from a line's amounts, or None and why the row looks wrong."""
    count = len(words)
    unlike = (f"The {f.description} row doesn't look like the others (it has {count} "
              f"amount{'' if count == 1 else 's'}, not {{}}), so it wasn't added. Check it on the document.")
    if f.amounts is not None and count != f.amounts:
        return None, unlike.format(f.amounts)
    if isinstance(f.amount, int):
        if count < f.amount:
            return None, unlike.format(f.amount)
        return words[f.amount - 1], ""
    return (words[0] if f.amount == "first" else words[-1]), ""


def read_with_layout(rt: RedactedText, layout: Layout, doc_id: str) -> ExtractResult:
    rt = require_redacted(rt)
    when = doc_date(rt)
    result = ExtractResult(doc_date=when)
    missing = flagged = found_any = 0
    for f in layout.fields:
        hits = 0
        for page, line in lines(rt):
            rest = _rest(line, f)
            words = amount_words(rest, dollars_only=f.dollars) if rest is not None else []
            if not words:
                continue
            picked, why = _pick(words, f)
            nonzero = picked is None or picked[1] != 0  # a misread or odd row counts: it may not be zero
            if f.unread:
                if nonzero:
                    flagged += 1
                    shown = (" ".join(w for w, _ in words) if picked is None
                             else picked[0] if picked[1] is None else format_dollars(picked[1]))
                    result.doubts.append(f"The document shows {f.description} ({shown}), which this layout doesn't "
                                         "read. Enter it by hand.")
                continue
            hits += 1
            if hits > 1 and not f.every:
                if nonzero:
                    result.doubts.append(f"There's more than one {f.description} line; only the first was read. "
                                         "Check the document.")
                    break
                continue
            found_any += 1
            if picked is None:
                flagged += 1
                result.doubts.append(why)
                continue
            word, value = picked
            if value is None:
                flagged += 1
                result.doubts.append(f'The {f.description} looks misread in the scan ("{word}"), so it wasn\'t '
                                     "added. Check it on the document.")
            elif value != 0:
                who = f"{layout.issuer} – " if layout.issuer else ""
                result.figures.append(figure(f.label, f"{who}{f.description}"[:120], value, doc_id, page, when,
                                             notes="suggested label" if f.suggested else ""))
        if not hits and f.required:
            missing += 1
            result.doubts.append(f"Didn't find the {f.description}.")
    if result.figures:
        result.parse_status = "partial" if missing or flagged else "parsed"
    else:
        result.parse_status = "manual_needed" if missing or flagged or not found_any else "parsed"
    return result


def load_layout(path: Path) -> Layout:
    """One layout file (a candidate being tried). Raises ValueError saying what's wrong with it."""
    path = Path(path)
    try:
        return _read_layout(path, load_doc_types(), load_labels())
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path.name}: {exc}") from None
