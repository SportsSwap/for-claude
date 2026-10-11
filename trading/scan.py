"""Scanner: which stocks gave a buy signal on the last completed bar?

Run it after the US close (or right after a bar closes during the day). Each signal
comes with a stop, a target and a share count sized so that hitting the stop costs
your chosen risk percent of the account.

    python scan.py                          # default strategy on 2h bars
    python scan.py --interval 4h --equity 1150
    python scan.py --variant 3              # use VARIANTS[3] from config.py instead

During market hours the newest bar is still forming, so its signal can disappear by
the close. Only act on bars that have finished.
"""

import argparse
from dataclasses import replace

import pandas as pd

import data
from backtest import fmt_time, position_size
from config import DEFAULT_RISK, DEFAULT_STRATEGY, INTERVALS, UNIVERSE, VARIANTS
from strategy import add_signals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=UNIVERSE)
    ap.add_argument("--interval", default="2h", choices=INTERVALS)
    ap.add_argument("--equity", type=float, default=DEFAULT_RISK.starting_capital, help="current account value")
    ap.add_argument("--risk-pct", type=float, default=DEFAULT_RISK.risk_per_trade * 100)
    ap.add_argument("--variant", type=int, default=None, help="index into config.VARIANTS")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    s = VARIANTS[args.variant] if args.variant is not None else DEFAULT_STRATEGY
    r = replace(DEFAULT_RISK, starting_capital=args.equity, risk_per_trade=args.risk_pct / 100)
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    daily = data.load(args.tickers, start, "1d", refresh=not args.offline, offline=args.offline)
    prices = daily if args.interval == "1d" else data.load(
        args.tickers, start, args.interval, refresh=not args.offline, offline=args.offline)

    signals, watch = [], []
    for t, df in prices.items():
        d = add_signals(df, s, daily.get(t) if args.interval != "1d" else None)
        last = d.iloc[-1]
        vs_ma = (last["Close"] / last["trend_ma"] - 1) * 100 if "trend_ma" in d and pd.notna(last["trend_ma"]) else None
        if last["entry_signal"]:
            entry = last["Close"]
            stop = entry - s.stop_atr_mult * last["atr"]
            shares = position_size(args.equity, args.equity, entry, stop, r)
            signals.append({
                "ticker": t,
                "close": round(entry, 2),
                "stop": round(stop, 2),
                "stop_%": round((stop / entry - 1) * 100, 1),
                "target": round(entry + s.target_r * (entry - stop), 2) if s.target_r else None,
                "shares": shares,
                "cost": round(shares * entry, 2),
                "risk_$": round(shares * (entry - stop), 2),
                "vs_200ma_%": round(vs_ma, 1) if vs_ma is not None else None,
            })
        # Getting close: MACD under zero, histogram negative but rising for 3 bars.
        hist = d["macd_hist"].iloc[-3:]
        if last["macd"] < 0 and hist.iloc[-1] < 0 and hist.is_monotonic_increasing:
            watch.append({"ticker": t, "close": round(last["Close"], 2),
                          "macd": round(last["macd"], 2), "macd_hist": round(hist.iloc[-1], 2),
                          "vs_200ma_%": round(vs_ma, 1) if vs_ma is not None else None})

    as_of = fmt_time(max(df.index[-1] for df in prices.values())) if prices else "n/a"
    print(f"\n{s.name}")
    print(f"MACD {s.macd_fast}/{s.macd_slow}/{s.macd_signal} on {args.interval} bars | last bar {as_of} "
          f"| account ${args.equity:,.0f}, risk {args.risk_pct:g}%")
    if signals:
        print("\nBUY SIGNALS (enter at the next bar's open; recompute the stop from your real fill):")
        print(pd.DataFrame(signals).to_string(index=False))
    else:
        print("\nNo buy signals. No trade is a fine trade.")
    if watch:
        print("\nWATCHLIST (MACD under zero and curling up toward a cross):")
        print(pd.DataFrame(watch).sort_values("macd_hist", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
