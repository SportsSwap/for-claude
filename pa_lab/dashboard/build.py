"""Build the presenter deck from saved result files only.

    LAB_ROOT=... python -m dashboard.build

Writes into <LAB_ROOT>/results/dashboard/:
  deck.html          one offline file, data and charts inline
  provenance.json    every number on screen: file, row, column, format, value, text
  pages.json/.md     every page's title, subtitle, numbers and conclusion
  pending.json       pages not drawn yet and the files they wait for

Refuses to build (exit 1, nothing written) if a second reader disagrees with
any value, if any digit on a page has no source, or if an em/en dash appears.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from . import pages as pg
from .provenance import Provenance, ProvenanceError, unsourced_digits
from .render import Page, document

DASHES = ("—", "–")


class BuildRefused(RuntimeError):
    pass


def lab_root() -> Path:
    return Path(os.environ.get("LAB_ROOT", Path(__file__).resolve().parent.parent))


ORDINAL_CLASSES = {"badge-n"}   # amber card badges: 1, 2, 3 ... ordinals, not measurements


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.stack = []
        self.out = []

    VOID = {"meta", "link", "br", "img", "input", "hr", "source", "wbr", "area", "base", "col"}

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        classes = set((dict(attrs).get("class") or "").split())
        hide = tag in ("script", "style", "title") or bool(classes & ORDINAL_CLASSES)
        self.stack.append(hide)
        self.skip += hide

    def handle_endtag(self, tag):
        if self.stack:
            self.skip -= self.stack.pop()

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.out.append(data.strip())


def visible_html_text(html: str) -> list[str]:
    p = _Text()
    p.feed(html)
    return p.out


def collect(results: Path):
    prov = Provenance(results)
    built: list[Page] = []
    pending = []
    for spec in pg.specs(prov):
        missing = [f for f in spec.needs if not prov.exists(f)]
        if missing:
            pending.append({"page": spec.key, "section": spec.section, "waiting_for": missing})
            continue
        n0 = len(prov.records)
        prov.page = spec.key
        try:
            built.append(spec.build(prov))
        except pg.Pending as e:
            del prov.records[n0:]
            pending.append({"page": spec.key, "section": spec.section, "waiting_for": [str(e)]})
    return prov, built, pending


def check(prov: Provenance, built: list[Page], html: str) -> None:
    prov.verify()
    bad = {}
    for p in built:
        b = unsourced_digits(p.visible(), prov.texts(p.key), pg.FIXED_LABELS)
        if b:
            bad[p.key] = b
    if bad:
        raise BuildRefused(f"digits without a source: {json.dumps(bad, indent=1)}")
    seen = visible_html_text(html)
    for p in built:  # the scan must actually see every page's title, or it proves nothing
        if p.title not in seen:
            raise BuildRefused(f"HTML text scan did not see the title of {p.key}")
    b = unsourced_digits(seen, prov.texts(), pg.FIXED_LABELS)
    if b:
        raise BuildRefused(f"digits without a source in the page HTML: {b}")
    for p in built:
        for s in p.visible():
            if any(d in s for d in DASHES):
                raise BuildRefused(f"em/en dash on page {p.key}: {s!r}")
    if any(d in html for d in DASHES):
        raise BuildRefused("em/en dash in the HTML")


def build(root: Path | None = None) -> dict:
    root = root or lab_root()
    results = root / "results"
    synthetic = root.name == "synthetic_lab"
    prov, built, pending = collect(results)
    label, banner = "", ""
    if synthetic:
        label, banner = "Synthetic data demo", "Synthetic data demo · real NQ and ES files not yet ingested"
    elif (results / "data_source.json").exists():   # a saved result written by the run, never data/
        src = json.loads((results / "data_source.json").read_text())
        label, banner = src["label"], src["banner"]
    if banner and built:
        built[0].banner = banner
    html = document(built, label, "Price Action Lab")
    check(prov, built, html)                       # raises before anything is written
    out = results / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    (out / "deck.html").write_text(html)
    prov.dump(out / "provenance.json")
    plist = [{"n": i + 1, "key": p.key, "section": p.section, "title": p.title, "subtitle": p.subtitle,
              "numbers": prov.texts(p.key), "conclusion": p.conclusion,
              "verdict": p.verdict} for i, p in enumerate(built)]
    (out / "pages.json").write_text(json.dumps(plist, indent=1) + "\n")
    md = ["# Deck pages", "", f"Data: {label or 'as ingested'}", ""]
    for x in plist:
        md += [f"## {x['n']}. {x['title']}", "", f"- section: {x['section']}", f"- subtitle: {x['subtitle']}",
               f"- numbers: {', '.join(x['numbers']) or '-'}", f"- conclusion: {x['conclusion'] or '-'}",
               f"- verdict: {x['verdict'] or '-'}", ""]
    (out / "pages.md").write_text("\n".join(md))
    (out / "pending.json").write_text(json.dumps(pending, indent=1) + "\n")
    return {"pages": len(built), "pending": pending, "numbers": len(prov.records), "out": str(out)}


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        r = build()
    except (BuildRefused, ProvenanceError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    print(f"built {r['pages']} pages, {r['numbers']} sourced values -> {r['out']}/deck.html")
    for p in r["pending"]:
        print(f"  pending {p['page']}: {', '.join(p['waiting_for'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
