"""Backtest the MACD swing strategy on US stocks.

    python run_backtest.py --compare                  # every variant, 2h bars, last ~2 years
    python run_backtest.py --interval 4h              # 4-hour bars instead
    python run_backtest.py --no-markers               # without the 30m/45m/1h marker check

Trades only on 2h and 4h bars. The 30m, 45m and 1h MACDs are markers that must agree at the
signal. Yahoo keeps 30m/45m for 60 days only, so before that just the 1h marker is checked.
    python run_backtest.py --tickers NVDA AMD SNDK    # just these stocks
    python run_backtest.py --group ai                 # just the AI list (see config.GROUPS)
    python run_backtest.py --risk-pct 3               # risk 3% of the account per trade
    python run_backtest.py --sides both               # take the short mirror trades as well
    python run_backtest.py --sides short              # shorts only
"""

import argparse
from dataclasses import replace
from pathlib import Path
import re

import pandas as pd

import backtest
import data
from config import BENCHMARKS, DEFAULT_RISK, DEFAULT_STRATEGY, INTERVALS, GROUPS, VARIANTS

RESULTS_DIR = Path(__file__).parent / "results"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=None, help="these stocks only (overrides --group)")
    ap.add_argument("--group", default="all", choices=list(GROUPS),
                    help="which stock list to use (default: all)")
    ap.add_argument("--interval", default="2h", choices=INTERVALS, help="bar size (default 2h)")
    ap.add_argument("--start", default=None,
                    help="first day of the test (default: all ~2 years Yahoo keeps for hourly bars)")
    ap.add_argument("--end", default=None)
    ap.add_argument("--capital", type=float, default=DEFAULT_RISK.starting_capital)
    ap.add_argument("--risk-pct", type=float, default=DEFAULT_RISK.risk_per_trade * 100,
                    help="percent of the account lost if a stop is hit (default 2)")
    ap.add_argument("--max-position-pct", type=float, default=DEFAULT_RISK.max_position_pct * 100,
                    help="largest single position as a percent of the account (default 34)")
    ap.add_argument("--sides", choices=["long", "short", "both"], default=None,
                    help="long, short or both (default: long). Ignored with --compare, whose variants set it")
    ap.add_argument("--no-markers", action="store_true", help="skip the 30m/45m/1h marker check")
    ap.add_argument("--compare", action="store_true", help="run every variant in config.VARIANTS")
    ap.add_argument("--refresh", action="store_true", help="re-download prices instead of using the cache")
    ap.add_argument("--offline", action="store_true", help="use cached CSVs only")
    args = ap.parse_args()
    args.tickers = args.tickers or GROUPS[args.group]

    start = args.start
    # Daily history reaches well back so the 200-day average is ready on day one.
    daily_start = (pd.Timestamp(start or pd.Timestamp.today()) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")

    print(f"Loading {args.interval} prices for {len(args.tickers)} tickers...")
    daily = data.load(args.tickers, daily_start, "1d", args.refresh, args.offline)
    prices = data.load(args.tickers, daily_start, args.interval, args.refresh, args.offline)
    markers = None
    if not args.no_markers:
        print("Loading the 30m / 45m / 1h marker bars...")
        markers = data.load_markers(args.tickers, daily_start, DEFAULT_STRATEGY.marker_tfs,
                                    args.refresh, args.offline)
    bench = data.load(BENCHMARKS, daily_start, "1d", args.refresh, args.offline)
    if not prices:
        raise SystemExit("No price data loaded. Check your internet connection or the cache folder.")

    risk = replace(DEFAULT_RISK, starting_capital=args.capital, risk_per_trade=args.risk_pct / 100,
                   max_position_pct=args.max_position_pct / 100)
    if args.compare:
        strategies = VARIANTS
    elif args.sides:
        names = {"long": DEFAULT_STRATEGY.name,
                 "short": "Short: MACD cross down above zero, below 200-day EMA",
                 "both": "Long + short"}
        strategies = [replace(DEFAULT_STRATEGY, sides=args.sides, name=names[args.sides])]
    else:
        strategies = [DEFAULT_STRATEGY]
    RESULTS_DIR.mkdir(exist_ok=True)

    rows, first_day = [], None
    for s in strategies:
        res = backtest.run(prices, s, risk, start, args.end, daily, markers, args.interval)
        st = backtest.stats(res)
        rows.append(st)
        if not res.equity.empty:
            first_day = res.equity.index[0] if first_day is None else min(first_day, res.equity.index[0])
        slug = re.sub(r"[^a-z0-9]+", "_", s.name.lower()).strip("_")
        res.trades.to_csv(RESULTS_DIR / f"trades_{args.interval}_{slug}.csv", index=False)
        res.equity.to_csv(RESULTS_DIR / f"equity_{args.interval}_{slug}.csv")
        if not args.compare:
            print_detail(st, res)

    for b, df in bench.items():
        bh = backtest.buy_and_hold(df, args.capital, first_day, args.end)
        if bh:
            rows.append({"strategy": f"Buy and hold {b}", **bh})

    table = pd.DataFrame(rows).set_index("strategy")
    for c in ("trades", "longest_losing_streak"):
        if c in table:
            table[c] = table[c].astype("Int64")
    cols = [c for c in ["final_equity", "total_return_pct", "cagr_pct", "max_drawdown_pct",
                        "trades", "win_rate_pct", "avg_r", "profit_factor",
                        "longest_losing_streak", "kill_switch_hit", "long_pnl", "short_pnl"] if c in table]
    print(f"\n{args.interval} bars | risk {args.risk_pct:g}% per trade | ${args.capital:,.0f} start")
    shown = table[cols].astype(object)
    print(shown.where(shown.notna(), "-").to_string())
    table.to_csv(RESULTS_DIR / f"summary_{args.interval}.csv")
    print(f"\nTrade logs and equity curves saved to {RESULTS_DIR}/")


def print_detail(st: dict, res: backtest.Result):
    print(f"\n=== {st['strategy']} | {st.get('start')} to {st.get('end')} ===")
    for k, v in st.items():
        if k not in ("strategy", "start", "end"):
            print(f"  {k:24s} {v}")
    if len(res.trades):
        if (res.trades.side == "short").any():
            by_side = res.trades.groupby("side").agg(
                trades=("pnl", "size"), pnl=("pnl", "sum"), avg_r=("r_multiple", "mean"),
                win_rate=("pnl", lambda x: round((x > 0).mean() * 100))).round(2)
            print("\n  Longs vs shorts:")
            print("  " + by_side.to_string().replace("\n", "\n  "))
        by_ticker = res.trades.groupby("ticker").agg(
            trades=("pnl", "size"), pnl=("pnl", "sum"),
            win_rate=("pnl", lambda x: round((x > 0).mean() * 100))).sort_values("pnl")
        print("\n  P&L by ticker (worst to best):")
        print("  " + by_ticker.to_string().replace("\n", "\n  "))
        if res.trades.markers.notna().any():
            by_mk = res.trades.groupby("markers").agg(
                trades=("pnl", "size"), pnl=("pnl", "sum"),
                win_rate=("pnl", lambda x: round((x > 0).mean() * 100))).round(2)
            print("\n  By markers agreeing (30m/45m/1h with data at the signal):")
            print("  " + by_mk.to_string().replace("\n", "\n  "))
        print("\n  Exit reasons:")
        print("  " + res.trades.exit_reason.value_counts().to_string().replace("\n", "\n  "))


if __name__ == "__main__":
    main()
