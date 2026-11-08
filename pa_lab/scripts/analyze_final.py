"""Read-only analysis of the saved final-test results (never the sealed data).

    python scripts/analyze_final.py   ->  results/analysis/final_summary.json

1. Did candidates hold up more often than versions at large? One-sided
   binomial test of the candidates' held count against the all-versions
   held share, per market.
2. Did each working setup beat matched random trades on the market where it
   worked in discovery? A tally over those (setup, chart, market) rows only.
"""
from __future__ import annotations

import sys
from pathlib import Path

from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
from lab.final_test import load_final_results, read_selections  # noqa: E402

ALPHA = 0.05


def main() -> int:
    load_final_results()                          # checks every final file against DONE.json
    fin = P.results() / "final"
    share = io.read_table(fin / "share_held.csv")
    out = {"alpha": ALPHA, "candidates": {}, "working": {}}
    for m in ("NQ", "ES"):
        s = share[share.market == m].set_index("group")
        k, n = int(s.loc["candidates", "held"]), int(s.loc["candidates", "versions"])
        base = float(s.loc["all", "share_held"])
        p = binomtest(k, n, base, alternative="greater").pvalue if n else float("nan")
        out["candidates"][m] = {"held": k, "versions": n, "share": k / n if n else None,
                                "all_share": base, "p_value": p, "beats_all": bool(n and p < ALPHA)}
    _, working, _ = read_selections()
    wv = io.read_table(fin / "working_vs_random.csv")
    rows = []
    for w in working:
        r = wv[(wv.market == w["market"]) & (wv.setup == w["setup"]) & (wv.setup_chart == w["chart"])]
        if len(r) == 1:
            rows.append({**w, "p_value": float(r.p_value.iloc[0]), "beats_random": bool(r.beats_random.iloc[0]),
                         "real_net": float(r.real_net.iloc[0])})
    beat = sum(r["beats_random"] for r in rows)
    out["working"] = {"tested": len(rows), "beat_random": beat,
                      "verdict": "true" if rows and beat == len(rows) else ("split" if beat else "false"),
                      "rows": rows}
    out["candidates_verdict"] = "true" if out["candidates"]["NQ"]["beats_all"] and \
        out["candidates"]["ES"]["share"] is not None and \
        out["candidates"]["ES"]["share"] > out["candidates"]["ES"]["all_share"] else "false"
    io.write_json({**out, **stamp()}, P.results() / "analysis" / "final_summary.json")
    print(io.read_json(P.results() / "analysis" / "final_summary.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
