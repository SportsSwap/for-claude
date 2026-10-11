"""Mechanics tests on hand-built price bars. They check the rules are applied
exactly as written; they say nothing about whether the strategy makes money."""

from dataclasses import replace
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest  # noqa: E402
from config import DEFAULT_RISK, DEFAULT_STRATEGY  # noqa: E402
from indicators import macd  # noqa: E402
from strategy import add_signals  # noqa: E402

NO_COSTS = replace(DEFAULT_RISK, slippage_pct=0.0, commission_min=0.0, commission_per_share=0.0)
S = replace(DEFAULT_STRATEGY, exit_on_macd_cross_down=False, max_hold_days=None)


def bars(rows, signal_days=(), cross_down_days=(), atr=1.0, momentum=0.0):
    """rows: list of (open, high, low, close). Signals are flagged at the close of the given day index."""
    idx = pd.bdate_range("2024-01-01", periods=len(rows))
    df = pd.DataFrame(rows, index=idx, columns=["Open", "High", "Low", "Close"])
    df["Volume"] = 1_000_000
    df["atr"] = atr
    df["momentum_20d"] = momentum
    df["entry_signal"] = [i in signal_days for i in range(len(rows))]
    df["cross_down"] = [i in cross_down_days for i in range(len(rows))]
    return df


@pytest.fixture
def fake_signals(monkeypatch):
    """Make backtest.run use the prepared columns instead of computing indicators."""
    monkeypatch.setattr(backtest, "add_signals", lambda df, s: df)


FLAT = (100, 100.5, 99.5, 100)


def test_macd_matches_tradingview_recursion():
    close = pd.Series(np.linspace(10, 20, 60) + np.sin(np.arange(60)))
    def ema(xs, n):
        a, out = 2 / (n + 1), [xs[0]]
        for x in xs[1:]:
            out.append(a * x + (1 - a) * out[-1])
        return np.array(out)
    line = ema(close.values, 12) - ema(close.values, 26)
    sig = ema(line, 9)
    m = macd(close)
    assert np.allclose(m["macd"], line)
    assert np.allclose(m["macd_signal"], sig)


def test_cross_up_detected_and_warmup_suppressed():
    # Long decline then a sharp rally: exactly one bullish cross, after warm-up.
    close = np.r_[np.linspace(200, 100, 80), np.linspace(100, 160, 40)]
    df = pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close,
                       "Volume": 1}, index=pd.bdate_range("2023-01-02", periods=len(close)))
    d = add_signals(df, replace(DEFAULT_STRATEGY, trend_sma=None))
    assert d["cross_up"].sum() == 1
    assert d["cross_up"].idxmax() > d.index[79]
    assert not d["entry_signal"].iloc[:36].any()


def test_entry_next_open_and_stop_hit(fake_signals):
    df = bars([FLAT, (101, 101.5, 100.5, 101), FLAT, (100, 100, 98.5, 99)], signal_days=[0])
    res = backtest.run({"X": df}, S, NO_COSTS)
    t = res.trades.iloc[0]
    assert str(t.entry_date) == "2024-01-02" and t.entry_price == 101   # next day's open
    assert t.stop == 99                                                 # 101 - 2 x ATR(1)
    assert t.exit_reason == "stop" and t.exit_price == 99
    assert t.r_multiple == pytest.approx(-1.0)


def test_risk_is_two_percent_of_equity(fake_signals):
    df = bars([FLAT, FLAT, (100, 100, 89, 89)], signal_days=[0], atr=5.0)   # stop $10 away -> 2 shares
    res = backtest.run({"X": df}, S, NO_COSTS)
    assert res.trades.iloc[0].pnl == pytest.approx(-20.0, abs=0.01)    # 2% of $1000


def test_position_capped_at_a_third_of_account():
    shares = backtest.position_size(1000, 1000, entry=100, stop=99.9, r=NO_COSTS)
    assert shares * 100 <= 340 + 1e-9


def test_target_hit(fake_signals):
    df = bars([FLAT, FLAT, (100, 104.5, 99.5, 104)], signal_days=[0])
    t = backtest.run({"X": df}, S, NO_COSTS).trades.iloc[0]
    assert t.exit_reason == "target" and t.exit_price == 104 and t.r_multiple == pytest.approx(2.0)


