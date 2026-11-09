#!/usr/bin/env bash
# The full lab on TQQQ (and SPXL as the replication market), rebuilt from index data.
# TQQQ sits in the lab's "NQ" slot and SPXL in the "ES" slot (tqqq_lab/data/instrument_spec.json).
# The final window here is NOT blind: it is the same Nasdaq path whose NQ final test was already opened.
#   bash scripts/run_tqqq_lab.sh [scale] [common_cells]
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
export PYTHONPATH=$PWD LAB_ROOT=$PWD/tqqq_lab
SCALE=${1:-0.1}
CELLS=${2:-0.4}
say() { echo "[$(date -u +%H:%M:%S)] $*"; }

if [ ! -f tqqq_lab/data/sealed/MANIFEST.json ]; then
  say "ingest rebuilt TQQQ/SPXL"
  LAB_UNLOCK=ingest python -m lab.ingest --src vendor_input/etf
fi
python - <<'PY'
from lab import io
from lab.config import P, stamp
io.write_json({"label": "TQQQ rebuilt from Nasdaq index data", "banner": "TQQQ rebuilt from Nasdaq index data · final window not blind", **stamp()},
              P.results() / "data_source.json")
PY
say "engine checks and behavior tests"
python scripts/random_entries.py
cp scripts/random_entries.py scripts/cheat_peek60.py
python scripts/cheat_peek60.py --peek-ahead 60
rm scripts/cheat_peek60.py
python scripts/run_behavior.py > tqqq_lab/results/behavior_run.log 2>&1
say "funnel (scale $SCALE, common cells $CELLS)"
python scripts/run_funnel.py gen --scale "$SCALE" --common-cells "$CELLS" --workers 4
python scripts/run_funnel.py run --workers 4
python scripts/run_funnel.py report
say "final test (not blind: same Nasdaq path as the NQ final window)"
python scripts/run_final_test.py check
python scripts/run_final_test.py rehearse
LAB_UNLOCK=final_test python scripts/run_final_test.py run > tqqq_lab/results/final_run.log 2>&1
python scripts/analyze_final.py > /dev/null
say "dashboard"
python -m dashboard.build
python -m dashboard.check_layout
say "done"
