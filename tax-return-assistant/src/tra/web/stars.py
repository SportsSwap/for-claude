"""Starred documents (My Starred): TRA_HOME/sawnx_stars.json, a list of "CODE/YEAR/DOCID" keys."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..privacy.guard import atomic_write_text, check_value

LOCATION = "sawnx_stars.json"
KEY = re.compile(r"^([A-Z0-9]{2,12})/(\d{4}|PERM|CORR)/(D\d{3,})$")


def stars_path(tra_home: Path) -> Path:
    return Path(tra_home) / "sawnx_stars.json"


def load_stars(tra_home: Path) -> set[str]:
    path = stars_path(tra_home)
    return set(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()


def set_stars(tra_home: Path, keys: list[str], starred: bool) -> None:
    if any(not KEY.match(k) for k in keys):
        raise ValueError("That isn't a document Sawnx knows.")
    stars = load_stars(tra_home)
    stars = stars | set(keys) if starred else stars - set(keys)
    data = sorted(stars)
    check_value(data, LOCATION)
    atomic_write_text(stars_path(tra_home), json.dumps(data, indent=2), LOCATION, prechecked=True)
