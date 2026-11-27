"""The test every bot goes through. Declared before any result was seen:

1. Grid of parameters, evaluated on the IN-SAMPLE window only.
2. Pick the setting with the best *plateau* Sharpe: the average of its own
   in-sample Sharpe and its direct grid neighbours'. A lone spike loses to a
   broad hill. The published/default setting is reported alongside.
3. Report the chosen setting on the OUT-OF-SAMPLE window, never used to pick.
4. Walk-forward: every January, re-pick on all data before that year, trade
   the year; the stitched path is a second out-of-sample test.
5. Deflated Sharpe of the out-of-sample path with trials = grid size, and
   PBO (CSCV, 16 blocks) across the whole grid.
6. Costs doubled: the chosen setting must still make money.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics as M

RESULTS = Path(__file__).resolve().parent.parent / "results"
RESULTS.mkdir(exist_ok=True)


def _grid(space: dict) -> list[dict]:
    keys = list(space)
    return [dict(zip(keys, vals)) for vals in itertools.product(*space.values())]


def _key(p: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in p.items())


def _sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * math.sqrt(252)) if len(r) > 20 and r.std() > 0 else -9.0


def _plateau(space: dict, scores: dict) -> dict:
    keys = list(space)
    best, best_score = None, -1e9
    for p in _grid(space):
        vals = [scores[_key(p)]]
        for k in keys:
            opts = space[k]
            i = opts.index(p[k])
            for j in (i - 1, i + 1):
                if 0 <= j < len(opts):
                    q = dict(p); q[k] = opts[j]
                    vals.append(scores[_key(q)])
        s = float(np.mean(vals))
        if s > best_score:
            best, best_score = p, s
    return best


def study(name: str, fn, space: dict, default: dict, is_end: str,
          benchmark: pd.Series | None = None, wf_min_years: int = 5,
          notes: str = "") -> dict:
    """fn(params: dict, cost_mult: float) -> backtest.Result"""
    grid = _grid(space)
    runs = {_key(p): fn(p, 1.0) for p in grid}
    rets = pd.DataFrame({k: r.returns for k, r in runs.items()}).fillna(0.0)
    is_end_ts = pd.Timestamp(is_end)
    is_scores = {k: _sharpe(rets[k].loc[:is_end_ts]) for k in rets}
    chosen = _plateau(space, is_scores)
    ck, dk = _key(chosen), _key(default)
    if dk not in runs:
        runs[dk] = fn(default, 1.0)
        rets[dk] = runs[dk].returns
    oos_start = is_end_ts + pd.Timedelta(days=1)

    # walk-forward re-optimisation
    years = sorted(set(rets.index.year))
    first_year = years[0] + wf_min_years
    wf_parts, wf_picks = [], {}
    for y in years:
        if y < first_year:
            continue
        hist = rets.loc[:f"{y - 1}-12-31"]
        sc = {k: _sharpe(hist[k]) for k in hist}
        pick = _key(_plateau(space, sc))
        wf_picks[y] = pick
        wf_parts.append(rets[pick].loc[f"{y}-01-01":f"{y}-12-31"])
    wf = pd.concat(wf_parts) if wf_parts else pd.Series(dtype=float)

    # trial-Sharpe variance (daily) for the deflated Sharpe
    sr_daily = np.array([rets[k].loc[:is_end_ts].mean() / rets[k].loc[:is_end_ts].std()
                         for k in rets if rets[k].loc[:is_end_ts].std() > 0])
    sr_var = float(np.var(sr_daily)) if len(sr_daily) > 1 else None
    n_trials = len(grid)

    stress = fn(chosen, 2.0)
    out = {
        "name": name, "notes": notes, "grid_size": n_trials,
        "space": {k: list(map(str, v)) for k, v in space.items()},
        "default": dk, "chosen": ck, "in_sample_end": is_end,
        "in_sample": runs[ck].summary(end=is_end_ts),
        "out_of_sample": runs[ck].summary(start=oos_start, trials=n_trials),
        "default_out_of_sample": runs[dk].summary(start=oos_start),
        "full": runs[ck].summary(),
        "walk_forward": M.summary(wf.loc[oos_start:]) if len(wf) else {},
        "walk_forward_full": M.summary(wf) if len(wf) else {},
        "costs_x2_out_of_sample": stress.summary(start=oos_start),
        "pbo": M.pbo(rets.loc[rets.index >= rets.index[0]]),
        "wf_picks": {str(k): v for k, v in wf_picks.items()},
    }
    oos_r = runs[ck].returns.loc[oos_start:]
    if len(oos_r) > 50:
        out["out_of_sample"]["DSR"] = M.dsr(oos_r, n_trials,
                                            sr_var if sr_var else None)
    if benchmark is not None:
        b = benchmark.reindex(runs[ck].returns.index).fillna(0.0)
        out["benchmark_out_of_sample"] = M.summary(b.loc[oos_start:])
        out["benchmark_full"] = M.summary(b)
        out["corr_to_benchmark_oos"] = float(oos_r.corr(b.loc[oos_start:]))
    eq = pd.DataFrame({"strategy": (1 + runs[ck].returns).cumprod()})
    if benchmark is not None:
        eq["benchmark"] = (1 + benchmark.reindex(eq.index).fillna(0.0)).cumprod()
    if len(wf):
        eq["walk_forward"] = (1 + wf.reindex(eq.index).fillna(0.0)).cumprod()
    slug = name.lower().replace(" ", "_").replace("/", "_")
    eq.to_csv(RESULTS / f"{slug}_equity.csv")
    runs[ck].returns.to_csv(RESULTS / f"{slug}_returns.csv")
    runs[ck].exposure.to_csv(RESULTS / f"{slug}_exposure.csv")
    if runs[ck].trades is not None and len(runs[ck].trades):
        runs[ck].trades.to_csv(RESULTS / f"{slug}_trades.csv", index=False)
    (RESULTS / f"{slug}.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def fmt(out: dict) -> str:
    def pct(x):
        return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x*100:.1f}%"
    def num(x):
        return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"
    o, b, w, s = out["out_of_sample"], out.get("benchmark_out_of_sample", {}), out["walk_forward"], out["costs_x2_out_of_sample"]
    lines = [f"== {out['name']}  chosen [{out['chosen']}]  default [{out['default']}]  grid={out['grid_size']}",
             f"   IS   CAGR {pct(out['in_sample'].get('CAGR'))} Sharpe {num(out['in_sample'].get('Sharpe'))} maxDD {pct(out['in_sample'].get('maxDD'))}",
             f"   OOS  CAGR {pct(o.get('CAGR'))} Sharpe {num(o.get('Sharpe'))} maxDD {pct(o.get('maxDD'))} exp {pct(o.get('exposure'))} "
             f"trades {o.get('trades','—')} win {pct(o.get('win_rate'))} PF {num(o.get('profit_factor'))} DSR {num(o.get('DSR'))}",
             f"   dflt CAGR {pct(out['default_out_of_sample'].get('CAGR'))} Sharpe {num(out['default_out_of_sample'].get('Sharpe'))} maxDD {pct(out['default_out_of_sample'].get('maxDD'))}",
             f"   WF   CAGR {pct(w.get('CAGR'))} Sharpe {num(w.get('Sharpe'))} maxDD {pct(w.get('maxDD'))}",
             f"   2xC  CAGR {pct(s.get('CAGR'))} Sharpe {num(s.get('Sharpe'))}",
             f"   B&H  CAGR {pct(b.get('CAGR'))} Sharpe {num(b.get('Sharpe'))} maxDD {pct(b.get('maxDD'))}  corr {num(out.get('corr_to_benchmark_oos'))}",
             f"   PBO  {num(out['pbo'].get('PBO'))}"]
    return "\n".join(lines)
