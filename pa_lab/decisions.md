# Decisions

Every decision and its reason, in the order made. Threshold changes are not
logged here: they go in `amendments.md` as numbered amendments, written before
any result they touch is looked at.

## Prompt 1: data and dials

D1. **Project layout.** The lab lives in `pa_lab/` inside this repo, in its own
`.venv`. Raw, clean and sealed bars are git-ignored (size and the seal);
result files, the rulebook, the news calendar and the ledgers are committed.

D2. **Master seed = 20220103**, the first discovery session. Every random draw
uses `lab.seed.rng(name)`, which derives a child stream from the master seed
and a name, so adding a consumer never shifts another's draws.

D3. **Locks.** `config/thresholds.json` and `rulebook_spec.json` are pinned by
sha256 in `config/amendments.json`. `config.thresholds()` refuses to load a
changed file until `python -m lab.amend "<reason>"` records an amendment. Every
result file carries the amendment number and the locked hashes.

D4. **Session dating.** ET wall clock + 6 hours, date part. 18:00 ET opens the
next day's session; Sunday evening is Monday. Bars in the 17:00 hour are
dropped. CME's DST switch happens at 02:00 ET Sunday while the market is
closed, so no session spans a clock change.

D5. **Gaps.** A gap is the time between consecutive bar opens inside one
session. "> 1 min" means at least one minute missing. Counted at >1, >5 and
>60 minutes; never filled. Higher charts carry `n_1m` so partial bars stay visible.

D6. **Cleaning** (counted in each audit file): drop exact and conflicting
duplicate timestamps (keep the first), sort, drop halt-hour bars, drop bars
dated on a weekend session, drop bars with impossible OHLC. Zero-volume bars
are kept and counted.

D7. **Audit pass rules** (in thresholds.json): zero conflicting duplicates,
zero invalid OHLC, contract id changes only at a roll and to the named
contract, adjusted minus unadjusted constant across O/H/L/C and stepping only
at the first bar at or after a roll by the roll's spread (0.01 pt tolerance),
no weekend sessions after cleaning, every window non-empty, NQ and ES hold the
same sessions. Gaps and zero volume are reported, never failed. A failed audit
stops the lab; fixing it is a human call recorded as an amendment.

D8. **Back-adjustment sign.** Only `|step| = |spread|` is checked, since data
vendors differ on the sign convention of `spread`.

D9. **Final-window detail stays sealed.** The audit's counts and lists for the
final window go to `data/sealed/audit_final.json`; the public audit files hold
only warm-up/discovery counts plus a pass/fail verdict for the whole file.
Session counts per window (including the final window) are written by the
ingest at write time; they are counts, not prices.

D10. **The guard.** `lab/io.py` is the only reader/writer; a test fails if any
other module calls a pandas/pyarrow reader. Every read checks the path
(`data/sealed/`) and every frame's sessions (any `session` or `ts_event`
column dated on or after the final-window start). An unlock needs both
`with guard.unlock("<step>")` and `LAB_UNLOCK=<step>` in the environment.
Steps: `ingest`, `final_test`. Every unlock, relock and guarded read under it
goes to `results/sealed_access_log.jsonl`. Only `ingest` writes `data/sealed/`,
each file once, then chmod read-only. The raw folder holds final-window bars,
so the ingest reads it under its own logged unlock.

D11. **Windows.** If the data starts within a week of 2021-10-01 and reaches
2024-08-01, the stated windows are used with the final window ending at the
last session. Otherwise the shape is kept: 3-month warm-up, 30-month discovery
split 12 months / rest into two eras, final window = the last ~2 years from
the first of the month. Data before the warm-up is dropped.

D12. **Charts.** Buckets are counted from each session's 18:00 ET open (UTC
offsets of 5/15/60 min align with the ET wall clock). 4h buckets use ET
wall-clock starts 18, 22, 02, 06, 10, 14 (last one 3 hours). `ts_avail` is the
nominal bucket end (the session close for daily), never the last seen 1m bar,
so a bar with missing minutes is still not usable early.

