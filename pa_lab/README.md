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

## Rules the code enforces

- One master seed (`lab/config.py`); named child streams (`lab/seed.py`).
- `config/thresholds.json` and `rulebook_spec.json` are hash-locked; change
  them only with `python -m lab.amend "<reason>"`, before looking at results.
- The final window is sealed: every read goes through `lab/io.py`, which
  raises on `data/sealed/` or any final-window session unless
  `guard.unlock(step)` and `LAB_UNLOCK=step` are both on. Every unlock is logged.

See `decisions.md` for every choice and its reason, `rulebook.md` for every dial.
