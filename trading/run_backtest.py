"""Backtest the MACD swing strategy on US stocks.

    python run_backtest.py --compare                  # every variant, 2h bars, last ~2 years
    python run_backtest.py --interval 4h              # 4-hour bars instead
    python run_backtest.py --interval 1d --start 2018-01-01 --compare   # daily bars, longer history
    python run_backtest.py --tickers NVDA AMD SNDK    # just these stocks
    python run_backtest.py --group ai                 # just the AI list (see config.GROUPS)
    python run_backtest.py --risk-pct 3               # risk 3% of the account per trade
    python run_backtest.py --sides long               # longs only (default is long + short)
    python run_backtest.py --sides short              # shorts only
    python run_backtest.py --buffer 0                 # no buffer: take crosses right under zero
    python run_backtest.py --mtf 2                    # need 2 of 15m/30m/45m to agree (last ~60 days only)
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
                    help="first day of the test (default: 2018-01-01 for 1d, all ~2 years for intraday)")
    ap.add_argument("--end", default=None)
    ap.add_argument("--capital", type=float, default=DEFAULT_RISK.starting_capital)
    ap.add_argument("--risk-pct", type=float, default=DEFAULT_RISK.risk_per_trade * 100,
                    help="percent of the account lost if a stop is hit (default 2)")
    ap.add_argument("--max-position-pct", type=float, default=DEFAULT_RISK.max_position_pct * 100,
                    help="largest single position as a percent of the account (default 34)")
    ap.add_argument("--sides", choices=["long", "short", "both"], default=None,
                    help="long, short or both (default: both). Ignored with --compare, whose variants set it")
    ap.add_argument("--buffer", type=float, default=None,
                    help="MACD must be at least this many ATRs past zero at the cross (default 0.5; 0 = off)")
    ap.add_argument("--mtf", type=int, default=None, choices=[0, 1, 2, 3],
                    help="load 15m/30m/45m bars and need this many to agree (0 = just record the count). "
                         "Yahoo keeps only ~60 days of these, so the test is limited to that window")
    ap.add_argument("--compare", action="store_true", help="run every variant in config.VARIANTS")
    ap.add_argument("--refresh", action="store_true", help="re-download prices instead of using the cache")
    ap.add_argument("--offline", action="store_true", help="use cached CSVs only")
    args = ap.parse_args()
    args.tickers = args.tickers or GROUPS[args.group]

    intraday = args.interval != "1d"
    start = args.start or (None if intraday else "2018-01-01")
    # Daily history reaches well back so the 200-day average is ready on day one.
    daily_start = (pd.Timestamp(start or pd.Timestamp.today()) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")

    print(f"Loading {args.interval} prices for {len(args.tickers)} tickers...")
    daily = data.load(args.tickers, daily_start, "1d", args.refresh, args.offline)
    prices = data.load(args.tickers, daily_start, args.interval, args.refresh, args.offline) if intraday else daily
    bench = data.load(BENCHMARKS, daily_start, "1d", args.refresh, args.offline)
    market = bench.get("QQQ")
    if market is None:
        print("Warning: no QQQ prices, so the short market filter blocks every short.")
    if not prices:
        raise SystemExit("No price data loaded. Check your internet connection or the cache folder.")
    if args.mtf is not None and not intraday:
        raise SystemExit("--mtf needs an intraday --interval (1h, 2h or 4h).")

    risk = replace(DEFAULT_RISK, starting_capital=args.capital, risk_per_trade=args.risk_pct / 100,
                   max_position_pct=args.max_position_pct / 100)
    if args.compare:
        strategies = VARIANTS
    elif args.sides:
        names = {"long": "Long only: dip buy below 200-day EMA",
                 "short": "Short only: MACD cross down above zero, above 200-day EMA",
                 "both": DEFAULT_STRATEGY.name}
        strategies = [replace(DEFAULT_STRATEGY, sides=args.sides, name=names[args.sides])]
    else:
        strategies = [DEFAULT_STRATEGY]
    if args.buffer is not None:
        strategies = [replace(s, min_macd_depth_atr=args.buffer,
                              name=f"{s.name} [buffer {args.buffer:g} ATR]") for s in strategies]
    if args.mtf:
        strategies = [replace(s, confirm_min=args.mtf,
                              name=f"{s.name} [{args.mtf} lower TFs agree]") for s in strategies]
    lower = None
    if args.mtf is not None:
        lower = data.load_lower(args.tickers, daily_start, args.refresh, args.offline)
        # Each lower MACD needs 2 x slow bars to warm up; start once every timeframe is ready.
        warm = 2 * max(s.macd_slow for s in strategies)
        ready = {}
        for frames in lower.values():
            for tf, df in frames.items():
                if len(df) > warm:
                    ready[tf] = min(ready.get(tf, df.index[warm]), df.index[warm])
        if not ready:
            raise SystemExit("Not enough 15m/30m/45m history for the lower-timeframe check.")
        start = max(pd.Timestamp(start or "1900-01-01"), max(ready.values())).strftime("%Y-%m-%d")
        print(f"Lower timeframes ready from {start}: the test is limited to that window.")
    RESULTS_DIR.mkdir(exist_ok=True)

    rows, first_day = [], None
    for s in strategies:
        res = backtest.run(prices, s, risk, start, args.end, daily if intraday else None, lower, args.interval,
                           market)
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
        t = res.trades
        if t.depth_atr.notna().any():
            depth = pd.cut(t.depth_atr.abs(), [0, 0.5, 1, 2, float("inf")],
                           labels=["<0.5 ATR", "0.5-1 ATR", "1-2 ATR", ">2 ATR"], include_lowest=True)
            print("\n  By how far from zero the MACD crossed (does the buffer help?):")
            print("  " + summarize(t.groupby(depth, observed=True)).to_string().replace("\n", "\n  "))
        if t.mtf_agree.notna().any():
            print("\n  By how many lower timeframes agreed (15m/30m/45m):")
            print("  " + summarize(t.groupby("mtf_agree")).to_string().replace("\n", "\n  "))
        by_ticker = res.trades.groupby("ticker").agg(
            trades=("pnl", "size"), pnl=("pnl", "sum"),
            win_rate=("pnl", lambda x: round((x > 0).mean() * 100))).sort_values("pnl")
        print("\n  P&L by ticker (worst to best):")
        print("  " + by_ticker.to_string().replace("\n", "\n  "))
        print("\n  Exit reasons:")
        print("  " + res.trades.exit_reason.value_counts().to_string().replace("\n", "\n  "))


def summarize(groups) -> pd.DataFrame:
    return groups.agg(trades=("pnl", "size"), pnl=("pnl", "sum"), avg_r=("r_multiple", "mean"),
                      win_rate=("pnl", lambda x: round((x > 0).mean() * 100))).round(2)


if __name__ == "__main__":
    main()
