"""Universe, strategy settings and risk rules.

Everything the backtester and scanner do is driven from here, so a rule changes in
one place and both tools pick it up.
"""

from dataclasses import dataclass, replace

MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

SEMIS = ["AVGO", "AMD", "TSM", "MU", "QCOM", "INTC", "ARM", "MRVL",
         "AMAT", "LRCX", "KLAC", "ASML", "TXN", "ON", "SMCI", "SNDK"]

# Large, liquid US names that move a lot.
HIGH_BETA = ["NFLX", "PLTR", "COIN", "MSTR", "SHOP", "UBER", "CRWD", "SNOW",
             "HOOD", "ORCL", "ADBE", "CRM", "NOW", "PANW"]

# AI infrastructure: GPU clouds, AI servers, data-centre power/cooling, storage, AI software.
# CRWV listed in March 2025, NBIS in October 2024 and SPCX (SpaceX) on 12 June 2026, so their
# backtests start late and they only get signals once the 144-bar MACD has 289 bars of history.
AI = ["CRWV", "NBIS", "DELL", "VRT", "WDC", "VST", "IBM", "SPCX"]

UNIVERSE = MAG7 + SEMIS + HIGH_BETA + AI

# Pick one with --group. Micron (MU) and SanDisk (SNDK) are memory/storage AI plays too,
# so the "ai" group includes them.
GROUPS = {
    "all": UNIVERSE,
    "mag7": MAG7,
    "semis": SEMIS,
    "high_beta": HIGH_BETA,
    "ai": AI + ["MU", "SNDK"],
}

BENCHMARKS = ["QQQ", "SMH"]

INTERVALS = ["1d", "1h", "2h", "4h"]


@dataclass(frozen=True)
class Strategy:
    name: str = "Long-term: MACD 12/144/9 buy above 200-day EMA"

    # Which trades to take: "long" (default), "short" or "both". Shorts are PARKED: the code works
    # and is tested, but they lost money in the 2024-2026 bull market; see README "Shorts (parked)".
    # A short is the long rule upside down: MACD crosses DOWN through its signal line while
    # ABOVE zero, with price ABOVE the 200-day EMA. With "both", the sell setup that ends a long
    # also opens a short on the same bar.
    sides: str = "long"

    # MACD. 12/144/9: the slow line acts as the trend, so signals are fewer and cleaner.
    macd_fast: int = 12
    macd_slow: int = 144
    macd_signal: int = 9

    # Entry trigger.
    #   "signal_cross": MACD line crosses above its signal line
    #   "zero_cross":   MACD line crosses above zero (the midline)
    entry: str = "signal_cross"
    require_below_zero: bool = True     # signal_cross only: the cross must happen under zero
                                        # (above zero for shorts)
    # Buffer: with require_below_zero, the cross only counts if the MACD is at least this many
    # ATRs (ATR(14) of the chart timeframe) below zero (above zero for shorts). 0 = off (default):
    # any cross under zero counts.
    min_macd_depth_atr: float = 0.0

    # Confirmation: don't enter on the cross itself. Wait this many bars; the MACD must stay on the
    # right side of its signal line AND the histogram must grow on every one of them. Crosses that
    # fizzle straight away (chop) are skipped. 0 = enter on the cross.
    confirm_bars: int = 2
    # Line-up window: after the confirmation bars, keep waiting up to this many more bars for the
    # higher timeframes (and the other filters) to agree, as long as the MACD stays above its
    # signal line. The trade fires on the first bar where everything lines up. Higher timeframes
    # turn later than the chart, so 0 (agree on the confirmation bar itself) almost never trades.
    align_window: int = 30

    # Higher timeframes must agree: at entry, the MACD (same 12/144/9) on each of these timeframes
    # must be above its signal line for a long (below for a short), using the last FINISHED bar
    # of that timeframe. Only timeframes longer than the chart count (on a 4h chart only 1d).
    higher_tfs: tuple[str, ...] = ("4h", "1d")
    require_higher: bool = True

    # Lower-timeframe check. A lower timeframe "agrees" with a buy when its own MACD
    # (same 12/144/9 settings) is above its signal line AND its histogram rose on its last
    # closed bar (mirror for shorts). Only timeframes shorter than the chart's count.
    # confirm_min = how many must agree to take the trade; 0 = don't filter, just record the
    # count on each trade. Yahoo keeps only 60 days of 15m/30m bars, so this can't be
    # backtested over long periods in Python.
    confirm_tfs: tuple[str, ...] = ("15m", "30m", "45m")
    confirm_min: int = 0

    # Moving-average filter: the 200 EMA.
    trend_ma: int | None = 200          # None turns it off
    trend_ma_type: str = "ema"          # "ema" or "sma"
    trend_ma_source: str = "daily"      # "daily" = 200-day EMA; "bars" = 200 EMA of the chart timeframe
    trend_side: str = "above"           # longs: price must be "above" (default) or "below" the average
                                        # (shorts use the opposite side)

    # Shorts.
    # Which side of its own 200-day EMA a stock must be on to be shorted:
    #   None = mirror of the long rule ("above" when longs need "below"): short stocks stretched up
    #   "below" = short stocks already in a downtrend (with the trend); "off" = no EMA rule for shorts
    short_trend_side: str | None = None
    # Market filter: only short while this index is BELOW its N-day EMA (yesterday's values), i.e.
    # the whole market is in a downtrend. Shorting in a bull market is what loses. None = off.
    short_market_filter: str | None = "QQQ"
    short_market_ma: int = 200
    # Risk on shorts as a fraction of the normal risk per trade (0.5 = half size).
    short_risk_mult: float = 1.0
    # Stop distance for shorts in ATRs; None = same as longs (stop_atr_mult).
    short_stop_atr_mult: float | None = None

    # "Price hasn't moved yet": skip the trade if price is already more than N ATRs
    # above its lowest low of the last run_lookback bars. None turns it off.
    max_run_atr: float | None = None
    run_lookback: int = 20

    # Exits. Built to let winners run: hold until the setup turns into its opposite.
    atr_period: int = 14
    stop_atr_mult: float = 3.0          # stop = entry -/+ 3 x ATR of the chart timeframe
    # When the MACD crossing back through its signal line ends the trade:
    #   "above_zero": longs sell only when the MACD crosses DOWN while ABOVE zero, the sell setup
    #                 (shorts cover when it crosses UP while BELOW zero). Wobbles under zero don't exit.
    #   "any":        any cross back exits (the old, quicker exit)
    #   "off":        never; only stops, target and time stop
    macd_exit: str = "above_zero"
    # Optional trailing stop: N x ATR behind the best close since entry; only ever tightens.
    # None = off (the stop stays where it started).
    trail_atr_mult: float | None = None
    target_r: float | None = None       # take profit at N x the risk; None = no target, let it run
    max_hold_days: int | None = None    # time stop in trading days; None = no limit

    # Ranking when more signals fire than there are free slots: higher wins for longs,
    # lower wins for shorts.
    rank_by: str = "momentum_20"


