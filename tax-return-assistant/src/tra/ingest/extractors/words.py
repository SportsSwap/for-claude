"""Suggesting a label from the words a client used (config/sheet_words.yaml).

Used for clients' own spreadsheets and the text of their emails. A suggestion is only made when the
words point to exactly one label; anything else is left for a person, never guessed.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ...paths import CONFIG_DIR

PRIVATE = "_private"


def load_sheet_words(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    raw = yaml.safe_load((path or CONFIG_DIR / "sheet_words.yaml").read_text(encoding="utf-8"))
    return {key: tuple(_normalise(w) for w in words) for key, words in raw.items()}


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9&]+", " ", str(text).lower()).split())


def _spans(text: str, phrase: str) -> list[tuple[int, int]]:
    return [m.span() for m in re.finditer(rf"\b{re.escape(phrase)}s?\b", text)]


def match_labels(text: str, words: dict[str, tuple[str, ...]]) -> list[str]:
    """Label keys the text points to. A match inside a longer match for another label doesn't count."""
    text = _normalise(text)
    if any(_spans(text, w) for w in words.get(PRIVATE, ())):
        return []
    hits = [(key, span) for key, phrases in words.items() if key != PRIVATE
            for phrase in phrases for span in _spans(text, phrase)]
    keys = []
    for key, (start, end) in hits:
        covered = any(other != key and s <= start and end <= e and (e - s) > (end - start)
                      for other, (s, e) in hits)
        if not covered and key not in keys:
            keys.append(key)
    return keys
