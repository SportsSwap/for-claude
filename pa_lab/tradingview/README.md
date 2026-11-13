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
