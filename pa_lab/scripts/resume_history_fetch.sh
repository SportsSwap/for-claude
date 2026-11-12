#!/usr/bin/env bash
# Idempotent: (re)start the 2013-2021 Dukascopy download unless it is running or finished.
set -uo pipefail
cd "$(dirname "$0")/.."
S=${1:?scratch dir for logs}
mkdir -p "$S"
if grep -q '^EXIT 0' "$S/fetch_hist.log" 2>/dev/null; then echo "history download finished"; exit 0; fi
if ! pgrep -f "fetch_dukascopy.py --out vendor_input/dukascopy_2013_2021" >/dev/null; then
  [ -f "$S/fetch_hist.log" ] && mv "$S/fetch_hist.log" "$S/fetch_hist_$(date +%s).log"
  (setsid nohup bash -c ". .venv/bin/activate && python -I scripts/fetch_dukascopy.py --out vendor_input/dukascopy_2013_2021 --cache vendor_cache/dukascopy --start 2012-12-02 --end 2021-09-25 --min-interval 1.0 > $S/fetch_hist.log 2>&1; echo EXIT \$? >> $S/fetch_hist.log" >/dev/null 2>&1 </dev/null &)
  echo "history download (re)started"
fi
echo "cached BID files: $(ls vendor_cache/dukascopy/*/ 2>/dev/null | grep -c BID) of ~8700"