@dataclass(frozen=True)
class Risk:
    starting_capital: float = 1000.0
    risk_per_trade: float = 0.02        # lose at most 2% of the account per trade
    max_positions: int = 3
    max_position_pct: float = 0.34      # no single position above ~1/3 of the account
    fractional_shares: bool = True      # IBKR allows fractional US shares
    kill_switch_pct: float = 0.80       # stop opening trades once equity hits 80% of start ($800)

    # Costs. IBKR Pro fixed: $0.005/share, $1 minimum, capped at 1% of trade value.
    commission_per_share: float = 0.005
    commission_min: float = 1.0
    commission_max_pct: float = 0.01
    slippage_pct: float = 0.0005        # 0.05% worse than the quoted price on every fill
    # Stock-loan fee on shorts, per year of the position's value. Mega caps are "easy to
    # borrow" at IBKR, typically 0.25-0.5% a year.
    short_borrow_pct_per_year: float = 0.005


DEFAULT_STRATEGY = Strategy()
DEFAULT_RISK = Risk()

# Two long systems that run side by side, each on its own share of the account.
#   Both only buy while price is ABOVE the 200-day EMA, when the MACD crosses up under zero.
#   Long-term: MACD 12/144/9, holds weeks to months.
#   Short-term: MACD 12/26/9, holds days to about two weeks: quicker confirmation (1 bar),
#   tighter stop (2 ATR), 10-day time limit.
#   (Parked) shorts mirror this: only while price is BELOW the 200-day EMA, when the MACD
#   crosses down above zero.
LONG_TERM = DEFAULT_STRATEGY
SHORT_TERM = replace(DEFAULT_STRATEGY, name="Short-term: MACD 12/26/9 buy above 200-day EMA",
                     macd_slow=26, confirm_bars=1, align_window=10, stop_atr_mult=2.0,
                     max_hold_days=10)
SYSTEMS = {"long-term": LONG_TERM, "short-term": SHORT_TERM}
SYSTEM_SPLIT = 0.5                      # share of the account for the long-term system; the rest is short-term

_D = DEFAULT_STRATEGY

# Variants for --compare. Each changes one thing from the default so the effect is readable.
VARIANTS = [
    _D,
    replace(_D, name="Enter on the cross (no 2-bar wait)", confirm_bars=0),
    replace(_D, name="No higher-timeframe check", require_higher=False),
    replace(_D, name="Neither filter (as before)", confirm_bars=0, require_higher=False),
    replace(_D, name="Old exits: 2R target, any MACD cross back, 15 days", target_r=2.0,
            macd_exit="any", max_hold_days=15),
    replace(_D, name="Sell setup exit + 3 ATR trailing stop", trail_atr_mult=3.0),
    replace(_D, name="3 ATR trailing stop only", macd_exit="off", trail_atr_mult=3.0),
    replace(_D, name="Above 200-bar EMA (as on your chart)", trend_ma_source="bars"),
    replace(_D, name="Below 200-day EMA (the old long-term rule)", trend_side="below"),
    replace(_D, name="No 200 EMA rule", trend_ma=None),
    replace(_D, name="Zero-line cross, price not run (<3 ATR)", entry="zero_cross",
            require_below_zero=False, trend_ma=None, max_run_atr=3.0),
    replace(_D, name="Zero-line cross, any", entry="zero_cross", require_below_zero=False, trend_ma=None),
    replace(_D, name="Trend: MACD cross, above 200-day EMA", require_below_zero=False, trend_side="above"),
    replace(_D, name="Classic 12/26/9, above 200-day EMA", macd_slow=26, require_below_zero=False,
            trend_side="above"),
    # Parked short side, kept for reference.
    replace(_D, name="(parked) Long + short", sides="both"),
    replace(_D, name="(parked) Short only", sides="short"),
]
