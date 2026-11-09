"""Write the two final-test survivors as TradingView Pine Script strategies.

    python scripts/make_pine.py      ->  tradingview/*.pine

The dials are copied from results/funnel/versions.jsonl (the hashed version
file), and the news days (CPI, jobs report, FOMC) from the verified calendar
plus the BLS release schedules for upcoming dates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lab import io  # noqa: E402
from lab.config import P  # noqa: E402

# Upcoming release dates from https://www.bls.gov/schedule/news_release/{cpi,empsit}.htm (fetched 2026-11-09)
UPCOMING = {
    "CPI": ["2026-11-10", "2026-12-10", "2027-01-13", "2027-02-11", "2027-03-10", "2027-04-13", "2027-05-12",
            "2027-06-10", "2027-07-14", "2027-08-11", "2027-09-14", "2027-10-14", "2027-11-10", "2027-12-10"],
    "NFP": ["2026-11-06", "2026-12-04", "2027-01-08", "2027-02-05", "2027-03-05", "2027-04-02", "2027-05-07",
            "2027-06-04", "2027-07-02", "2027-08-06", "2027-09-03", "2027-10-08", "2027-11-05", "2027-12-03"],
}


def version(vid: str) -> dict:
    for line in open(P.results() / "funnel" / "versions.jsonl"):
        v = json.loads(line)
        if v["id"] == vid:
            return v
    raise KeyError(vid)


def news_string() -> str:
    cal = io.read_table(P.news() / "news_calendar.csv")
    days = {d.replace("-", "") for d in cal.loc[cal.verified.astype(bool) & (cal.date >= "2021-09-01"), "date"]}
    days |= {d.replace("-", "") for ds in UPCOMING.values() for d in ds}
    return ",".join(sorted(days))


HEADER = """//@version=6
// Price Action Lab survivor: {vid}
// Survived the lab's sealed final test (2024-08-01 to 2026-11-06, Dukascopy CFD data):
// {result}
// Dials are fixed by the lab. Changing any value tests a different, untested version.
// Costs as in the lab: $4 per round trip, 1 tick slippage, limits need 1 tick through.
// Differences from the lab: TradingView fills on chart bars, not 1-minute bars, and on a
// bar that hits both stop and target it may not assume the stop first (the lab does).
// Margin is not modelled (one contract, as in the lab).
// Paper trade before risking money.
"""

BREAKOUT = HEADER + r"""strategy("PA Lab 15m Level Breakout", shorttitle="PALab Breakout", overlay=true,
     process_orders_on_close=true, pyramiding=0, default_qty_type=strategy.fixed, default_qty_value=1,
     commission_type=strategy.commission.cash_per_contract, commission_value=2.0, slippage=1,
     backtest_fill_limits_assumption=1, margin_long=0, margin_short=0, max_bars_back=600)

// ---------------------------------------------------------------- dials (from the lab)
int   SWING     = {swing}       // swing strength: bars each side
float TOL_ATR   = {tol}    // swings within this many ATR form one level
int   TOUCHES   = {touches}       // swings a level needs
int   LIFE      = 500     // bars a level lives after its last swing
float STOP_BUF  = {buf}     // stop buffer beyond the last swing, in ATR
float TARGET_R  = {target}     // target in multiples of risk
int   TIME_BARS = {timebars}      // exit after this many 15m bars
int   SESS_FROM = 480     // entries only when the bar closes 08:00 ...
int   SESS_TO   = 960     // ... to 16:00 New York time

if timeframe.period != "15"
    runtime.error("Put this strategy on a 15-minute chart (NQ1! or ES1!).")

float atrPrior = ta.atr(14)[1]          // Wilder ATR through the previous bar only

// ---------------------------------------------------------------- swings (confirmed SWING bars later)
// The bar SWING bars ago is a swing high when its high beats the SWING highs before it
// and is at least as high as the SWING highs after it (no loops: built-ins only).
float maxBefore = ta.highest(high, SWING)[SWING + 1]
float maxAfter  = ta.highest(high, SWING)
float minBefore = ta.lowest(low, SWING)[SWING + 1]
float minAfter  = ta.lowest(low, SWING)
bool newHigh = bar_index > 2 * SWING and high[SWING] > maxBefore and high[SWING] >= maxAfter
bool newLow  = bar_index > 2 * SWING and low[SWING] < minBefore and low[SWING] <= minAfter
var float lastSwingHigh = na
var float lastSwingLow  = na

