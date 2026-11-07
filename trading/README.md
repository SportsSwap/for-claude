# MACD swing trading: backtester and scanner

Step 1 of a trading assistant for a $1,000 account trading large US stocks:
the Magnificent 7, semiconductors, AI infrastructure, and other big names that move a lot.

## The stock lists

Set in `config.py`. Pick one with `--group` (default `all`), or name stocks with `--tickers`.

| Group | Stocks |
|---|---|
| `mag7` | AAPL MSFT GOOGL AMZN NVDA META TSLA |
| `semis` | AVGO AMD TSM MU QCOM INTC ARM MRVL AMAT LRCX KLAC ASML TXN ON SMCI SNDK |
| `high_beta` | NFLX PLTR COIN MSTR SHOP UBER CRWD SNOW HOOD ORCL ADBE CRM NOW PANW |
| `ai` | CRWV (CoreWeave) NBIS (Nebius) DELL VRT (Vertiv) WDC (Western Digital) VST (Vistra) IBM SPCX (SpaceX), plus MU and SNDK |

Some of these have short price histories: CoreWeave listed in March 2025, Nebius in October 2024 and
SpaceX on 12 June 2026. The 12/144/9 MACD needs 289 bars before it gives signals, so SpaceX gets
none on daily bars yet (it has about 100). On 2h bars it has had signals since around September 2026.
A 200-day EMA on a stock with under 200 days of history is not a real 200-day average either, so
treat SpaceX's results and signals as a rough guide until it has traded for a year.

The plan, in order:

1. **Backtest** (this folder): does the strategy make money on real past prices?
2. **Scanner** (this folder): which stocks gave a signal on the last completed bar?
3. **AI agent**: Claude reads the scanner output and the news, then writes a briefing and trade plans.
4. **Paper trading**: at least a month on Interactive Brokers paper, with the agent running.
5. **Real money**: only if step 4 made money, and you approve every order.

## The strategy: two long-only systems

Two MACD systems run side by side, each on **half the account** (`SYSTEM_SPLIT` in `config.py`), with
their own positions, stops and $800-style kill switch on their half:

