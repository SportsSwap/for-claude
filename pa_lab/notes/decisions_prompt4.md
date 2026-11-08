# Decisions: prompt 4 (the final test)

To be merged into `decisions.md`.

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
