"""Free 1-minute data: Dukascopy index CFDs as stand-ins for NQ and ES futures.

    python scripts/fetch_dukascopy.py --out vendor_input/dukascopy [--start 2021-09-26 --end 2026-11-06]

NQ <- USATECHIDXUSD (Nasdaq 100 CFD), ES <- USA500IDXUSD (S&P 500 CFD).
Each UTC day is one LZMA file of 24-byte big-endian records: seconds from
00:00 UTC, open, close, low, high (int32, price x 1000) and volume (float32,
tick volume). Bid candles by default; --mid averages bid and ask. Minutes with
zero volume (market closed) are dropped. The output is the lab's input
format: <M>_1m_backadjusted.parquet with one constant contract id, and an
empty <M>_rolls.csv (a CFD never rolls).

What this is not: CME futures. Prices differ from the futures by the
basis, volume counts ticks, not contracts, and there are no rolls. See
decisions.md D39.
"""
from __future__ import annotations

import argparse
import datetime as dt
import lzma
import struct
import sys
import time
import threading

import requests
from pathlib import Path

import numpy as np
import pandas as pd

INSTR = {"NQ": "USATECHIDXUSD", "ES": "USA500IDXUSD"}
URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/{d:02d}/{side}_candles_min_1.bi5"
AGENT = "pa-lab/0.1 (research backtest)"
SCALE = 1000.0


_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "s"):
        _local.s = requests.Session()           # one kept-alive connection, reused for every file
        _local.s.headers["User-Agent"] = AGENT
    return _local.s


MIN_INTERVAL = 1.0      # seconds between requests (set by --min-interval)
COOL_DOWN = 300         # seconds to wait after the server starts refusing
_last = [0.0]


def fetch(sym: str, day: dt.date, side: str, cache: Path) -> bytes:
    p = cache / sym / f"{day.isoformat()}_{side}.bi5"
    if p.exists():
        return p.read_bytes()
    url = URL.format(sym=sym, y=day.year, m=day.month - 1, d=day.day, side=side)  # month is 0-based
    for attempt in range(12):
        wait = MIN_INTERVAL - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = _session().get(url, timeout=30)
            if r.status_code in (200, 404):
                body = r.content if r.status_code == 200 else b""
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(body)
                return body
        except requests.RequestException:
            _local.__dict__.pop("s", None)      # drop a broken connection
        pause = 10 if attempt < 2 else COOL_DOWN   # a refusal streak means slow down for minutes, not seconds
        print(f"  refused ({url.rsplit('/', 5)[-5:]}), waiting {pause}s", flush=True)
        time.sleep(pause)
    raise RuntimeError(f"failed after retries: {url}")


def decode(blob: bytes, day: dt.date) -> pd.DataFrame:
    if not blob:
        return pd.DataFrame(columns=["ts_event", "open", "high", "low", "close", "volume"])
    raw = lzma.decompress(blob)
    a = np.frombuffer(raw, dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"),
                                           ("h", ">i4"), ("v", ">f4")]))
    base = pd.Timestamp(day, tz="UTC")
    return pd.DataFrame({"ts_event": base + pd.to_timedelta(a["t"].astype(np.int64), unit="s"),
                         "open": a["o"] / SCALE, "high": a["h"] / SCALE, "low": a["l"] / SCALE,
                         "close": a["c"] / SCALE, "volume": a["v"].astype(float)})


SIDES = ("BID",)   # bid only by default: halves the requests; the CFD spread is about a point (D39)


def one_day(sym, day, cache):
    bars = [decode(fetch(sym, day, side, cache), day) for side in SIDES]
    if any(b.empty for b in bars):
        return None
    if len(bars) == 1:
        out = bars[0].copy()
    else:
        m = bars[0].merge(bars[1], on="ts_event", suffixes=("_b", "_a"))
        out = pd.DataFrame({"ts_event": m.ts_event})
        for c in ("open", "high", "low", "close"):
            out[c] = (m[f"{c}_b"] + m[f"{c}_a"]) / 2
        out["volume"] = m["volume_b"] + m["volume_a"]
    out = out[out.volume > 0]
    out["high"] = out[["open", "high", "close"]].max(axis=1)   # mid of extremes can sit inside the body
    out["low"] = out[["open", "low", "close"]].min(axis=1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("vendor_cache/dukascopy"))
    ap.add_argument("--start", default="2021-09-26")
    ap.add_argument("--end", default="2026-11-06")
    ap.add_argument("--min-interval", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--mid", action="store_true", help="average bid and ask (twice the requests)")
    a = ap.parse_args(argv)
    global MIN_INTERVAL, SIDES
    MIN_INTERVAL = a.min_interval
    SIDES = ("BID", "ASK") if a.mid else ("BID",)
    days = [d.date() for d in pd.date_range(a.start, a.end, freq="D") if d.weekday() != 5]  # no Saturday trading
    a.out.mkdir(parents=True, exist_ok=True)
    for mkt, sym in INSTR.items():
        t0 = time.time()
        parts = []
        for i, d in enumerate(days):
            parts.append(one_day(sym, d, a.cache))
            if i % 100 == 99:
                print(f"  {mkt} {d} ({i + 1}/{len(days)}, {time.time() - t0:.0f}s)", flush=True)
        df = pd.concat([p for p in parts if p is not None and len(p)], ignore_index=True)
        df = df.sort_values("ts_event").reset_index(drop=True)
        df["contract"] = sym
        df.to_parquet(a.out / f"{mkt}_1m_backadjusted.parquet", index=False)
        pd.DataFrame(columns=["roll_time_utc", "old_contract", "new_contract", "spread"]).to_csv(
            a.out / f"{mkt}_rolls.csv", index=False)
        print(f"{mkt} <- {sym}: {len(df):,} bars, {df.ts_event.min()} .. {df.ts_event.max()} ({time.time() - t0:.0f}s)",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
