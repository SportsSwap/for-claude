## Prompt 3: the funnel

P3-1. **Random-draw targets.** "As often as random draws would give it" is read as:
pick one of the 13 chart pairs uniformly, then every dial uniformly from the
values valid in that context. The target share of each dial value is the
average over pairs of 1/(number of valid values), zero where the value is
excluded (e.g. `gap_middle` outside FVG). Pairs target 1/13 each.

P3-2. **Greedy spread fill with the 40-signal rule.** Uniform random draws are
counted for NQ discovery signals first (`strategy.signals`, no P&L), in rounds
until each setup has at least 1.5x its quota of eligible (>= 40 signal)
versions or 8 rounds pass. The greedy fill then draws 400 unused eligible
candidates at a time and adds the one that minimises the sum of squared gaps
between dial shares and targets. Counting signals is part of building the set,
not a result, so it happens before versions.jsonl is hashed; no P&L is
computed until `run`, which refuses to start if either hash changed.

P3-3. **No duplicates** use a canonical key over the dials. For level setups
with `level_min_touches == 1`, box and line are the same version (a one-swing
level has lo == hi), so the key maps box to line (main session D29). The
version is stored as drawn.

P3-4. **Common set.** Usual settings (swing 3, both directions, trigger = setup
chart, daily triggers on 1h, hard stop 0.1 ATR beyond the reference, hold,
96-bar time exit, no filters) on all six charts, crossed with:
- entries: touch setups take a resting limit at the level, a close back, or
  an engulfing/rejection candle (`either_candle`) entered at the close; break
  setups (breakout, BOS, CHoCH, sweep, trend-line break) take the break close
  or a limit back at the level;
- stops beyond the level or beyond the last swing;
- targets 1R, 2R, 3R and the next swing;
- no filter, or exactly one of: trend agrees (setup chart), New York
  08:00-16:00, skip news days;
- main variants: level setups 2 or 3 touches x line or box (flip zone: 2 or 3
  touches x retest within 12 or 24 bars), trend line bounce or break x 2 or 3
  touches, sweep depth 0.25 or 0.5 ATR x reclaim in 1 or 2 bars, zones of 2-
  or 3-candle runs x fresh or not, gaps of at least 0.1 or 0.25 ATR x 24 or 96
  bars of age; trend pullback, BOS and CHoCH have no variants.
That gives 15,552 versions (reference lab: 14,016). Every common and named
version is run; the funnel's stage 1 (30 trades) does the screening.

P3-5. **Named versions.** Lab defaults are `funnel.USUAL` for anything left out.
- Bare Minimum: level bounce on 15m, 2-touch line, resting limit at the level,
  stop 0.1 ATR beyond, 2R, no confirmation, no filters.
- Daily Version: daily levels traded from 1h, close back, stop 0.25 ATR beyond
  the level, target the next swing, daily trend agrees.
- Checklist: trend pullback on 1h, 15m trigger, engulfing or rejection candle,
  4h trend agrees, New York hours, no news days, stop beyond the last swing, 2R.
- Sweep System: sweep and reclaim on 15m, 5m trigger confirmed by a 1m break
  of structure, stop beyond the sweep wick, next-swing target, New York open
  09:30-11:00, no news days.
- Zone System: fresh 3-candle supply/demand zones on 1h, resting limit at the
  zone edge, stop 0.1 ATR beyond the zone, 3R, 4h trend agrees.
- Entry Model: fair value gap on 5m with a 1m trigger, resting limit at the
  gap edge, stop at the far end of the gap's middle candle (no buffer), 2R,
  New York open, 15m trend agrees.

P3-6. **Sampled set.** Per setup, 40% no filter, 40% exactly one, 20% exactly two
(filters picked uniformly among those that apply in the context, each set to
a random non-off value), every other dial uniform over its valid values, no
duplicates. Only versions with >= 40 NQ discovery signals are graded and run.

P3-7. **Stages** are fixed in `stages.json` (hashed with versions.jsonl):
1) >= 30 NQ trades; 2) NQ net > 0 after costs; 3) NQ Sharpe >= 0.5;
4) fewer than 5% of 10,000 twin sets make at least the real net;
5) ES net > 0 and ES Sharpe >= 0.3. Candidate = 1-4, NQ net > 0 in both eras,
and 5. Sharpe = mean/std of daily P&L over every tradable discovery session,
zero days included, x sqrt(252).

P3-8. **Twins.** Each real trade gets 100 simulated twins: same direction, a
random entry minute (bar close) in the same 30 minutes of the ET day in a
tradable discovery session outside a roll blackout, stop and target at the
same distances in setup-chart ATR (as of that minute), the same holding time
as a time exit, the same size and costs (a limit-entry trade's twins get the
market-entry tick back). Each of the 10,000 sets picks one of the 100 twins per
trade at random; p = share of sets whose total >= the real net. Twins run only
for versions that pass stages 1-3, since stage 4 cannot change anything else.
A test plants a 60-minute peek (p < 0.05) and checks random directions give
spread-out p-values (one lucky seed of eight is allowed: an early fixed seed
happened to be +3.6 sd).

P3-9. **Judging a setup as a whole.** For each setup x setup chart x market, the
daily P&L of every graded version is summed per session and divided by the
number of graded versions (one contract each, equal weight; versions with no
exit that day count as zero). It works when net > 0 in each calendar year of
discovery (2022, 2023, Jan-Jul 2024), Sharpe >= 0.5, and net > 0 in era 1
(2022) and era 2 (2023-01-01 to 2024-07-31).

P3-10. **Rule effects.** In the common set, versions are paired when they differ
in one rule and match on everything else; the table reports the mean change
in NQ net and Sharpe, the share of pairs that improved, and the ES change,
against the alphabetically first value of that rule.

P3-11. **Scale-down, measured first.** A pilot of 600 uniform random draws on
4 workers (cores shared with two other forks) measured 0.43 s wall per NQ
signal count, 46% of draws reaching 40 signals, and 1.74 s wall per version
for the NQ + ES run with twins. The full counts would need about 130k signal
counts for the spread pool plus 47k for the sampled set (~21 h) and about
77k graded runs (~37 h). To finish in about 2 hours, the spread and sampled
sets are scaled uniformly to 3.5% (140 spread and 166 sampled per setup,
keeping 4,000:4,733 per setup, 10 setups, the greedy fill and the 40/40/20
filter mix). The common grid (15,552) is sampled by whole cells: 15% of its
486 setup x chart x variant x entry cells, each kept with all 32 of its
stop x target x filter versions, so rule-effect pairs stay intact. The six
named versions are all kept. On the real data, run
`run_funnel.py gen --scale 1 --common-cells 1` on a bigger machine; nothing
else changes.

P3-12. **Twin budget.** A version with 30,000 trades would need 3 million twin
simulations, so twins per trade = min(100, 200,000 / trades), never below 20
(`stage4_max_twin_sims_per_version`, `stage4_min_twins_per_trade` in
stages.json). Sets still number 10,000.

P3-13. **Signals for the common set** are not counted in `gen`: common and named
versions are graded in full and screened by stage 1; `nq_signals` is null
for common versions.
