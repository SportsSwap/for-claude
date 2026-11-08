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
