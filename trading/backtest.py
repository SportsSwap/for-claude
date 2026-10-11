"""Bar-by-bar portfolio backtest of the MACD swing strategy. Works on daily or intraday bars.

Order of events on each bar:
  1. Open: exits flagged at the previous close (MACD cross down, time stop) fill at the open.
  2. Open: if a stock gaps through its stop or target, it fills at the open.
  3. Open: entries flagged at the previous close fill at the open.
  4. During the bar: stops and targets are checked against the bar's low and high.
     If both are touched in the same bar, the stop is assumed to have hit first.
  5. Close: equity is marked to market and the next bar's exits and entries are chosen.
"""

from dataclasses import dataclass, field
import math

import pandas as pd

from config import Risk, Strategy
from strategy import add_signals


@dataclass
class Position:
    ticker: str
    entry_time: pd.Timestamp
    entry_price: float
    shares: float
    stop: float
    target: float | None
    entry_cost: float
    days_held: int = 1                  # trading sessions, counting the entry session
    last_day: object = None
    exit_next_open: str | None = None


@dataclass
class Result:
    strategy: Strategy
    risk: Risk
    trades: pd.DataFrame
    equity: pd.Series
    kill_switch_date: pd.Timestamp | None = None
    skipped_signals: int = 0
    notes: list[str] = field(default_factory=list)


def fmt_time(ts: pd.Timestamp) -> str:
    return str(ts.date()) if ts == ts.normalize() else ts.strftime("%Y-%m-%d %H:%M")


def commission(shares: float, price: float, r: Risk) -> float:
    fee = max(r.commission_min, shares * r.commission_per_share)
    return min(fee, r.commission_max_pct * shares * price)


def position_size(equity: float, cash: float, entry: float, stop: float, r: Risk) -> float:
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return 0.0
    by_risk = equity * r.risk_per_trade / risk_per_share
    by_cap = equity * r.max_position_pct / entry
    by_cash = cash / (entry * (1 + r.commission_max_pct))
    shares = max(0.0, min(by_risk, by_cap, by_cash))
    if not r.fractional_shares:
        return float(math.floor(shares))
    return math.floor(shares * 10_000) / 10_000


def run(prices: dict[str, pd.DataFrame], s: Strategy, r: Risk,
        start: str | None = None, end: str | None = None,
        daily: dict[str, pd.DataFrame] | None = None) -> Result:
    rows: dict[str, dict] = {}
    for t, df in prices.items():
        if not len(df):
            continue
        d = add_signals(df, s, (daily or {}).get(t))
        d["prev_atr"] = d["atr"].shift(1)
        rows[t] = d.to_dict("index")

    times = sorted(set().union(*(rows_t.keys() for rows_t in rows.values()))) if rows else []
    times = [ts for ts in times if (start is None or ts >= pd.Timestamp(start))
             and (end is None or ts < pd.Timestamp(end) + pd.Timedelta(days=1))]

    cash = r.starting_capital
    positions: dict[str, Position] = {}
    pending_entries: list[str] = []
    trades: list[dict] = []
    equity_curve: dict[pd.Timestamp, float] = {}
    last_close: dict[str, float] = {}
    kill_date = None
    skipped = 0
    equity = cash

    def close_position(p: Position, ts, raw_price: float, reason: str):
        nonlocal cash
        price = raw_price * (1 - r.slippage_pct)
        fee = commission(p.shares, price, r)
        cash += p.shares * price - fee
        pnl = p.shares * price - fee - p.entry_cost
        risk_dollars = p.shares * (p.entry_price - p.stop)
        trades.append({
            "ticker": p.ticker,
            "entry_date": fmt_time(p.entry_time),
            "entry_price": round(p.entry_price, 4),
            "exit_date": fmt_time(ts),
            "exit_price": round(price, 4),
            "shares": p.shares,
            "stop": round(p.stop, 4),
            "target": round(p.target, 4) if p.target else None,
            "days_held": p.days_held,
            "exit_reason": reason,
            "pnl": round(pnl, 2),
            "r_multiple": round(pnl / risk_dollars, 2) if risk_dollars > 0 else 0.0,
        })
        del positions[p.ticker]

    for ts in times:
        bars = {t: rows_t[ts] for t, rows_t in rows.items() if ts in rows_t}
        day = ts.date()

        # 1-2. Exits at the open.
        for p in list(positions.values()):
            bar = bars.get(p.ticker)
            if bar is None:
                continue
            if day != p.last_day:
                p.days_held += 1
                p.last_day = day
            if p.exit_next_open:
                close_position(p, ts, bar["Open"], p.exit_next_open)
            elif bar["Open"] <= p.stop:
                close_position(p, ts, bar["Open"], "stop (gap)")
            elif p.target and bar["Open"] >= p.target:
                close_position(p, ts, bar["Open"], "target (gap)")

        # 3. Entries at the open, sized off the previous bar's equity.
        for t in pending_entries:
            bar = bars.get(t)
            if bar is None or t in positions or pd.isna(bar["prev_atr"]):
                continue
            entry = bar["Open"] * (1 + r.slippage_pct)
            stop = entry - s.stop_atr_mult * bar["prev_atr"]
            shares = position_size(equity, cash, entry, stop, r)
            if shares <= 0 or stop <= 0:
                skipped += 1
                continue
            cost = shares * entry + commission(shares, entry, r)
            cash -= cost
            target = entry + s.target_r * (entry - stop) if s.target_r else None
            positions[t] = Position(t, ts, entry, shares, stop, target, cost, last_day=day)
        pending_entries = []

        # 4. Stops and targets during the bar.
        for p in list(positions.values()):
            bar = bars.get(p.ticker)
            if bar is None:
                continue
            if bar["Low"] <= p.stop:
                close_position(p, ts, p.stop, "stop")
            elif p.target and bar["High"] >= p.target:
                close_position(p, ts, p.target, "target")

        # 5. Close: mark to market, then plan the next bar.
        for t, bar in bars.items():
            last_close[t] = bar["Close"]
        equity = cash + sum(p.shares * last_close[p.ticker] for p in positions.values())
        equity_curve[ts] = equity

        for p in positions.values():
            bar = bars.get(p.ticker)
            if bar is None:
                continue
            if s.exit_on_macd_cross_down and bar["cross_down"]:
                p.exit_next_open = "MACD cross down"
            elif s.max_hold_days and p.days_held >= s.max_hold_days:
                p.exit_next_open = "time stop"

        if kill_date is None and equity <= r.starting_capital * r.kill_switch_pct:
            kill_date = ts
        if kill_date is not None:
            continue

        candidates = [(t, bar[s.rank_by]) for t, bar in bars.items()
                      if bar["entry_signal"] and t not in positions]
        candidates.sort(key=lambda c: -(c[1] if pd.notna(c[1]) else -1e9))
        open_slots = r.max_positions - sum(1 for p in positions.values() if not p.exit_next_open)
        pending_entries = [t for t, _ in candidates[:max(open_slots, 0)]]
        skipped += max(len(candidates) - len(pending_entries), 0)

    # Close anything still open at the last available price.
    if times:
        for p in list(positions.values()):
            close_position(p, times[-1], last_close[p.ticker], "end of test")
        equity_curve[times[-1]] = cash

    return Result(s, r, pd.DataFrame(trades), pd.Series(equity_curve, name="equity", dtype=float),
                  kill_date, skipped)