// ---------------------------------------------------------------- levels: clusters of swings
var array<float> clSum  = array.new<float>()
var array<int>   clN    = array.new<int>()
var array<int>   clLast = array.new<int>()
var array<float> lvPrice = array.new<float>()
var array<int>   lvBorn  = array.new<int>()

var int nSwings = 0
var int nLevelsMade = 0
var int nBreaks = 0

// new swings this bar (a bar can confirm a swing high and a swing low)
array<float> fresh = array.new<float>()
if newHigh
    lastSwingHigh := high[SWING]
    array.push(fresh, high[SWING])
if newLow
    lastSwingLow := low[SWING]
    array.push(fresh, low[SWING])

if array.size(fresh) > 0 and not na(atrPrior)
    for p in fresh
        nSwings += 1
        int best = -1
        float bestD = 1.0e18
        int n = array.size(clSum)
        if n > 0
            for i = 0 to n - 1
                if bar_index - array.get(clLast, i) <= LIFE
                    float d = math.abs(p - array.get(clSum, i) / array.get(clN, i))
                    if d <= TOL_ATR * atrPrior and d < bestD
                        best := i
                        bestD := d
        if best < 0
            array.push(clSum, p)
            array.push(clN, 1)
            array.push(clLast, bar_index)
            best := array.size(clSum) - 1
        else
            array.set(clSum, best, array.get(clSum, best) + p)
            array.set(clN, best, array.get(clN, best) + 1)
            array.set(clLast, best, bar_index)
        if array.get(clN, best) >= TOUCHES
            array.push(lvPrice, array.get(clSum, best) / array.get(clN, best))
            array.push(lvBorn, bar_index)
            nLevelsMade += 1
            array.remove(clSum, best)
            array.remove(clN, best)
            array.remove(clLast, best)
        int m = array.size(clSum)
        if m > 0
            for i = m - 1 to 0
                if bar_index - array.get(clLast, i) > LIFE
                    array.remove(clSum, i)
                    array.remove(clN, i)
                    array.remove(clLast, i)

// ---------------------------------------------------------------- breaks: first close through a level
int breakDir = 0
float breakLevel = na
int nl = array.size(lvPrice)
if nl > 0
    for i = nl - 1 to 0
        if bar_index - array.get(lvBorn, i) > LIFE
            array.remove(lvPrice, i)
            array.remove(lvBorn, i)
nl := array.size(lvPrice)
if nl > 0
    for i = 0 to nl - 1
        float lv = array.get(lvPrice, i)
        if breakDir == 0 and bar_index > array.get(lvBorn, i)
            if close[1] < lv and close > lv
                breakDir := 1
                breakLevel := lv
            else if close[1] > lv and close < lv
                breakDir := -1
                breakLevel := lv

// ---------------------------------------------------------------- entries and exits
int closeMin = hour(time_close, "America/New_York") * 60 + minute(time_close, "America/New_York")
bool inSession = closeMin >= SESS_FROM and closeMin <= SESS_TO
var int entryBar = na

if strategy.position_size != 0 and not na(entryBar) and bar_index >= entryBar + TIME_BARS
    strategy.close_all(comment="time exit")
    entryBar := na

if strategy.position_size == 0 and breakDir != 0 and inSession and not na(atrPrior)
    if breakDir == 1 and not na(lastSwingLow)
        float stop = lastSwingLow - STOP_BUF * atrPrior
        float risk = close - stop
        if risk >= syminfo.mintick
            strategy.entry("Long", strategy.long)
            strategy.exit("Long exit", "Long", stop=stop, limit=close + TARGET_R * risk)
            entryBar := bar_index
    else if breakDir == -1 and not na(lastSwingHigh)
        float stop = lastSwingHigh + STOP_BUF * atrPrior
        float risk = stop - close
        if risk >= syminfo.mintick
            strategy.entry("Short", strategy.short)
            strategy.exit("Short exit", "Short", stop=stop, limit=close - TARGET_R * risk)
            entryBar := bar_index