D13. **ATR.** Wilder, 14 bars, seeded with the mean of the first 14 true
ranges. The `atr` column on bar i uses bars up to i-1 only. The ATR runs
continuously across sessions on back-adjusted prices.

D14. **Rolls.** `roll_no_entry` on any bar opening within 60 minutes before
the next roll; `roll_force_exit` on the last bar opening before the roll (exit
at its close).

D15. **News calendar.** FOMC from federalreserve.gov (decision day = last day
of a scheduled meeting; notation votes skipped; 14:00 ET). CPI and jobs
reports from the BLS release archives (08:30 ET). BLS refuses anonymous
automated clients, and the lab will not fake a browser or use anyone's contact
details without being told to, so CPI/NFP ship hand-seeded and marked
`verified=False` until `LAB_HTTP_CONTACT="name email" python -m lab.news build`
runs. `load_calendar()` refuses unverified rows by default.

D16. **Dials.** Values in `lab/dials.py`, written to `rulebook_spec.json` and
`rulebook.md`. Where the prompt left a choice open:
- `direction` = long / short / both.
- `swing_strength` is a shared detector dial for every setup: every setup
  needs swings for its stop, next-swing target or CHoCH exit.
- Own dials added where the prompt names none: flip-zone retest window
  (6/12/24/48 bars), sweep depth (0.25/0.5/1 ATR) and reclaim bars (1/2/3),
  trend-line event (bounce/break), fresh-zone-only, FVG minimum gap
  (0/0.1/0.25 ATR) and FVG age (24/96 bars).
- Trend lines need 2-4 touches with a 0.1/0.25/0.5 ATR tolerance.
- Choppy day = prior session |close-open| < 30% of its range. Run = 3 or 5
  daily closes in the same direction. Pullback depth: shallow < 50% of the
  last impulse leg, deep 50-100%.
- Session windows: London+NY 03:00-16:00 ET.

D17. **Exclusions.** X1-X9 in `rulebook.md`. Each depends only on (setup,
setup chart, trigger chart), so the count is an exact product per context;
a test checks it against brute-force enumeration with an independent check.

D18. **The count is 592,111,296,000, not 20,265,402,866,688.** The prompt
does not list every setup's own dials or every exclusion, so the reference
count cannot be reproduced exactly. Dials were not padded to hit the number.
The later prompts sample from the space (40,000 spread versions, a 14k grid,
~47k sampled), which works the same at either size.

D19. **Synthetic data** (`scripts/make_synthetic.py`) proves the pipeline end
to end until the real files arrive: a log random walk per market, quarterly
rolls at the Wednesday 18:00 ET open before the 2nd-Thursday-before-expiry
session, Panama back-adjustment, and injected defects (gaps, holes,
duplicates, halt-hour bars, zero volume, swapped rows). Contract ids end in
`SYN`. It caught one bug in itself: a halt-hour copy was given the wrong
adjustment offset, and the audit flagged the step.

## Prompt 2: engine and behavior tests

D20. **Engine** (`lab/engine.py`, one numba kernel). Fills and exits on 1m
bars only. Market entry = close of the decision bar + 1 tick. Limits fill
only when a bar trades 1 tick through, at the limit price. Targets the same.
Hard stops at stop - 1 tick, or open - 1 tick on a gap. Close-based stops at
the first trigger-bar close beyond the stop - 1 tick. Structure (CHoCH)
exits at the 1m close - 1 tick. Time and roll exits at the close, no
slippage. Stop and target in one bar: the stop. On a limit's fill bar only
the stop can trigger (ambiguous, so a loss). $4 per round trip; half size
halves contracts and commission. P&L is booked on the exit session; the daily
series covers every discovery session with zeros. Sharpe = mean/sd x sqrt(252).

