# First Candle Rule (the_quant_room video) - declared before looking (draft, outside the project)
Market: Nasdaq-100 minutes (NQ/MNQ stand-in), day session, New York time. ES checked the same way.
1. First candle: the 5-minute candle 09:30-09:35 (= the first five 1-minute bars). Its high and low
   are the only levels for the day.
2. From 09:35 on 1-minute bars, one setup a day, entries allowed until 12:00.
3. Break with a gap: a 3-candle fair value gap that forms as price breaks the level. Short: bars
   (a, b, c) with high[c] < low[a] and close[c] below the first-candle low. Long mirrored (low[c] >
   high[a], close[c] above the high). The first such gap of the day sets the direction; the gap is
   the zone between high[c] and low[a] (short).
4. Retest: a later bar trades back into the gap (short: high >= high[c]).
5. Engulfing: on or after the retest bar, a bar in the trade's direction whose body engulfs the
   previous bar's body, the previous bar being the opposite colour (short: prev close > prev open,
   close < open, open >= prev close, close <= prev open). Enter at its close.
   The setup is cancelled if, before entry, a bar closes beyond the far side of the gap (short:
   close > low[a]) or 12:00 passes.
6. Stop: 1 tick beyond the extreme of the engulfing bar and the bar before it (short: max of the two
   highs). Target: 3 x risk. Otherwise out at 15:55. Stops/targets checked on 1-minute bars, stop
   first if a bar touches both.
Costs per NQ contract: $4 commission + 1 tick slippage each side.
Periods: 2013-Sep 2021 / 2022-Jul 2024 / Aug 2024-Nov 2026 (logged unlock). Null: the same entries
with random directions (same stop distance, same 3R target), 1,000 sets.
It "works" if it makes money after costs in all three periods and beats random directions (p<0.05).
