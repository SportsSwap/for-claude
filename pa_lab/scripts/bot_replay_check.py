"""Does the live bot's strategy code take exactly the lab's trades?

    python scripts/bot_replay_check.py

Feeds 2013 .. Jul 2024 Nasdaq-100 minutes (the open data; no unlock) into bot/noise_band_core.py
one bar at a time and compares every trade (day, entry minute, side, exit minute) with the lab's
own vectorised code (scripts/noise_band_search.py) on the same bars.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bot"))
from lab import io  # noqa: E402
from lab.config import P  # noqa: E402
import noise_band_qqq as nb  # noqa: E402
import noise_band_search as ns  # noqa: E402
import run_history_test as ht  # noqa: E402
from noise_band_core import NoiseBand  # noqa: E402

LAB = {
    "best": dict(band_mult=1.25, band_days=20, or_offset_atr=0.15, vwap=False, interval=30, last_check="14:00",
                 exit="vwap_cross", stop_atr=0.5),
    "as_written": dict(band_mult=1.25, band_days=20, or_offset_atr=0.3, vwap=True, interval=10, last_check="14:00",
                       exit="hold", stop_atr=None),
}


def open_minutes() -> pd.DataFrame:
    old, _ = ht.clean_bars(ROOT / "vendor_input" / "dukascopy_2013_2021" / "NQ_1m_backadjusted.parquet")
    new = io.read_table(P.clean() / "NQ_1m.parquet")
    cols = ["ts_event", "open", "high", "low", "close", "volume"]
    m = pd.concat([old[cols], new[cols]], ignore_index=True)
    m["ts_event"] = pd.to_datetime(m["ts_event"], utc=True)
    return m.drop_duplicates("ts_event").sort_values("ts_event").reset_index(drop=True)


def main() -> int:
    days, A, _ = nb.rth_grid(open_minutes())
    F = nb.features(days, A)
    O, H, L, C, V = (A[k] for k in ("open", "high", "low", "close", "volume"))
    # which minutes were real bars (the grid forward-fills the others with volume 0 and o=h=l=c)
    real = V > 0
    real[:, 0] = True
    ok_all = True
    for version, v in LAB.items():
        d, e, side = ns.entries(A, F, ns.sigma_for(A, F, 20), v)
        x = ns.exits_vec(A, F, d, e, side, v)
        lab = {(int(a), int(b), int(c_), int(y)) for a, b, c_, y in zip(d, e, side, x)}
        bot, nb_ = set(), NoiseBand(version)
        open_trade = None
        for i, day in enumerate(days):
            nb_.start_day(day)
            for k in range(nb.RTH):
                if not real[i, k] and k != 0:
                    continue                      # missing minute: the bot never sees a bar there
                for act in nb_.on_bar(k, O[i, k], H[i, k], L[i, k], C[i, k], V[i, k]):
                    if act["type"] == "enter":
                        open_trade = (i, act["k"], act["side"])
                    else:
                        bot.add((*open_trade, act["k"]))
                        open_trade = None
        nb_.finish_day()
        only_lab, only_bot = sorted(lab - bot), sorted(bot - lab)
        print(f"{version}: lab {len(lab)} trades, bot {len(bot)} trades, identical {len(lab & bot)}, "
              f"only in lab {len(only_lab)}, only in bot {len(only_bot)}")
        for t in (only_lab[:5] + only_bot[:5]):
            print("   ", days[t[0]], "entry bar", t[1], "side", t[2], "exit bar", t[3])
        ok_all &= not only_lab and not only_bot
    print("MATCH" if ok_all else "MISMATCH")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
