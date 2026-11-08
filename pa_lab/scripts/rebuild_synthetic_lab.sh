#!/usr/bin/env bash
# Rebuild the synthetic demo lab from nothing and run every prompt on it.
#   bash scripts/rebuild_synthetic_lab.sh [scale] [common_cells]
# The real lab is never touched: everything runs with LAB_ROOT=synthetic_lab.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
export PYTHONPATH=$PWD LAB_ROOT=$PWD/synthetic_lab
SCALE=${1:-0.035}
CELLS=${2:-0.15}
say() { echo "[$(date -u +%H:%M:%S)] $*"; }

say "prompt 1: synthetic input (generator v2, path wicks) and ingest"
rm -rf synthetic_input synthetic_lab/data synthetic_lab/results
python scripts/make_synthetic.py --out synthetic_input --defects
mkdir -p synthetic_lab
LAB_UNLOCK=ingest python -m lab.ingest --src synthetic_input > /dev/null
cp -r data/news synthetic_lab/data/

say "prompt 2: random entries, the cheat (run once, then deleted), behavior tests"
python scripts/random_entries.py
cp scripts/random_entries.py scripts/cheat_peek60.py
python scripts/cheat_peek60.py --peek-ahead 60
rm scripts/cheat_peek60.py
python scripts/run_behavior.py > synthetic_lab/results/behavior_run.log 2>&1

say "prompt 3: funnel (scale $SCALE, common cells $CELLS)"
python scripts/run_funnel.py gen --scale "$SCALE" --common-cells "$CELLS" --workers 4
python scripts/run_funnel.py run --workers 4
python scripts/run_funnel.py report

say "prompt 4: final test"
python scripts/run_final_test.py check
python scripts/run_final_test.py rehearse
LAB_UNLOCK=final_test python scripts/run_final_test.py run > synthetic_lab/results/final_run.log 2>&1

say "prompt 5: dashboard"
python -m dashboard.build
python -m dashboard.check_layout
say "done"
