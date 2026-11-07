"""Bar-by-bar portfolio backtest of the MACD swing strategy. Works on daily or intraday bars.

Order of events on each bar:
  1. Open: exits flagged at the previous close (MACD cross down, time stop) fill at the open.
  2. Open: if a stock gaps through its stop or target, it fills at the open.
  3. Open: entries flagged at the previous close fill at the open.
  4. During the bar: stops and targets are checked against the bar's low and high.
     If both are touched in the same bar, the stop is assumed to have hit first.
  5. Close: equity is marked to market and the next bar's exits and entries are chosen.

Trailing stop: at each close the stop is raised to N x ATR below the highest close since entry
(never lowered) and used from the next bar. R multiples are measured against the FIRST stop.

Shorts mirror longs: the stop sits above the entry and the target below, a gap UP through the
stop fills at the open, and the trade covers when the MACD crosses back up. A short sets aside
cash equal to its value (no leverage), so it is sized and limited exactly like a long, and pays
a stock-loan fee for the days it is open.
"""

from dataclasses import dataclass, field, replace
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
    side: int = 1                       # +1 long, -1 short
    first_stop: float = 0.0             # the stop at entry; R is measured against this
    best_close: float = 0.0             # highest close since entry (lowest for shorts)
    depth_atr: float | None = None      # MACD in ATRs from zero at the signal bar
    mtf: str | None = None              # lower timeframes that agreed, e.g. "2/3"
    days_held: int = 1                  # trading sessions, counting the entry session
    last_day: object = None
    exit_next_open: str | None = None


    def value(self, price: float) -> float:
        """What the position is worth at this price. A short's cash collateral grows as the price falls."""
        return self.shares * (self.entry_price + self.side * (price - self.entry_price))

    def hits_stop(self, price: float) -> bool:
        return price <= self.stop if self.side > 0 else price >= self.stop

    def hits_target(self, price: float) -> bool:
        return self.target is not None and (price >= self.target if self.side > 0 else price <= self.target)


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
    """Works for both sides: the stop is below a long's entry and above a short's."""
    risk_per_share = abs(entry - stop)
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
        daily: dict[str, pd.DataFrame] | None = None,
        lower: dict[str, dict[str, pd.DataFrame]] | None = None, interval: str = "1d",
        market: pd.DataFrame | None = None) -> Result:
    """lower: {ticker: {"15m": bars, ...}} for the lower-timeframe check (data.load_lower).
    market: daily bars of the index used by the short market filter (QQQ)."""
    rows: dict[str, dict] = {}
    for t, df in prices.items():
        if not len(df):
            continue
        d = add_signals(df, s, (daily or {}).get(t), (lower or {}).get(t), interval, market)
        d["prev_atr"] = d["atr"].shift(1)
        rows[t] = d.to_dict("index")

    times = sorted(set().union(*(rows_t.keys() for rows_t in rows.values()))) if rows else []
    times = [ts for ts in times if (start is None or ts >= pd.Timestamp(start))
             and (end is None or ts < pd.Timestamp(end) + pd.Timedelta(days=1))]

    cash = r.starting_capital
    positions: dict[str, Position] = {}
    pending_entries: list[tuple[str, int, dict]] = []
    trades: list[dict] = []
    equity_curve: dict[pd.Timestamp, float] = {}
    last_close: dict[str, float] = {}
    kill_date = None
    skipped = 0
    equity = cash

    def close_position(p: Position, ts, raw_price: float, reason: str):
        nonlocal cash
        price = raw_price * (1 - p.side * r.slippage_pct)    # sell lower, buy to cover higher
        fee = commission(p.shares, price, r)
        if p.side < 0:
            days = max((ts - p.entry_time).days, 1)
            fee += p.shares * p.entry_price * r.short_borrow_pct_per_year * days / 365
        proceeds = p.value(price) - fee
        cash += proceeds
        pnl = proceeds - p.entry_cost
        risk_dollars = p.shares * abs(p.entry_price - p.first_stop)
        trades.append({
            "ticker": p.ticker,
            "side": "long" if p.side > 0 else "short",
            "entry_date": fmt_time(p.entry_time),
            "entry_price": round(p.entry_price, 4),
            "exit_date": fmt_time(ts),
            "exit_price": round(price, 4),
            "shares": p.shares,
            "stop": round(p.first_stop, 4),
            "exit_stop": round(p.stop, 4),
            "target": round(p.target, 4) if p.target else None,
            "days_held": p.days_held,
            "exit_reason": reason,
            "depth_atr": round(p.depth_atr, 2) if p.depth_atr is not None else None,
            "mtf_agree": p.mtf,
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
            elif p.hits_stop(bar["Open"]):
                close_position(p, ts, bar["Open"], "stop (gap)" if p.stop == p.first_stop else "trailing stop (gap)")
            elif p.hits_target(bar["Open"]):
                close_position(p, ts, bar["Open"], "target (gap)")

        # 3. Entries at the open, sized off the previous bar's equity.
        for t, side, sig in pending_entries:
            bar = bars.get(t)
            if bar is None or t in positions or pd.isna(bar["prev_atr"]):
                continue
            entry = bar["Open"] * (1 + side * r.slippage_pct)   # buy higher, short lower
            mult = s.short_stop_atr_mult if side < 0 and s.short_stop_atr_mult else s.stop_atr_mult
            stop = entry - side * mult * bar["prev_atr"]
            risk = r if side > 0 else replace(r, risk_per_trade=r.risk_per_trade * s.short_risk_mult)
            shares = position_size(equity, cash, entry, stop, risk)
            if shares <= 0 or stop <= 0:
                skipped += 1
                continue
            cost = shares * entry + commission(shares, entry, r)
            cash -= cost
            target = entry + s.target_r * (entry - stop) if s.target_r else None
            mtf = None
            if pd.notna(sig.get("mtf_max", float("nan"))):
                agreed = sig["mtf_up"] if side > 0 else sig["mtf_down"]
                mtf = f"{int(agreed)}/{int(sig['mtf_max'])}"
            depth = sig.get("depth_atr")
            positions[t] = Position(t, ts, entry, shares, stop, target, cost, side, stop, entry,
                                    depth if depth is not None and pd.notna(depth) else None, mtf,
                                    last_day=day)
        pending_entries = []

        # 4. Stops and targets during the bar.
        for p in list(positions.values()):
            bar = bars.get(p.ticker)
            if bar is None:
                continue
            worst, best = (bar["Low"], bar["High"]) if p.side > 0 else (bar["High"], bar["Low"])
            if p.hits_stop(worst):
                close_position(p, ts, p.stop, "stop" if p.stop == p.first_stop else "trailing stop")
            elif p.hits_target(best):
                close_position(p, ts, p.target, "target")

        # 5. Close: mark to market, then plan the next bar.
        for t, bar in bars.items():
            last_close[t] = bar["Close"]
        equity = cash + sum(p.value(last_close[p.ticker]) for p in positions.values())
        equity_curve[ts] = equity

        for p in positions.values():
            bar = bars.get(p.ticker)
            if bar is None:
                continue
            if s.trail_atr_mult and pd.notna(bar["atr"]):
                if p.side > 0:
                    p.best_close = max(p.best_close, bar["Close"])
                    p.stop = max(p.stop, p.best_close - s.trail_atr_mult * bar["atr"])
                else:
                    p.best_close = min(p.best_close, bar["Close"])
                    p.stop = min(p.stop, p.best_close + s.trail_atr_mult * bar["atr"])
            crossed_back = bar["cross_down"] if p.side > 0 else bar["cross_up"]
            beyond_zero = bar.get("macd", 0) * p.side > 0       # above zero for longs, below for shorts
            if crossed_back and (s.macd_exit == "any" or (s.macd_exit == "above_zero" and beyond_zero)):
                p.exit_next_open = (("MACD sell setup" if beyond_zero else "MACD cross down") if p.side > 0
                                    else ("MACD buy setup" if beyond_zero else "MACD cross up"))
            elif s.max_hold_days and p.days_held >= s.max_hold_days:
                p.exit_next_open = "time stop"

        if kill_date is None and equity <= r.starting_capital * r.kill_switch_pct:
            kill_date = ts
        if kill_date is not None:
            continue

        # Longs rank highest-first, shorts lowest-first (the weakest stock is the best short).
        candidates = []
        for t, bar in bars.items():
            held = positions.get(t)
            # A stock already held is skipped, unless that trade exits at the next open: then a new
            # signal can take its place (the sell setup that ends a long is also a short signal).
            if held is not None and not held.exit_next_open:
                continue
            score = bar[s.rank_by] if pd.notna(bar[s.rank_by]) else None
            if bar["entry_signal"]:
                candidates.append((t, 1, score if score is not None else -1e9, bar))
            elif bar.get("short_signal", False):
                candidates.append((t, -1, -score if score is not None else -1e9, bar))
        candidates.sort(key=lambda c: -c[2])
        open_slots = r.max_positions - sum(1 for p in positions.values() if not p.exit_next_open)
        pending_entries = [(t, side, bar) for t, side, _, bar in candidates[:max(open_slots, 0)]]
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
        if "side" in tr and (tr.side == "short").any():
            for side in ("long", "short"):
                part = tr[tr.side == side]
                out[f"{side}_trades"] = len(part)
                out[f"{side}_pnl"] = round(part.pnl.sum(), 2)
                out[f"{side}_win_rate_pct"] = round((part.pnl > 0).mean() * 100, 1) if len(part) else 0.0
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
