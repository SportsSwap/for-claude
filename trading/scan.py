"""Scanner: which stocks gave a buy (or short) signal on the last completed bar?

Run it after the US close (or right after a bar closes during the day). Each signal
comes with a stop, a target and a share count sized so that hitting the stop costs
your chosen risk percent of the account.

    python scan.py                          # default strategy on 2h bars
    python scan.py --interval 4h --equity 1150
    python scan.py --no-markers             # skip the 30m/45m/1h marker check
    python scan.py --variant 3              # use VARIANTS[3] from config.py instead
    python scan.py --group ai               # just the AI list
    python scan.py --sides both             # also look for shorts: MACD cross down above zero,
                                            # price below the 200-day EMA

During market hours the newest bar is still forming, so its signal can disappear by
the close. Only act on bars that have finished.
"""

import argparse
from dataclasses import replace

import pandas as pd

import data
from backtest import fmt_time, position_size
from config import DEFAULT_RISK, DEFAULT_STRATEGY, INTERVALS, GROUPS, VARIANTS
from strategy import add_signals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=None, help="these stocks only (overrides --group)")
    ap.add_argument("--group", default="all", choices=list(GROUPS),
                    help="which stock list to use (default: all)")
    ap.add_argument("--interval", default="2h", choices=INTERVALS)
    ap.add_argument("--equity", type=float, default=DEFAULT_RISK.starting_capital, help="current account value")
    ap.add_argument("--risk-pct", type=float, default=DEFAULT_RISK.risk_per_trade * 100)
    ap.add_argument("--variant", type=int, default=None, help="index into config.VARIANTS")
    ap.add_argument("--sides", choices=["long", "short", "both"], default=None,
                    help="which signals to look for (default: what the strategy sets, long)")
    ap.add_argument("--no-markers", action="store_true", help="skip the 30m/45m/1h marker check")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    args.tickers = args.tickers or GROUPS[args.group]

    s = VARIANTS[args.variant] if args.variant is not None else DEFAULT_STRATEGY
    if args.sides:
        s = replace(s, sides=args.sides)
    r = replace(DEFAULT_RISK, starting_capital=args.equity, risk_per_trade=args.risk_pct / 100)
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    daily = data.load(args.tickers, start, "1d", refresh=not args.offline, offline=args.offline)
    prices = data.load(args.tickers, start, args.interval, refresh=not args.offline, offline=args.offline)
    markers = None
    if not args.no_markers:
        markers = data.load_markers(args.tickers, start, s.marker_tfs, refresh=not args.offline,
                                    offline=args.offline)

    signals, shorts, watch, watch_short = [], [], [], []
    for t, df in prices.items():
        d = add_signals(df, s, daily.get(t), (markers or {}).get(t, {}) if markers is not None else None,
                        args.interval)
        mk = lambda col: f"{int(last[col])}/{int(last['mk_n'])}" if "mk_n" in d else "-"
        last = d.iloc[-1]
        vs_ma = (last["Close"] / last["trend_ma"] - 1) * 100 if "trend_ma" in d and pd.notna(last["trend_ma"]) else None
        vs_ma = round(vs_ma, 1) if vs_ma is not None else None
        for side, flag, out in ((1, "entry_signal", signals), (-1, "short_signal", shorts)):
            if not last[flag]:
                continue
            entry = last["Close"]
            stop = entry - side * s.stop_atr_mult * last["atr"]
            shares = position_size(args.equity, args.equity, entry, stop, r)
            out.append({
                "ticker": t,
                "close": round(entry, 2),
                "stop": round(stop, 2),
                "stop_%": round((stop / entry - 1) * 100, 1),
                "target": round(entry + s.target_r * (entry - stop), 2) if s.target_r else None,
                "shares": shares,
                "value": round(shares * entry, 2),
                "risk_$": round(shares * abs(entry - stop), 2),
                "vs_200ma_%": vs_ma,
                "markers": mk("mk_up" if side > 0 else "mk_down"),
            })
        hist = d["macd_hist"].iloc[-3:]
        row = {"ticker": t, "close": round(last["Close"], 2), "macd": round(last["macd"], 2),
               "macd_hist": round(hist.iloc[-1], 2), "vs_200ma_%": vs_ma, "markers_up": mk("mk_up")}
        # Getting close to a buy: MACD under zero, histogram negative but rising for 3 bars.
        if s.sides in ("long", "both") and last["macd"] < 0 and hist.iloc[-1] < 0 and hist.is_monotonic_increasing:
            watch.append(row)
        # Getting close to a short: MACD above zero, histogram positive but falling for 3 bars.
        if s.sides in ("short", "both") and last["macd"] > 0 and hist.iloc[-1] > 0 and hist.is_monotonic_decreasing:
            watch_short.append(row)

    as_of = fmt_time(max(df.index[-1] for df in prices.values())) if prices else "n/a"
    print(f"\n{s.name}")
    print(f"MACD {s.macd_fast}/{s.macd_slow}/{s.macd_signal} on {args.interval} bars | last bar {as_of} "
          f"| account ${args.equity:,.0f}, risk {args.risk_pct:g}%")
    if s.sides in ("long", "both"):
        if signals:
            print("\nBUY SIGNALS (enter at the next bar's open; recompute the stop from your real fill):")
            print(pd.DataFrame(signals).to_string(index=False))
        else:
            print("\nNo buy signals.")
    if s.sides in ("short", "both"):
        if shorts:
            print("\nSHORT SIGNALS (sell short at the next bar's open; stop is ABOVE, target BELOW):")
            print(pd.DataFrame(shorts).to_string(index=False))
        else:
            print("\nNo short signals.")
    if not signals and not shorts:
        print("No trade is a fine trade.")
    if watch:
        print("\nWATCHLIST, LONG (MACD under zero and curling up toward a cross):")
        print(pd.DataFrame(watch).sort_values("macd_hist", ascending=False).to_string(index=False))
    if watch_short:
        print("\nWATCHLIST, SHORT (MACD above zero and rolling over toward a cross):")
        print(pd.DataFrame(watch_short).sort_values("macd_hist").to_string(index=False))


if __name__ == "__main__":
    main()
