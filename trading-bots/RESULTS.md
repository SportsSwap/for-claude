# Trading bots: research, backtests and results

Built 27 Nov 2026. 17 strategies, 13 of them tested on 1993–2026 data
(crypto 2014–2026). Every number below is **net of trading costs** and comes
from free daily Yahoo Finance prices (dividend-adjusted).

**This is research, not financial advice. Past results, even out of sample,
do not promise future returns.** Paper-trade anything before real money.

## How every bot was tested (fixed before any result was seen)

1. A small grid of settings around the published rule, tested only on the
   **in-sample** years (ETFs: to 2012 or 2014; VIX: to 2016; crypto: to 2019/2020).
2. The setting picked is the best **plateau** (it and its neighbours all do
   well), not the single best spike.
3. That setting is then run on the **out-of-sample** years it never saw. That
   is the column that matters.
4. **Walk-forward:** re-pick every January using only past data, trade the year.
5. **Deflated Sharpe** (Bailey & López de Prado): the chance the Sharpe is real
   after allowing for how many settings were tried. ≥ 0.95 is good.
6. **PBO** (probability of backtest overfitting, CSCV with 16 blocks): the chance
   the in-sample winner is below median out of sample. Lower is better; 0.5 = coin flip.
7. **Costs doubled**: must still make money.

Costs per side: SPY/QQQ/IWM/DIA 2 bps, other ETFs 4 bps, SVXY/VIXY 8 bps,
crypto 20 bps, FX 1 bp. Signals use data up to the bar's close only; "at the
close" bots need market-on-close orders, others trade at the next open.

**Grades.** A: out-of-sample Sharpe ≥ 0.7, walk-forward Sharpe ≥ 0.6,
deflated Sharpe ≥ 0.95, PBO ≤ 0.5, profitable at 2× costs. B: Sharpe ≥ 0.5,
walk-forward ≥ 0.5, deflated Sharpe ≥ 0.9, profitable at 2× costs.
C: Sharpe ≥ 0.5 only. F: fails. \* = biased stock/coin list (survivorship), not trusted.

## Results (out of sample)

| Bot | Grade | OOS years | CAGR | Sharpe | Max DD | Time in market | Walk-fwd Sharpe | Deflated Sharpe | PBO | CAGR at 2× costs | Buy & hold CAGR / Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 Faber GTAA trend | **B** | 2015–2026 | 4.1% | 0.62 | -11.2% | 100.0% | 0.62 | 0.96 | 0.82 | 3.8% | 12.9% / 0.78 |
| 02 Time series momentum | **A** | 2015–2026 | 3.6% | 0.78 | -8.3% | 100.0% | 0.68 | 0.97 | 0.38 | 3.4% | 12.9% / 0.78 |
| 03 Keller VAA dual momentum | **C** | 2015–2026 | 4.5% | 0.51 | -23.4% | 100.0% | 0.47 | 0.78 | 0.57 | 3.9% | 12.9% / 0.78 |
| 04 Crypto Donchian trend BTC | **B** | 2020–2026 | 19.9% | 0.88 | -33.7% | 36.3% | 0.88 | 0.96 | 0.67 | 16.6% | 36.2% / 0.82 |
| 05 VIX term structure SVXY | **F** | 2017–2026 | 6.5% | 0.36 | -50.1% | 83.5% | 0.34 | 0.32 | 0.39 | 4.7% | 14.2% / 0.82 |
| 06 Connors RSI2 index ETFs | **F** | 2013–2026 | 3.7% | 0.36 | -40.9% | 29.5% | 0.29 | 0.78 | 0.99 | 2.9% | 14.2% / 0.88 |
| 07 IBS mean reversion | **A** | 2013–2026 | 11.8% | 0.91 | -20.3% | 43.1% | 0.90 | 1.00 | 0.38 | 9.7% | 14.2% / 0.88 |
| 08 Overnight after down days | **A** | 2013–2026 | 2.4% | 0.82 | -6.9% | 8.1% | 0.82 | 0.98 | 0.10 | 1.6% | 14.2% / 0.88 |
| 09 Turn of the month SPY | **B** | 2013–2026 | 5.9% | 0.66 | -15.8% | 33.4% | 0.58 | 0.97 | 0.60 | 5.4% | 14.2% / 0.88 |
| 10 Sector momentum rotation | **C** | 2013–2026 | 8.7% | 0.69 | -22.9% | 100.0% | 0.69 | 0.84 | 0.53 | 8.2% | 14.2% / 0.88 |
| 11 FX trend majors | **F** | 2015–2026 | -3.0% | -0.24 | -36.8% | 200.0% | -0.32 | 0.04 | 0.40 | -3.3% | — / — |
| 12 Lower band IBS SPY QQQ | **A** | 2013–2026 | 8.6% | 0.88 | -14.5% | 11.3% | 0.88 | 0.99 | 0.31 | 8.2% | 14.2% / 0.88 |
| 13 Your MACD 12-144-9 dip rule | **A*** | 2015–2026 | 21.1% | 0.90 | -33.8% | 69.3% | 0.90 | 0.99 | 0.08 | 19.3% | 35.7% / 1.22 |
| 14 Keller HAA | **A** | 2015–2026 | 10.0% | 0.98 | -12.9% | 100.0% | 0.96 | 1.00 | 0.16 | 9.7% | 12.9% / 0.78 |
| 15 Volatility Edge VIX | **B** | 2017–2026 | 3.9% | 0.67 | -8.1% | 15.5% | 0.76 | 0.96 | 0.21 | 3.5% | 14.2% / 0.82 |
| 16 Connors Double 7s | **F** | 2013–2026 | 6.5% | 0.47 | -35.5% | 60.4% | 0.28 | 0.91 | 0.58 | 4.7% | 14.2% / 0.88 |
| 17 Crypto trend top coins | **A*** | 2021–2026 | 12.7% | 1.16 | -17.2% | 14.7% | 0.86 | 0.99 | 0.45 | 11.2% | 13.3% / 0.50 |

