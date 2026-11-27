"""Multi-strategy portfolio of the bots that passed, the way multi-strat funds
combine uncorrelated edges. Rules fixed before looking at the result:

- Members: grade A/B bots (see grade()). The MACD bot is excluded (its stock
  list has survivorship bias); FX, VIX, RSI2, VAA and sector rotation failed.
- Each bot's chosen settings were fixed on its own in-sample window. Only its
  out-of-sample days are used here.
- Weights: inverse trailing-252-day volatility of each bot's daily returns,
  recomputed at each month end and applied from the next day.
- "unlevered": weights sum to 100%.  "stacked 10% vol": the same mix scaled
  so its trailing volatility targets 10% a year, gross capped at 2x (needs a
  margin account; the mean-reversion bots sit in cash most days).
"""
import json

import numpy as np
import pandas as pd

from engine import metrics as M
from engine.validate import RESULTS


def grade(o: dict) -> str:
    oos, wf, s2 = o["out_of_sample"], o["walk_forward"], o["costs_x2_out_of_sample"]
    sr, wsr, dsr, pbo = oos.get("Sharpe", -9), wf.get("Sharpe", -9), oos.get("DSR", 0), o["pbo"].get("PBO", 1)
    ok2 = s2.get("CAGR", -1) > 0
    if sr >= 0.7 and wsr >= 0.6 and dsr >= 0.95 and ok2 and pbo <= 0.5:
        return "A"
    if sr >= 0.5 and wsr >= 0.5 and dsr >= 0.90 and ok2:
        return "B"
    if sr >= 0.5 and ok2:
        return "C"
    return "F"


def load_members(summary, allowed=("A", "B"), exclude=("13 ", "17 ")):
    rets = {}
    for o in summary:
        if grade(o) not in allowed or any(o["name"].startswith(e) for e in exclude):
            continue
        slug = o["name"].lower().replace(" ", "_").replace("/", "_")
        r = pd.read_csv(RESULTS / f"{slug}_returns.csv", index_col=0, parse_dates=True).iloc[:, 0]
        oos_start = pd.Timestamp(o["in_sample_end"]) + pd.Timedelta(days=1)
        rets[o["name"]] = r.loc[oos_start:]
    return pd.DataFrame(rets)


def combine(R: pd.DataFrame, E: pd.DataFrame, rate: pd.Series, stacked: bool = False,
            target_vol=0.10, cap=2.0):
    """Returns (net portfolio returns, gross exposure). Financing from the
    actual exposure: borrowed money pays T-bill + 1.5%, idle cash earns
    T-bill - 0.5% (IBKR-style; IBKR pays nothing on the first $10k)."""
    vol = R.rolling(252, min_periods=126).std() * np.sqrt(252)
    me = R.index.to_series().dt.month != R.index.to_series().shift(-1).dt.month
    inv = (1 / vol).where(me).ffill().shift(1).where(R.notna())
    w = inv.div(inv.sum(axis=1), axis=0).fillna(0.0)
    port = (w * R.fillna(0.0)).sum(axis=1)
    scale = pd.Series(1.0, index=R.index)
    if stacked:
        pv = port.rolling(252, min_periods=126).std() * np.sqrt(252)
        scale = (target_vol / pv).where(me).ffill().shift(1).clip(upper=cap).fillna(1.0)
    gross = scale * (w * E.reindex_like(w).fillna(0.0)).sum(axis=1)
    rf = rate.reindex(R.index).ffill().fillna(0.0)
    fin = (-(gross - 1).clip(lower=0) * (rf + 0.015) + (1 - gross).clip(lower=0) * (rf - 0.005).clip(lower=0)) / 252
    net = port * scale + fin
    start = w.sum(axis=1).gt(0).idxmax()
    return net.loc[start:], gross.loc[start:]


if __name__ == "__main__":
    from engine import data
    summary = json.loads((RESULTS / "summary.json").read_text())
    for o in summary:
        print(f"{grade(o)}  {o['name']}")
    R = load_members(summary)
    E = {}
    for o in summary:
        if o["name"] in R:
            slug = o["name"].lower().replace(" ", "_").replace("/", "_")
            E[o["name"]] = pd.read_csv(RESULTS / f"{slug}_exposure.csv", index_col=0, parse_dates=True).iloc[:, 0]
    # put crypto on the stock calendar: compound weekend returns into the next weekday
    stock_days = pd.read_csv(RESULTS / "07_ibs_mean_reversion_returns.csv", index_col=0, parse_dates=True).index
    R2, E2 = {}, {}
    for col in R:
        r = R[col].dropna()
        pos = stock_days.searchsorted(r.index)
        g = (1 + r).groupby(pos).prod() - 1
        ge = E[col].reindex(r.index).groupby(pos).mean()
        valid = g.index < len(stock_days)
        R2[col] = pd.Series(g.values[valid], index=stock_days[g.index[valid]])
        E2[col] = pd.Series(ge.values[valid], index=stock_days[ge.index[valid]])
    R, E = pd.DataFrame(R2), pd.DataFrame(E2)
    rate = data.load("^IRX")["close"] / 100
    print("\nMembers:", list(R.columns))
    corr = R.dropna().corr().round(2)
    print("\nOOS correlation of daily returns:")
    print(corr.to_string())
    spy = data.load("SPY")["close"].pct_change()
    out = {"correlation": corr.to_dict()}
    for label, start, cols in [("2015-2026 without crypto", "2015-01-01", [c for c in R if "Crypto" not in c]),
                               ("2020-2026 all members", "2020-01-01", list(R.columns))]:
        for stacked in (False, True):
            p, g = combine(R.loc[start:, cols], E.loc[start:, cols], rate, stacked=stacked)
            s = M.summary(p)
            b = M.summary(spy.reindex(p.index).fillna(0))
            key = f"{label} | {'stacked to 10% vol (margin)' if stacked else 'unlevered'}"
            yearly = ((1 + p).groupby(p.index.year).prod() - 1).round(4).to_dict()
            out[key] = {"portfolio": s, "SPY": b, "members": cols, "avg_gross_exposure": float(g.mean()),
                        "max_gross_exposure": float(g.max()), "yearly": yearly}
            print(f"\n{key}   avg gross exposure {g.mean():.2f}x (max {g.max():.2f}x)"
                  f"\n   portfolio CAGR {s['CAGR']*100:.1f}% Sharpe {s['Sharpe']:.2f} maxDD {s['maxDD']*100:.1f}% "
                  f"worst yr {s['worst_year']*100:.1f}% yrs up {s['pct_years_up']*100:.0f}%"
                  f"\n   SPY       CAGR {b['CAGR']*100:.1f}% Sharpe {b['Sharpe']:.2f} maxDD {b['maxDD']*100:.1f}%"
                  f"\n   yearly {dict((k, round(v*100,1)) for k, v in yearly.items())}")
            p.to_csv(RESULTS / f"portfolio_{'stacked' if stacked else 'unlevered'}_{start[:4]}.csv")
    (RESULTS / "portfolio.json").write_text(json.dumps(out, indent=2, default=str))
