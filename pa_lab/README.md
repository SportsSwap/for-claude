# Price-action lab (NQ, ES)

Turns price-action trading rules into exact, testable rules on 1-minute NQ and
ES futures. Built in five prompts: data and dials, engine and behavior tests,
the funnel, the final test, the dashboard.

## Setup

```bash
cd pa_lab
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

## Prompt 1: data and dials

```bash
# put the vendor files in one folder: NQ/ES back-adjusted (+ optional unadjusted) and rolls
LAB_UNLOCK=ingest python -m lab.ingest --src /path/to/folder
LAB_HTTP_CONTACT="Your Name you@example.com" python -m lab.news build   # BLS needs a contact
python -m lab.dials                                                      # rulebook.md + spec
```

File names must contain `NQ` or `ES` as a word; `roll` marks the rolls file and
`unadj` the unadjusted file. Columns: `ts_event, open, high, low, close,
volume, contract` and `roll_time_utc, old_contract, new_contract, spread`.

Outputs: `data/raw/` + `MANIFEST.json`, `data/clean/` (warm-up and
discovery), `data/sealed/` + `MANIFEST.json` (final window, written once,
read-only), `data/windows.json`, `results/audit/`, `results/session_counts.csv`,
`results/sealed_access_log.jsonl`.

To prove the pipeline without real data:

```bash
python scripts/make_synthetic.py --out synthetic_input --defects
LAB_ROOT=/tmp/lab_demo LAB_UNLOCK=ingest python -m lab.ingest --src synthetic_input
```

## Prompt 2: engine and behavior tests

```bash
python scripts/random_entries.py        # 20,000 random entries per market (engine sanity)
python scripts/run_behavior.py          # 23 behavior tests -> results/behavior/
```

`lab/engine.py` fills on 1-minute bars with the prompt's costs; `lab/detectors.py`
and `lab/strategy.py` turn any rulebook version into orders;
`tests/test_lookahead.py` proves no detector or setup sees the future.

## Prompt 3: the funnel

```bash
python scripts/run_funnel.py gen        # version sets, hashed before anything runs
python scripts/run_funnel.py run        # every version on NQ and ES discovery
python scripts/run_funnel.py report     # funnel, twins, per-setup judgment, hashed selections
```

`--scale` shrinks the version sets uniformly when the machine is too small
(see `decisions.md` P3-11).

## Prompt 4: the final test (once, ever)

```bash
python scripts/run_final_test.py check
python scripts/run_final_test.py rehearse
LAB_UNLOCK=final_test python scripts/run_final_test.py run
```

The run checks every hash, needs a passing rehearsal, unlocks once through
the guard, and refuses to run again. Later analysis reads `results/final/` only.

## Prompt 5: the dashboard

```bash
python -m dashboard.build               # refuses if any number lacks a source
python -m dashboard.check_layout        # headless Chromium at 1920x1080 and 1280x720
```

## Synthetic demo

Until real files arrive, everything runs with `LAB_ROOT=$PWD/synthetic_lab`
on a synthetic random walk. Its results are committed under
`synthetic_lab/results/` and every page of the deck says so. On a random walk
nothing should work; anything that does is a bug or chance (see
`decisions.md` D27-D32).

## Rules the code enforces

- One master seed (`lab/config.py`); named child streams (`lab/seed.py`).
- `config/thresholds.json` and `rulebook_spec.json` are hash-locked; change
  them only with `python -m lab.amend "<reason>"`, before looking at results.
- The final window is sealed: every read goes through `lab/io.py`, which
  raises on `data/sealed/` or any final-window session unless
  `guard.unlock(step)` and `LAB_UNLOCK=step` are both on. Every unlock is logged.

See `decisions.md` for every choice and its reason, `rulebook.md` for every dial.
