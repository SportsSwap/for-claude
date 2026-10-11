"""Nightly scanner: which stocks gave a MACD buy signal at today's close?

Run it after the US close. Each signal comes with a stop, a target and a share
count sized so that hitting the stop costs about 2% of your account.

    python scan.py                    # account size from config ($1000)
    python scan.py --equity 1150      # your current account value
"""

import argparse

import pandas as pd

import data
from backtest import position_size
from config import DEFAULT_RISK, DEFAULT_STRATEGY, UNIVERSE
from dataclasses import replace
from strategy import add_signals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=UNIVERSE)
    ap.add_argument("--equity", type=float, default=DEFAULT_RISK.starting_capital)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    s, r = DEFAULT_STRATEGY, replace(DEFAULT_RISK, starting_capital=args.equity)
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    prices = data.load(args.tickers, start, refresh=not args.offline, offline=args.offline)

    signals, watch = [], []
    for t, df in prices.items():
        d = add_signals(df, s)
        last = d.iloc[-1]
        if last["entry_signal"]:
            entry = last["Close"]
            stop = entry - s.stop_atr_mult * last["atr"]
            shares = position_size(args.equity, args.equity, entry, stop, r)
            signals.append({
                "ticker": t,
                "close": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(entry + s.target_r * (entry - stop), 2) if s.target_r else None,
                "shares": shares,
                "cost": round(shares * entry, 2),
                "risk_$": round(shares * (entry - stop), 2),
                "momentum_20d_%": round(last["momentum_20d"] * 100, 1),
            })
        # Near a cross: histogram negative but rising for 3 days, in an uptrend.
        hist = d["macd_hist"].iloc[-3:]
        uptrend = not s.trend_sma or last["Close"] > last.get("trend_sma", 0)
        if hist.iloc[-1] < 0 and hist.is_monotonic_increasing and uptrend:
            watch.append({"ticker": t, "close": round(last["Close"], 2),
                          "macd_hist": round(hist.iloc[-1], 3)})

    as_of = max(df.index[-1] for df in prices.values()).date() if prices else "n/a"
    print(f"\nMACD scan for the close of {as_of}  (account ${args.equity:,.0f})")
    if signals:
        print("\nBUY SIGNALS (enter at tomorrow's open; recompute the stop from your real fill):")
        print(pd.DataFrame(signals).sort_values("momentum_20d_%", ascending=False).to_string(index=False))
    else:
        print("\nNo buy signals today. No trade is a fine trade.")
    if watch:
        print("\nWATCHLIST (MACD curling up toward a cross, in an uptrend):")
        print(pd.DataFrame(watch).sort_values("macd_hist", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
