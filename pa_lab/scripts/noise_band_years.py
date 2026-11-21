"""D67: year-by-year results for the rules as written and the pick made on 2013-2021 (D66)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lab import io  # noqa: E402
from lab.config import P, stamp  # noqa: E402
import noise_band_qqq as nb  # noqa: E402
import noise_band_search as ns  # noqa: E402

VERSIONS = {
    "as_written": dict(band_mult=1.25, band_days=20, or_offset_atr=0.3, vwap=True, interval=10, last_check="14:00", exit="hold", stop_atr=None),
    "picked_on_2013_2021": dict(band_mult=1.25, band_days=20, or_offset_atr=0.15, vwap=False, interval=30, last_check="14:00", exit="vwap_cross", stop_atr=0.5),
}


def main() -> int:
    out = P.results() / "noise_band"
    m = nb.load_minutes()
    days, A, _ = nb.rth_grid(m)
    F = nb.features(days, A)
    res, tables = {}, []
    for name, v in VERSIONS.items():
        tr = ns.score(days, A, F, ns.sigma_for(A, F, v["band_days"]), v)
        tr = tr[tr["day"].map(nb.period_of).notna()]
        tr["year"] = tr["day"].map(lambda x: x.year)
        y = tr.groupby("year").agg(trades=("qqq", "size"), qqq_pct=("qqq", "sum"), win=("qqq", lambda s: (s > 0).mean()),
                                   opt1_1c=("opt1", "sum"), opt3_1c=("opt3", "sum")).round(3)
        y.insert(0, "version", name)
        tables.append(y.reset_index())
        cal = [x for x in days if nb.period_of(x)]
        daily = tr.set_index("day")["qqq"].reindex(cal, fill_value=0.0)
        eq = daily.cumsum()
        res[name] = {"trades": int(len(tr)), "qqq_sum_pct": round(float(daily.sum()), 1),
                     "sharpe": round(float(daily.mean() / daily.std(ddof=1) * 252 ** 0.5), 2),
                     "max_drawdown_pct": round(float((eq.cummax().clip(lower=0) - eq).max()), 1),
                     "years_positive": int((y["qqq_pct"] > 0).sum()), "years": int(len(y))}
        io.write_table(tr.drop(columns=["year"]), out / f"trades_{name}_qqq.csv")
    t = pd.concat(tables, ignore_index=True)
    io.write_table(t, out / "by_year_two_versions.csv")
    io.write_json({**res, "versions": VERSIONS, **stamp()}, out / "two_versions.json")
    pd.set_option("display.width", 200)
    print(t.to_string(index=False))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