if breakDir != 0
    nBreaks += 1

plotshape(breakDir == 1 and inSession, "Break up", shape.triangleup, location.belowbar, color.new(color.teal, 0), size=size.small)
plotshape(breakDir == -1 and inSession, "Break down", shape.triangledown, location.abovebar, color.new(color.red, 0), size=size.small)

// status label on the last bar: shows where the logic stops if nothing trades
var label status = na
if barstate.islast
    label.delete(status)
    status := label.new(bar_index, high, "swings " + str.tostring(nSwings) + " | levels made " + str.tostring(nLevelsMade) +
         " | live levels " + str.tostring(array.size(lvPrice)) + " | breaks " + str.tostring(nBreaks),
         style=label.style_label_down, color=color.new(color.gray, 20), textcolor=color.white, size=size.small)
"""

FVG = HEADER + r"""strategy("PA Lab Daily Fair Value Gap, 1h", shorttitle="PALab Daily FVG", overlay=true,
     process_orders_on_close=true, pyramiding=0, default_qty_type=strategy.fixed, default_qty_value=1,
     commission_type=strategy.commission.cash_per_contract, commission_value=2.0, slippage=1,
     backtest_fill_limits_assumption=1, margin_long=0, margin_short=0)

// ---------------------------------------------------------------- dials (from the lab)
float MIN_GAP_ATR = {min_gap}   // smallest daily gap kept, in daily ATR
float STOP_BUF    = {buf}   // stop beyond the gap's far edge, in daily ATR
float TARGET_R    = {target}   // target in multiples of risk
int   TIME_BARS   = {timebars}    // the limit lives, and a trade is closed after, this many 1h bars
bool  SKIP_NEWS   = {skip_news}  // no gap formed on a CPI, jobs-report or FOMC day is traded

if timeframe.period != "60"
    runtime.error("Put this strategy on a 1-hour chart (NQ1! or ES1!).")

// News days (CPI, jobs report, FOMC), YYYYMMDD, from the lab's verified calendar
var array<int> NEWS = array.new<int>()
if barstate.isfirst
    for s in str.split("{news}", ",")
        array.push(NEWS, int(str.tonumber(s)))

// ---------------------------------------------------------------- the last completed daily bar (no repainting)
[dHigh, dLow, dClose, dHigh2, dLow2, dAtrPrior, dDay] = request.security(syminfo.tickerid, "D",
     [high[1], low[1], close[1], high[3], low[3], ta.atr(14)[2], time_tradingday[1]], lookahead=barmerge.lookahead_on)
bool newDay = ta.change(dDay) != 0     // a daily bar has just completed

// ---------------------------------------------------------------- the strategy state
var int decisionBar = na     // bar where the current order or trade was decided
var bool pending = false

if not na(decisionBar) and bar_index >= decisionBar + TIME_BARS
    if pending
        strategy.cancel_all()
        pending := false
        alert("PALab FVG " + syminfo.ticker + ": time is up, CANCEL the unfilled limit order", alert.freq_once_per_bar_close)
    if strategy.position_size != 0
        strategy.close_all(comment="time exit")
        alert("PALab FVG " + syminfo.ticker + ": time is up, CLOSE the open trade at market", alert.freq_once_per_bar_close)
    decisionBar := na
if pending and strategy.position_size != 0
    pending := false

