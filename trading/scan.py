"""Scanner: which stocks gave a buy signal on the last completed bar?

Runs both long systems by default, each sized on its share of the account:
  Long-term  (MACD 12/144/9): deep dips below the 200-day EMA, held weeks to months.
  Short-term (MACD 12/26/9):  pullbacks in stocks above the 200-day EMA, held days to ~2 weeks.

Run it after the US close (or right after a bar closes during the day). Each signal
comes with a stop and a share count sized so that hitting the stop costs your chosen
risk percent of that system's share of the account.

    python scan.py                          # both systems on 2h bars
    python scan.py --system long-term       # just the 12/144/9 long-term system
    python scan.py --system short-term      # just the 12/26/9 short-term system
    python scan.py --interval 4h --equity 1150
    python scan.py --group ai               # just the AI list
    python scan.py --mtf 2                  # only signals where 2 of 15m/30m/45m agree
    python scan.py --variant 5              # one of config.VARIANTS instead of the systems
    python scan.py --sides both             # (parked) also look for short-selling signals

During market hours the newest bar is still forming, so its signal can disappear by
the close. Only act on bars that have finished.
"""

import argparse
from dataclasses import replace

import pandas as pd

import data
from backtest import fmt_time, position_size
from config import (DEFAULT_RISK, GROUPS, INTERVALS, LONG_TERM, SHORT_TERM, SYSTEM_SPLIT, SYSTEMS, Strategy,
                    VARIANTS)
from strategy import add_signals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=None, help="these stocks only (overrides --group)")
    ap.add_argument("--group", default="all", choices=list(GROUPS),
                    help="which stock list to use (default: all)")
    ap.add_argument("--interval", default="2h", choices=INTERVALS)
    ap.add_argument("--equity", type=float, default=DEFAULT_RISK.starting_capital, help="current account value")
    ap.add_argument("--risk-pct", type=float, default=DEFAULT_RISK.risk_per_trade * 100)
    ap.add_argument("--system", choices=["both", *SYSTEMS], default="both",
                    help="both (default), long-term (12/144/9) or short-term (12/26/9)")
    ap.add_argument("--variant", type=int, default=None, help="index into config.VARIANTS (replaces --system)")
    ap.add_argument("--sides", choices=["long", "short", "both"], default=None,
                    help="(parked) short selling: long (default), short or both")
    ap.add_argument("--buffer", type=float, default=None,
                    help="MACD must be at least this many ATRs past zero at the cross (default off)")
    ap.add_argument("--mtf", type=int, default=None, choices=[0, 1, 2, 3],
                    help="need this many of 15m/30m/45m to agree (default: show the count, don't filter)")
    ap.add_argument("--no-mtf", action="store_true", help="skip downloading 15m/30m/45m bars")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    args.tickers = args.tickers or GROUPS[args.group]

    if args.variant is not None:
        systems = [(VARIANTS[args.variant], 1.0)]
    elif args.system == "both":
        systems = [(LONG_TERM, SYSTEM_SPLIT), (SHORT_TERM, 1 - SYSTEM_SPLIT)]
    else:
        systems = [(SYSTEMS[args.system], 1.0)]
    overrides = {}
    if args.sides:
        overrides["sides"] = args.sides
    if args.buffer is not None:
        overrides["min_macd_depth_atr"] = args.buffer
    if args.mtf is not None:
        overrides["confirm_min"] = args.mtf
    systems = [(replace(s, **overrides), share) for s, share in systems]

    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    daily = data.load(args.tickers, start, "1d", refresh=not args.offline, offline=args.offline)
    prices = daily if args.interval == "1d" else data.load(
        args.tickers, start, args.interval, refresh=not args.offline, offline=args.offline)

    lower = {}
    if args.interval != "1d" and not args.no_mtf:
        lower = data.load_lower(args.tickers, start, refresh=not args.offline, offline=args.offline)
    elif any(s.confirm_min for s, _ in systems):
        raise SystemExit("--mtf needs an intraday --interval and can't be used with --no-mtf.")
    higher = data.load_higher(args.tickers, start, args.interval, systems[0][0].higher_tfs, daily,
                              refresh=not args.offline, offline=args.offline)
    market = None
    short_filter = next((s.short_market_filter for s, _ in systems if s.sides != "long"), None)
    if short_filter:
        market = data.load([short_filter], start, "1d", refresh=not args.offline,
                           offline=args.offline).get(short_filter)

    as_of = fmt_time(max(df.index[-1] for df in prices.values())) if prices else "n/a"
    print(f"\n{args.interval} bars | last bar {as_of} | account ${args.equity:,.0f}, risk {args.risk_pct:g}% per trade")
    for s, share in systems:
        scan_system(s, args.equity * share, args, prices, daily, lower, higher, market)