D21. **Lab defaults the prompt leaves open:** a limit back at the level lives
12 trigger bars and is cancelled if the stop trades first. Break setups allow
a retest confirmation within 12 setup bars. A trend-pullback zone is armed
50 setup bars. Levels live 500 setup bars after their last swing; zones 500;
trend lines 300. An episode ends when a trigger bar closes 0.25 ATR through
the band. ltf_bos must arrive within 3 trigger bars of the touch. flat_1600
versions take no entries after 16:00. A version's next-swing target needs
at least 1R or the signal is skipped.

D22. **Confirmation 'none' with a limit entry** rests a limit at the band from
the moment the object is known until the object expires. With a market entry
it enters at the close of the touching trigger bar, and for break setups at
the break bar's close.

D23. **Look-ahead bug found and fixed.** pandas 3 stores timestamps in
microseconds; the market cache assumed nanoseconds, so the "last setup bar
closed by the decision" was looked up 16.7 hours late. The cut-at-a-random-bar
test caught it; all timestamps now go through `.dt.as_unit("ns")`, and a
regression test pins one minute = 60e9 ns.

D24. **Random entries (engine check):** 20,000 per market, random direction,
1 ATR (5m) stop, 2R target, each trade independent. Synthetic NQ:
-$23.70 a trade (about -0.07R), ES -$38.09. Losing a little is right: the
costs and the conservative fill rules on a driftless walk. The reference lab
got -$9.80 on real NQ; the synthetic walk's volatility differs.

D25. **The cheat** (`scripts/cheat_peek60.py`, a copy of the random-entry
script choosing direction from the close 60 minutes ahead) made +$336.07 a
trade on NQ and +$126.48 on ES, then was deleted in the same command. Its
results stay in `results/engine/cheat_peek60*.`

D26. **Behavior tests**: swing strength 3, level tolerance 0.25 ATR, levels
from every swing (min touches 1). Touches are episodes on the same chart.
Verdict: *true* when NQ pooled points the claimed way with a 95% interval
excluding zero, ES pooled has the same sign and both NQ eras have the same
sign; *split* when NQ pooled holds but ES or an era does not; *false* when NQ
pooled does not. The claim for every test is the folk rule (sign +1); the
metric is always A minus B, defined per test in `lab/behavior.py`.

D27. **Stand-ins sit on the tick grid.** The first run on synthetic data
said "real levels hold more than random lines" (+0.45 points of hold rate on
NQ, +1.6 on ES). On a random walk that cannot be behavior. The cause: real
levels are swing prices, which lie on the tick grid, so a bar that just tags
the level counts as a touch, while a shifted line at an off-grid price needs
a deeper poke. Shifts are now rounded to whole ticks; the effect vanishes
(NQ +0.12 [-0.16, +0.43] points). Found on synthetic data before any real
data existed, so this is a bug fix in the stand-in, not a moved threshold.
On real data, this artifact alone would have produced a false "levels work".

D28. **Speed.** Detectors and setup objects are cached per (market, chart,
dials that matter); a cached version runs in 4-90 ms on 2.5 years of 1m data.

D29. **Box equals line at one touch.** A level made of a single swing has
lo = hi, so `level_shape` = box and line give identical versions whenever
`level_min_touches` = 1. The behavior test `line_vs_box` therefore uses
2-touch levels (its first run compared identical sets and returned exactly
0). In the rulebook these pairs are duplicates; the count (D18) is left as
locked, and the funnel treats them as one version when sampling (logged in
its notes).

D30. **Gap-fill stand-in matches distance.** With the prompt's 1-3 ATR shifted
bands, `fvg_fill` said "true" on the random walk (+21.7 points: 89% of gaps
filled within 50 bars against 68% of random bands), uniformly on every chart
and both markets. A new gap sits right behind price while the stand-in sits
1-3 ATR away, so the test measured distance. The fill stand-in is now the gap
mirrored across the formation close (same size, same distance, other side).
`fvg_hold` keeps the prompt's shifted bands. Found on synthetic data.