bool placedLong = false
bool placedShort = false
if newDay and not na(dAtrPrior) and not na(dHigh2) and strategy.position_size == 0 and not pending
    int day = year(dDay, "UTC") * 10000 + month(dDay, "UTC") * 100 + dayofmonth(dDay, "UTC")
    bool news = SKIP_NEWS and array.includes(NEWS, day)
    if not news
        if dLow > dHigh2 and dLow - dHigh2 >= MIN_GAP_ATR * dAtrPrior and dClose > dLow
            float near = dLow
            float stop = dHigh2 - STOP_BUF * dAtrPrior
            float risk = near - stop
            strategy.entry("Long", strategy.long, limit=near)
            strategy.exit("Long exit", "Long", stop=stop, limit=near + TARGET_R * risk)
            pending := true
            decisionBar := bar_index
            placedLong := true
            alert("PALab FVG " + syminfo.ticker + ": BUY LIMIT 1 at " + str.tostring(near, format.mintick) +
                 " | stop " + str.tostring(stop, format.mintick) + " | target " + str.tostring(near + TARGET_R * risk, format.mintick) +
                 " | cancel or close after 96 hourly bars (about 4 days)", alert.freq_once_per_bar_close)
        else if dHigh < dLow2 and dLow2 - dHigh >= MIN_GAP_ATR * dAtrPrior and dClose < dHigh
            float near = dHigh
            float stop = dLow2 + STOP_BUF * dAtrPrior
            float risk = stop - near
            strategy.entry("Short", strategy.short, limit=near)
            strategy.exit("Short exit", "Short", stop=stop, limit=near - TARGET_R * risk)
            pending := true
            decisionBar := bar_index
            placedShort := true
            alert("PALab FVG " + syminfo.ticker + ": SELL LIMIT 1 at " + str.tostring(near, format.mintick) +
                 " | stop " + str.tostring(stop, format.mintick) + " | target " + str.tostring(near - TARGET_R * risk, format.mintick) +
                 " | cancel or close after 96 hourly bars (about 4 days)", alert.freq_once_per_bar_close)

plotshape(placedLong, "Gap: buy limit placed", shape.triangleup, location.belowbar, color.new(color.teal, 0), size=size.tiny)
plotshape(placedShort, "Gap: sell limit placed", shape.triangledown, location.abovebar, color.new(color.red, 0), size=size.tiny)
"""


FVG_ETF = """//@version=6
// Price Action Lab: daily fair value gap ({vid}) traded on a Nasdaq ETF.
// Signals come from NQ futures (read in the background); trades go into this chart's ETF:
//   TQQQ chart: NQ long signals buy TQQQ.   SQQQ chart: NQ short signals buy SQQQ.   QQQ: longs, 1x.
// NQ prices (limit, stop, target) are converted to ETF prices with the ETF's leverage.
// NOT TESTED BY THE LAB: the lab tested NQ itself. Paper trade before risking money.
// ETFs trade 9:30-16:00 New York, so a gap seen after NQ's 17:00 close is acted on next morning.
strategy("PA Lab Daily FVG on ETF", shorttitle="PALab FVG ETF", overlay=true,
     process_orders_on_close=true, pyramiding=0, default_qty_type=strategy.cash, default_qty_value=10000,
     commission_type=strategy.commission.percent, commission_value=0.0, slippage=1,
     backtest_fill_limits_assumption=1, margin_long=0, margin_short=0)

// ---------------------------------------------------------------- dials (from the lab)
float MIN_GAP_ATR = {min_gap}
float STOP_BUF    = {buf}
float TARGET_R    = {target}
int   HOLD_DAYS   = 4      // NQ's 96 hourly bars are about 4 sessions: exit at the 4th ETF close
bool  SKIP_NEWS   = {skip_news}
string NQ = input.symbol("CME_MINI:NQ1!", "Signal market")

if timeframe.period != "60"
    runtime.error("Put this strategy on a 1-hour chart of TQQQ, SQQQ or QQQ.")

float LEV = syminfo.ticker == "SQQQ" ? -3.0 : syminfo.ticker == "TQQQ" ? 3.0 : syminfo.ticker == "QQQ" ? 1.0 : na
if na(LEV)
    runtime.error("Use this on TQQQ, SQQQ or QQQ.")
int WANT = LEV > 0 ? 1 : -1                 // which NQ signal this ETF takes

var array<int> NEWS = array.new<int>()
if barstate.isfirst
    for s in str.split("{news}", ",")
        array.push(NEWS, int(str.tonumber(s)))

// ---------------------------------------------------------------- NQ: last completed daily bar, and NQ now
[dHigh, dLow, dClose, dHigh2, dLow2, dAtrPrior, dDay] = request.security(NQ, "D",
     [high[1], low[1], close[1], high[3], low[3], ta.atr(14)[2], time_tradingday[1]], lookahead=barmerge.lookahead_on)
