# MACD swing trading: backtester and scanner

Step 1 of a trading assistant for a $1,000 account trading large US stocks:
the Magnificent 7, semiconductors, and other big names that move a lot.

The plan, in order:

1. **Backtest** (this folder): does the strategy make money on real past prices?
2. **Scanner** (this folder): which stocks gave a signal on the last completed bar?
3. **AI agent**: Claude reads the scanner output and the news, then writes a briefing and trade plans.
4. **Paper trading**: at least a month on Interactive Brokers paper, with the agent running.
5. **Real money**: only if step 4 made money, and you approve every order.

## The strategy

The default is the setup traded on TradingView: **MACD 12/144/9 on 1h–4h charts plus the 200 EMA.**

| Rule | Default | Where to change it |
|---|---|---|
| Chart | 2h bars (1h, 4h and daily also supported) | `--interval` |
| Entry | MACD line crosses above its signal line **while under zero**, and price is **below the 200 EMA** | `config.py` → `Strategy` |
| 200 EMA | The 200-**day** EMA. The 200-**bar** EMA of the chart timeframe (what a "200" EMA on a 2h chart shows, about 50 trading days) is tested as a variant | `trend_ma_source` |
| Fill | Open of the next bar (no peeking at the future) | `backtest.py` |
| Stop | Entry − 3 × ATR(14) of the chart timeframe | `stop_atr_mult` |
| Target | 2 × the risk (2R) | `target_r` |
| Other exits | MACD crosses back below its signal line → sell at the next bar's open; 15-trading-day time stop | `exit_on_macd_cross_down`, `max_hold_days` |
| Size | Lose 2% of the account if the stop hits; no position above ~34% of the account; fractional shares | `--risk-pct`, `--max-position-pct` |
| Limits | Max 3 positions; no new trades once the account hits $800 | `max_positions`, `kill_switch_pct` |
| Costs | IBKR Pro fixed commissions + 0.05% slippage per fill | `Risk` |

`--compare` runs these side by side:

| Variant | What it tests |
|---|---|
| Dip buy, below 200-day EMA | The default above |
| Dip buy, below 200-bar EMA | Same, using the 200 EMA of the chart timeframe instead of the daily |
| Dip buy, no 200 EMA rule | Whether the 200 EMA filter helps at all |
| Zero-line cross, price not run | MACD crosses above zero while price is still within 3 ATR of its 20-bar low ("MACD turned, price hasn't moved yet") |
| Zero-line cross, any | Same without the "price hasn't moved" check |
| Trend: MACD cross, above 200-day EMA | The opposite idea: only buy stocks already in an uptrend |
| Classic 12/26/9, above 200-day EMA | The textbook MACD for comparison |

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
python -m pytest -q tests        # should print "21 passed"
```

## Run the backtest

```bash
python run_backtest.py --compare                         # all variants, 2h bars
python run_backtest.py --compare --interval 4h           # 4h bars
python run_backtest.py --compare --interval 1h
python run_backtest.py --compare --interval 1d --start 2018-01-01   # daily bars, includes the 2022 crash
python run_backtest.py --compare --risk-pct 3            # same again at 3% risk per trade
python run_backtest.py --tickers NVDA AMD SNDK           # default strategy on a few stocks, with detail
```

Prices come from Yahoo Finance (free, cached in `data/`; add `--refresh` to re-download). **Yahoo only
has about two years of hourly data**, which has been mostly a bull market, so dip-buying will look
better than it would in a year like 2022. Run the daily version too: it goes back to 2018 and
includes the 2022 drawdown. Interactive Brokers' API has longer intraday history, which we can wire in later.
TradingView's 45-minute chart can't be backtested here: Yahoo keeps under 30-minute bars for only 60 days.

### How to read the results

- **total_return_pct / cagr_pct**: what $1,000 became, as a total and per year.
- **max_drawdown_pct**: the worst drop from a high. This is the pain you would have sat through.
- **win_rate_pct**: share of trades that made money. Below 50% is normal at a 2R target.
- **avg_r**: average result per trade, in units of what was risked. Anything above 0 means the strategy has an edge.
- **profit_factor**: dollars won ÷ dollars lost. Above 1.3 is decent; below 1.1 is close to noise.
- **longest_losing_streak**: how many losses in a row you need to be able to stomach.
- **kill_switch_hit**: when the account would have dropped to $800, if it did.

**The bar to clear:** beat buy-and-hold QQQ, or come close with a much smaller drawdown. If no
variant manages that, trading it is extra work for less money.

**Watch for overfitting.** If you tweak settings until the backtest looks great, you've fitted the
past, not found an edge. Change one thing at a time, for a reason.

**Known limit:** the stock list contains today's winners, so past results look better than they
would have in real time (survivorship bias). Treat any backtest return as an upper bound.

## Run the scanner

```bash
python scan.py --equity 1000                 # 2h bars, default strategy, your current account value
python scan.py --interval 4h --variant 3     # 4h bars, zero-line-cross variant
```

For each buy signal it prints a stop, a target and a share count, sized so that hitting the stop
costs your risk percent of the account. It also prints a watchlist of stocks with the MACD under zero and
curling up toward a cross. Run it after a bar closes: during market hours the newest bar is still
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