D31. **False positives on noise, kept as found.** On the synthetic random walk
`rejection_at_levels` came out *true* (NQ +0.041 ATR [+0.013, +0.071], ES
+0.004) and `engulfing_at_levels` *split*. Both are NQ-only, driven by the
15m chart, with per-chart signs flipping, which is what 23 tests on noise
produce by chance. The verdict rule asks ES only for the same sign, so an ES
effect of zero can confirm. The rule is the prompt's and stays; read any
"true" on real data with this base rate in mind.

D32. **Box against line is a difference of differences.** After D29 the test
said "true" on the random walk (+4.3 points): a touch is scored against the
band's far edge, so a wider band is harder to close through by construction.
The metric is now (real box - random box) - (real line - random line), which
cancels the width. Found on synthetic data.

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

P3-14. **What the twin stage can and cannot do.** The twin test asks whether a
version beat random entries with the same shape. A version that reached
stage 4 was already picked for a high net from many versions, so on pure noise
it still beats fresh random twins most of the time: in a small dry run on the
synthetic random walk, 31 of 52 stage-3 survivors passed stage 4 and 6 of 356
graded versions became candidates. That is selection luck, not edge, and the
funnel cannot remove it; only the sealed final window (Prompt 4) can. Nothing
was tuned in response; the thresholds stay as fixed in stages.json.

P3-15. **versions.jsonl** carries, per version, the id, set, name (named only),
the NQ signal count used for the 40-signal rule (`nq_signals`, a construction
input, not a result), the `graded` flag, and every dial. Its sha256 is in
`versions.sha256` and in `selection_manifest.json`.

P3-16. **How close the spread set got** (`results/funnel/spread_shares.csv`). Mean
absolute gap between a dial value's share and its target: 0.021 for the spread
set against 0.026 for unfiltered random draws of the same size. Where the
40-signal rule bites hardest (BOS, CHoCH, trend pullback: 20-26% of draws
reach 40 signals, 211-240 eligible for 140 places), slow charts rarely qualify,
so chart-pair shares cannot reach 1/13 and the worst single gap is larger than
random's (0.21 vs 0.08 for BOS). That is the rule working as written: the set
can only spread across versions that trade enough.

## Prompt 4: the final test


P4-1. **One code path.** `lab.final_test.run(source)` runs both the rehearsal
and the real test. `source` changes only where bars come from
(`load_frames`) and where results go (`results/final_rehearsal/` or
`results/final/`). Everything else, from complete-session filtering and
market build to versions, engine, costs and tables, is shared.

P4-2. **Pre-flight before any unlock.** It checks the lock ledger
(`verify_locks`), every file named in `results/funnel/selection_manifest.json`
(versions, stages, candidates, working setups, named versions), and
`versions.jsonl` against `versions.sha256`. Any difference stops the run
before the guard is touched.

P4-3. **Runs once.** The real run refuses when `results/final/` holds anything
or when the access log already shows a `final_test` unlock. It also needs a
`REHEARSAL_OK.json` whose selection hashes match the current ones, so a
rehearsal must have passed on exactly these selections.

P4-4. **One unlock.** Inside one `guard.unlock("final_test")` (also needs
`LAB_UNLOCK=final_test`), the run reads `data/sealed/MANIFEST.json`, checks
every sealed file's sha256 against it (stopping if any differs), and reads
both markets' sealed bars and rolls. Then it relocks. All computing happens
after the relock. The guard logs the open, the reads and the close.

P4-5. **Warm-up.** Discovery bars from the first of the month three months
before the final window (2024-05-01 for a 2024-08-01 start) warm the
detectors. Sessions before the window are not traded: Market tradable =
window sessions only, and era = calendar year.

P4-6. **Complete sessions.** A session is kept only if it has a bar opening at
15:59 ET or later. A dropped session becomes an extra roll at its first bar's
time: open positions close at the last bar before it, and the usual 60-minute
no-entry rule applies. That hour is usually the 17:00 halt, so in practice
only the forced exit bites. Dropped sessions are listed in `summary.json`.

