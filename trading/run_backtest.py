"""Backtest the MACD swing strategy on US stocks.

    python run_backtest.py                      # default strategy, full universe, since 2018
    python run_backtest.py --compare            # compare all strategy variants side by side
    python run_backtest.py --tickers NVDA AMD   # just these stocks
    python run_backtest.py --start 2022-01-01   # test from 2022 onwards
"""

import argparse
from pathlib import Path
import re

import pandas as pd

import backtest
import data
from config import BENCHMARKS, DEFAULT_RISK, DEFAULT_STRATEGY, UNIVERSE, VARIANTS
from dataclasses import replace

RESULTS_DIR = Path(__file__).parent / "results"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=UNIVERSE)
    ap.add_argument("--start", default="2018-01-01", help="first trading day of the test")
    ap.add_argument("--end", default=None)
    ap.add_argument("--capital", type=float, default=DEFAULT_RISK.starting_capital)
    ap.add_argument("--compare", action="store_true", help="run every variant in config.VARIANTS")
    ap.add_argument("--refresh", action="store_true", help="re-download prices instead of using the cache")
    ap.add_argument("--offline", action="store_true", help="use cached CSVs only")
    args = ap.parse_args()

    # Download a year before the test start so indicators are warmed up on day one.
    history_start = (pd.Timestamp(args.start) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    print(f"Loading prices for {len(args.tickers)} tickers...")
    prices = data.load(args.tickers, history_start, args.refresh, args.offline)
    bench = data.load(BENCHMARKS, history_start, args.refresh, args.offline)
    if not prices:
        raise SystemExit("No price data loaded. Check your internet connection or the cache folder.")

    risk = replace(DEFAULT_RISK, starting_capital=args.capital)
    strategies = VARIANTS if args.compare else [DEFAULT_STRATEGY]
    RESULTS_DIR.mkdir(exist_ok=True)

    rows = []
    for s in strategies:
        res = backtest.run(prices, s, risk, args.start, args.end)
        st = backtest.stats(res)
        rows.append(st)
        slug = re.sub(r"[^a-z0-9]+", "_", s.name.lower()).strip("_")
        res.trades.to_csv(RESULTS_DIR / f"trades_{slug}.csv", index=False)
        res.equity.to_csv(RESULTS_DIR / f"equity_{slug}.csv")

        if not args.compare:
            print_detail(st, res)

    for b, df in bench.items():
        bh = backtest.buy_and_hold(df, args.capital, args.start, args.end)
        if bh:
            rows.append({"strategy": f"Buy and hold {b}", **bh})

    table = pd.DataFrame(rows).set_index("strategy")
    for c in ("trades", "longest_losing_streak"):
        if c in table:
            table[c] = table[c].astype("Int64")
    cols = [c for c in ["final_equity", "total_return_pct", "cagr_pct", "max_drawdown_pct",
                        "trades", "win_rate_pct", "avg_r", "profit_factor",
                        "longest_losing_streak", "kill_switch_hit"] if c in table]
    print("\n" + table[cols].to_string(na_rep="-"))
    table.to_csv(RESULTS_DIR / "summary.csv")
    print(f"\nTrade logs and equity curves saved to {RESULTS_DIR}/")


def print_detail(st: dict, res: backtest.Result):
    print(f"\n=== {st['strategy']} | {st['start']} to {st['end']} ===")
    for k, v in st.items():
        if k not in ("strategy", "start", "end"):
            print(f"  {k:24s} {v}")
    if len(res.trades):
        by_ticker = res.trades.groupby("ticker").agg(
            trades=("pnl", "size"), pnl=("pnl", "sum"),
            win_rate=("pnl", lambda x: round((x > 0).mean() * 100))).sort_values("pnl")
        print("\n  P&L by ticker (worst to best):")
        print("  " + by_ticker.to_string().replace("\n", "\n  "))
        print("\n  Exit reasons:")
        print("  " + res.trades.exit_reason.value_counts().to_string().replace("\n", "\n  "))


if __name__ == "__main__":
    main()