def stats(res: Result) -> dict:
    eq, tr = res.equity, res.trades
    if eq.empty:
        return {"strategy": res.strategy.name, "trades": 0}
    start_cap = res.risk.starting_capital
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    drawdown = eq / eq.cummax() - 1
    out = {
        "strategy": res.strategy.name,
        "start": eq.index[0].date(),
        "end": eq.index[-1].date(),
        "final_equity": round(eq.iloc[-1], 2),
        "total_return_pct": round((eq.iloc[-1] / start_cap - 1) * 100, 1),
        "cagr_pct": round(((eq.iloc[-1] / start_cap) ** (1 / years) - 1) * 100, 1),
        "max_drawdown_pct": round(drawdown.min() * 100, 1),
        "lowest_equity": round(eq.min(), 2),
        "trades": len(tr),
        "kill_switch_hit": fmt_time(res.kill_switch_date) if res.kill_switch_date is not None else "no",
    }
    if len(tr):
        wins, losses = tr[tr.pnl > 0], tr[tr.pnl <= 0]
        streak = longest = 0
        for pnl in tr.sort_values("exit_date").pnl:
            streak = streak + 1 if pnl <= 0 else 0
            longest = max(longest, streak)
        out.update({
            "win_rate_pct": round(len(wins) / len(tr) * 100, 1),
            "avg_win": round(wins.pnl.mean(), 2) if len(wins) else 0.0,
            "avg_loss": round(losses.pnl.mean(), 2) if len(losses) else 0.0,
            "avg_r": round(tr.r_multiple.mean(), 2),
            "profit_factor": round(wins.pnl.sum() / -losses.pnl.sum(), 2) if losses.pnl.sum() < 0 else float("inf"),
            "longest_losing_streak": longest,
            "avg_days_held": round(tr.days_held.mean(), 1),
        })
    return out


def buy_and_hold(df: pd.DataFrame, capital: float, start=None, end=None) -> dict:
    px = df["Close"]
    if start is not None:
        px = px[px.index >= pd.Timestamp(start).normalize()]
    if end is not None:
        px = px[px.index <= pd.Timestamp(end)]
    if px.empty:
        return {}
    eq = capital * px / px.iloc[0]
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    return {
        "final_equity": round(eq.iloc[-1], 2),
        "total_return_pct": round((eq.iloc[-1] / capital - 1) * 100, 1),
        "cagr_pct": round(((eq.iloc[-1] / capital) ** (1 / years) - 1) * 100, 1),
        "max_drawdown_pct": round((eq / eq.cummax() - 1).min() * 100, 1),
    }
