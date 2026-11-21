"""D69: both noise-band versions, unchanged, on the S&P 500 CFD minutes (stand-in for SPY)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
import noise_band_qqq as nb  # noqa: E402
import noise_band_search as ns  # noqa: E402
import noise_band_years as ny  # noqa: E402


def main() -> int:
    m = nb.load_minutes("ES")
    days, A, _ = nb.rth_grid(m)
    F = nb.features(days, A)
    res, rows = {}, []
    for name, v in ny.VERSIONS.items():
        tr = ns.score(days, A, F, ns.sigma_for(A, F, v["band_days"]), v)
        tr = tr[tr["day"].map(nb.period_of).notna()].sort_values("day")
        per = tr["day"].map(nb.period_of)
        r = {}
        for k in nb.PERIODS:
            cal = [x for x in days if nb.period_of(x) == k]
            daily = tr[per == k].set_index("day")["qqq"].reindex(cal, fill_value=0.0)
            eq = daily.cumsum()
            r[k] = {"trades": int((per == k).sum()), "sum_pct": round(float(daily.sum()), 1),
                    "sharpe": round(float(daily.mean() / daily.std(ddof=1) * 252 ** 0.5), 2),
                    "max_dd_pct": round(float((eq.cummax().clip(lower=0) - eq).max()), 1)}
            rows.append({"version": name, "period": k, **r[k]})
        x = tr["qqq"].to_numpy() / 100
        yrs = tr["day"].map(lambda d: d.year).to_numpy()
        r["by_year_pct"] = {int(y): round(float(x[yrs == y].sum() * 100), 1) for y in sorted(set(yrs))}
        r["compounded_3x_10k"] = round(float(10000 * np.prod(1 + 3 * x)))
        res[name] = r
    io.write_json({**res, **stamp()}, P.results() / "noise_band" / "sp500_check.json")
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps({k: {"by_year_pct": v["by_year_pct"], "3x": v["compounded_3x_10k"]} for k, v in res.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
