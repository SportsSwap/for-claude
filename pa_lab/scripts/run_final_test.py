"""Prompt 4: the final test.

    # 1. rehearse with the seal closed (last discovery month, shifted in price)
    LAB_ROOT=... python scripts/run_final_test.py rehearse [--n 60]
    # 2. the one run: unlocks once, writes results/final/, refuses to run again
    LAB_ROOT=... LAB_UNLOCK=final_test python scripts/run_final_test.py run
    # 3. pre-flight only (no unlock)
    LAB_ROOT=... python scripts/run_final_test.py check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import final_test as ft  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "rehearse", "run"])
    ap.add_argument("--n", type=int, default=ft.REHEARSAL_VERSIONS, help="rehearsal versions")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        ft.refuse_if_done()
        print(json.dumps(ft.preflight(), indent=2))
        print("pre-flight passed; final results do not exist yet")
        return 0
    if a.cmd == "rehearse":
        s = ft.run("rehearsal", ft.rehearsal_subset(a.n), a.workers)
    else:
        s = ft.run("final", None, a.workers)
    print(json.dumps({k: s[k] for k in ("source", "window", "versions", "errors", "share_held")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