def describe_exits(s: Strategy) -> str:
    exits = [f"stop {s.stop_atr_mult:g} ATR",
             {"above_zero": "sell when the MACD crosses down ABOVE zero",
              "any": "sell on any MACD cross back", "off": "no MACD exit"}[s.macd_exit]]
    if s.trail_atr_mult:
        exits.append(f"trailing stop {s.trail_atr_mult:g} ATR behind the best close")
    exits.append(f"target {s.target_r:g}R" if s.target_r else "no fixed target")
    if s.max_hold_days:
        exits.append(f"{s.max_hold_days}-day time stop")
    return ", ".join(exits)


def scan_system(s: Strategy, equity: float, args, prices, daily, lower, higher, market):
    r = replace(DEFAULT_RISK, starting_capital=equity, risk_per_trade=args.risk_pct / 100)
    signals, shorts, watch, watch_short = [], [], [], []
    for t, df in prices.items():
        d = add_signals(df, s, daily.get(t) if args.interval != "1d" else None, lower.get(t), args.interval,
                        market, higher.get(t))
        last = d.iloc[-1]
        vs_ma = (last["Close"] / last["trend_ma"] - 1) * 100 if "trend_ma" in d and pd.notna(last["trend_ma"]) else None
        vs_ma = round(vs_ma, 1) if vs_ma is not None else None
        for side, flag, out in ((1, "entry_signal", signals), (-1, "short_signal", shorts)):
            if not last[flag]:
                continue
            entry = last["Close"]
            mult = s.short_stop_atr_mult if side < 0 and s.short_stop_atr_mult else s.stop_atr_mult
            stop = entry - side * mult * last["atr"]
            shares = position_size(equity, equity, entry, stop, r)
            out.append({
                "ticker": t,
                "close": round(entry, 2),
                "stop": round(stop, 2),
                "stop_%": round((stop / entry - 1) * 100, 1),
                "shares": shares,
                "value": round(shares * entry, 2),
                "risk_$": round(shares * abs(entry - stop), 2),
                "vs_200ma_%": vs_ma,
                **({"target": round(entry + s.target_r * (entry - stop), 2)} if s.target_r else {}),
                "higher_tfs": f"{int(last['htf_up' if side > 0 else 'htf_down'])}/{int(last['htf_max'])}",
                "lower_tfs": f"{int(last['mtf_up' if side > 0 else 'mtf_down'])}/{int(last['mtf_max'])}"
                             if "mtf_max" in d else "-",
            })
        hist = d["macd_hist"].iloc[-3:]
        row = {"ticker": t, "close": round(last["Close"], 2), "macd": round(last["macd"], 2),
               "macd_hist": round(hist.iloc[-1], 2), "vs_200ma_%": vs_ma,
               "higher_up": f"{int(last['htf_up'])}/{int(last['htf_max'])}"}
        # Getting close to a buy: MACD under zero, histogram negative but rising for 3 bars.
        if s.sides in ("long", "both") and last["macd"] < 0 and hist.iloc[-1] < 0 and hist.is_monotonic_increasing:
            watch.append(row)
        # (parked) Getting close to a short: MACD above zero, histogram positive but falling.
        if s.sides in ("short", "both") and last["macd"] > 0 and hist.iloc[-1] > 0 and hist.is_monotonic_decreasing:
            watch_short.append(row)

    print(f"\n=== {s.name} | MACD {s.macd_fast}/{s.macd_slow}/{s.macd_signal} | ${equity:,.0f} of the account ===")
    print("Exits: " + describe_exits(s))
    print(f"Filters: wait {s.confirm_bars} bar(s) after the cross; "
          + (f"{'/'.join(s.higher_tfs)} MACDs must agree" if s.require_higher else "no higher-timeframe check")
          + (f"; need {s.confirm_min} of {'/'.join(s.confirm_tfs)}" if s.confirm_min else ""))
    if s.sides in ("long", "both"):
        if signals:
            print("\nBUY SIGNALS (enter at the next bar's open; recompute the stop from your real fill):")
            print(pd.DataFrame(signals).to_string(index=False))
        else:
            print("\nNo buy signals. No trade is a fine trade.")
    if s.sides in ("short", "both"):
        if shorts:
            print("\n(parked) SHORT SIGNALS (the stop is ABOVE the entry):")
            print(pd.DataFrame(shorts).to_string(index=False))
        else:
            print("\n(parked) No short signals.")
    if watch:
        print("\nWATCHLIST (MACD under zero and curling up toward a cross):")
        print(pd.DataFrame(watch).sort_values("macd_hist", ascending=False).to_string(index=False))
    if watch_short:
        print("\n(parked) SHORT WATCHLIST (MACD above zero and rolling over):")
        print(pd.DataFrame(watch_short).sort_values("macd_hist").to_string(index=False))


if __name__ == "__main__":
    main()
