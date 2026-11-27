"""Run every bot through the validation protocol and write results/summary.json."""
import json
import sys
import time

from bots.strategies import REGISTRY, bh
from engine import validate as V

only = sys.argv[1:]
summary = []
for spec in REGISTRY:
    if only and not any(o in spec["name"] for o in only):
        continue
    t0 = time.time()
    from bots.strategies import macd_bench
    bench = macd_bench() if spec["bench"] == "MACD_BASKET" else (bh(spec["bench"]) if spec["bench"] else None)
    out = V.study(spec["name"], spec["fn"], spec["space"], spec["default"], spec["is_end"],
                  benchmark=bench, notes=spec["notes"])
    print(V.fmt(out), f"  ({time.time()-t0:.0f}s)", flush=True)
    summary.append(out)

if not only:
    (V.RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