| | **Long-term** (`LONG_TERM`) | **Short-term** (`SHORT_TERM`) |
|---|---|---|
| MACD | **12/144/9**: slow, catches big swings | **12/26/9**: the classic, catches short swings |
| Buy | MACD crosses up **under zero** while price is **below** the 200-day EMA (a deep dip) | MACD crosses up **under zero** while price is **above** the 200-day EMA (a pullback in a stock that's already rising) |
| Wait after the cross | 2 bars | 1 bar |
| Line-up window | then up to 30 more bars for everything to agree | then up to 10 more bars |
| Higher timeframes | 4h and daily 12/144/9 MACDs must agree | 4h and daily 12/26/9 MACDs must agree |
| Stop | 3 × ATR | 2 × ATR |
| Sell | The sell setup: MACD crosses down **above zero** | The sell setup, or after **10 trading days** |
| Typical hold | weeks to months | days to about two weeks |

Run one system with `--system long-term` or `--system short-term` (backtester and scanner).

Rules both systems share (each one's settings live in `config.py` → `Strategy`):

| Rule | Default | Where to change it |
|---|---|---|
| Chart | 2h bars (1h, 4h and daily also supported) | `--interval` |
| Confirmation | **Don't enter on the cross.** Wait N bars: the MACD must stay above its signal line and the histogram must grow on each. Crosses that fizzle straight away are skipped | `confirm_bars` |
| Higher timeframes | The 4h and daily MACDs must be above their signal lines (last finished bar). Only timeframes longer than the chart count | `higher_tfs`, `require_higher` |
| Line-up window | Higher timeframes turn **later** than the chart, so after the wait the system keeps watching for up to N bars, as long as the chart's MACD stays above its signal line. It buys on the **first bar where everything lines up**. One entry per cross. Without this window (0) almost no trades happen | `align_window` |
| Buffer | Off: any cross under zero counts. Can require the cross to be N × ATR(14) below zero | `min_macd_depth_atr`, `--buffer` |
| Lower timeframes | Counts how many of **15m / 30m / 45m** agree (their MACD above its signal line and histogram rising). Shown on every trade; doesn't block trades unless you ask | `confirm_min`, `--mtf` |
| 200 EMA | The 200-**day** EMA. The 200-**bar** EMA of the chart timeframe is tested as a variant | `trend_ma_source` |
| Fill | Open of the next bar (no peeking at the future) | `backtest.py` |
| Exit | **Hold until the sell setup:** the MACD crosses back below its signal line **while above zero** → sell at the next bar's open. A cross back while still under zero doesn't exit | `macd_exit` |
| Trailing stop / target | Off: winners run until the sell setup, the stop or the time limit | `trail_atr_mult`, `target_r` |
| Size | Lose 2% of the system's half if the stop hits; no position above ~34% of it; fractional shares | `--risk-pct`, `--max-position-pct` |
| Limits | Max 3 positions per system; a system stops opening trades once its half drops to 80% | `max_positions`, `kill_switch_pct` |
| Costs | IBKR Pro fixed commissions + 0.05% slippage per fill | `Risk` |
| Shorts | **Off (parked).** See below | `sides` |

The same stock can be held by both systems at once: they're separate books.

### Shorts (parked)

Short selling is switched off but kept, tested and documented so it can come back. Everything below
still works: `--sides both` (or `short`) in Python, **Entry → Trades to take** in TradingView.

**Why it's parked:** in TradingView tests on 2024-2026 charts, adding shorts made the strategy
unprofitable. These AI and chip stocks mostly went up, and the short rule bets against stocks stretched
above their 200-day EMA, which is betting against the trend.

**What was built:**

| Rule | Short |
|---|---|
| Entry | MACD crosses **below** its signal line **while above zero**, and price is **above the 200-day EMA** (mirror of the long-term buy) |
| Market filter | Only while **QQQ is below its own 200-day EMA** (yesterday's close), i.e. a falling market. In a bull market this blocks nearly every short |
| Stop / exit | Entry + 3 × ATR; hold until the **buy setup** (MACD crosses back up **while below zero**) |
| Flip | With longs and shorts both on, the sell setup that ends a long opens the short on the same bar (and the reverse) |
| Size | Same as longs, sharing the position slots; 0.5%/year stock-loan fee |

| Short setting | Options |
|---|---|
| `short_market_filter` | `"QQQ"` (default) or `None` |
| `short_trend_side` | mirror of longs (default: stock above its 200 EMA), `"below"` (short stocks already falling, with the trend), `"off"` |
| `short_stop_atr_mult` | a different stop for shorts (default: same as longs) |
| `short_risk_mult` | 0.5 = shorts risk half as much |

**Before reviving it:** run `python optimize_shorts.py` (and with `--interval 2h`). It tries every
combination of the short settings on the first 70% of history and checks each on the last 30%, then
compares long only against long + short. Only switch shorts back on if a setting makes money in both
halves on 20+ trades. Test on history that includes 2022, the last real bear market.

**Real-money limits at Interactive Brokers:** shorting needs a **margin account** (at least
**$2,000**), and **fractional shares can't be shorted**. A short's loss has no ceiling: a gap up on
earnings can cost far more than 2%. In a small cash account, the bearish alternatives are **put options**
(the most you can lose is what you paid) or **inverse ETFs** (SQQQ, SOXS, NVDS).

`--compare` runs these side by side:

| Variant | What it tests |
|---|---|
| Dip buy, below 200-day EMA | The default above: hold until the sell setup |
| Enter on the cross (no 2-bar wait) | Is waiting for confirmation worth it? |
| No higher-timeframe check | Does making the 4h and daily agree help? |
| Neither filter (as before) | Both filters off: more trades, lower quality? |
| Old exits: 2R target, any MACD cross back, 15 days | The earlier, quicker exits, to see how much letting winners run changes |
| Sell setup exit + 3 ATR trailing stop | The default, plus a stop that follows price up (gives back less, but can exit earlier) |
| 3 ATR trailing stop only | No MACD exit at all: ride until a 3 ATR pullback from the best close |
| Dip buy, below 200-bar EMA | Same, using the 200 EMA of the chart timeframe instead of the daily |
| Dip buy, no 200 EMA rule | Whether the 200 EMA filter helps at all |
| Zero-line cross, price not run | MACD crosses above zero while price is still within 3 ATR of its 20-bar low ("MACD turned, price hasn't moved yet") |
| Zero-line cross, any | Same without the "price hasn't moved" check |
| Trend: MACD cross, above 200-day EMA | The opposite idea: only buy stocks already in an uptrend |
| Classic 12/26/9, above 200-day EMA | The textbook MACD for comparison |
| (parked) Long + short | Long-term system plus short selling |
| (parked) Short only | The short rule on its own |

`--compare` also adds the **short-term system** on the full account and **both systems** together.

The backtester is deliberately pessimistic in two places. If a stop and a target are both touched in
the same bar, it assumes the stop hit first. If a stock gaps through the stop, it fills at the
(worse) open price.

## Setup (on your own computer)

You need Python 3.10 or later.

```bash
cd trading
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q tests        # should print "63 passed"
```

## Run the backtest

```bash
python run_backtest.py --compare                         # all variants, 2h bars
python run_backtest.py --compare --interval 4h           # 4h bars
python run_backtest.py --compare --interval 1h
python run_backtest.py --compare --interval 1d --start 2018-01-01   # daily bars, includes the 2022 crash
python run_backtest.py --compare --risk-pct 3            # same again at 3% risk per trade
python run_backtest.py --tickers NVDA AMD SNDK           # default strategy on a few stocks, with detail
python run_backtest.py --system long-term                # only the 12/144/9 system (default: both systems)
python run_backtest.py --system short-term               # only the 12/26/9 system
python run_backtest.py --compare --group ai              # every variant on the AI list only
python run_backtest.py --sides both                      # (parked) add short selling back in
python run_backtest.py --buffer 0.5                      # only crosses at least 0.5 ATR under zero
python run_backtest.py --mtf 0                           # record the 15m/30m/45m count on each trade
python run_backtest.py --mtf 2                           # only trades where 2 of 3 lower timeframes agree
```

### The buffer and the lower-timeframe check

**Buffer (off by default).** The MACD is measured in ATRs (ATR(14) of the chart timeframe), so one
number works for a $100 stock and a $900 stock, and on 1h, 2h and 4h charts. At 0.5, a buy only counts
if the blue MACD line is at least half an ATR below zero when it crosses up (mirror for shorts). Try it
with `--buffer 0.5`; the detailed output also splits results by how far from zero each cross was.

**Lower timeframes.** A lower timeframe "agrees" with a buy when its own MACD (same 12/144/9) is above
its signal line and its histogram rose on its last closed bar. Only lower-timeframe bars that had
finished when the chart bar closed are used, so the test can't peek ahead.

- **Yahoo keeps only 60 days of 15m and 30m bars**, so `--mtf` limits the Python test to that window:
  a handful of trades, not enough to judge. The cache keeps growing each time you run the scanner, so
  the history builds up. TradingView can test it further back.
- **Lower timeframes usually agree already.** The rally that turns the 2h MACD up has normally turned
  the 15m up hours before. So "3 of 3" may be close to always true and add little. Watch the count first
  (`--mtf 0`, or the "x/3" next to each trade in TradingView), then switch the filter on if trades with
  2–3 agreeing clearly beat trades with 0–1 over 30+ trades.

The detailed output (`--tickers ...` or any run without `--compare`) breaks results down by how far from
zero the cross was and by how many lower timeframes agreed, so you can see whether either one helps.

Prices come from Yahoo Finance (free, cached in `data/`; add `--refresh` to re-download). **Yahoo only
has about two years of hourly data**, which has been mostly a bull market, so dip-buying will look
better than it would in a year like 2022. Run the daily version too: it goes back to 2018 and
includes the 2022 drawdown. Interactive Brokers' API has longer intraday history, which we can wire in later.
TradingView's 45-minute chart can't be backtested here: Yahoo keeps under 30-minute bars for only 60 days.

### How to read the results

- **total_return_pct / cagr_pct**: what $1,000 became, as a total and per year.
- **max_drawdown_pct**: the worst drop from a high. This is the pain you would have sat through.
- **win_rate_pct**: share of trades that made money. Holding for the sell setup means fewer, bigger
  winners, so a win rate well below 50% is normal. Look at avg_r and profit_factor instead.
- **avg_r**: average result per trade, in units of what was risked. Anything above 0 means the strategy has an edge.
- **profit_factor**: dollars won ÷ dollars lost. Above 1.3 is decent; below 1.1 is close to noise.
- **longest_losing_streak**: how many losses in a row you need to be able to stomach.
- **kill_switch_hit**: when the account would have dropped to $800, if it did.
- **long_pnl / short_pnl**: dollars made by each side, when shorts are on. If the shorts lose money
  while the longs make it, leave shorts off.

**The bar to clear:** beat buy-and-hold QQQ, or come close with a much smaller drawdown. If no
variant manages that, trading it is extra work for less money.

**Watch for overfitting.** If you tweak settings until the backtest looks great, you've fitted the
past, not found an edge. Change one thing at a time, for a reason.

**Shorts and the last two years:** this has mostly been a bull market for these stocks, so shorts
will probably look worse here than in a year like 2022. Run the daily test from 2018 before deciding.

**Known limit:** the stock list contains today's winners, so past results look better than they
would have in real time (survivorship bias). Treat any backtest return as an upper bound.

## Test it in TradingView (Pine Script)

`pine/macd_dip_buy.pine` is the same two systems as a TradingView strategy script, so you can run them in
TradingView's Strategy Tester on TradingView's own data and see every trade on your chart.

**System** (top of the settings) picks **Long-term: 12/144/9** (default) or **Short-term: 12/26/9**,
which fix the MACD, 200 EMA side, wait bars, stop and time limit to that system's rules. To watch both
on one chart, add the script **twice** and set the second copy to Short-term. Trades are labelled "LT"
or "ST". **Custom** uses every setting as you set it; settings marked "(Custom only)" are ignored
otherwise.

1. Open a chart (for example NVDA or SNDK) and set the timeframe to 2h (or 1h, 4h, 45m).
2. Open the **Pine Editor** at the bottom of the screen, delete what's there, paste in the whole file, and click **Add to chart**.
   Optional, only if you turn the buffer on: `pine/macd_panel.pine` is the MACD panel with the buffer
   drawn as dotted lines (set its buffer to the same number).
3. Open the **Strategy Tester** tab at the bottom. **Overview** shows the equity curve, **List of trades** shows each trade.
4. Click the gear on the strategy to change settings. To test each variant:

| Variant | Settings to change from the default |
|---|---|
| Long-term system | Default, nothing to change |
| Short-term system | System: **Short-term: 12/26/9** |

For the rows below, first set System to **Custom** (it starts from the long-term settings).

| Variant | Settings to change (System: Custom) |
|---|---|
| Enter on the cross | Only the best trades → Wait N bars: **0** |
| No higher-timeframe check | Untick **Higher timeframes must agree** |
| Old exits: 2R target, any MACD cross back, 15 days | Exits → MACD exit: **Any cross back**; Target in R: **2**; Time stop: **15** |
| Sell setup exit + 3 ATR trailing stop | Exits → Trailing stop: **3** |
| 3 ATR trailing stop only | Exits → MACD exit: **Off**; Trailing stop: **3** |
| With a buffer | Entry → Buffer: **0.5** (or 1) |
| Dip buy, below 200-bar EMA | 200 EMA filter → EMA timeframe: **Chart** |
| Dip buy, no 200 EMA rule | 200 EMA filter → Price must be: **Off** |
| Zero-line cross, price not run | Entry trigger: **Zero-line cross**; Skip if price ran more than: **3**; Price must be: **Off** |
| Zero-line cross, any | Entry trigger: **Zero-line cross**; Price must be: **Off** |
| Trend: MACD cross above 200-day EMA | Untick "must happen under zero"; Price must be: **Above** |
| Classic 12/26/9 | Slow length: **26**; untick "must happen under zero"; Price must be: **Above** |
| (parked) Long + short | Entry → Trades to take: **Long and short** |
| (parked) Short only | Entry → Trades to take: **Short only** |

**Your MACD panel must be 12/144/9 to match the strategy.** TradingView's built-in MACD defaults to
12/26/9, a much faster indicator whose crosses the strategy never sees. Open the MACD indicator's
settings and set Slow length to 144.

**Fewer, better trades:** by default the strategy waits 2 bars after a cross (both must confirm) and
needs the 4h and daily MACDs to point the same way. The box at the top right shows "Higher TFs up /
down" right now. To compare, set **Only the best trades → Wait N bars** to 0, or untick **Higher
timeframes must agree**.

Short signals show as pink triangles above the bar; buy signals as teal triangles below. The red line
is the stop while a trade is open. With the buffer on, grey crosses mark signals it skipped.

**Lower timeframes:** each trade is labelled with how many of 15m/30m/45m agreed, like "Long 2/3",
and the box at the top right shows the count right now. To make it a rule, set **Lower timeframes →
How many must agree** to 2 or 3. Only timeframes shorter than the chart count (on a 30m chart only 15m
does). How far back this works depends on how much 15m history your TradingView plan loads.

For each stock and variant, note **Net profit**, **Max drawdown**, **Total closed trades**, **Percent
profitable** and **Profit factor**, or just screenshot the Overview and Performance Summary.

Differences from the Python backtester:

- **One stock at a time.** TradingView tests the strategy on the chart's symbol only, so the
  3-position limit and ranking between stocks don't apply. Each stock gets the full $1,000.
- **Commission** is set to a flat $1 per order (the IBKR minimum, which is what small orders pay),
  plus 2 ticks of slippage.
- **Same-bar stop and target:** when both are touched in one bar, TradingView guesses the order from
  the bar's shape. Python always assumes the stop hit first.
- **History** depends on your TradingView plan. Intraday charts load a limited number of bars, so a
  2h test may only reach back a year or two.
- **One trade at a time per copy.** Each copy of the script holds one position on the chart's stock.
  In Python each system can hold up to 3 different stocks, and both systems can hold the same stock.
- **Account size:** each TradingView copy starts with the full $1,000; in Python each system gets $500.
- The script also fires an **alert** on each buy signal. Create an alert on the strategy to get pinged,
  and later the agent can receive these by webhook.

## Run the scanner

```bash
python scan.py --equity 1000                 # both systems, 2h bars, your current account value
python scan.py --system short-term           # only the 12/26/9 short-term system
python scan.py --interval 4h --group ai      # 4h bars, AI list only
python scan.py --mtf 2                       # only signals where 2 of 15m/30m/45m agree
```

It prints a section per system. Each buy signal comes with a stop and a share count, sized so that
hitting the stop costs your risk percent of that system's half of the account, plus `higher_tfs` (how
many of 4h/daily agree) and `lower_tfs` (how many of 15m/30m/45m agree). It also prints a watchlist of
stocks with the MACD under zero and curling up toward a cross. Add `--no-mtf` to skip downloading the
lower timeframes. Run it after a bar closes: during market hours the newest bar is still
forming and its signal can disappear by the close. The MACD and EMA match TradingView's formulas, so
you can check any signal on your chart.

## Is my Interactive Brokers account paper or live?

- Paper account numbers start with **DU**. Live accounts usually start with **U**.
- The TWS / IBKR desktop login has a **Live / Paper** switch. In the web portal and app, the paper
  account shows a "Paper Trading" banner.
- For the agent later: TWS uses port **7497** for paper and **7496** for live. IB Gateway uses **4002**
  for paper and **4001** for live. The agent will be set up to refuse live ports until you choose to switch.

---

General information only, not personal financial advice. Backtested results are hypothetical and do
not guarantee future returns.
