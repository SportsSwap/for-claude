"""Numbered amendments: the only way to change a locked threshold or dial.

    python -m lab.amend "A3: widen gap threshold because ..."   # after editing the file
    python -m lab.amend --baseline                                 # amendment 0 (lab setup)

The amendment records the new sha256 of every locked file and the time it was
written. Results carry the amendment number they ran under (config.stamp()),
so a result older than an amendment can never be mistaken for one under it.
Write the amendment before you look at anything it affects.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from .config import LOCKED_FILES, P, code_root, sha256_file


def current_hashes() -> dict:
    return {rel: sha256_file(code_root() / rel) for rel in LOCKED_FILES if (code_root() / rel).exists()}


def record(reason: str, baseline: bool = False) -> dict:
    path = P.config() / "amendments.json"
    ledger = json.loads(path.read_text()) if path.exists() else {"amendments": []}
    if baseline and ledger["amendments"]:
        raise SystemExit("baseline already recorded")
    if not baseline and not ledger["amendments"]:
        raise SystemExit("record the baseline first: python -m lab.amend --baseline")
    hashes = current_hashes()
    if ledger["amendments"] and ledger["amendments"][-1]["hashes"] == hashes:
        raise SystemExit("nothing changed in the locked files; no amendment needed")
    n = len(ledger["amendments"])
    prev = ledger["amendments"][-1]["hashes"] if ledger["amendments"] else {}
    entry = {"n": n, "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "reason": reason, "changed": sorted(k for k in hashes if prev.get(k) != hashes[k]),
             "hashes": hashes}
    ledger["amendments"].append(entry)
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    md = code_root() / "amendments.md"
    with open(md, "a") as f:
        f.write(f"\n## Amendment {n} - {entry['utc']}\n\n{reason}\n\nChanged: "
                f"{', '.join(entry['changed']) or '-'}\n")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reason", nargs="?")
    ap.add_argument("--baseline", action="store_true")
    a = ap.parse_args(argv)
    if a.baseline:
        e = record(a.reason or "Baseline: thresholds and rulebook as set up by the data prompt.", True)
    elif not a.reason:
        raise SystemExit("give the reason for the amendment")
    else:
        e = record(a.reason)
    print(json.dumps(e, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
