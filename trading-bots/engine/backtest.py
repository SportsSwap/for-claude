"""Vectorised daily backtester with honest execution timing and costs.

Each trading day d is split in two pieces:
  overnight  : close[d-1] -> open[d]     return r_on[d]
  intraday   : open[d]    -> close[d]    return r_id[d]
The book holds weights p_on[d] overnight and p_id[d] intraday.

A signal s[d] can only use data up to close[d]. It is then executed either
  "open"   at the next open  : p_id[d+1] = s[d], p_on[d+1] = s[d-1]
  "close"  at the same close (market-on-close; needs the signal a few minutes
           before the bell, which works for slow daily signals)
                             : p_on[d+1] = p_id[d+1] = s[d]
  "overnight" hold only from close to next open : p_on[d+1] = s[d], p_id = 0
  "intraday"  hold only from next open to next close : p_id[d+1] = s[d], p_on = 0

Costs are charged on every change of weight, at the price where it happens,
as `cost_bps` per unit of turnover (one side). Weights may be multi-asset
(DataFrame, columns = tickers). Cash earns `cash_rate` (annual) when idle.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import metrics as M


@dataclass
class Result:
    returns: pd.Series                 # daily net returns of the book
    gross: pd.Series                   # before costs
    exposure: pd.Series                # sum |weight| held intraday
    turnover: pd.Series                # one-sided turnover per day
    weights: pd.DataFrame | None = None
    trades: pd.DataFrame | None = None
    stats: dict = field(default_factory=dict)

    def summary(self, start=None, end=None, trials: int = 1) -> dict:
        r = self.returns.loc[start:end]
        st = M.summary(r, exposure=self.exposure.loc[start:end],
                       turnover=self.turnover.loc[start:end], trials=trials)
        if self.trades is not None and len(self.trades):
            t = self.trades
            if start is not None:
                t = t[t["entry"] >= pd.Timestamp(start)]
            if end is not None:
                t = t[t["entry"] <= pd.Timestamp(end)]
            st.update(M.trade_stats(t["ret"]))
        return st


def _as_frame(x, index, cols=None) -> pd.DataFrame:
    if isinstance(x, pd.Series):
        x = x.to_frame(cols[0] if cols else "asset")
    return x.reindex(index).fillna(0.0)


def run(opens: pd.DataFrame, closes: pd.DataFrame, signal: pd.DataFrame | pd.Series,
        mode: str = "open", cost_bps: float | dict = 2.0, cash_rate: float = 0.0,
        trade_list: bool = True) -> Result:
    if isinstance(opens, pd.Series):
        name = closes.name or "asset"
        opens, closes = opens.rename(name).to_frame(), closes.rename(name).to_frame()
        if isinstance(signal, pd.Series):
            signal = signal.rename(name).to_frame()
    idx = closes.index
    s = _as_frame(signal, idx, list(closes.columns))
    s = s[closes.columns] if set(closes.columns) <= set(s.columns) else s
    prev_close = closes.shift(1)
    r_on = (opens / prev_close - 1).fillna(0.0)
    r_id = (closes / opens - 1).fillna(0.0)

    if mode == "open":
        p_id, p_on = s.shift(1), s.shift(2)
    elif mode == "close":
        p_id = p_on = s.shift(1)
    elif mode == "overnight":
        p_on, p_id = s.shift(1), s * 0.0
    elif mode == "intraday":
        p_id, p_on = s.shift(1), s * 0.0
    else:
        raise ValueError(mode)
    p_id, p_on = p_id.fillna(0.0), p_on.fillna(0.0)

    # weights drift with prices inside a segment; we rebalance to target at each
    # boundary, which is what the turnover below charges for.
    gross_on = (p_on * r_on).sum(axis=1)
    gross_id = (p_id * r_id).sum(axis=1)
    # turnover at today's open: from overnight book (drifted) to intraday target
    # drifted weight = position value / book value after the move
    drift_on = (p_on * (1 + r_on)).div(1 + gross_on, axis=0)
    t_open = (p_id - drift_on).abs()
    # turnover at yesterday's close: from yesterday's drifted intraday book to tonight's book
    drift_id_prev = (p_id * (1 + r_id)).div(1 + gross_id, axis=0).shift(1).fillna(0.0)
    t_close = (p_on - drift_id_prev).abs()

    if isinstance(cost_bps, dict):
        c = pd.Series({k: cost_bps.get(k, cost_bps.get("default", 2.0)) for k in closes.columns}) / 1e4
    else:
        c = pd.Series(cost_bps / 1e4, index=closes.columns)
    cost = (t_open * c).sum(axis=1) + (t_close * c).sum(axis=1)
    turnover = t_open.sum(axis=1) + t_close.sum(axis=1)

    gross = (1 + gross_on) * (1 + gross_id) - 1
    idle = (1 - p_id.abs().sum(axis=1)).clip(lower=0)
    cash = idle * cash_rate / 252
    net = gross - cost + cash

    first = s.abs().sum(axis=1).ne(0).idxmax() if s.abs().sum().sum() > 0 else idx[0]
    net, gross = net.loc[first:], gross.loc[first:]
    expo = np.maximum(p_id.abs().sum(axis=1), p_on.abs().sum(axis=1))
    res = Result(returns=net, gross=gross, exposure=expo.loc[first:],
                 turnover=turnover.loc[first:], weights=s.loc[first:])
    if trade_list and s.shape[1] == 1:
        res.trades = trades_from_positions(net, (p_id + p_on).iloc[:, 0].loc[first:] / 2)
    return res


def trades_from_positions(net: pd.Series, pos: pd.Series) -> pd.DataFrame:
    """Group consecutive days in the market into trades (single asset)."""
    held = pos.abs() > 1e-9
    if not held.any():
        return pd.DataFrame(columns=["entry", "exit", "days", "ret"])
    grp = (held != held.shift()).cumsum()
    rows = []
    for _, g in net[held].groupby(grp[held]):
        rows.append({"entry": g.index[0], "exit": g.index[-1], "days": len(g),
                     "ret": float((1 + g).prod() - 1)})
    return pd.DataFrame(rows)