P4-7. **Rehearsal.** The last month of discovery (2024-07-01 to 2024-07-31),
with its own three-month warm-up, prices shifted up by 1,000 points (a whole
number of ticks), run on a seeded subset: named versions plus an even spread
across setups (60 by default). Any version error fails the rehearsal.

P4-8. **Held up.** A version holds on a market when its net is above zero after
costs and its Sharpe is at least 0.5 over that market's final window. A setup
on a chart holds when the equal-weight average daily P&L of its versions made
money in every calendar year of the window and its Sharpe is at least 0.5.

P4-9. **Matched random trades for working setups.** Up to 40 of the setup's
versions are drawn (seeded) and their final-window trades pooled, capped at
3,000 trades. Each trade gets a twin with the same direction, a random entry
minute in the same 30 minutes of the day (window sessions, outside roll
blackouts), the same stop and target distances in 5m ATR, the same holding
time and the same engine costs. There are 1,000 twin sets (the funnel uses
10,000; 1,000 keeps the run inside an hour). The setup beats random when fewer
than 5% of sets make at least as much. Twins enter at market, so a
limit-entry trade's twin pays one tick of entry slippage the real trade did
not.

P4-10. **Best usual-settings version.** For each setup, the `set == "common"`
version with the best NQ discovery Sharpe in `results/funnel/metrics_NQ.parquet`
(ties broken on net), reported on both markets.

P4-11. **Dials in common.** For every dial value: its share among the versions
that held on a market, its share among all versions, and the lift (held / all).

P4-12. **Saved results.** `metrics_{NQ,ES}.parquet` (every version: trades, net,
per trade, win rate, avg R, Sharpe, net per year, held, candidate, error) and
`daily/{market}/{setup}.parquet` (id, day, pnl; non-zero days only, float32)
plus the tables. `DONE.json` holds the sha256 of every result file. Dates use
a column named `day`: the guard treats `session` / `ts_event` columns dated
in the final window as sealed market data.

P4-13. **Later analyses** call `lab.final_test.load_final_results()`. It reads
only `results/final/` and checks each file against `DONE.json` first.

P4-14. **Parallel run.** Versions are sorted by setup and chart, then run in
chunks of 150 on a fork pool (one worker per core) that shares the
already-built markets. Each chunk clears the strategy cache to bound memory.

## Prompt 5: the dashboard

P5-1. **Inputs.** The builder reads only `<LAB_ROOT>/results/`. `Provenance.path()` refuses any
path outside it or under `data/`; a test spies on every path the build opens.

P5-2. **Provenance.** Every number on screen is created by `Provenance.json/cell/count`, which
records file, row, column, format, value and the text shown in `provenance.json`. Before
anything is written, `verify()` re-reads every value with a second reader on a different code
path (CSV: `csv.DictReader` vs pandas with string dtype; JSON: `json` with Decimal floats;
parquet: `pyarrow` vs pandas) and refuses on any difference in value or text. Counts are a
recorded operation (`count where verdict = false`), recomputed by the second reader.

P5-3. **Unsourced digits.** Every visible string on every page, and every text node in the final
HTML (scripts and styles excluded), must have its digits covered by a recorded text or one of
these fixed labels: chart names `1m 5m 15m 1h 4h`, test horizons `10/20/50 bars`, `95% interval`,
era names `2022` and `2023-24`. The amber card badges (1, 2, 3...) are ordinals and are skipped
by element class `badge-n`. The page counter `N / M` is drawn by script at run time.

P5-4. **Formats.** Dollars `-$23.70`; rates `32.4%`; differences of rates in percentage points
`+0.1 pp` (not "pts", which reads as index points); behaviour moves `+0.03 ATR`. Minus is a
plain hyphen. No em or en dashes anywhere; the build refuses one.

