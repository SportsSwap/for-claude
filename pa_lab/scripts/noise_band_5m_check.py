"""D68: the two noise-band versions with exits judged only on 5-minute closes."""
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

_orig = ns.exits_vec


def exits_5m(A, F, d, e, side, v):
    """As ns.exits_vec, but an exit can only happen on a bar that closes a 5-minute bar."""
    C = A["close"][d][:, : nb.EXIT_BAR + 1]
    W = F["vwap"][d][:, : nb.EXIT_BAR + 1]
    a = F["atr_daily"][d][:, None]
    cols = np.arange(nb.EXIT_BAR + 1)[None, :]
    live = (cols > e[:, None]) & ((cols + 1) % 5 == 0)
    path = side[:, None] * (C - C[np.arange(len(d)), e][:, None])
    hit = np.zeros_like(live)
    if v["exit"] == "vwap_cross":
        hit |= live & (side[:, None] * (C - W) < 0)
    elif v["exit"].startswith("trail"):
        trig = float(v["exit"].split("_")[1])
        best = np.maximum.accumulate(np.where(live, path, -np.inf), axis=1)
        hit |= live & (best >= trig * a) & (path <= 0.5 * best)
    elif v["exit"] == "hold" and v.get("trail_4_stop_10"):
        pass
    if v["stop_atr"] is not None:
        hit |= live & (path <= -v["stop_atr"] * a)
    return np.where(hit.any(axis=1), np.argmax(hit, axis=1), nb.EXIT_BAR)


def main() -> int:
    m = nb.load_minutes()
    days, A, _ = nb.rth_grid(m)
    F = nb.features(days, A)
    res = {}
    for name, v in ny.VERSIONS.items():
        for mode, fn in (("1m_exits", _orig), ("5m_exits", exits_5m)):
            ns.exits_vec = fn
            tr = ns.score(days, A, F, ns.sigma_for(A, F, v["band_days"]), v)
            tr = tr[tr["day"].map(nb.period_of).notna()]
            per = tr["day"].map(nb.period_of)
            r = {}
            for k in nb.PERIODS:
                cal = [x for x in days if nb.period_of(x) == k]
                daily = tr[per == k].set_index("day")["qqq"].reindex(cal, fill_value=0.0)
                eq = daily.cumsum()
                r[k] = {"trades": int((per == k).sum()), "qqq_sum_pct": round(float(daily.sum()), 1),
                        "sharpe": round(float(daily.mean() / daily.std(ddof=1) * 252 ** 0.5), 2),
                        "max_dd_pct": round(float((eq.cummax().clip(lower=0) - eq).max()), 1)}
            res[f"{name}:{mode}"] = r
    ns.exits_vec = _orig
    io.write_json({**res, **stamp()}, P.results() / "noise_band" / "five_minute_exits.json")
    rows = [{"version": k, "period": p, **x} for k, v in res.items() for p, x in v.items()]
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
