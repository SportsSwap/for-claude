#!/usr/bin/env bash
# Idempotent: (re)start the Dukascopy download and the chain that runs the real
# lab after it, unless they are already running or already finished.
set -uo pipefail
cd "$(dirname "$0")/.."
S=${1:?scratch dir for logs}
if grep -q '^EXIT' "$S/real_lab.log" 2>/dev/null; then echo "real lab already finished"; exit 0; fi
if ! pgrep -f "python -I scripts/fetch_dukascopy.py" >/dev/null && ! grep -q '^EXIT 0' "$S/fetch4.log" 2>/dev/null; then
  [ -f "$S/fetch4.log" ] && mv "$S/fetch4.log" "$S/fetch4_$(date +%s).log"
  setsid nohup bash -c ". .venv/bin/activate && python -I scripts/fetch_dukascopy.py --out vendor_input/dukascopy --cache vendor_cache/dukascopy --start 2021-09-26 --end 2026-11-06 --min-interval 1.0 > $S/fetch4.log 2>&1; echo EXIT \$? >> $S/fetch4.log" >/dev/null 2>&1 </dev/null &
  echo "download (re)started"
fi
if ! pgrep -f "until grep -q '\^EXIT' $S/fetch4.log" >/dev/null && ! pgrep -f run_real_lab.sh >/dev/null; then
  setsid nohup bash -c "until grep -q '^EXIT' $S/fetch4.log 2>/dev/null; do sleep 60; done; if grep -q '^EXIT 0' $S/fetch4.log; then bash scripts/run_real_lab.sh vendor_input/dukascopy 'Dukascopy CFD stand-in data' > $S/real_lab.log 2>&1; echo EXIT \$? >> $S/real_lab.log; else echo 'fetch failed; real lab not started' > $S/real_lab.log; echo EXIT 9 >> $S/real_lab.log; fi" >/dev/null 2>&1 </dev/null &
  echo "chain (re)started"
fi
echo "cached days: $(ls vendor_cache/dukascopy/*/ 2>/dev/null | grep -c BID) of ~3200"
