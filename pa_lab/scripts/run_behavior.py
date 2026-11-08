"""Run every behavior test on NQ (claim) and ES (replication) discovery.

    LAB_ROOT=... python scripts/run_behavior.py [--only name,name]

Writes results/behavior/<test>.csv (one row per market x chart, plus pooled)
and results/behavior/verdicts.csv + verdicts.md (one line per test).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import behavior, io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
from lab.market import Market  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    names = [n for n in behavior.TESTS if not a.only or n in a.only.split(",")]
    markets = {"NQ": Market.load("NQ"), "ES": Market.load("ES")}
    out = P.results() / "behavior"
    verdicts = []
    for name in names:
        t0 = time.time()
        table, v = behavior.run_test(name, markets)
        io.write_table(table, out / f"{name}.csv")
        verdicts.append(v)
        print(f"{name:24s} {v['verdict']:6s} NQ {v['nq_point']:+.4f} [{v['nq_lo']:+.4f}, {v['nq_hi']:+.4f}] "
              f"ES {v['es_point']:+.4f}  ({time.time() - t0:.0f}s)", flush=True)
    vd = pd.DataFrame(verdicts)
    if a.only and (out / "verdicts.csv").exists():
        old = io.read_table(out / "verdicts.csv")
        vd = pd.concat([old[~old.test.isin(vd.test)], vd]).set_index("test").loc[
            [n for n in behavior.TESTS if n in set(old.test) | set(vd.test)]].reset_index()
    io.write_table(vd, out / "verdicts.csv")
    lines = ["# Behavior test verdicts", "", f"Provenance: {stamp()}", "",
             "| test | verdict | NQ pooled (95% CI) | ES pooled | era 1 / era 2 | claim |", "|---|---|---|---|---|---|"]
    for r in vd.itertuples():
        lines.append(f"| `{r.test}` | **{r.verdict}** | {r.nq_point:+.4f} ({r.nq_lo:+.4f}, {r.nq_hi:+.4f}) | "
                     f"{r.es_point:+.4f} | {r.nq_era1:+.4f} / {r.nq_era2:+.4f} | {r.claim} {r.why} |")
    (out / "verdicts.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
