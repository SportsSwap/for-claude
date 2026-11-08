#!/usr/bin/env bash
# Run prompts 1-3 and the dashboard on the real lab (LAB_ROOT = this folder).
# Stops before the final test: that unlock is the user's call, once.
#   bash scripts/run_real_lab.sh <input folder> "<data label>" [scale] [common_cells]
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
export PYTHONPATH=$PWD
unset LAB_ROOT
SRC=$1
LABEL=$2
SCALE=${3:-0.035}
CELLS=${4:-0.15}
say() { echo "[$(date -u +%H:%M:%S)] $*"; }

if [ ! -f data/sealed/MANIFEST.json ]; then
  say "prompt 1: ingest $SRC (seals the final window, once)"
  LAB_UNLOCK=ingest python -m lab.ingest --src "$SRC"
else
  say "prompt 1: already ingested and sealed; skipping"
fi
python - "$LABEL" <<'EOF'
import json, sys
from lab import io
from lab.config import P, stamp
label = sys.argv[1]
io.write_json({"label": label, "banner": f"{label} · see decisions.md D39", **stamp()},
              P.results() / "data_source.json")
EOF

say "prompt 2: random entries, the cheat (run once, then deleted), behavior tests"
python scripts/random_entries.py
cp scripts/random_entries.py scripts/cheat_peek60.py
python scripts/cheat_peek60.py --peek-ahead 60
rm scripts/cheat_peek60.py
python scripts/run_behavior.py > results/behavior_run.log 2>&1

say "prompt 3: funnel (scale $SCALE, common cells $CELLS)"
python scripts/run_funnel.py gen --scale "$SCALE" --common-cells "$CELLS" --workers 4
python scripts/run_funnel.py run --workers 4
python scripts/run_funnel.py report

say "prompt 4: pre-flight and rehearsal only (seal stays closed)"
python scripts/run_final_test.py check
python scripts/run_final_test.py rehearse

say "prompt 5: dashboard (final pages wait for the final test)"
python -m dashboard.build
python -m dashboard.check_layout
say "done; the final test waits for the user: LAB_UNLOCK=final_test python scripts/run_final_test.py run"
