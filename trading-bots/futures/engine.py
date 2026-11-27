"""Contract-level simulation on 1-minute bars.

Every bot produces a list of trades in index points. Costs are then charged
per contract:
                      $/point  commission round trip   tick
  NQ  (E-mini Nasdaq)   20          $4.50               0.25
  MNQ (Micro Nasdaq)     2          $1.24               0.25
  ES  (E-mini S&P)      50          $4.50               0.25
  MES (Micro S&P)        5          $1.24               0.25
plus 1 tick of slippage on every market or stop fill (a resting limit fills at
its price, but only once price trades 1 tick through it). Commissions follow
IBKR's tiered schedule including exchange and regulatory fees (approximate).

For the validation (deflated Sharpe, PBO, walk-forward) each trade's points
are divided by the index level at entry, which gives the return of holding
one unit of notional, unlevered. Dollars per contract are reported alongside.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine.backtest import Result

SPEC = {
    "NQ": {"usd": 20.0, "comm": 4.50, "tick": 0.25, "base": "NQ"},
    "MNQ": {"usd": 2.0, "comm": 1.24, "tick": 0.25, "base": "NQ"},
    "ES": {"usd": 50.0, "comm": 4.50, "tick": 0.25, "base": "ES"},
    "MES": {"usd": 5.0, "comm": 1.24, "tick": 0.25, "base": "ES"},
}
MICRO = {"NQ": "MNQ", "ES": "MES"}


def cost_points(contract: str, sides_slipped: int = 2, mult: float = 1.0) -> float:
    s = SPEC[contract]
    return mult * (sides_slipped * s["tick"] + s["comm"] / s["usd"])


def walk(hi, lo, cl, i0, i1, side, stop, target):
    """Scan bars i0..i1 (inclusive) for a stop or target. Returns (exit_index, exit_price, reason).
    Stop is assumed hit first when one bar touches both. A bar that opens through
    the stop would fill worse, but intraday 1-minute gaps are negligible here."""
    for i in range(i0, i1 + 1):
        if side > 0:
            if stop is not None and lo[i] <= stop:
                return i, stop, "stop"
            if target is not None and hi[i] >= target:
                return i, target, "target"
        else:
            if stop is not None and hi[i] >= stop:
                return i, stop, "stop"
            if target is not None and lo[i] <= target:
                return i, target, "target"
    return i1, cl[i1], "time"


def to_result(trades: pd.DataFrame, sym: str, days: pd.DatetimeIndex, cost_mult: float = 1.0,
              contract: str | None = None) -> Result:
    """trades: columns entry_time, exit_time, side, entry, exit, slipped (sides with slippage).
    Builds a daily return series on unlevered notional, net of the micro contract's costs."""
    contract = contract or MICRO[sym]
    t = trades.copy()
    if len(t):
        t["gross_pts"] = t["side"] * (t["exit"] - t["entry"])
        t["cost_pts"] = [cost_points(contract, int(s), cost_mult) for s in t["slipped"]]
        t["net_pts"] = t["gross_pts"] - t["cost_pts"]
        t["ret"] = t["net_pts"] / t["entry"]
        t["exit_day"] = pd.to_datetime(t["exit_time"]).dt.normalize()
        daily = t.groupby("exit_day")["ret"].sum()
        daily_pts = t.groupby("exit_day")["net_pts"].sum()
    else:
        daily = pd.Series(dtype=float)
        daily_pts = pd.Series(dtype=float)
    r = daily.reindex(days).fillna(0.0)
    expo = pd.Series(0.0, index=days)
    if len(t):
        held = pd.to_datetime(t["entry_time"]).dt.normalize()
        expo.loc[expo.index.isin(held)] = 1.0
    res = Result(returns=r, gross=r, exposure=expo, turnover=expo * 2,
                 trades=t.assign(entry=pd.to_datetime(t["entry_time"]) if len(t) else [])
                 [["entry", "ret"]] if len(t) else pd.DataFrame(columns=["entry", "ret"]))
    res.points = daily_pts.reindex(days).fillna(0.0)
    res.raw_trades = t
    return res


def dollars(t: pd.DataFrame, contract: str, start=None, end=None, cost_mult: float = 1.0) -> dict:
    """Per-contract dollar stats for trades whose entry falls in [start, end]."""
    if t is None or len(t) == 0:
        return {"trades": 0}
    x = t.copy()
    et = pd.to_datetime(x["entry_time"])
    if start is not None:
        x = x[et >= pd.Timestamp(start)]
    if end is not None:
        x = x[pd.to_datetime(x["entry_time"]) <= pd.Timestamp(end) + pd.Timedelta(days=1)]
    if len(x) == 0:
        return {"trades": 0}
    s = SPEC[contract]
    cost = np.array([cost_points(contract, int(v), cost_mult) for v in x["slipped"]])
    pnl = (x["side"] * (x["exit"] - x["entry"]) - cost) * s["usd"]
    day = pd.to_datetime(x["exit_time"]).dt.normalize()
    d = pnl.groupby(day.values).sum()
    span = (pd.Timestamp(end or d.index.max()) - pd.Timestamp(start or d.index.min())).days / 365.25
    span = max(span, 1 / 12)
    bdays = pd.bdate_range(start or d.index.min(), end or d.index.max())
    dd = d.reindex(bdays).fillna(0.0)
    eq = dd.cumsum()
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    years = pd.Series(pnl.values, index=day.values).groupby(lambda i: i.year).sum()
    return {
        "trades": int(len(x)), "net_usd": float(pnl.sum()), "usd_per_year": float(pnl.sum() / span),
        "avg_trade_usd": float(pnl.mean()), "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "max_dd_usd": float((eq - eq.cummax()).min()),
        "sharpe": float(dd.mean() / dd.std() * np.sqrt(252)) if dd.std() > 0 else 0.0,
        "years_up": f"{int((years > 0).sum())}/{len(years)}",
        "worst_year_usd": float(years.min()), "best_year_usd": float(years.max()),
    }