P5-5. **Verdicts.** `true / split / false` map to the badges `survived / split / didn't survive`.
Verdict values are compared case-insensitively because `verdicts.csv` was seen holding both
`false` and `False`.

P5-6. **Layout.** 1920x1080 stage scaled to the window. Findings: chart at x 96-1276, y 330-990;
stats and conclusion at x 1340-1824, y 330-702, so the facecam corner (x 1400-1920, y 712-1080)
stays empty. `check_layout.js` (headless Chromium via Node Playwright; the Python package is not
installed) checks every page at 1920x1080 and 1280x720 for anything off stage, anything in the
corner, text overflow, a wrapped subtitle and page scrolling, screenshots every page at
1920x1080, and `check_layout.py` confirms screenshot count and titles match `pages.json`.

P5-7. **Pending pages.** Funnel and final pages name the files and columns they expect in
`dashboard/pages.py` (`FUNNEL_PAGES`, `FINAL_PAGES`). Until those exist the page is listed in
`pending.json`, not drawn. If prompts 3 and 4 write different names, edit those specs.

P5-8. **Synthetic label.** When `LAB_ROOT` is `synthetic_lab`, every eyebrow carries
"SYNTHETIC DATA DEMO" and the title slide carries a banner saying real files are not yet ingested.

P5-9. **Funnel and final pages read the files as written** (main session).
Stage counts are recorded counts over `funnel/funnel.parquet` (stages are
cumulative); stage thresholds in labels come from `funnel/stages.json`;
rule-effect labels name the baseline ("news: skip to trade"). R-multiple
targets (2R, 3R) are dial names on the fixed-label list.

P5-10. **Digit scan tightened** (main session). A sourced number now covers
only itself, never part of a longer number: before, a sourced "0" turned
"50 bars" into "5 bars" and any sourced "5" would have approved every 5 on
the page. The second reader treats an empty CSV cell as a missing number,
as the first reader does.

## After the first full synthetic run

D33. **The first synthetic generator had a flaw the funnel found.** On the v1
random walk, candidates held up in the sealed window twice as often as
other versions (NQ 36% against 18%; non-candidates with similar trade counts
21%, about 3 sd apart), and change of character on NQ 1h "beat random
trades". A look-ahead leak would survive removing the wicks; it did not. On
fresh v1 paths the 72 candidates made +0.5 and +2.1 gross points a trade
with wicks and -4.0 and -2.7 with high = max(open, close), low = min(open,
close). Cause: v1 drew each 1m wick as noise independent of where price went
next, so targets and limits filled on a wick harvested free noise while
close-based stops ignored it. Candidates leaned that way: 64% close-based
stops (27% overall) and 62% limit entries (42%). Generator v2 builds each
minute from 8 steps of one random-walk path, so a wick is price that really
traded; on fresh v2 paths the same candidates make -1.4 and -2.4 gross points
a trade (19-26 of 72 positive). Real data has no such flaw, but the
close-stop / wick-target asymmetry is worth watching on it.

D34. **Pooled twins share an entry minute.** The final test pools up to 40
versions of a working setup; versions often take the same trade. Twins were
drawn per trade, so 40 copies of one trade counted as 40 independent draws
and the pooled p-value was too confident. Twins are now drawn per distinct
(entry minute, side) and shared. Fixed before any real seal was opened; the
v1 synthetic final run used the old method.

D35. **The synthetic lab is rebuilt on generator v2** and every prompt rerun
on it (`--wick-model noise` rebuilds v1). The v1 results stay in git
history at the commit before the rebuild.

