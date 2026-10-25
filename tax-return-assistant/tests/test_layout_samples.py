"""Every layout Sawnx has learned is proved by a made-up copy of it (tests/layout_samples/<layout>.yaml).

A copy has `text:` (the layout's wording and order, invented names and numbers; pages split by a line holding only
`---page---`) and `figures:` (each `label` and `amount` the layout must read, in order). A layout file without a
copy fails here, so nothing is learned without proof. The repo hygiene test scans the copies for identifiers.
"""

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from tra.ingest.layouts import LAYOUTS_DIR, load_layouts, match_layout, matching_layouts, read_with_layout
from tra.privacy.redact import redact_pages

SAMPLES = Path(__file__).parent / "layout_samples"
LAYOUTS, PROBLEMS = load_layouts()


def test_every_layout_file_is_valid():
    assert PROBLEMS == []


def test_every_layout_has_a_made_up_copy():
    learned = {p.stem for p in LAYOUTS_DIR.glob("*.yaml")}
    copies = {p.stem for p in SAMPLES.glob("*.yaml")} if SAMPLES.is_dir() else set()
    assert learned - copies == set(), "each layout needs tests/layout_samples/<layout>.yaml"
    assert copies - learned == set(), "a made-up copy without a layout file"


@pytest.mark.parametrize("layout", LAYOUTS, ids=lambda lay: lay.slug)
def test_layout_reads_its_copy(layout):
    sample = yaml.safe_load((SAMPLES / f"{layout.slug}.yaml").read_text(encoding="utf-8"))
    rt = redact_pages([page.strip("\n") for page in sample["text"].split("---page---")])
    assert matching_layouts(rt, LAYOUTS) == [layout], "the copy must be recognised as this layout and no other"
    assert match_layout(rt, LAYOUTS) is layout
    result = read_with_layout(rt, layout, "D001")
    assert [(f.label_key, f.amount) for f in result.figures] == [
        (f["label"], Decimal(str(f["amount"]))) for f in sample["figures"]]
    assert result.doubts == sample.get("doubts", [])