def test_stop_assumed_first_when_both_touched(fake_signals):
    df = bars([FLAT, FLAT, (100, 105, 97, 101)], signal_days=[0])
    assert backtest.run({"X": df}, S, NO_COSTS).trades.iloc[0].exit_reason == "stop"


def test_gap_below_stop_fills_at_open(fake_signals):
    df = bars([FLAT, FLAT, (95, 96, 94, 95)], signal_days=[0])
    t = backtest.run({"X": df}, S, NO_COSTS).trades.iloc[0]
    assert t.exit_reason == "stop (gap)" and t.exit_price == 95


def test_macd_cross_down_exits_next_open(fake_signals):
    df = bars([FLAT, FLAT, FLAT, (100.7, 101, 100, 100.5)], signal_days=[0], cross_down_days=[2])
    t = backtest.run({"X": df}, replace(S, exit_on_macd_cross_down=True), NO_COSTS).trades.iloc[0]
    assert t.exit_reason == "MACD cross down" and str(t.exit_date) == "2024-01-04" and t.exit_price == 100.7


def test_time_stop(fake_signals):
    df = bars([FLAT] * 8, signal_days=[0])
    t = backtest.run({"X": df}, replace(S, max_hold_days=3), NO_COSTS).trades.iloc[0]
    assert t.exit_reason == "time stop" and t.days_held == 4   # flagged at day 3's close, out at day 4's open


def test_max_positions_and_ranking(fake_signals):
    prices = {f"T{i}": bars([FLAT] * 3, signal_days=[0], momentum=i / 10) for i in range(5)}
    res = backtest.run(prices, S, NO_COSTS)
    assert sorted(res.trades.ticker) == ["T2", "T3", "T4"]
    assert res.skipped_signals == 2


def test_kill_switch_blocks_new_entries(fake_signals):
    # Gap from 100 to 30 on a ~1/3 position takes the account below $800.
    crash = bars([FLAT, FLAT, (30, 30, 30, 30), (30, 30.5, 29.5, 30), (30, 30.5, 29.5, 30)],
                 signal_days=[0, 2, 3])
    res = backtest.run({"X": crash}, S, replace(NO_COSTS, risk_per_trade=1.0))
    assert res.kill_switch_date is not None
    assert len(res.trades) == 1


def test_costs_reduce_pnl_and_equity_reconciles(fake_signals):
    df = bars([FLAT, FLAT, (100, 104.5, 99.5, 104)], signal_days=[0])
    res = backtest.run({"X": df}, S, DEFAULT_RISK)
    t = res.trades.iloc[0]
    assert t.entry_price > 100 and t.exit_price < 104
    assert res.equity.iloc[-1] == pytest.approx(1000 + res.trades.pnl.sum(), abs=0.01)


def test_commission_ibkr_fixed():
    r = DEFAULT_RISK
    assert backtest.commission(10, 100, r) == 1.0          # $1 minimum
    assert backtest.commission(1000, 100, r) == 5.0        # $0.005/share
    assert backtest.commission(0.5, 50, r) == 0.25         # capped at 1% of trade value


def test_runs_end_to_end_on_random_walk():
    rng = np.random.default_rng(0)
    prices = {}
    for t in ["A", "B", "C", "D"]:
        close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, 600)))
        open_ = close * (1 + rng.normal(0, 0.003, 600))
        prices[t] = pd.DataFrame({
            "Open": open_, "High": np.maximum(open_, close) * 1.01,
            "Low": np.minimum(open_, close) * 0.99, "Close": close, "Volume": 1,
        }, index=pd.bdate_range("2020-01-01", periods=600))
    res = backtest.run(prices, DEFAULT_STRATEGY, DEFAULT_RISK)
    st = backtest.stats(res)
    assert st["trades"] > 0
    # P&L is rounded to cents per trade in the log.
    assert res.equity.iloc[-1] == pytest.approx(1000 + res.trades.pnl.sum(), abs=0.005 * len(res.trades) + 0.01)
    # Never more than three positions open at once.
    events = [(d, 1) for d in res.trades.entry_date] + [(d, -1) for d in res.trades.exit_date]
    open_count = peak = 0
    for _, delta in sorted(events, key=lambda e: (e[0], e[1])):
        open_count += delta
        peak = max(peak, open_count)
    assert peak <= 3
