"""Internal label keys and their ATO return items. See config/labels.yaml."""

from __future__ import annotations

from dataclasses import dataclass
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


def load_labels(path: Path | None = None) -> dict[str, LabelDef]:
    raw = yaml.safe_load((path or CONFIG_DIR / "labels.yaml").read_text(encoding="utf-8"))
    defs = [
        LabelDef(key=key, item=str(spec["item"]), label=str(spec.get("label", "")),
                 letter_verified=bool(spec.get("letter_verified", False)), description=spec["description"],
                 role=spec["role"], tab=spec["tab"], order=int(spec["order"]), computed=bool(spec.get("computed", False)))
        for key, spec in raw.items()
    ]
    return {d.key: d for d in sorted(defs, key=lambda d: d.order)}


def figure_allowed(label: LabelDef) -> bool:
    return label.role not in NOT_FIGURE_ROLES and not label.computed
