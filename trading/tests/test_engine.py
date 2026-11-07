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
from data import resample_session  # noqa: E402
from strategy import add_signals  # noqa: E402

NO_COSTS = replace(DEFAULT_RISK, slippage_pct=0.0, commission_min=0.0, commission_per_share=0.0)
# Mechanics tests use simple fixed exits: 2-ATR stop, 2R target, nothing else.
S = replace(DEFAULT_STRATEGY, macd_exit="off", max_hold_days=None, stop_atr_mult=2.0, target_r=2.0,
            trail_atr_mult=None, short_market_filter=None)
CLASSIC = replace(DEFAULT_STRATEGY, macd_slow=26, require_below_zero=False, trend_ma=None)


def bars(rows, signal_days=(), cross_down_days=(), atr=1.0, momentum=0.0):
    """rows: list of (open, high, low, close). Signals are flagged at the close of the given day index."""
    idx = pd.bdate_range("2024-01-01", periods=len(rows))
    df = pd.DataFrame(rows, index=idx, columns=["Open", "High", "Low", "Close"])
    df["Volume"] = 1_000_000
    df["atr"] = atr
    df["momentum_20"] = momentum
    df["entry_signal"] = [i in signal_days for i in range(len(rows))]
    df["cross_down"] = [i in cross_down_days for i in range(len(rows))]
    return df


@pytest.fixture
def fake_signals(monkeypatch):
    """Make backtest.run use the prepared columns instead of computing indicators."""
    monkeypatch.setattr(backtest, "add_signals", lambda df, s, daily=None, lower=None, interval="1d", market=None, higher=None: df)


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
    d = add_signals(df, CLASSIC)
    assert d["cross_up"].sum() == 1
    assert d["cross_up"].idxmax() > d.index[79]
    assert d["entry_signal"].sum() == 1
    assert not d["entry_signal"].iloc[:53].any()


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
    t = backtest.run({"X": df}, replace(S, macd_exit="any"), NO_COSTS).trades.iloc[0]
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
    res = backtest.run(prices, CLASSIC, DEFAULT_RISK)
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


# --- Your setup: MACD 12/144/9, 200-day rule, zero-line crosses, intraday bars ---

def ohlc(close, index):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close,
                         "Volume": 1}, index=index)


