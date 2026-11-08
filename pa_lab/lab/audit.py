"""Data audit: flag every bar, then count flags per window.

Counts are only reported, never repaired, except where cleaning.md says so:
gaps are counted and never filled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sessions import in_halt_hour, is_weekend, session_date

PRICE = ["open", "high", "low", "close"]


def flag_bars(df: pd.DataFrame, gap_minutes=(1, 5, 60), halt_hour: int = 17) -> pd.DataFrame:
    """Return df (raw order) with a session column and boolean flag columns."""
    out = df.copy()
    out["ts_event"] = pd.to_datetime(out["ts_event"], utc=True)
    out["session"] = session_date(out["ts_event"])
    ts = out["ts_event"]

    out["f_duplicate"] = ts.duplicated(keep="first")
    dup_all = ts.duplicated(keep=False)
    cols = [c for c in PRICE + ["volume", "contract"] if c in out.columns]
    distinct = out[dup_all].drop_duplicates(subset=["ts_event"] + cols)
    n_versions = distinct.groupby("ts_event").size()
    conflict_ts = set(n_versions[n_versions > 1].index)
    out["f_duplicate_conflict"] = ts.isin(conflict_ts) & out["f_duplicate"]
    out["f_out_of_order"] = ts.lt(ts.cummax().shift(1)).fillna(False)

    p = out[PRICE]
    out["f_ohlc_invalid"] = (
        p.isna().any(axis=1) | (p <= 0).any(axis=1)
        | (out["high"] < out[["open", "close"]].max(axis=1))
        | (out["low"] > out[["open", "close"]].min(axis=1))
        | (out["high"] < out["low"]))
    out["f_zero_volume"] = out["volume"].fillna(0) <= 0
    out["f_halt_hour"] = in_halt_hour(ts, halt_hour)
    out["f_weekend_session"] = is_weekend(out["session"])

    # gaps inside a session: measured on the sorted, de-duplicated, in-session bars
    ok = ~out["f_duplicate"] & ~out["f_halt_hour"]
    s = out.loc[ok, ["ts_event", "session"]].sort_values("ts_event")
    delta = s["ts_event"].diff().dt.total_seconds().div(60)
    same = s["session"].eq(s["session"].shift(1))
    for g in gap_minutes:
        col = f"f_gap_gt_{g}m"
        out[col] = False
        out.loc[s.index[(same & (delta > g)).to_numpy()], col] = True
    out["gap_minutes"] = np.nan
    out.loc[s.index, "gap_minutes"] = delta.where(same).to_numpy()
    return out


def flag_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("f_")]


def summarize(flagged: pd.DataFrame, by: pd.Series) -> pd.DataFrame:
    """Count every flag per group (window label)."""
    cols = flag_columns(flagged)
    g = flagged[cols].groupby(by.to_numpy())
    out = g.sum().astype(int)
    out.insert(0, "rows", g.size())
    out.insert(1, "sessions", flagged.groupby(by.to_numpy())["session"].nunique())
    return out


def _first_index_at_or_after(ts: pd.Series, times: pd.Series) -> np.ndarray:
    return np.searchsorted(ts.to_numpy(), pd.to_datetime(times, utc=True).to_numpy(), side="left")


def audit_contracts(adj: pd.DataFrame, rolls: pd.DataFrame) -> dict:
    """The contract id may only change at a roll, from old_contract to new_contract."""
    a = adj.sort_values("ts_event").reset_index(drop=True)
    change = np.flatnonzero(a["contract"].ne(a["contract"].shift(1)).to_numpy()[1:]) + 1
    roll_idx = _first_index_at_or_after(a["ts_event"], rolls["roll_time_utc"])
    ok_idx = {}
    for i, r in zip(roll_idx, rolls.itertuples()):
        ok_idx[int(i)] = (r.old_contract, r.new_contract)
    off, wrong = [], []
    for i in change:
        if int(i) not in ok_idx:
            off.append(str(a["ts_event"].iat[i]))
        elif (a["contract"].iat[i - 1], a["contract"].iat[i]) != ok_idx[int(i)]:
            wrong.append(str(a["ts_event"].iat[i]))
    return {"contract_changes": int(len(change)), "changes_off_roll": off,
            "changes_wrong_ids": wrong, "rolls": int(len(rolls))}


def audit_adjustment(adj: pd.DataFrame, unadj: pd.DataFrame, rolls: pd.DataFrame,
                     tol: float, spread_tol: float) -> dict:
    """Adjusted minus unadjusted must be one constant per bar across O/H/L/C and
    may only step at a roll, by the roll's spread."""
    res = {"row_for_row": bool(len(adj) == len(unadj)
                               and (pd.to_datetime(adj["ts_event"], utc=True).to_numpy()
                                    == pd.to_datetime(unadj["ts_event"], utc=True).to_numpy()).all())}
    a = adj.sort_values("ts_event").drop_duplicates("ts_event").reset_index(drop=True)
    u = unadj.sort_values("ts_event").drop_duplicates("ts_event").reset_index(drop=True)
    m = a[["ts_event"] + PRICE].merge(u[["ts_event"] + PRICE], on="ts_event", suffixes=("_a", "_u"))
    diffs = np.column_stack([m[f"{c}_a"] - m[f"{c}_u"] for c in PRICE])
    res["bars_compared"] = int(len(m))
    res["bars_inconsistent_ohlc_offset"] = int((np.ptp(diffs, axis=1) > tol).sum())
    d = diffs[:, 3]
    step = np.diff(d)
    step_idx = np.flatnonzero(np.abs(step) > tol) + 1
    roll_idx = _first_index_at_or_after(m["ts_event"], rolls["roll_time_utc"])
    spread_at = dict(zip(roll_idx.tolist(), rolls["spread"].astype(float).tolist()))
    unexplained, spread_mismatch = [], []
    for i in step_idx:
        t = str(m["ts_event"].iat[i])
        if int(i) not in spread_at:
            unexplained.append({"ts_event": t, "step": float(step[i - 1])})
        elif abs(abs(step[i - 1]) - abs(spread_at[int(i)])) > spread_tol:
            spread_mismatch.append({"ts_event": t, "step": float(step[i - 1]),
                                    "spread": spread_at[int(i)]})
    rolls_without_step = [str(m["ts_event"].iat[i]) for i, s in spread_at.items()
                          if i < len(m) and abs(s) > tol and i not in set(step_idx.tolist())]
    res.update({"steps": int(len(step_idx)), "unexplained_steps": unexplained,
                "spread_mismatch": spread_mismatch, "rolls_without_step": rolls_without_step})
    return res
