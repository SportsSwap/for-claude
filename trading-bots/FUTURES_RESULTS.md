# Futures bots: NQ / MNQ and ES / MES

Built 27 Nov 2026 on free 1-minute Nasdaq-100 and S&P 500 index data from
HistData.com (Nov 2010 to 13 Nov 2026, New York time). Every number is
**per 1 micro contract, after costs**: $1.24 commission per round trip plus
1 tick (0.25 point) of slippage on every market or stop fill. MNQ = $2 a
point, MES = $5 a point. **One full-size NQ or ES is 10× the dollars and 10× the
drawdowns.**

Research and education, not financial advice. Paper trade first.

## How they were tested

Same rules as the systematic bots, fixed before any result was seen:
settings picked only on **2011–2021**, then run unchanged on **2022–Jul 2024
(NEW)** and **Aug 2024–Nov 2026 (FIN)**, the windows of your PA Lab. Plus
walk-forward, deflated Sharpe, overfitting probability (PBO) and doubled costs.
Grades as before: A passes everything, B a looser bar, C made money but could be
luck, F failed.

Data caveats: these are index quotes, not CME futures (no roll gaps, no basis);
2023 is missing about 60 days; the data has no volume, so "VWAP" in the Python
tests is a time-weighted price (the Pine scripts use real VWAP).

Two bugs were caught and fixed before these numbers: a look-ahead in the
intraday-momentum filter (it had shown a fake Sharpe of 4.7) and a 1-hour peek
in the daily FVG's decision time.

## Results (1 micro contract, dollars per year)

| Bot | Grade | Settings (picked on 2011–21) | 2011–21 | NEW 2022–Jul 24 | FIN Aug 24–26 | 2022–26 | Profit factor | Win | Trades | Worst fall | Years up | 2022–26 at 2× costs | QQQ-style 3× ETF CAGR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F07 Lower band IBS NQ | **A** | n=20,k=3.0 | $1,671 | $3,241 | $6,087 | $4,571 | 2.43 | 72% | 74 | $-4,622 | 5/5 | $4,537 | TQQQ 40% |
| F06 IBS dip buy NQ | **B** | thr=0.25,trend=False | $2,120 | $3,811 | $5,725 | $4,705 | 1.60 | 72% | 176 | $-4,957 | 4/5 | $4,624 | TQQQ 43% |
| F12 Turnaround Tuesday NQ | **B** | drop=1.5,hold=2 | $537 | $1,595 | $2,564 | $2,011 | 8.36 | 82% | 17 | $-774 | 5/5 | $2,003 | TQQQ 18% |
| F01 Noise band NQ | **C** | k=1.5,lookback=20,check=60,side=both | $491 | $2,768 | $-149 | $1,398 | 1.18 | 45% | 487 | $-3,817 | 2/5 | $1,173 | TQQQ 12% |
| F02 Opening range breakout NQ | **C** | minutes=5,R=10,stop=atr10,side=both | $-459 | $1,971 | $183 | $1,131 | 1.08 | 17% | 1151 | $-7,241 | 3/5 | $606 | TQQQ 11% |
| F04 Overnight drift NQ | **C** | down=False,trend=True,exit=09:30 | $695 | $1,863 | $4,839 | $3,259 | 1.17 | 56% | 851 | $-4,799 | 4/5 | $2,867 | TQQQ 20% |
| F05 Daily fair value gap NQ | **C** | R=4.0,hours=48,min_gap=0.1,skip_news=True | $284 | $834 | $2,557 | $1,637 | 1.57 | 41% | 93 | $-2,422 | 5/5 | $1,604 | TQQQ 13% |
| F06 IBS dip buy ES | **C** | thr=0.2,trend=False | $928 | $1,693 | $934 | $1,337 | 1.37 | 64% | 140 | $-3,364 | 5/5 | $1,229 | UPRO 15% |
| F07 Lower band IBS ES | **C** | n=5,k=2.0 | $761 | $279 | $2,513 | $1,325 | 1.67 | 74% | 65 | $-3,161 | 5/5 | $1,275 | UPRO 11% |
| F01 Noise band ES | **F** | k=1.5,lookback=10,check=60,side=both | $60 | $1,067 | $-609 | $280 | 1.06 | 48% | 551 | $-3,443 | 3/5 | $-144 | UPRO 4% |
| F02 Opening range breakout ES | **F** | minutes=5,R=5,stop=range,side=both | $-846 | $-1,799 | $536 | $-702 | 0.90 | 20% | 1162 | $-6,162 | 1/5 | $-1,555 | UPRO -11% |
| F03 Intraday momentum ES | **F** | signal=first30_agree,min_move=0.5 | $57 | $102 | $-129 | $-7 | 0.99 | 48% | 235 | $-876 | 3/5 | $-188 | UPRO 0% |
| F03 Intraday momentum NQ | **F** | signal=first30_agree,min_move=0.5 | $128 | $55 | $-217 | $-73 | 0.97 | 48% | 311 | $-2,053 | 2/5 | $-216 | TQQQ -0% |
| F04 Overnight drift ES | **F** | down=True,trend=True,exit=09:30 | $179 | $-311 | $1,110 | $356 | 1.08 | 53% | 387 | $-2,376 | 3/5 | $58 | UPRO 1% |
| F05 Daily fair value gap ES | **F** | R=4.0,hours=48,min_gap=0.25,skip_news=True | $139 | $382 | $-309 | $63 | 1.04 | 43% | 74 | $-2,275 | 4/5 | $25 | UPRO 2% |
| F08 Opening gap ES | **F** | k=0.25,mode=go | $-72 | $-2,612 | $-3,070 | $-2,825 | 0.74 | 40% | 623 | $-15,159 | 0/5 | $-3,304 | UPRO -31% |
| F08 Opening gap NQ | **F** | k=0.5,mode=go | $152 | $-699 | $-3,530 | $-2,026 | 0.82 | 48% | 282 | $-13,620 | 1/5 | $-2,156 | TQQQ -17% |
| F09 Turn of the month ES | **F** | before=5,after=5 | $1,118 | $1,454 | $72 | $804 | 1.25 | 57% | 58 | $-5,994 | 3/5 | $760 | UPRO 4% |
| F09 Turn of the month NQ | **F** | before=5,after=4 | $1,303 | $3,157 | $74 | $1,709 | 1.27 | 66% | 59 | $-9,626 | 4/5 | $1,681 | TQQQ 4% |
| F10 Volatility breakout ES | **F** | k=0.25,side=long,stop_at_open=False | $-72 | $-467 | $-298 | $-388 | 0.97 | 52% | 813 | $-4,174 | 2/5 | $-1,013 | UPRO -6% |
| F10 Volatility breakout NQ | **F** | k=1.0,side=long,stop_at_open=True | $258 | $790 | $-270 | $292 | 1.11 | 51% | 169 | $-3,368 | 3/5 | $215 | TQQQ 3% |
| F11 VWAP trend ES | **F** | confirm=15,start=30,side=long | $-455 | $1,066 | $-161 | $489 | 1.04 | 36% | 1634 | $-3,828 | 4/5 | $-767 | UPRO 7% |
| F11 VWAP trend NQ | **F** | confirm=15,start=30,side=long | $507 | $2,561 | $-667 | $1,045 | 1.04 | 39% | 1589 | $-7,628 | 4/5 | $313 | TQQQ 12% |
| F12 Turnaround Tuesday ES | **F** | drop=0.5,hold=1 | $554 | $-47 | $936 | $376 | 1.56 | 47% | 36 | $-1,150 | 4/5 | $346 | UPRO 3% |

