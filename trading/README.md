# MACD swing trading: backtester and scanner

Step 1 of a trading assistant for a $1,000 account trading large US stocks:
the Magnificent 7, semiconductors, and other big names that move a lot.

The plan, in order:

1. **Backtest** (this folder): does the MACD strategy make money on real past prices?
2. **Scanner** (this folder): which stocks gave a signal at today's close?
3. **AI agent**: Claude reads the scanner output and the news, then writes a nightly briefing and trade plans.
4. **Paper trading**: at least a month on Interactive Brokers paper, with the agent running every night.
5. **Real money**: only if step 4 made money, and you approve every order.

## Setup (on your own computer)

You need Python 3.10 or later.

```bash
cd trading
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q tests        # should print "15 passed"
```

## Run the backtest

```bash
python run_backtest.py --compare
```

This downloads daily prices from Yahoo Finance (free, cached in `data/`). It runs every strategy
variant from 2018 to today and compares them against simply buying and holding QQQ and SMH.
Trade-by-trade logs go to `results/`.

Other options:

```bash
python run_backtest.py                          # default strategy, with a P&L breakdown by stock
python run_backtest.py --tickers NVDA AMD TSLA  # just these stocks
python run_backtest.py --start 2022-01-01       # test from 2022 onwards (includes the 2022 crash)
python run_backtest.py --refresh                # re-download prices
```

### How to read the results

- **total_return_pct / cagr_pct**: what $1,000 became, as a total and per year.
- **max_drawdown_pct**: the worst drop from a high. This is the pain you would have sat through.
- **win_rate_pct**: share of trades that made money. Below 50% is normal for this kind of strategy.
- **avg_r**: average result per trade, in units of what was risked. Anything above 0 means the strategy has an edge.
- **profit_factor**: dollars won ÷ dollars lost. Above 1.3 is decent; below 1.1 is close to noise.
- **longest_losing_streak**: how many losses in a row you need to be able to stomach.
- **kill_switch_hit**: the date the account would have dropped to $800, if it did.

**The bar to clear:** the strategy has to beat buy-and-hold QQQ, or at least come close with a
much smaller drawdown. If it can't, trading it is extra work for less money.

**Watch for overfitting.** If you tweak settings until the backtest looks great, you've fitted the
past, not found an edge. Pick settings for a reason, then check them on a period you didn't tune on
(for example, tune on 2018–2022 and then run `--start 2023-01-01`).

## Run the scanner (nightly, after the US close)

```bash
python scan.py --equity 1000     # put your current account value here
```

For each buy signal it prints a stop, a target and a share count, sized so that hitting the stop
costs about 2% of the account. It also prints a watchlist of stocks whose MACD is curling up toward a cross.
The MACD settings match TradingView's defaults (12, 26, 9), so you can check any signal on a chart.

## The strategy

| Rule | Default | Where to change it |
|---|---|---|
| Entry | MACD line crosses above signal line at the close, **and** price is above its 50-day average | `config.py` → `Strategy` |
| Fill | Next day's open (no peeking at the future) | `backtest.py` |
| Stop | Entry − 2 × ATR(14) | `stop_atr_mult` |
| Target | 2 × the risk (2R) | `target_r` |
| Other exits | MACD crosses back down → sell next open; 15-day time stop | `exit_on_macd_cross_down`, `max_hold_days` |
| Size | Risk 2% of account per trade; no position above ~34% of account; fractional shares | `Risk` |
| Limits | Max 3 positions; no new trades once the account hits $800 | `max_positions`, `kill_switch_pct` |
| Costs | IBKR Pro fixed commissions + 0.05% slippage per fill | `Risk` |

The backtester is deliberately pessimistic in two places. If a stop and a target are both touched on
the same day, it assumes the stop hit first. If a stock gaps through the stop overnight, it fills at
the (worse) open price.

**Known limit:** the stock list contains today's winners, so past results look better than they
would have in real time (survivorship bias). Treat any backtest return as an upper bound.

## Is my Interactive Brokers account paper or live?

- Paper account numbers start with **DU**. Live accounts usually start with **U**.
- At the TWS / IBKR desktop login there is a **Live / Paper** switch. In the web portal and app, the
  paper account shows a "Paper Trading" banner.
- For the agent later: TWS uses port **7497** for paper and **7496** for live. IB Gateway uses **4002**
  for paper and **4001** for live. The agent will be set up to refuse live ports until you choose to switch.

---

General information only, not personal financial advice. Backtested results are hypothetical and do
not guarantee future returns.
