"""Universe, strategy settings and risk rules.

Everything the backtester and scanner do is driven from here, so a rule changes in
one place and both tools pick it up.
"""

from dataclasses import dataclass, replace

MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

SEMIS = ["AVGO", "AMD", "TSM", "MU", "QCOM", "INTC", "ARM", "MRVL",
         "AMAT", "LRCX", "KLAC", "ASML", "TXN", "ON", "SMCI"]

# Large, liquid US names that move a lot.
HIGH_BETA = ["NFLX", "PLTR", "COIN", "MSTR", "SHOP", "UBER", "CRWD", "SNOW",
             "HOOD", "ORCL", "ADBE", "CRM", "NOW", "PANW"]

UNIVERSE = MAG7 + SEMIS + HIGH_BETA

BENCHMARKS = ["QQQ", "SMH"]


@dataclass(frozen=True)
class Strategy:
    name: str = "MACD + 50-day trend"

    # MACD, same defaults as TradingView (12, 26, 9) so charts line up.
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Entry filters. A MACD cross only counts when the stock is in an uptrend.
    trend_sma: int | None = 50          # None turns the trend filter off
    require_below_zero: bool = False    # only take crosses that happen under the zero line

    # Exits.
    atr_period: int = 14
    stop_atr_mult: float = 2.0          # stop = entry - 2 x ATR
    target_r: float | None = 2.0        # take profit at 2x the risk; None = no target
    exit_on_macd_cross_down: bool = True
    max_hold_days: int | None = 15      # time stop in trading days; None = no limit

    # Ranking when more signals fire than there are free slots: higher wins.
    rank_by: str = "momentum_20d"


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

# Variants for --compare. Each changes one thing so the effect is readable.
VARIANTS = [
    replace(DEFAULT_STRATEGY, name="MACD cross only (no filter)", trend_sma=None),
    DEFAULT_STRATEGY,
    replace(DEFAULT_STRATEGY, name="MACD + trend + below zero", require_below_zero=True),
    replace(DEFAULT_STRATEGY, name="MACD + trend, 3R target", target_r=3.0),
    replace(DEFAULT_STRATEGY, name="MACD + trend, no target (ride it)", target_r=None),
]