The last column puts the whole account in each trade through a 3× ETF (TQQQ for
NQ, UPRO for ES), compounded, ignoring the ETF's fees: a rough guide to the
"QQQ / TQQQ" version of each bot.

## The futures portfolio (2022–2026, out of sample)

The bots that passed (A/B): F06 IBS dip buy NQ, F07 Lower band IBS NQ, F12 Turnaround Tuesday NQ, 1 MNQ each.

- **$11,142 a year**, $54,148 in total, worst fall $-5,361, Sharpe 1.74.
- Every year up: 2022: $5,600, 2023: $11,969, 2024: $12,110, 2025: $11,374, 2026: $13,095.
- At most 3 MNQ open at once (average 0.8). Check your broker's overnight
  margin per MNQ (it changes with volatility) and keep enough on top to sit through a fall at least twice the worst one above.

All three are "buy the Nasdaq dip" bots, so they depend on the same market.
Adding your style of bots (daily FVG, noise band, overnight drift, all grade C)
gave about $17,400 a year with a worst fall of about $8,900 over the same years
(Sharpe 1.92). Higher, but those three are not proven.

## What this says about your bot types

- **Daily FVG (your PA Lab bot):** better on this data than on Dukascopy's. On NQ it
  made money in 2011–21 (+$284/yr per MNQ) and in all 5 later years
  (+$1,637/yr); your lab setting (3R, 96h) made +$2,776/yr after 2022. On ES it was
  flat. Grade C: real enough to paper trade, not proven.
- **Noise band:** worked in 2022–Jul 2024, flat since Aug 2024, flat on ES. The paper's
  results do not hold up on futures after costs, which matches the independent
  replications the research found.
- **Opening range breakout:** lost money on NQ in 2011–21 and made money after 2022
  (grade C); lost on ES in both. **VWAP trend, gap, volatility breakout, intraday
  momentum:** none survived costs on futures. Independent costed tests online
  found the same.
- **What did work:** buying sharp one-day dips in the Nasdaq at the close (IBS,
  lower band, Turnaround Tuesday) and holding the overnight session.

## Files

- `futures/` — data loader, contract engine, the 12 bots, runner, portfolio, this report.
- `tradingview/futures/` — Pine Script v6 for all 12; `tradingview/index.html` is the copy page.
- `results/futures/` — every number and every trade list.
- `research_notes/Round 3 intraday futures/` — the research behind the rules.
