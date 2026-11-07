"""(Parked) Find out whether shorts help, and which short rules (if any) make money.

Runs the SHORT side on its own with every combination of the short settings, on the first
70% of the history (in-sample), then shows how each did on the last 30% it never saw
(out-of-sample). A setting only counts as a fix if it also holds up out-of-sample.
Finally it compares long-only against long + short with the best short setting.

    python optimize_shorts.py                                    # daily bars from 2018 (includes 2022)
    python optimize_shorts.py --interval 2h                      # 2h bars, last ~2 years
    python optimize_shorts.py --group ai --interval 4h

Reading it: avg_r > 0 and profit_factor > 1.2 in BOTH halves, on 20+ trades, is a short rule
worth keeping. If nothing passes, leave shorts off (--sides long / "Long only" in TradingView).
"""

import argparse
from dataclasses import replace
from itertools import product

import pandas as pd

import backtest
import data
from config import DEFAULT_RISK, DEFAULT_STRATEGY, GROUPS, INTERVALS

GRID = {
    "short_trend_side": ["above", "below", "off"],   # stock vs its 200-day EMA
    "short_market_filter": ["QQQ", None],            # only short when QQQ is below its 200-day EMA
    "short_stop_atr_mult": [2.0, 3.0, 4.0],
}
LABELS = {"above": "stock above 200EMA", "below": "stock below 200EMA", "off": "any stock",
          "QQQ": "QQQ downtrend only", None: "any market"}


def summary(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "win_%": None, "avg_r": None, "pf": None, "pnl": 0.0}
    wins, losses = trades[trades.pnl > 0], trades[trades.pnl <= 0]
    lost = -losses.pnl.sum()
    return {"trades": len(trades), "win_%": round(len(wins) / len(trades) * 100),
            "avg_r": round(trades.r_multiple.mean(), 2),
            "pf": round(wins.pnl.sum() / lost, 2) if lost > 0 else float("inf"),
            "pnl": round(trades.pnl.sum(), 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", default="1d", choices=INTERVALS)
    ap.add_argument("--start", default=None, help="default: 2018-01-01 for 1d, all ~2 years intraday")
    ap.add_argument("--group", default="all", choices=list(GROUPS))
    ap.add_argument("--tickers", nargs="+", default=None)
    ap.add_argument("--split", type=float, default=0.7, help="share of history used in-sample (default 0.7)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    tickers = args.tickers or GROUPS[args.group]

    intraday = args.interval != "1d"
    start = args.start or (None if intraday else "2018-01-01")
    daily_start = (pd.Timestamp(start or pd.Timestamp.today()) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    print(f"Loading {args.interval} prices for {len(tickers)} tickers...")
    daily = data.load(tickers, daily_start, "1d", args.refresh, args.offline)
    prices = data.load(tickers, daily_start, args.interval, args.refresh, args.offline) if intraday else daily
    market = data.load(["QQQ"], daily_start, "1d", args.refresh, args.offline).get("QQQ")
    higher = data.load_higher(tickers, daily_start, args.interval, DEFAULT_STRATEGY.higher_tfs, daily,
                              args.refresh, args.offline)
    if not prices or market is None:
        raise SystemExit("Need stock prices and QQQ. Check your internet connection or the cache folder.")

    first = max(pd.Timestamp(start or "1900-01-01"), min(df.index[0] for df in prices.values()))
    last = max(df.index[-1] for df in prices.values())
    cut = first + (last - first) * args.split
    periods = {"in": (first, cut), "out": (cut, last)}
    print(f"In-sample {first.date()} to {cut.date()}, out-of-sample {cut.date()} to {last.date()}\n")

    def run(s, a, b):
        res = backtest.run(prices, s, DEFAULT_RISK, str(a.date()), str(b.date()),
                           daily if intraday else None, None, args.interval, market, higher)
        return res

    rows = []
    for combo in product(*GRID.values()):
        settings = dict(zip(GRID, combo))
        s = replace(DEFAULT_STRATEGY, sides="short", **settings)
        row = {"stocks": LABELS[settings["short_trend_side"]], "market": LABELS[settings["short_market_filter"]],
               "stop_atr": settings["short_stop_atr_mult"]}
        for name, (a, b) in periods.items():
            for k, v in summary(run(s, a, b).trades).items():
                row[f"{name}_{k}"] = v
        rows.append((settings, row))

    table = pd.DataFrame([r for _, r in rows])
    table = table.sort_values(["in_avg_r", "in_trades"], ascending=False, na_position="last")
    pd.set_option("display.width", 200)
    print("SHORTS ONLY, every combination (sorted by in-sample avg R):")
    print(table.to_string(index=False))

    ok = table[(table.in_trades >= 20) & (table.in_avg_r > 0) & (table.out_avg_r > 0)
               & (table.in_pf > 1.2) & (table.out_pf > 1.2)]
    print()
    if ok.empty:
        print("No short setting made money in BOTH halves with 20+ trades. Shorts are hurting this "
              "strategy on this data: trade long only (--sides long, or 'Long only' in TradingView).")
        best = None
    else:
        best_row = ok.iloc[0]
        best = next(st for st, r in rows if r["stocks"] == best_row.stocks and r["market"] == best_row.market
                    and r["stop_atr"] == best_row.stop_atr)
        print(f"Best short setting that held up out-of-sample: {best_row.stocks}, {best_row.market}, "
              f"stop {best_row.stop_atr:g} ATR")

    # Does adding shorts improve the whole strategy?
    print("\nWHOLE STRATEGY, full period:")
    candidates = [("Long only", replace(DEFAULT_STRATEGY, sides="long")),
                  ("Long + short, default short rules", replace(DEFAULT_STRATEGY, sides="both"))]
    if best:
        candidates.append(("Long + short, best short setting", replace(DEFAULT_STRATEGY, sides="both", **best)))
        candidates.append(("Long + short, best, half-size shorts",
                           replace(DEFAULT_STRATEGY, sides="both", short_risk_mult=0.5, **best)))
    out = []
    for name, s in candidates:
        st = backtest.stats(run(s, first, last))
        out.append({"strategy": name, **{k: st.get(k) for k in
                    ["final_equity", "total_return_pct", "max_drawdown_pct", "trades", "win_rate_pct",
                     "avg_r", "profit_factor", "long_pnl", "short_pnl", "kill_switch_hit"]}})
    print(pd.DataFrame(out).set_index("strategy").to_string())
    print("\nOnly trust a setting that wins in both halves. Picking the top row of the in-sample table "
          "alone is curve-fitting.")


if __name__ == "__main__":
    main()
