"""Self-checks. Each returns ReviewNotes; nothing here changes the return."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..paths import CONFIG_DIR


def load_checks_cfg(path: Path | None = None) -> dict:
    return yaml.safe_load((path or CONFIG_DIR / "checks.yaml").read_text(encoding="utf-8"))


def label_name(labels, key: str) -> str:
    """'Item 10 L Gross interest' style, for messages."""
    d = labels.get(key)
    if d is None:
        return key
    return f"Item {d.item}{' ' + d.label if d.label and len(d.label) <= 2 else ''} {d.description}"


def load_citations(path: Path | None = None) -> dict[str, dict]:
    return yaml.safe_load((path or CONFIG_DIR / "citations.yaml").read_text(encoding="utf-8"))


def run_all_checks(ctx) -> list:
    """Every self-check, ranked. Imported lazily so the check modules can use the helpers above."""
    from .dual_calc import check_dual_calc, check_rates_status
    from .notes import rank_notes
    from .prefill import check_prefill
    from .prior_year import check_prior_year
    from .reconcile import check_reconcile
    from .sanity import check_sanity

    notes = []
    for check in (check_dual_calc, check_rates_status, check_reconcile, check_prefill, check_sanity, check_prior_year):
        notes += check(ctx)
    return rank_notes(notes)
