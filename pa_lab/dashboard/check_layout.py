"""Run the headless-Chromium layout check and confirm the screenshots match the page list.

    LAB_ROOT=... python -m dashboard.check_layout
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .build import lab_root


def run(out: Path | None = None) -> dict:
    out = out or lab_root() / "results" / "dashboard"
    js = Path(__file__).with_name("check_layout.js")
    for old in (out / "screens").glob("page_*.png") if (out / "screens").exists() else []:
        old.unlink()
    proc = subprocess.run(["node", str(js), str(out / "deck.html"), str(out)], capture_output=True, text=True)
    if not (out / "layout_report.json").exists():
        raise RuntimeError(f"layout check did not run: {proc.stderr[-2000:]}")
    rep = json.loads((out / "layout_report.json").read_text())
    plist = json.loads((out / "pages.json").read_text())
    shots = sorted((out / "screens").glob("page_*.png"))
    match = (len(shots) == len(plist) == len(rep["pages"])
             and all(a["title"] == b["title"] and a["key"] == b["key"] for a, b in zip(rep["pages"], plist)))
    rep["screenshots_match_page_list"] = bool(match)
    rep["clean"] = bool(match and all(not v["problems"] for v in rep["sizes"].values()))
    (out / "layout_report.json").write_text(json.dumps(rep, indent=1) + "\n")
    return rep


def main() -> int:
    rep = run()
    for size, v in rep["sizes"].items():
        print(f"{size}: {v['pages']} pages, {len(v['problems'])} problems")
        for p in v["problems"][:40]:
            print("   ", p)
    print("screenshots match page list:", rep["screenshots_match_page_list"])
    return 0 if rep["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
