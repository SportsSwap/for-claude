"""Rebuild 3x leveraged ETFs minute by minute from the index CFD data.

    python scripts/make_leveraged_etf.py --src vendor_input/dukascopy --out vendor_input/etf \
        --yahoo <folder with TQQQ.json, SPXL.json from Yahoo's chart API>

TQQQ resets to 3x the Nasdaq 100's move every day; SPXL to 3x the S&P 500's.
For each regular-hours minute (09:30-16:00 New York):
    ETF = ETF_prev_close * (1 + 3 * (index / index_prev_close - 1))
where *_prev_close is the previous day's 16:00 close; highs and lows map the
same way. A daily drag (fees and swap financing) is fitted so the rebuilt
daily closes track the real ones. The output uses the lab's input format with
TQQQ in the NQ slot and SPXL in the ES slot (decisions.md D42).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ETF = {"NQ": ("TQQQ", 3.0), "ES": ("SPXL", 3.0)}
TICK = 0.01


def rth(df: pd.DataFrame) -> pd.DataFrame:
    et = df["ts_event"].dt.tz_convert("America/New_York")
    m = et.dt.hour * 60 + et.dt.minute
    keep = (m >= 570) & (m < 960) & (et.dt.day_of_week < 5)
    out = df[keep].copy()
    out["day"] = et[keep].dt.date
    return out


def yahoo_closes(path: Path) -> pd.Series:
    r = json.loads(path.read_text())["chart"]["result"][0]
    ts = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert("America/New_York").date
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    return pd.Series(adj, index=pd.Index(ts, name="day"), dtype=float).dropna()


def build(idx: pd.DataFrame, lev: float, start_price: float, drag_per_day: float) -> pd.DataFrame:
    b = rth(idx)
    day_close = b.groupby("day")["close"].last()
    days = day_close.index.to_list()
    prev_idx_close = pd.Series(day_close.shift(1).to_numpy(), index=days)
    # ETF closes day by day (drag applied once a day)
    etf_close = {}
    p = start_price
    for d in days:
        pc = prev_idx_close[d]
        if np.isfinite(pc):
            p = p * (1 + lev * (day_close[d] / pc - 1)) * (1 - drag_per_day)
        etf_close[d] = p
    prev_etf = pd.Series(etf_close).shift(1)
    prev_etf.iloc[0] = start_price
    pc = b["day"].map(prev_idx_close).to_numpy()
    pe = b["day"].map(prev_etf).to_numpy()
    first = ~np.isfinite(pc)
    pc = np.where(first, b["day"].map(day_close).to_numpy(), pc)   # first day: anchor on its own close
    out = pd.DataFrame({"ts_event": b["ts_event"].to_numpy()})
    for c in ("open", "high", "low", "close"):
        out[c] = pe * (1 + lev * (b[c].to_numpy() / pc - 1))
    if lev < 0:
        out["high"], out["low"] = out["low"].copy(), out["high"].copy()
    for c in ("open", "high", "low", "close"):
        out[c] = np.round(out[c] / TICK) * TICK
    out["high"] = out[["open", "high", "close"]].max(axis=1)
    out["low"] = out[["open", "low", "close"]].min(axis=1)
    out["volume"] = b["volume"].to_numpy()
    out["ts_event"] = pd.to_datetime(out["ts_event"], utc=True)
    return out, pd.Series(etf_close)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--yahoo", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    report = {}
    for slot, (name, lev) in ETF.items():
        idx = pd.read_parquet(a.src / f"{slot}_1m_backadjusted.parquet")
        real = yahoo_closes(a.yahoo / f"{name}.json")
        b = rth(idx)
        first_day = b["day"].iloc[0]
        start = float(real[real.index <= first_day].iloc[-1]) if (real.index <= first_day).any() else float(real.iloc[0])
        # fit the daily drag on log returns of matched days
        _, nodrag = build(idx, lev, start, 0.0)
        common = nodrag.index.intersection(real.index)
        r_syn = np.log(nodrag[common]).diff().dropna()
        r_real = np.log(real[common]).diff().dropna()
        k = r_syn.index.intersection(r_real.index)
        drag = float(max(0.0, (r_syn[k] - r_real[k]).mean()))
        bars, closes = build(idx, lev, start, drag)
        c = closes.index.intersection(real.index)
        rs, rr = closes[c].pct_change().dropna(), real[c].pct_change().dropna()
        kk = rs.index.intersection(rr.index)
        report[name] = {"days": int(len(kk)), "daily_return_corr": round(float(np.corrcoef(rs[kk], rr[kk])[0, 1]), 4),
                        "tracking_error_daily_pct": round(float((rs[kk] - rr[kk]).std() * 100), 3),
                        "drag_per_year_pct": round(drag * 252 * 100, 2),
                        "start_price": round(start, 2), "end_synthetic": round(float(closes.iloc[-1]), 2),
                        "end_real": round(float(real.iloc[-1]), 2), "bars": int(len(bars))}
        bars["contract"] = f"{name}SYN"
        bars.to_parquet(a.out / f"{slot}_1m_backadjusted.parquet", index=False)
        pd.DataFrame(columns=["roll_time_utc", "old_contract", "new_contract", "spread"]).to_csv(
            a.out / f"{slot}_rolls.csv", index=False)
        print(name, report[name], flush=True)
    (a.out / "build_report.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
