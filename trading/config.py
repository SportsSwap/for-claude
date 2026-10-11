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

UNIVERSE = MAG7 + SEMIS + HIGH_BETA

BENCHMARKS = ["QQQ", "SMH"]

INTERVALS = ["1d", "1h", "2h", "4h"]


@dataclass(frozen=True)
class Strategy:
    name: str = "Dip buy: MACD cross under zero, below 200-day EMA"

    # MACD. 12/144/9: the slow line acts as the trend, so signals are fewer and cleaner.
    macd_fast: int = 12
    macd_slow: int = 144
    macd_signal: int = 9

    # Entry trigger.
    #   "signal_cross": MACD line crosses above its signal line
    #   "zero_cross":   MACD line crosses above zero (the midline)
    entry: str = "signal_cross"
    require_below_zero: bool = True     # signal_cross only: the cross must happen under zero

    # Moving-average filter: the 200 EMA.
    trend_ma: int | None = 200          # None turns it off
    trend_ma_type: str = "ema"          # "ema" or "sma"
    trend_ma_source: str = "daily"      # "daily" = 200-day EMA; "bars" = 200 EMA of the chart timeframe
    trend_side: str = "below"           # price must be "below" or "above" the average

    # "Price hasn't moved yet": skip the trade if price is already more than N ATRs
    # above its lowest low of the last run_lookback bars. None turns it off.
    max_run_atr: float | None = None
    run_lookback: int = 20

    # Exits.
    atr_period: int = 14
    stop_atr_mult: float = 3.0          # stop = entry - 3 x ATR of the chart timeframe
    target_r: float | None = 2.0        # take profit at 2x the risk; None = no target
    exit_on_macd_cross_down: bool = True
    max_hold_days: int | None = 15      # time stop in trading days; None = no limit

    # Ranking when more signals fire than there are free slots: higher wins.
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


DEFAULT_STRATEGY = Strategy()
DEFAULT_RISK = Risk()

_D = DEFAULT_STRATEGY

# Variants for --compare. Each changes one thing from the default so the effect is readable.
VARIANTS = [
    _D,
    replace(_D, name="Dip buy, below 200-bar EMA (as on your chart)", trend_ma_source="bars"),
    replace(_D, name="Dip buy, no 200 EMA rule", trend_ma=None),
    replace(_D, name="Zero-line cross, price not run (<3 ATR)", entry="zero_cross",
            require_below_zero=False, trend_ma=None, max_run_atr=3.0),
    replace(_D, name="Zero-line cross, any", entry="zero_cross", require_below_zero=False, trend_ma=None),
    replace(_D, name="Trend: MACD cross, above 200-day EMA", require_below_zero=False, trend_side="above"),
    replace(_D, name="Classic 12/26/9, above 200-day EMA", macd_slow=26, require_below_zero=False,
            trend_side="above"),
]