D36. **Final-page verdicts rest on a test, not a bigger bar.** The first deck
called candidates "survived" whenever their held-up share beat the overall
share (17.9% against 14.5% from 28 candidates on v2). `scripts/analyze_final.py`
now reads only saved results and writes `results/analysis/final_summary.json`:
a one-sided binomial test of the candidates' held count against the
all-versions share per market (survived only when NQ p < 0.05 and ES points
the same way), and a tally of working setups against random trades on the
market where each worked in discovery (all = survived, some = split, none =
didn't survive). The deck takes its badges from that file.

D37. **Synthetic lab v2 results** (scale 0.035, 4,953 versions): all 23
behavior tests false; random entries -$25.12 a trade on ES and +$0.03 on NQ
(+0.20 +/- 0.21 points before commission, within noise of the expected small
loss); the cheat +$307.68 a trade on NQ; 28 candidates; NQ candidates held up
5 of 28 (17.9%) against 14.5% of all versions (p = 0.38); 1 of 4 working
setups beat random trades on its own market (trend pullback NQ 4h, p = 0.02).
That is what a random walk should give, up to chance.

D38. **News calendar verified from bls.gov.** Fetched with the user's name and
email in the User-Agent, as BLS asks of automated clients (the user approved
this). CPI and jobs-report dates now come from the BLS release archives (224
CPI and 226 jobs releases since 2008; 60 of each between 2021-10-01 and
2026-10-16), FOMC from the Fed. All 96 hand-seeded dates matched. The
archives also carry the 2025 shutdown delays (CPI 2025-10-24, jobs
2025-11-20 and 2026-02-11). `Market.load` now requires verified dates; an
unverified row stops the lab. The synthetic results already committed used
the hand-seeded dates, identical through their last seeded date (Sep 2025).

## Real data, free source

D39. **Dukascopy index CFDs stand in for NQ and ES futures** because the user
chose not to pay for CME data. NQ <- USATECHIDXUSD (Nasdaq 100 CFD), ES <-
USA500IDXUSD (S&P 500 CFD), 1-minute bid candles from datafeed.dukascopy.com (`scripts/fetch_dukascopy.py`,
generic User-Agent, one kept-alive connection, one request a second, five-minute
cool-downs). Dukascopy rate-limits hard (about 5 files a minute sustained), so
bid only halves the ~6,400 daily files; the CFD bid-ask spread is about a point,
negligible at 1-minute scale (`--mid` averages bid and ask). HistData.com was
considered and rejected: its download needs a script-made token. What differs from the prompt's inputs:
- prices are the CFD's, not the futures'; levels differ by the basis but
  moves in points are close, so the NQ/ES point values ($20/$50) and tick
  (0.25) still turn points into dollars;
- volume is tick volume, not contracts (only the audit's zero-volume count
  uses it);
- no contract rolls, so the rolls files are empty, the roll blackout never
  fires, and there is no unadjusted file or adjustment-step audit;
- the CFD trades 18:00-16:15 ET (1,335 minutes a session), not to 17:00, so
  the last 45 minutes of each futures session are missing; nominal chart
  times are unchanged and the final test's complete-session rule (a bar at
  15:59 or later) still holds.
Every result on this data says "CFD stand-in" in its decisions and the deck.
The stated windows apply: warm-up from 2021-10-01, discovery 2022-01-03 to
2024-07-31, final window 2024-08-01 to the last session fetched (2026-11-06).

D40. **Real-data discovery results (CFD stand-ins), before the final test.**
Funnel at the same scale as the synthetic run (4,886 graded versions):
4,462 with 30+ trades, 1,200 profitable after costs, 410 with Sharpe >= 0.5,
210 beat matched random trades, 53 candidates. Unlike the v1 synthetic run,
candidates lean toward hard stops (83% vs 73% overall), not the close-based
stops a wick artifact would favour. Candidates cluster on slow charts (fair
value gap daily 11, 4h 8). Setups that work as a whole: three, all on ES
(fair value gap 4h and daily, breakout daily). Slow-chart winners from a
2022 bear and a 2023-24 bull can be riding the trend; the sealed window is
what separates that from an edge. Named systems: none became a candidate.
The deck banner no longer cites "D39": the digit scan correctly refused an
unsourced number in my own label.
