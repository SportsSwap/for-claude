"""Scanner: which stocks gave a buy (or short) signal on the last completed bar?

Run it after the US close (or right after a bar closes during the day). Each signal
comes with a stop, a target and a share count sized so that hitting the stop costs
your chosen risk percent of the account.

    python scan.py                          # default strategy on 2h bars
    python scan.py --interval 4h --equity 1150
    python scan.py --variant 5              # use VARIANTS[5] from config.py instead
    python scan.py --group ai               # just the AI list
    python scan.py --mtf 2                  # only signals where 2 of 15m/30m/45m agree
    python scan.py --buffer 0               # no buffer: include crosses right under zero
    python scan.py --sides both             # also look for shorts: MACD cross down above zero,
                                            # price above the 200-day EMA

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
                    help="which signals to look for (default: both)")
    ap.add_argument("--buffer", type=float, default=None,
                    help="MACD must be at least this many ATRs past zero at the cross (default 0.5; 0 = off)")
    ap.add_argument("--mtf", type=int, default=None, choices=[0, 1, 2, 3],
                    help="need this many of 15m/30m/45m to agree (default: show the count, don't filter)")
    ap.add_argument("--no-mtf", action="store_true", help="skip downloading 15m/30m/45m bars")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    args.tickers = args.tickers or GROUPS[args.group]

    s = VARIANTS[args.variant] if args.variant is not None else DEFAULT_STRATEGY
    if args.sides:
        s = replace(s, sides=args.sides)
    if args.buffer is not None:
        s = replace(s, min_macd_depth_atr=args.buffer)
    if args.mtf is not None:
        s = replace(s, confirm_min=args.mtf)
    r = replace(DEFAULT_RISK, starting_capital=args.equity, risk_per_trade=args.risk_pct / 100)
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    daily = data.load(args.tickers, start, "1d", refresh=not args.offline, offline=args.offline)
    prices = daily if args.interval == "1d" else data.load(
        args.tickers, start, args.interval, refresh=not args.offline, offline=args.offline)

    lower = {}
    if args.interval != "1d" and not args.no_mtf:
        lower = data.load_lower(args.tickers, start, refresh=not args.offline, offline=args.offline)
    elif s.confirm_min:
        raise SystemExit("--mtf needs an intraday --interval and can't be used with --no-mtf.")

    signals, shorts, watch, watch_short = [], [], [], []
    for t, df in prices.items():
        d = add_signals(df, s, daily.get(t) if args.interval != "1d" else None, lower.get(t), args.interval)
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
                "shares": shares,
                "value": round(shares * entry, 2),
                "risk_$": round(shares * abs(entry - stop), 2),
                "vs_200ma_%": vs_ma,
                "depth_atr": round(last["depth_atr"], 2),
                **({"target": round(entry + s.target_r * (entry - stop), 2)} if s.target_r else {}),
                "lower_tfs_agree": f"{int(last['mtf_up' if side > 0 else 'mtf_down'])}/{int(last['mtf_max'])}"
                                   if "mtf_max" in d else "-",
            })
        hist = d["macd_hist"].iloc[-3:]
        row = {"ticker": t, "close": round(last["Close"], 2), "macd": round(last["macd"], 2),
               "depth_atr": round(last["depth_atr"], 2), "macd_hist": round(hist.iloc[-1], 2),
               "vs_200ma_%": vs_ma}
        if "mtf_max" in d:
            row["lower_up"] = f"{int(last['mtf_up'])}/{int(last['mtf_max'])}"
            row["lower_down"] = f"{int(last['mtf_down'])}/{int(last['mtf_max'])}"
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
    exits = [f"stop {s.stop_atr_mult:g} ATR",
             {"above_zero": "sell when the MACD crosses down ABOVE zero (cover shorts when it crosses up below zero)",
              "any": "sell on any MACD cross back", "off": "no MACD exit"}[s.macd_exit]]
    if s.trail_atr_mult:
        exits.append(f"trailing stop {s.trail_atr_mult:g} ATR behind the best close")
    exits.append(f"target {s.target_r:g}R" if s.target_r else "no fixed target")
    if s.max_hold_days:
        exits.append(f"{s.max_hold_days}-day time stop")
    print("Exits: " + ", ".join(exits))
    print(f"Buffer: {f'cross at least {s.min_macd_depth_atr:g} ATR past zero' if s.min_macd_depth_atr else 'off'}"
          " | lower timeframes: "
          + (f"need {s.confirm_min} of {'/'.join(s.confirm_tfs)} to agree" if s.confirm_min
             else "shown, not filtered"))
    if s.sides in ("long", "both"):
        if signals:
            print("\nBUY SIGNALS (enter at the next bar's open; recompute the stop from your real fill):")
            print(pd.DataFrame(signals).to_string(index=False))
        else:
            print("\nNo buy signals.")
    if s.sides in ("short", "both"):
        if shorts:
            print("\nSHORT SIGNALS (sell short at the next bar's open; the stop is ABOVE the entry):")
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