float nqNow = request.security(NQ, timeframe.period, close)
bool newDay = ta.change(dDay) != 0

toEtf(float nqPrice) =>
    close * (1 + LEV * (nqPrice / nqNow - 1))

// ---------------------------------------------------------------- state
var bool pending = false
var int daysHeld = 0
bool sessionClose = hour(time_close, "America/New_York") == 16 and minute(time_close, "America/New_York") == 0
if pending or strategy.position_size != 0
    if sessionClose
        daysHeld += 1
    if sessionClose and daysHeld >= HOLD_DAYS
        strategy.cancel_all()
        strategy.close_all(comment="time exit")
        pending := false
if pending and strategy.position_size != 0
    pending := false
if not pending and strategy.position_size == 0
    daysHeld := 0

// ---------------------------------------------------------------- signal from NQ, order in the ETF
bool placed = false
if newDay and not na(dAtrPrior) and not na(dHigh2) and not na(nqNow) and strategy.position_size == 0 and not pending
    int day = year(dDay, "UTC") * 10000 + month(dDay, "UTC") * 100 + dayofmonth(dDay, "UTC")
    bool news = SKIP_NEWS and array.includes(NEWS, day)
    int sig = 0
    float near = na
    float stop = na
    if not news
        if dLow > dHigh2 and dLow - dHigh2 >= MIN_GAP_ATR * dAtrPrior and dClose > dLow
            sig := 1
            near := dLow
            stop := dHigh2 - STOP_BUF * dAtrPrior
        else if dHigh < dLow2 and dLow2 - dHigh >= MIN_GAP_ATR * dAtrPrior and dClose < dHigh
            sig := -1
            near := dHigh
            stop := dLow2 + STOP_BUF * dAtrPrior
    if sig == WANT
        float target = near + TARGET_R * (near - stop)
        float eNear = toEtf(near)
        float eStop = toEtf(stop)
        float eTarget = toEtf(target)
        if eNear < close and eStop < eNear and eTarget > eNear      // a buy limit under price, sane levels
            strategy.entry("Buy", strategy.long, limit=eNear)
            strategy.exit("Exit", "Buy", stop=eStop, limit=eTarget)
            pending := true
            daysHeld := 0
            placed := true

plotshape(placed, "Buy limit placed", shape.triangleup, location.belowbar, color.new(color.teal, 0), size=size.small)
"""


def main() -> int:
    out = ROOT / "tradingview"
    out.mkdir(exist_ok=True)
    news = news_string()
    b = version("C-breakout-00051")
    (out / "palab_breakout_15m.pine").write_text(BREAKOUT.format(
        vid="C-breakout-00051",
        result="NQ 941 trades, +$112,064, Sharpe 0.72; ES 993 trades, +$45,704, Sharpe 0.59.",
        swing=b["swing_strength"], tol=b["level_tol_atr"], touches=b["level_min_touches"],
        buf=b["stop_buffer_atr"], target=float(b["target"].rstrip("R")), timebars=int(b["time_exit"].split("_")[1])))
    f = version("C-fair_value_gap-00364")
    (out / "palab_daily_fvg_1h.pine").write_text(FVG.format(
        vid="C-fair_value_gap-00364",
        result="NQ 50 trades, +$100,990, Sharpe 1.01; ES 49 trades, +$39,679, Sharpe 0.84.",
        min_gap=f["fvg_min_gap_atr"], buf=f["stop_buffer_atr"], target=float(f["target"].rstrip("R")),
        timebars=int(f["time_exit"].split("_")[1]), skip_news="true" if f["news"] == "skip" else "false",
        news=news))
    (out / "palab_daily_fvg_etf_1h.pine").write_text(FVG_ETF.format(
        vid="C-fair_value_gap-00364", min_gap=f["fvg_min_gap_atr"], buf=f["stop_buffer_atr"],
        target=float(f["target"].rstrip("R")), skip_news="true" if f["news"] == "skip" else "false", news=news))
    print("wrote", [p.name for p in out.glob("*.pine")], "news days:", news.count(",") + 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
