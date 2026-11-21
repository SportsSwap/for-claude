# The two survivors, for TradingView

Both strategies survived the lab's sealed final test (2024-08-01 to
2026-11-06) on Dukascopy CFD data, then failed a backward check on
2013-2021 (table below). Regenerate with `python scripts/make_pine.py`.

| File | Chart | What it does |
|---|---|---|
| `palab_breakout_15m.pine` | NQ1! or ES1!, 15 minutes | Levels from 3 swing points (strength 3) within 0.25 ATR. Enters at the close of the first 15m bar that closes through a level, long or short, only when the bar closes 08:00-16:00 New York. Stop beyond the last swing plus 0.1 ATR, target 1R, out after 96 bars. |
| `palab_daily_fvg_1h.pine` | NQ1! or ES1!, 1 hour | At each daily close (17:00 ET), a three-day fair value gap of at least 0.1 daily ATR gets a limit order at the gap's near edge, long under price or short above. Stop beyond the far edge plus 0.1 ATR, target 3R. The order lives, and a trade is closed after, 96 hourly bars. Gaps formed on CPI, jobs-report or FOMC days are skipped. |

## How to use

1. In TradingView open a chart of `NQ1!` (or `ES1!`) on the right timeframe.
2. Open the Pine Editor, paste the file, click **Add to chart**.
3. Read the **Strategy Tester** tab. Then paper trade it: TradingView's paper
   trading account, one contract, for at least a few weeks.

## What the lab measured (one contract, after costs)

| Version | Window | NQ | ES |
|---|---|---|---|
| Breakout 15m | 2022-01 to 2024-07 | 1,086 trades, +$160,561, Sharpe 1.27 | 1,067 trades, +$43,873, Sharpe 0.58 |
| Breakout 15m | 2024-08 to 2026-11 (sealed) | 941 trades, +$112,064, Sharpe 0.72 | 993 trades, +$45,704, Sharpe 0.59 |
| Daily FVG, 1h | 2022-01 to 2024-07 | 59 trades, +$73,394, Sharpe 1.13 | 60 trades, +$13,726, Sharpe 0.40 |
| Daily FVG, 1h | 2024-08 to 2026-11 (sealed) | 50 trades, +$100,990, Sharpe 1.01 | 49 trades, +$39,679, Sharpe 0.84 |
| Breakout 15m | 2013-01 to 2021-09 (backward check) | 3,383 trades, +$34,344, Sharpe 0.17 | 3,290 trades, -$65,028, Sharpe -0.51 |
| Daily FVG, 1h | 2013-01 to 2021-09 (backward check) | 175 trades, +$8,574, Sharpe 0.09 | 165 trades, +$6,710, Sharpe 0.12 |

**Both failed the backward check** (decisions.md D48-D50): unchanged rules on
2013-2021, years the lab never used, needed NQ Sharpe 0.5 or more with ES
profitable. Both lost money in most years before 2018. Dukascopy's data for
2013 and 2015-2017 is incomplete (shorter trading day or missing sessions),
which may explain part of it, but 2014 has full data and lost too.

TradingView's numbers will differ: it uses CME futures (the lab used CFD
prices), fills on chart bars instead of 1-minute bars, and does not always
assume the stop came first in a bar that touched both. Expect similar trade
counts and the same sign, not the same dollars. Most of the profit sits in
single years (breakout ES: 2025; FVG: 2026), so a few flat or losing months
are normal and a sustained loss means stop.

Not financial advice. A Sharpe of 0.6 to 1.0 is a modest edge, on CFD data,
from a search over thousands of versions. Paper trade first.

## Noise band, any symbol (`palab_noise_band.pine`)

The rules from the post the user shared. Works on any symbol on a minute
chart of 30 minutes or less (5 minutes recommended); set the session in the
settings if it is not a US stock or ETF (default 9:30-16:00 New York). Version menu: "As written" or "Best from 2013-2021". The lab tested
it on 2013-2026 with Nasdaq-100 minutes (decisions.md D64-D67):

| Version | 2013-Sep 2021 | 2022-Jul 2024 | Aug 2024-Nov 2026 | Worst drop |
|---|---|---|---|---|
| As written, QQQ shares | +7.7% | +36.7% | +12.6% | 11.8% |
| Best from 2013-2021, QQQ shares | +30.4% | +21.0% | +8.7% | 8.4% |

Simple sums of each trade's QQQ move, no leverage. The call/put direction is
real (it beats random directions in every test), but buying 1-3 day options
on it lost money in most years in the lab's Black-Scholes estimate, because
time decay and the spread cost more than the average move pays.

On the S&P 500 (SPY stand-in) the same rules did not work: as written -18.3% /
+15.9% / -3.9%, best from 2013-2021 -2.9% / +9.9% / -0.2% (D69-D71). All figures
use the corrected 15:45 exit (D70). Other symbols
are untested.

On futures (NQ1!, MNQ1!, ES1!) the script trades a fixed number of contracts
(setting "Contracts per trade on futures", default 1): 100% of equity buys less
than one NQ contract and TradingView rounds the order to zero. Set Properties >
Commission to about $2 a contract (NQ) or $0.50 (MNQ) for futures.
