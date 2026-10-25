"""File names: "[ClientCode] [YYYY-MM-DD] [Kind] - [Issuer].ext", e.g. "SMIT01 2026-03-24 Dividend statement - SAMPLE
MINING LTD.pdf". Readable in a folder or FYI, and still led by the client code, never the client's name.

The issuer comes from what was read (a learned layout, or the payer on the figures). It's left out when it isn't
known, when it holds any word of the client's name (a statement's first line is sometimes the account holder:
"MR J SMITH"), when it looks like an address (a street word, or a state with a postcode), or when it holds a
blanked number. Digits and characters Windows doesn't allow are dropped. The original file name is never
used. Every name is checked by the output guard.
"""

from __future__ import annotations

import re
from datetime import date

from ..privacy.guard import check_text

MAX_ISSUER = 40
# An address, not an issuer: a street word, or a state with a postcode ("NSW school" is a school, "NSW 2000" a place).
_STREET = re.compile(r"\b(?:street|st|road|rd|avenue|ave|lane|drive|dr|court|ct|place|pl|crescent|unit|box)\b", re.I)
_STATE = re.compile(r"\b(?:NSW|VIC|QLD|SA|WA|TAS|NT|ACT)\b", re.I)
_POSTCODE = re.compile(r"(?<!\d)\d{4}(?!\d)")


def _has_client_name(text: str, client_name: str) -> bool:
    """Any word of the client's name of 3+ letters (a surname, a first name), or all of a short name's words."""
    name_words = set(re.findall(r"[a-z]+", client_name.lower()))
    words = set(re.findall(r"[a-z]+", text.lower()))
    return bool(name_words) and (name_words <= words or any(len(w) >= 3 and w in words for w in name_words))


def _looks_like_address(raw: str) -> bool:
    return bool(_STREET.search(raw) or (_STATE.search(raw) and _POSTCODE.search(raw)))


def clean_issuer(issuer: str | None, client_name: str | None = None) -> str:
    text = " ".join(re.sub(r"[^A-Za-z&'.\- ]+", " ", issuer or "").split()).strip(" .-")
    if not re.search(r"[A-Za-z]{2}", text) or "redacted" in (issuer or "").lower():
        return ""
    if (client_name and _has_client_name(text, client_name)) or _looks_like_address(issuer or ""):
        return ""
    if len(text) > MAX_ISSUER:  # cut at a word
        text = text[:MAX_ISSUER] if text[MAX_ISSUER] == " " else text[:MAX_ISSUER].rsplit(" ", 1)[0]
    return text


def kind_name(doc_type: str) -> str:
    from ..ingest.classify import load_doc_types

    found = load_doc_types().get(doc_type)
    return found.short if found else doc_type


def filed_name(client_code: str, income_year: int | None, doc_type: str, doc_date: date, suffix: str,
               existing: set[str], *, issuer: str | None = None, client_name: str | None = None) -> str:
    who = clean_issuer(issuer, client_name)
    stem = f"{client_code} {doc_date.isoformat()} {kind_name(doc_type)}" + (f" - {who}" if who else "")
    ext = suffix.lower()
    name = f"{stem}{ext}"
    n = 2
    while name in existing:
        name = f"{stem} ({n}){ext}"
        n += 1
    check_text(name, "filename")
    return name
