"""Synthetic NQ/ES 1-minute data in the exact input format, for proving the
pipeline before real data arrives. Never mix with real data: it writes to its
own folder and every contract id ends in 'SYN'.

    python scripts/make_synthetic.py --out synthetic_input [--start 2021-10-01 --end 2026-10-16] [--defects]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab.seed import rng  # noqa: E402
from lab.sessions import session_bounds  # noqa: E402

MARKETS = {"NQ": dict(p0=16000.0, sigma=0.00035, spread=(60, 160)),
           "ES": dict(p0=4500.0, sigma=0.00025, spread=(15, 45))}
TICK = 0.25
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}
HOLIDAYS = {(1, 1), (7, 4), (12, 25)}


def sessions(start: str, end: str) -> list:
    days = pd.bdate_range(start, end)
    return [d.date() for d in days if (d.month, d.day) not in HOLIDAYS]


def roll_schedule(start: str, end: str) -> list[tuple[pd.Timestamp, int, int]]:
    """Roll at the open (Wed 18:00 ET) of the Thursday session 8 days before the 3rd Friday."""
    out = []
    for y in range(pd.Timestamp(start).year - 1, pd.Timestamp(end).year + 2):
        for m in (3, 6, 9, 12):
            first = pd.Timestamp(y, m, 1)
            first_fri = first + pd.Timedelta(days=(4 - first.weekday()) % 7)
            thu = first_fri + pd.Timedelta(days=14) - pd.Timedelta(days=8)
            out.append((thu, y, m))
    return out


def contract_id(mkt: str, y: int, m: int) -> str:
    return f"{mkt}{MONTH_CODE[m]}{y % 10}SYN"


def next_contract(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 3) if m == 12 else (y, m + 3)


def make_market(mkt: str, start: str, end: str, defects: bool):
    cfg = MARKETS[mkt]
    sess = sessions(start, end)
    b = session_bounds(sess)
    n_per = ((b["close_utc"] - b["open_utc"]).dt.total_seconds() // 60).astype(int).to_numpy()
    ts = np.concatenate([o.to_datetime64() + np.arange(n) * np.timedelta64(1, "m")
                         for o, n in zip(b["open_utc"], n_per)])
    ts = pd.to_datetime(ts, utc=True)
    n = len(ts)
    g = rng(f"synthetic:{mkt}")
    r = g.normal(0, cfg["sigma"], n)
    close = cfg["p0"] * np.exp(np.cumsum(r))
    close = np.round(close / TICK) * TICK
    open_ = np.r_[cfg["p0"], close[:-1]]
    wig = np.round(np.abs(g.normal(0, cfg["sigma"] * cfg["p0"] * 0.6, (2, n))) / TICK) * TICK
    high = np.maximum(open_, close) + wig[0]
    low = np.minimum(open_, close) - wig[1]
    vol = g.integers(5, 2000, n)

    # rolls and contracts
    sched = roll_schedule(start, end)
    roll_rows, roll_times = [], []
    for thu, y, m in sched:
        rt = pd.Timestamp(thu.date() - pd.Timedelta(days=1)).replace(hour=18).tz_localize("America/New_York").tz_convert("UTC")
        if ts[0] < rt <= ts[-1]:
            ny, nm = next_contract(y, m)
            spread = float(np.round(g.uniform(*cfg["spread"]) / TICK) * TICK)
            roll_rows.append({"roll_time_utc": rt, "old_contract": contract_id(mkt, y, m),
                              "new_contract": contract_id(mkt, ny, nm), "spread": spread})
            roll_times.append(rt)
    rolls = pd.DataFrame(roll_rows, columns=["roll_time_utc", "old_contract", "new_contract", "spread"])
    if rolls.empty:
        raise SystemExit("span holds no roll; pick dates that cross a quarterly roll")
    k = np.searchsorted(rolls["roll_time_utc"].to_numpy(), ts.to_numpy(), side="right")
    contracts = np.array([rolls["old_contract"].iat[0]] + rolls["new_contract"].tolist())[k]
    # back adjustment: adjusted = unadjusted + sum of spreads of rolls still ahead
    cum_ahead = np.r_[np.cumsum(rolls["spread"].to_numpy()[::-1])[::-1], 0.0][k]

    adj = pd.DataFrame({"ts_event": ts, "open": open_, "high": high, "low": low, "close": close,
                        "volume": vol, "contract": contracts})
    adj["volume"] = adj["volume"].astype("int64")
    if defects:
        d = rng(f"synthetic_defects:{mkt}")
        keep = np.ones(len(adj), bool)
        keep[d.choice(len(adj), 3000, replace=False)] = False                    # scattered 1-min gaps
        for s in d.choice(len(adj) - 200, 12, replace=False):                     # 10-minute holes
            keep[s:s + 10] = False
        for s in d.choice(len(adj) - 200, 3, replace=False):                      # 2-hour holes
            keep[s:s + 120] = False
        adj = adj[keep].reset_index(drop=True)
        cum_ahead = cum_ahead[keep]
        adj.loc[d.choice(len(adj), 500, replace=False), "volume"] = 0           # zero volume
        dup_idx = d.choice(len(adj), 50, replace=False)                          # exact duplicates
        halt = adj[pd.to_datetime(adj["ts_event"]).dt.tz_convert("America/New_York").dt.hour == 16].sample(
            40, random_state=int(d.integers(1 << 31)))
        halt = halt.assign(ts_event=halt["ts_event"] + pd.Timedelta(minutes=60))  # 16:mm -> 17:mm, inside the halt
        cum_halt = cum_ahead[halt.index.to_numpy()]  # same contract as the bar it was copied from
        extra = pd.concat([adj.iloc[dup_idx], halt])
        cum_extra = np.r_[cum_ahead[dup_idx], cum_halt]
        adj = pd.concat([adj, extra], ignore_index=True)
        cum_ahead = np.r_[cum_ahead, cum_extra]
        order = np.argsort(adj["ts_event"].to_numpy(), kind="stable")
        adj, cum_ahead = adj.iloc[order].reset_index(drop=True), cum_ahead[order]
        for i in d.choice(len(adj) - 2, 20, replace=False):                     # a few swapped rows
            adj.iloc[[i, i + 1]] = adj.iloc[[i + 1, i]].to_numpy()
            cum_ahead[[i, i + 1]] = cum_ahead[[i + 1, i]]
    unadj = adj.copy()
    for c in ("open", "high", "low", "close"):
        unadj[c] = adj[c] - cum_ahead
    return adj, unadj, rolls


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", default="2021-10-01")
    ap.add_argument("--end", default="2026-10-16")
    ap.add_argument("--defects", action="store_true")
    ap.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    for m in MARKETS:
        adj, unadj, rolls = make_market(m, a.start, a.end, a.defects)
        ext = a.format
        w = (lambda df, p: df.to_parquet(p, index=False)) if ext == "parquet" else (lambda df, p: df.to_csv(p, index=False))
        w(adj, a.out / f"{m}_1m_backadjusted.{ext}")
        w(unadj, a.out / f"{m}_1m_unadjusted.{ext}")
        rolls.to_csv(a.out / f"{m}_rolls.csv", index=False)
        print(f"{m}: {len(adj):,} bars, {len(rolls)} rolls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