def test_dip_buy_requires_cross_below_zero_and_price_under_200_day():
    # Fall then bounce: the MACD crosses its signal line while still under zero.
    close = np.r_[np.linspace(300, 300, 300), np.linspace(300, 200, 60), np.linspace(200, 215, 20)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    df = ohlc(close, idx)
    d = add_signals(df, DEFAULT_STRATEGY, daily=df)
    hits = d[d.entry_signal]
    assert len(hits) >= 1
    assert (hits.macd < 0).all() and (hits.Close < hits.trend_ma).all()
    # Same bounce but the stock is above its 200-day average: no dip-buy signal.
    lifted = ohlc(close + 500, idx)
    low_daily = ohlc(np.full(len(close), 100.0), idx)
    assert not add_signals(lifted, DEFAULT_STRATEGY, daily=low_daily).entry_signal.any()


def test_200_day_ema_on_intraday_bars_uses_yesterdays_value():
    days = pd.bdate_range("2023-01-02", periods=210)
    daily = ohlc(np.arange(210, dtype=float), days)
    times = [d + pd.Timedelta(hours=h, minutes=30) for d in days[-3:] for h in (9, 11, 13, 15)]
    bars_2h = ohlc(np.full(len(times), 50.0), pd.DatetimeIndex(times))
    d = add_signals(bars_2h, DEFAULT_STRATEGY, daily=daily)
    expected = daily.Close.ewm(span=200, adjust=False).mean().shift(1)
    for ts, val in d.trend_ma.items():
        assert val == pytest.approx(expected.loc[ts.normalize()])


def test_zero_line_cross_and_price_not_run_filter():
    close = np.r_[np.linspace(300, 200, 300), np.linspace(200, 260, 150)]
    df = ohlc(close, pd.bdate_range("2022-01-03", periods=len(close)))
    zero = replace(DEFAULT_STRATEGY, entry="zero_cross", require_below_zero=False, trend_ma=None, confirm_bars=0)
    d = add_signals(df, zero)
    hits = d[d.entry_signal]
    assert len(hits) == 1
    i = d.index.get_loc(hits.index[0])
    assert d.macd.iloc[i] > 0 and d.macd.iloc[i - 1] <= 0
    # By the time the zero line is crossed the price has run well off its low, so a tight filter blocks it.
    assert d.loc[hits.index[0], "Close"] - d.Low.iloc[i - 19:i + 1].min() > 0.5 * d.atr.iloc[i]
    assert not add_signals(df, replace(zero, max_run_atr=0.5)).entry_signal.any()


def test_resample_2h_and_4h_match_tradingview_sessions():
    day = pd.Timestamp("2024-03-05")
    times = [day + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(hours=h) for h in range(7)]
    h1 = pd.DataFrame({"Open": range(1, 8), "High": range(11, 18), "Low": range(0, 7),
                       "Close": range(2, 9), "Volume": [10] * 7}, index=pd.DatetimeIndex(times), dtype=float)
    two = resample_session(h1, 2)
    assert [t.strftime("%H:%M") for t in two.index] == ["09:30", "11:30", "13:30", "15:30"]
    assert two.iloc[0].tolist() == [1, 12, 0, 3, 20]
    four = resample_session(h1, 4)
    assert [t.strftime("%H:%M") for t in four.index] == ["09:30", "13:30"]
    assert four.iloc[1].tolist() == [5, 17, 4, 8, 30]


def test_time_stop_counts_trading_days_not_bars(fake_signals):
    times = [d + pd.Timedelta(hours=h, minutes=30) for d in pd.bdate_range("2024-01-01", periods=5)
             for h in (9, 11, 13, 15)]
    df = pd.DataFrame([FLAT] * len(times), index=pd.DatetimeIndex(times), columns=["Open", "High", "Low", "Close"])
    df["Volume"], df["atr"], df["momentum_20"], df["cross_down"] = 1, 1.0, 0.0, False
    df["entry_signal"] = [i == 0 for i in range(len(times))]
    t = backtest.run({"X": df}, replace(S, max_hold_days=2), NO_COSTS).trades.iloc[0]
    assert t.entry_date == "2024-01-01 11:30"
    assert t.exit_reason == "time stop" and t.exit_date == "2024-01-02 11:30"


def test_higher_risk_pct_means_bigger_position(fake_signals):
    df = bars([FLAT, FLAT, (100, 100, 89, 89)], signal_days=[0], atr=5.0)
    small = backtest.run({"X": df}, S, NO_COSTS).trades.iloc[0]
    big = backtest.run({"X": df}, S, replace(NO_COSTS, risk_per_trade=0.03)).trades.iloc[0]
    assert big.pnl == pytest.approx(1.5 * small.pnl, abs=0.02)


# --- Shorts: MACD crosses down above zero while price is above the 200-day EMA ---

SHORT = replace(S, sides="short")
NO_BORROW = replace(NO_COSTS, short_borrow_pct_per_year=0.0)


def short_bars(rows, signal_days=(), cross_up_days=(), atr=1.0, momentum=0.0):
    df = bars(rows, atr=atr, momentum=momentum)
    df["entry_signal"] = False
    df["short_signal"] = [i in signal_days for i in range(len(rows))]
    df["cross_up"] = [i in cross_up_days for i in range(len(rows))]
    return df


def test_short_signal_is_the_mirror_of_the_dip_buy():
    # Rise then roll over: the MACD crosses down through its signal line while still above zero.
    close = np.r_[np.linspace(100, 100, 300), np.linspace(100, 200, 60), np.linspace(200, 185, 20)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    df = ohlc(close, idx)
    d = add_signals(df, SHORT, daily=df)
    hits = d[d.short_signal]
    assert len(hits) >= 1
    assert (hits.macd > 0).all() and (hits.Close > hits.trend_ma).all()
    assert not d.entry_signal.any()                         # shorts only: no longs
    # Same roll-over but the stock is below its 200-day average: no short.
    high_daily = ohlc(np.full(len(close), 1000.0), idx)
    assert not add_signals(df, SHORT, daily=high_daily).short_signal.any()
    # Long-only mode never shorts; the default (both sides) does.
    assert not add_signals(df, replace(DEFAULT_STRATEGY, sides="long"), daily=df).short_signal.any()
    assert add_signals(df, replace(DEFAULT_STRATEGY, short_market_filter=None), daily=df).short_signal.any()


def test_short_entry_stop_above_and_stop_hit(fake_signals):
    df = short_bars([FLAT, (101, 101.5, 100.5, 101), FLAT, (100, 111.5, 100, 111)], signal_days=[0], atr=5.0)
    t = backtest.run({"X": df}, SHORT, NO_BORROW).trades.iloc[0]
    assert t.side == "short" and t.entry_price == 101 and str(t.entry_date) == "2024-01-02"
    assert t.stop == 111 and t.target == 81                  # 101 + 2 x ATR(5); 2R below
    assert t.exit_reason == "stop" and t.exit_price == 111
    assert t.r_multiple == pytest.approx(-1.0)
    assert t.pnl == pytest.approx(-20.0, abs=0.01)           # 2% of $1000, same as a long


def test_short_target_hit_makes_money(fake_signals):
    df = short_bars([FLAT, FLAT, (100, 100.5, 95.5, 96)], signal_days=[0])
    t = backtest.run({"X": df}, SHORT, NO_BORROW).trades.iloc[0]
    assert t.exit_reason == "target" and t.exit_price == 96 and t.r_multiple == pytest.approx(2.0)
    assert t.pnl > 0


def test_short_stop_assumed_first_when_both_touched(fake_signals):
    df = short_bars([FLAT, FLAT, (100, 103, 95, 99)], signal_days=[0])
    assert backtest.run({"X": df}, SHORT, NO_BORROW).trades.iloc[0].exit_reason == "stop"


def test_short_gap_up_through_stop_fills_at_open(fake_signals):
    df = short_bars([FLAT, FLAT, (105, 106, 104, 105)], signal_days=[0])
    t = backtest.run({"X": df}, SHORT, NO_BORROW).trades.iloc[0]
    assert t.exit_reason == "stop (gap)" and t.exit_price == 105 and t.r_multiple < -1


def test_short_covers_on_macd_cross_up(fake_signals):
    df = short_bars([FLAT, FLAT, FLAT, (99.3, 100, 99, 99.5)], signal_days=[0], cross_up_days=[2])
    t = backtest.run({"X": df}, replace(SHORT, macd_exit="any"), NO_BORROW).trades.iloc[0]
    assert t.exit_reason == "MACD cross up" and str(t.exit_date) == "2024-01-04" and t.exit_price == 99.3


def test_short_costs_and_equity_reconcile(fake_signals):
    df = short_bars([FLAT, FLAT, FLAT, (99, 99.5, 98.5, 99)], signal_days=[0])
    free = backtest.run({"X": df}, SHORT, NO_BORROW)
    paid = backtest.run({"X": df}, SHORT, DEFAULT_RISK)
    t = paid.trades.iloc[0]
    assert t.entry_price < 100                               # shorted below the open (slippage)
    assert paid.trades.pnl.sum() < free.trades.pnl.sum()     # commissions + borrow fee
    assert paid.equity.iloc[-1] == pytest.approx(1000 + paid.trades.pnl.sum(), abs=0.01)
    # Mark-to-market while open: price fell from 100 to 99, so the short is up.
    assert free.equity.iloc[2] == pytest.approx(1000, abs=0.01)
    assert free.equity.iloc[3] > 1000


def test_both_sides_share_the_position_limit(fake_signals):
    # Longs rank by highest momentum, shorts by lowest, on one scale.
    prices = {"L_strong": bars([FLAT] * 3, signal_days=[0], momentum=0.7),
              "L_weak": bars([FLAT] * 3, signal_days=[0], momentum=0.1),
              "S_weak": short_bars([FLAT] * 3, signal_days=[0], momentum=-0.65),
              "S_mid": short_bars([FLAT] * 3, signal_days=[0], momentum=-0.6),
              "S_strong": short_bars([FLAT] * 3, signal_days=[0], momentum=0.2)}
    res = backtest.run(prices, replace(S, sides="both"), NO_COSTS)
    assert sorted(res.trades.ticker) == ["L_strong", "S_mid", "S_weak"]
    assert res.skipped_signals == 2
    assert dict(zip(res.trades.ticker, res.trades.side)) == {"L_strong": "long", "S_mid": "short", "S_weak": "short"}


# --- Buffer: the cross must happen far enough from zero ---

def test_buffer_blocks_crosses_just_under_zero():
    close = np.r_[np.linspace(300, 300, 300), np.linspace(300, 200, 60), np.linspace(200, 215, 20)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    df = ohlc(close, idx)
    none = add_signals(df, replace(DEFAULT_STRATEGY, min_macd_depth_atr=0.0), daily=df)
    hit = none[none.entry_signal]
    assert len(hit) == 1
    depth = abs(hit.depth_atr.iloc[0])
    assert hit.depth_atr.iloc[0] == pytest.approx(hit.macd.iloc[0] / hit.atr.iloc[0])
    # A buffer just under the cross depth keeps it; just over removes it.
    keep = add_signals(df, replace(DEFAULT_STRATEGY, min_macd_depth_atr=depth * 0.9), daily=df)
    drop = add_signals(df, replace(DEFAULT_STRATEGY, min_macd_depth_atr=depth * 1.1), daily=df)
    assert keep.entry_signal.sum() == 1 and not drop.entry_signal.any()


def test_buffer_mirrors_for_shorts():
    close = np.r_[np.linspace(100, 100, 300), np.linspace(100, 200, 60), np.linspace(200, 185, 20)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    df = ohlc(close, idx)
    base = add_signals(df, replace(SHORT, min_macd_depth_atr=0.0), daily=df)
    depth = base[base.short_signal].depth_atr.iloc[0]
    assert depth > 0
    assert add_signals(df, replace(SHORT, min_macd_depth_atr=depth * 0.9), daily=df).short_signal.any()
    assert not add_signals(df, replace(SHORT, min_macd_depth_atr=depth * 1.1), daily=df).short_signal.any()


# --- Lower-timeframe agreement ---

def session_bars(day, minutes, closes):
    start = pd.Timestamp(day) + pd.Timedelta(hours=9, minutes=30)
    idx = pd.DatetimeIndex([start + pd.Timedelta(minutes=minutes * i) for i in range(len(closes))])
    return ohlc(closes, idx)


def test_resample_45m_from_15m():
    from data import resample_session
    m15 = session_bars("2024-03-05", 15, np.arange(26, dtype=float))   # 9:30 .. 15:45
    m45 = resample_session(m15, 3)
    assert [t.strftime("%H:%M") for t in m45.index][:4] == ["09:30", "10:15", "11:00", "11:45"]
    assert m45.index[-1].strftime("%H:%M") == "15:30"          # last bar: 15:30-16:00 only
    assert m45.Close.iloc[0] == 2 and m45.Open.iloc[1] == 3


def test_bar_ends_cut_at_close():
    from data import bar_ends
    two_h = session_bars("2024-03-05", 120, [1, 2, 3, 4])
    ends = bar_ends(two_h.index, "2h")
    assert [t.strftime("%H:%M") for t in ends] == ["11:30", "13:30", "15:30", "16:00"]


def test_lower_tf_uses_only_bars_closed_by_the_chart_close():
    from strategy import lower_tf_agreement
    s = replace(DEFAULT_STRATEGY, macd_slow=5, macd_fast=2, macd_signal=2)
    # Lower bars rise steadily, then the 45m bar that STARTS at 11:00 (ends 11:45) crashes.
    days = pd.bdate_range("2024-03-01", periods=3)
    m45 = pd.concat([session_bars(d, 45, (np.arange(9, dtype=float) + 9 * k) ** 3 / 10 + 100)
                     for k, d in enumerate(days)])                   # accelerating rise
    last_day = days[-1] + pd.Timedelta(hours=11)
    m45.loc[last_day, ["Open", "High", "Low", "Close"]] = [0.0, 1.0, -1.0, 0.0]
    chart = session_bars(days[-1], 120, [100.0, 100, 100, 100])
    out = lower_tf_agreement(chart, "2h", {"45m": m45}, s)
    # The 9:30-11:30 2h bar must use the 10:15 45m bar (rising), not the 11:00 crash bar.
    assert out.loc[chart.index[0], "mtf_up"] == 1 and out.loc[chart.index[0], "mtf_n"] == 1
    # The 11:30-13:30 bar sees the crash's aftermath: no longer agreeing with a buy.
    assert out.loc[chart.index[1], "mtf_up"] == 0
    # 15m, 30m and 45m all sit under a 2h chart, even though only 45m data was given.
    assert (out.mtf_max == 3).all() and (out.mtf_n == 1).all()


def test_lower_tf_missing_data_does_not_reach_back_to_old_bars():
    from strategy import lower_tf_agreement
    s = replace(DEFAULT_STRATEGY, macd_slow=5, macd_fast=2, macd_signal=2)
    m15 = session_bars("2024-03-01", 15, np.arange(26, dtype=float))
    chart = session_bars("2024-03-08", 120, [1.0, 2, 3, 4])            # a week later, no 15m data
    out = lower_tf_agreement(chart, "2h", {"15m": m15}, s)
    assert (out.mtf_n == 0).all() and (out.mtf_up == 0).all()


def test_confirm_filter_counts_agreeing_timeframes():
    close = np.r_[np.linspace(300, 300, 300), np.linspace(300, 200, 60), np.linspace(200, 215, 20)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    df = ohlc(close, idx)
    base = add_signals(df, DEFAULT_STRATEGY, daily=df)
    assert base.entry_signal.sum() == 1
    # Fake "lower timeframe" columns via a stand-in: confirm_min with no lower data -> no trades.
    assert not add_signals(df, replace(DEFAULT_STRATEGY, confirm_min=1), daily=df).entry_signal.any()
    from strategy import _confirmed
    d = base.assign(mtf_up=[2] * len(df), mtf_down=0, mtf_n=3, mtf_max=3)
    assert _confirmed(d, replace(DEFAULT_STRATEGY, confirm_min=2), "mtf_up").all()
    assert not _confirmed(d, replace(DEFAULT_STRATEGY, confirm_min=3), "mtf_up").any()
    # Only one lower timeframe under this chart: needing "2" means that one must agree.
    d1 = base.assign(mtf_up=1, mtf_down=0, mtf_n=1, mtf_max=1)
    assert _confirmed(d1, replace(DEFAULT_STRATEGY, confirm_min=2), "mtf_up").all()


def test_trade_log_records_depth_and_agreement(fake_signals):
    df = bars([FLAT, FLAT, (100, 104.5, 99.5, 104)], signal_days=[0])
    df["depth_atr"], df["mtf_up"], df["mtf_down"], df["mtf_max"] = -1.25, 2, 0, 3
    t = backtest.run({"X": df}, S, NO_COSTS).trades.iloc[0]
    assert t.depth_atr == -1.25 and t.mtf_agree == "2/3"


def test_lower_tf_warmup_is_unknown_not_disagree():
    from strategy import lower_tf_agreement
    s = replace(DEFAULT_STRATEGY, macd_slow=5, macd_fast=2, macd_signal=2)
    m15 = session_bars("2024-03-05", 15, np.arange(26, dtype=float) ** 2)   # only 26 bars
    chart = session_bars("2024-03-05", 120, [1.0, 2, 3, 4])
    out = lower_tf_agreement(chart, "2h", {"15m": m15}, s)
    # First 2h bar ends 11:30: the 15m MACD has only 8 bars (< 10 warm-up) -> unknown.
    assert out.mtf_n.iloc[0] == 0 and out.mtf_up.iloc[0] == 0
    assert out.mtf_n.iloc[-1] == 1 and out.mtf_up.iloc[-1] == 1


def test_daily_chart_never_uses_yesterdays_lower_bar():
    from strategy import lower_tf_agreement
    s = replace(DEFAULT_STRATEGY, macd_slow=5, macd_fast=2, macd_signal=2)
    m15 = session_bars("2024-03-04", 15, np.arange(26, dtype=float) ** 2)   # Monday only
    daily = ohlc([1.0, 2.0], pd.DatetimeIndex(["2024-03-04", "2024-03-05"]))
    out = lower_tf_agreement(daily, "1d", {"15m": m15}, s)
    assert out.mtf_n.tolist() == [1, 0]                                   # Tuesday: no 15m data


def test_load_lower_builds_45m_and_drops_unfinished_bars(tmp_path):
    import data
    day = pd.Timestamp.today().normalize()
    future = day + pd.Timedelta(days=7)                                  # bars "not closed yet"
    past = pd.bdate_range(end=day - pd.Timedelta(days=1), periods=2)
    m15 = pd.concat([session_bars(d, 15, np.arange(26, dtype=float)) for d in list(past) + [future]])
    m30 = pd.concat([session_bars(d, 30, np.arange(13, dtype=float)) for d in past])
    m15.rename_axis("Date").to_csv(tmp_path / "X_15m.csv")
    m30.rename_axis("Date").to_csv(tmp_path / "X_30m.csv")
    out = data.load_lower(["X"], "2000-01-01", offline=True, cache_dir=tmp_path)["X"]
    assert set(out) == {"15m", "30m", "45m"}
    assert len(out["15m"]) == 52 and out["15m"].index.max() < future      # future day dropped
    assert len(out["45m"]) == 18                                         # 9 x 45m bars per day


def test_failed_download_falls_back_to_cache(tmp_path, monkeypatch):
    import data
    cached = session_bars("2024-03-05", 15, np.arange(26, dtype=float))
    cached.rename_axis("Date").to_csv(tmp_path / "X_15m.csv")
    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(data, "_download", boom)
    out = data.load(["X"], "2000-01-01", "15m", refresh=True, cache_dir=tmp_path)
    assert len(out["X"]) == 26


# --- Letting winners run: sell-setup exit and trailing stop ---

def test_long_exits_only_on_cross_down_above_zero(fake_signals):
    df = bars([FLAT] * 6, signal_days=[0], cross_down_days=[1, 3])
    df["macd"] = [-5, -2, 1, 2, 1, 1]          # day 1: cross under zero (ignored); day 3: above zero
    df["cross_up"] = False
    t = backtest.run({"X": df}, replace(S, macd_exit="above_zero", target_r=None), NO_COSTS).trades.iloc[0]
    assert t.exit_reason == "MACD sell setup" and str(t.exit_date) == "2024-01-05"
    # The old rule leaves at the first cross back, under zero.
    t_any = backtest.run({"X": df}, replace(S, macd_exit="any", target_r=None), NO_COSTS).trades.iloc[0]
    assert t_any.exit_reason == "MACD cross down" and str(t_any.exit_date) == "2024-01-03"


def test_short_covers_only_on_cross_up_below_zero(fake_signals):
    df = short_bars([FLAT] * 6, signal_days=[0], cross_up_days=[1, 3])
    df["macd"], df["cross_down"] = [5, 2, -1, -2, -1, -1], False
    t = backtest.run({"X": df}, replace(SHORT, macd_exit="above_zero", target_r=None), NO_BORROW).trades.iloc[0]
    assert t.exit_reason == "MACD buy setup" and str(t.exit_date) == "2024-01-05"


def test_default_has_no_target_and_no_time_stop():
    assert DEFAULT_STRATEGY.target_r is None and DEFAULT_STRATEGY.max_hold_days is None
    assert DEFAULT_STRATEGY.macd_exit == "above_zero" and DEFAULT_STRATEGY.min_macd_depth_atr == 0


def test_trailing_stop_follows_best_close_and_never_loosens(fake_signals):
    rows = [FLAT, FLAT, (104, 106, 103.5, 106), (106, 110.5, 105.5, 110), (110, 110.5, 107, 108),
            (108, 108.5, 107.4, 107.5)]
    df = bars(rows, signal_days=[0])
    t = backtest.run({"X": df}, replace(S, target_r=None, trail_atr_mult=3.0), NO_COSTS).trades.iloc[0]
    # Entry 100, first stop 98 (2 ATR). Best close 110 -> trail 107. Day 4 close 108 keeps it at 107.
    assert t.stop == 98 and t.exit_stop == 107
    assert t.exit_reason == "trailing stop" and t.exit_price == 107
    assert t.r_multiple == pytest.approx(3.5)                  # (107-100) / (100-98)


def test_short_trailing_stop_mirrors(fake_signals):
    rows = [FLAT, FLAT, (96, 96.5, 94, 94), (94, 94.5, 90, 90), (90, 93.5, 89.5, 93)]
    df = short_bars(rows, signal_days=[0])
    t = backtest.run({"X": df}, replace(SHORT, target_r=None, trail_atr_mult=3.0), NO_BORROW).trades.iloc[0]
    assert t.stop == 102 and t.exit_stop == 93 and t.exit_reason == "trailing stop"
    assert t.r_multiple == pytest.approx(3.5)


def test_sell_setup_flips_long_into_short(fake_signals):
    # Day 0: buy signal. Day 3: MACD crosses down above zero = long's exit AND a short signal.
    df = bars([FLAT] * 7, signal_days=[0], cross_down_days=[3])
    df["macd"], df["cross_up"] = 1.0, False
    df["short_signal"] = [i == 3 for i in range(7)]
    res = backtest.run({"X": df}, replace(S, sides="both", macd_exit="above_zero", target_r=None), NO_BORROW)
    tr = res.trades
    assert list(tr.side) == ["long", "short"]
    assert tr.exit_date.iloc[0] == tr.entry_date.iloc[1] == "2024-01-05"
    assert tr.exit_reason.iloc[0] == "MACD sell setup"


def test_default_takes_both_sides():
    assert DEFAULT_STRATEGY.sides == "both"



# --- Fixing shorts: market filter, which stocks to short, smaller size ---

def rollover():
    close = np.r_[np.linspace(100, 100, 300), np.linspace(100, 200, 60), np.linspace(200, 185, 20)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    return ohlc(close, idx)


def test_market_filter_blocks_shorts_in_a_bull_market():
    df = rollover()
    on = replace(SHORT, short_market_filter="QQQ")
    bull = ohlc(np.linspace(100, 300, len(df)), df.index)              # QQQ rising: above its EMA
    bear = ohlc(np.linspace(300, 100, len(df)), df.index)              # QQQ falling: below its EMA
    assert not add_signals(df, on, daily=df, market=bull).short_signal.any()
    assert add_signals(df, on, daily=df, market=bear).short_signal.any()
    assert not add_signals(df, on, daily=df).short_signal.any()        # no market data: no shorts
    # Longs are never affected by the market filter.
    assert add_signals(df, on, daily=df, market=bull).entry_signal.sum() == \
        add_signals(df, replace(on, short_market_filter=None), daily=df).entry_signal.sum()


def test_market_filter_uses_yesterdays_close():
    from strategy import market_downtrend
    s = replace(DEFAULT_STRATEGY, short_market_ma=3)
    idx = pd.bdate_range("2024-01-01", periods=8)
    qqq = ohlc([10, 10, 10, 10, 10, 1, 1, 1], idx)                     # drops below its EMA on day 5
    down = market_downtrend(qqq, s, idx)
    assert not down.iloc[5] and down.iloc[6]                           # known only the next day


def test_short_trend_side_options():
    df = rollover()
    base = add_signals(df, replace(SHORT, short_trend_side="off"), daily=df)
    assert base.short_signal.any()
    low_daily = ohlc(np.full(len(df), 1000.0), df.index)               # stock far below its "EMA"
    assert not add_signals(df, replace(SHORT, short_trend_side="above"), daily=low_daily).short_signal.any()
    assert add_signals(df, replace(SHORT, short_trend_side="below"), daily=low_daily).short_signal.any()


def test_short_risk_mult_halves_short_size(fake_signals):
    df = short_bars([FLAT, (101, 101.5, 100.5, 101), FLAT, (100, 111.5, 100, 111)], signal_days=[0], atr=5.0)
    full = backtest.run({"X": df}, SHORT, NO_BORROW).trades.iloc[0]
    half = backtest.run({"X": df}, replace(SHORT, short_risk_mult=0.5), NO_BORROW).trades.iloc[0]
    assert half.pnl == pytest.approx(full.pnl / 2, abs=0.01)


def test_short_stop_can_differ_from_long_stop(fake_signals):
    df = short_bars([FLAT, (101, 101.5, 100.5, 101), FLAT, FLAT], signal_days=[0])
    t = backtest.run({"X": df}, replace(SHORT, short_stop_atr_mult=4.0), NO_BORROW).trades.iloc[0]
    assert t.stop == 105                                      # 101 + 4 x ATR(1), not the 2 ATR long stop



# --- Only the best trades: wait for confirmation, higher timeframes must agree ---

def dip_and_bounce():
    close = np.r_[np.linspace(300, 300, 300), np.linspace(300, 200, 60), np.linspace(200, 230, 25)]
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    return ohlc(close, idx)


def test_entry_waits_for_confirmation_bars():
    df = dip_and_bounce()
    now = add_signals(df, replace(DEFAULT_STRATEGY, confirm_bars=0), daily=df)
    wait = add_signals(df, replace(DEFAULT_STRATEGY, confirm_bars=2), daily=df)
    i_now = now.index.get_loc(now[now.entry_signal].index[0])
    i_wait = wait.index.get_loc(wait[wait.entry_signal].index[0])
    assert i_wait == i_now + 2
    # Both bars after the cross: MACD still above its signal line and the histogram growing.
    for j in (i_now + 1, i_now + 2):
        assert wait.macd.iloc[j] > wait.macd_signal.iloc[j] and wait.macd_hist.iloc[j] > wait.macd_hist.iloc[j - 1]


def test_cross_that_fizzles_is_skipped():
    from strategy import confirmed_after
    idx = pd.bdate_range("2024-01-01", periods=6)
    df = pd.DataFrame({"macd": [-5, -4, -3.5, -3.6, -3, -2], "macd_signal": [-4, -4.1, -3.8, -3.5, -3.4, -3.3]}, index=idx)
    df["macd_hist"] = df.macd - df.macd_signal
    trigger = pd.Series([False, True, False, False, False, False], index=idx)   # cross up on day 1
    # Day 3 the MACD drops back under its signal line: no entry.
    assert not confirmed_after(trigger, df, 2, 1).any()
    assert confirmed_after(trigger, df, 1, 1).tolist() == [False, False, True, False, False, False]


def test_higher_timeframes_must_agree():
    from strategy import higher_tf_agreement
    s = replace(DEFAULT_STRATEGY, macd_slow=5, macd_fast=2, macd_signal=2)
    days = pd.bdate_range("2024-01-01", periods=40)
    up_daily = ohlc(np.linspace(100, 200, 40) ** 1.5, days)            # daily MACD above signal
    dn_daily = ohlc(300 - np.arange(40) ** 2 / 8, days)                # accelerating fall
    chart = session_bars(days[-1], 120, [1.0, 2, 3, 4])                # 2h bars on the last day
    up = higher_tf_agreement(chart, "2h", {"1d": up_daily}, s)
    dn = higher_tf_agreement(chart, "2h", {"1d": dn_daily}, s)
    assert (up.htf_max == 2).all() and (up.htf_up == 1).all() and (dn.htf_down == 1).all()


def test_higher_timeframe_uses_only_finished_bars():
    from strategy import higher_tf_agreement
    s = replace(DEFAULT_STRATEGY, macd_slow=5, macd_fast=2, macd_signal=2)
    days = pd.bdate_range("2024-01-01", periods=40)
    close = np.linspace(100, 200, 40) ** 1.5
    close[-1] = 1.0                                                    # today's daily bar crashes
    daily = ohlc(close, days)
    chart = session_bars(days[-1], 120, [1.0, 2, 3, 4])
    out = higher_tf_agreement(chart, "2h", {"1d": daily}, s)
    # Today's daily bar isn't finished during today's 2h bars, so yesterday's (rising) one is used.
    assert (out.htf_up == 1).all()


def test_missing_higher_data_blocks_entries_on_intraday_charts():
    days = pd.bdate_range("2023-01-02", periods=200)
    times = [d + pd.Timedelta(hours=h, minutes=30) for d in days for h in (9, 11, 13, 15)]
    close = np.r_[np.linspace(300, 300, 400), np.linspace(300, 200, 300), np.linspace(200, 260, 100)]
    df = ohlc(close, pd.DatetimeIndex(times))
    s = replace(DEFAULT_STRATEGY, trend_ma=None, sides="long")
    assert add_signals(df, replace(s, require_higher=False), interval="2h").entry_signal.any()
    assert not add_signals(df, s, interval="2h").entry_signal.any()
