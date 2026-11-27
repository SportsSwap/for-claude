"""Free 1-minute index data from HistData.com (no sign-up).

NSXUSD = Nasdaq-100, SPXUSD = S&P 500 (cash index CFD quotes, used here as
stand-ins for NQ/MNQ and ES/MES futures: same points, no roll gaps, no basis).
Timestamps are EST without daylight saving (fixed UTC-5), per HistData docs.
Full years come as one zip; the current year comes month by month.
"""
import sys
import time
from pathlib import Path

from histdata import download_hist_data as dl
from histdata.api import Platform as P, TimeFrame as TF

OUT = Path(__file__).resolve().parent.parent / "data" / "histdata"
OUT.mkdir(parents=True, exist_ok=True)


def get(pair, year, month=None):
    name = f"DAT_ASCII_{pair.upper()}_M1_{year}{'' if month is None else f'{month:02d}'}.zip"
    if (OUT / name).exists() and (OUT / name).stat().st_size > 1000:
        return True
    for attempt in range(4):
        try:
            p = dl(year=str(year), month=month, pair=pair, platform=P.GENERIC_ASCII,
                   time_frame=TF.ONE_MINUTE, output_directory=str(OUT), verbose=False)
            print("ok", p, flush=True)
            return True
        except Exception as e:  # missing months raise
            print("fail", pair, year, month, type(e).__name__, str(e)[:80], flush=True)
            time.sleep(5 * (attempt + 1))
    return False


if __name__ == "__main__":
    for pair in ("nsxusd", "spxusd"):
        for y in range(2010, 2026):
            get(pair, y)
            time.sleep(1)
        for m in range(1, 12):
            get(pair, 2026, m)
            time.sleep(1)
    print("DONE", flush=True)
