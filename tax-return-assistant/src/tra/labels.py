"""Internal label keys and their ATO return items. See config/labels.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .paths import CONFIG_DIR

# Keys a figure may never carry: pre-fill information and the computed CGT labels.
NOT_FIGURE_ROLES = frozenset({"info"})


@dataclass(frozen=True)
class LabelDef:
    key: str
    item: str
    label: str
    letter_verified: bool
    description: str
    role: str
    tab: str
    order: int
    computed: bool = False
    part_of: str | None = None  # a breakdown of another label (a rental expense category of Item 21 U)


def return_key(labels: dict[str, LabelDef], key: str) -> str:
    """The return label a figure counts towards: its own, or the one it is part of."""
    d = labels.get(key)
    return d.part_of if d is not None and d.part_of else key


def load_labels(path: Path | None = None) -> dict[str, LabelDef]:
    """Read once and kept until the file changes (every page needs them); each caller gets its own dict."""
    path = Path(path or CONFIG_DIR / "labels.yaml")
    return dict(_load_labels(str(path), path.stat().st_mtime_ns))


@lru_cache(maxsize=8)
def _load_labels(path: str, _mtime: int) -> dict[str, LabelDef]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defs = [
        LabelDef(key=key, item=str(spec["item"]), label=str(spec.get("label", "")),
                 letter_verified=bool(spec.get("letter_verified", False)), description=spec["description"],
                 role=spec["role"], tab=spec["tab"], order=int(spec["order"]), computed=bool(spec.get("computed", False)),
                 part_of=spec.get("part_of"))
        for key, spec in raw.items()
    ]
    by_key = {d.key: d for d in defs}
    for d in defs:
        parent = by_key.get(d.part_of) if d.part_of else None
        if d.part_of and (parent is None or parent.part_of or (parent.item, parent.label, parent.role, parent.tab)
                          != (d.item, d.label, d.role, d.tab)):
            raise ValueError(f"labels.yaml: {d.key} is part_of {d.part_of!r}, which must be a label of its own with "
                             "the same item, letter, role and tab.")
    return {d.key: d for d in sorted(defs, key=lambda d: d.order)}


load_labels.cache_clear = _load_labels.cache_clear


def figure_allowed(label: LabelDef) -> bool:
    return label.role not in NOT_FIGURE_ROLES and not label.computed