"Time in market" counts bond/T-bill holdings as invested for the allocation bots.

## What each result means

- **01 Faber GTAA trend** — Works mainly as drawdown control (max DD -11% vs SPY -34%); lags SPY's return in the 2015-26 bull market. PBO high: the 6 vs 10 month choice is noise.
- **02 Time series momentum** — Steady, low volatility, Sharpe 0.78 out of sample. Low return on its own; a good portfolio building block.
- **03 Keller VAA dual momentum** — Decayed after publication (out-of-sample Sharpe 0.51, deflated Sharpe below 0.9). Superseded by HAA (#14).
- **04 Crypto Donchian trend BTC** — 19.9%/yr vs 36.2% for holding BTC, but the drawdown is -34% instead of -77% and the Sharpe is a bit higher (0.88 vs 0.82). Setting choice is fragile (PBO 0.67), so expect less.
- **05 VIX term structure SVXY** — Simple SVXY contango rule: -50% drawdowns, Sharpe 0.36 out of sample. Don't run it.
- **06 Connors RSI2 index ETFs** — Connors RSI(2) has decayed: out-of-sample Sharpe 0.36, -41% drawdown. Matches the published re-tests.
- **07 IBS mean reversion** — Best single bot. Works on each ETF separately (QQQ Sharpe 1.14, SPY 0.94, ~340 trades each, ~72% winners) and still works when filled at the next open (Sharpe 0.76).
- **08 Overnight after down days** — Clean but tiny edge (~2.4%/yr, -7% DD). Only the 3-down-day version works; the 1-day default does not. Useful as a diversifier.
- **09 Turn of the month SPY** — The turn-of-month effect still exists on SPY (63% winning months, profit factor 1.8). Holding 5 days before month end works better than the classic 1.
- **10 Sector momentum rotation** — Decent (8.8%/yr, Sharpe 0.69) but deflated Sharpe 0.84: could be luck. Not proven.
- **11 FX trend majors** — FX trend on majors lost money 2015-26, as the research warned (post-publication Sharpe near zero). Spot only, carry not included.
- **12 Lower band IBS SPY QQQ** — Strong (Sharpe 0.88, in the market 11% of days) but sensitive to fill timing: Sharpe 0.56 if filled at the next open. Needs market-on-close orders.
- **13 Your MACD 12-144-9 dip rule** — Your MACD 12/144/9 rule exactly as specified LOSES (-1.2%/yr out of sample). The optimiser's pick (12/26/9, no filter, 60 days) made 21%/yr but simply holding the same 12 stocks made 36%/yr, and the list is today's winners (survivorship bias). Not recommended.
- **14 Keller HAA** — Strong new find: 10%/yr, Sharpe 0.98, max DD -13% out of sample; the published setting was also the plateau pick (PBO 0.16).
- **15 Volatility Edge VIX** — Works only WITHOUT the paper's long-VIX leg (Sharpe 0.67, DD -8%). The paper's exact version: Sharpe 0.54, DD -30%.
- **16 Connors Double 7s** — Double 7s has decayed: Sharpe 0.47, -36% drawdown, and walk-forward Sharpe 0.28.
- **17 Crypto trend top coins** — Good on paper (12.7%/yr, Sharpe 1.16 vs BTC 0.50, DD -17%) but the coin list is today's survivors, which flatters it. Kept out of the portfolio.

## The multi-strategy portfolio

Single bots mostly don't beat simply holding SPY on return. Combined, they do
much better on risk, because they rarely lose at the same time (most pairwise
correlations are 0.0–0.4). This is how multi-strategy funds work.

Members (grade A/B, unbiased lists): 01 Faber GTAA trend, 02 Time series momentum, 04 Crypto Donchian trend BTC, 07 IBS mean reversion, 08 Overnight after down days, 09 Turn of the month SPY, 12 Lower band IBS SPY QQQ, 14 Keller HAA, 15 Volatility Edge VIX.
Each is weighted by the inverse of its trailing 1-year volatility, monthly.
"Stacked" scales the mix to 10% volatility with up to 2× gross exposure (a
margin account). Borrowing is charged at T-bill + 1.5%; idle cash earns
T-bill − 0.5% (IBKR pays nothing on the first US$10k, so small accounts earn less).

| Portfolio | CAGR | Sharpe | Max DD | Worst year | Avg gross exposure | SPY CAGR / Sharpe / Max DD |
|---|---|---|---|---|---|---|
| 2015-2026 without crypto — unlevered | 6.2% | 1.44 | -5.4% | -1.3% | 0.46x | 13.3% / 0.79 / -33.7% |
| 2015-2026 without crypto — stacked to 10% vol (margin) | 10.0% | 1.19 | -10.9% | -2.7% | 0.91x | 13.3% / 0.79 / -33.7% |
| 2020-2026 all members — unlevered | 8.1% | 1.75 | -5.4% | -1.1% | 0.46x | 14.8% / 0.90 / -24.5% |
| 2020-2026 all members — stacked to 10% vol (margin) | 13.2% | 1.44 | -11.0% | -3.8% | 0.90x | 14.8% / 0.90 / -24.5% |

In 2022, when SPY fell about 18%, the stacked portfolio lost 3.8% (2020–26 mix).

## High-octane option (read the warning)

The IBS signal (bot 07) on SPY traded through 2× and 3× ETFs, 2013–2026:
SSO 18.2%/yr (max DD −35%), UPRO 27.1%/yr (max DD −48%, worst year −39%).
On QQQ via TQQQ it made 40.5%/yr with a −36% max DD, but QQQ was picked
*because* it did best out of sample, so that number is cherry-picked. Leveraged
ETFs can lose most of their value in a crash; size them small.

## Files

- `bots/strategies.py` — all 17 bots, with sources in the comments.
- `engine/` — data cache, backtester, metrics (deflated Sharpe, PBO), validation.
- `run_all.py` — reruns every test. `portfolio.py` — the combined portfolio.
- `signals.py` — today's target positions for the passing bots (never places orders).
- `tradingview/` — Pine Script v6 versions of bots 07 and 12 (not compiled here; check in the Pine Editor).
- `reports/Retail systematic trading strategies.md` — the research report.
- `research_notes/` — the raw research notes with sources.
- `results/` — every number, equity curve and trade list.

## Limits

- Research agents could read search summaries and some primary pages, not every
  paper (the network blocked many sites), so published figures are second-hand.
  The backtests here are first-hand.
- Yahoo data only. No survivorship-free stock universe, so stock-picking bots
  (like Clenow's) were not built.
- Out-of-sample periods are 6–14 years; 2015–2026 was a strong bull market,
  which flatters buy-and-hold and hurts defensive bots.
