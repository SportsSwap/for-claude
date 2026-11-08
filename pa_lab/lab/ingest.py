"""Ingest: copy, audit, clean, window, seal.

    LAB_UNLOCK=ingest python -m lab.ingest --src /path/to/data_folder

The ingest is the only step that sees the final window. It writes it once to
data/sealed/ with a sha256 manifest and never again.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import sys
from pathlib import Path

import pandas as pd

from . import audit, guard, io
from .config import P, derive_windows, sha256_file, stamp, thresholds
from .sessions import session_date, weekday_sessions

KINDS = ("adjusted", "unadjusted", "rolls")
EXTS = (".parquet", ".csv", ".csv.gz")


# --------------------------------------------------------------------------- discovery of inputs
def classify(name: str, markets) -> tuple[str, str] | None:
    low = name.lower()
    if not low.endswith(EXTS):
        return None
    toks = set(re.split(r"[^a-z0-9]+", low))
    mk = [m for m in markets if m.lower() in toks]
    if len(mk) != 1:
        return None
    if "roll" in low:
        kind = "rolls"
    elif "unadj" in low or "unadjusted" in low:
        kind = "unadjusted"
    else:
        kind = "adjusted"
    return mk[0], kind


def find_inputs(src: Path, markets) -> dict[tuple[str, str], Path]:
    found: dict[tuple[str, str], Path] = {}
    for f in sorted(src.iterdir()):
        c = classify(f.name, markets)
        if c is None:
            continue
        if c in found:
            raise SystemExit(f"two files look like {c}: {found[c].name}, {f.name}")
        found[c] = f
    for m in markets:
        for k in ("adjusted", "rolls"):
            if (m, k) not in found:
                raise SystemExit(f"missing the {k} file for {m} in {src}")
    return found


def copy_raw(found) -> dict:
    P.raw().mkdir(parents=True, exist_ok=True)
    manifest = {}
    for (m, k), f in found.items():
        dest = P.raw() / f.name
        h = sha256_file(f)
        if dest.exists():
            if sha256_file(dest) != h:
                raise SystemExit(f"{dest} exists with different contents; raw files are never replaced")
        else:
            shutil.copy2(f, dest)
            if sha256_file(dest) != h:
                raise SystemExit(f"copy of {f} does not match its source hash")
        manifest[dest.name] = {"market": m, "kind": k, "sha256": h,
                               "bytes": dest.stat().st_size, "source": str(f)}
    io.write_json({"files": manifest, **stamp()}, P.raw() / "MANIFEST.json")
    return manifest


# --------------------------------------------------------------------------- loading
def _ts(s: pd.Series) -> pd.Series:
    if pd.api.types.is_integer_dtype(s):
        return pd.to_datetime(s, unit="ns", utc=True)
    return pd.to_datetime(s, utc=True)


BAR_COLS = ["ts_event", "open", "high", "low", "close", "volume", "contract"]
ROLL_COLS = ["roll_time_utc", "old_contract", "new_contract", "spread"]


def load_bars(path: Path) -> pd.DataFrame:
    df = io.read_table(path)
    missing = set(BAR_COLS) - set(df.columns)
    if missing:
        raise SystemExit(f"{path.name} is missing columns {sorted(missing)}")
    df = df[BAR_COLS].copy()
    df["ts_event"] = _ts(df["ts_event"])
    df["contract"] = df["contract"].astype(str)
    return df.reset_index(drop=True)


def load_rolls(path: Path) -> pd.DataFrame:
    df = io.read_table(path)
    missing = set(ROLL_COLS) - set(df.columns)
    if missing:
        raise SystemExit(f"{path.name} is missing columns {sorted(missing)}")
    df = df[ROLL_COLS].copy()
    df["roll_time_utc"] = _ts(df["roll_time_utc"])
    df["old_contract"] = df["old_contract"].astype(str)
    df["new_contract"] = df["new_contract"].astype(str)
    return df.sort_values("roll_time_utc").reset_index(drop=True)


# --------------------------------------------------------------------------- cleaning
def clean(flagged: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    drop = {
        "duplicate_rows": flagged["f_duplicate"],
        "halt_hour_bars": flagged["f_halt_hour"] & ~flagged["f_duplicate"],
        "weekend_session_bars": flagged["f_weekend_session"] & ~flagged["f_duplicate"] & ~flagged["f_halt_hour"],
        "ohlc_invalid_bars": flagged["f_ohlc_invalid"] & ~flagged["f_duplicate"]
                             & ~flagged["f_halt_hour"] & ~flagged["f_weekend_session"],
    }
    mask = pd.Series(False, index=flagged.index)
    for v in drop.values():
        mask |= v
    out = flagged.loc[~mask, BAR_COLS + ["session"]].sort_values("ts_event").reset_index(drop=True)
    return out, {k: int(v.sum()) for k, v in drop.items()}


def _readonly(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


# --------------------------------------------------------------------------- main
def run(src: Path, windows_override=None) -> int:
    """windows_override: a config.Windows, used only by the tests' short data spans."""
    th = thresholds()
    markets, ta = th["markets"], th["audit"]
    if P.sealed().exists() and any(P.sealed().iterdir()):
        raise SystemExit("data/sealed/ already holds the final window; the ingest runs once. "
                         "Remove the whole data/ folder deliberately to start a fresh lab.")
    found = find_inputs(src, markets)
    copy_raw(found)
    raw = {k: P.raw() / f.name for k, f in found.items()}

    with guard.unlock("ingest"):
        loaded = {}
        for m in markets:
            adj = load_bars(raw[(m, "adjusted")])
            unadj = load_bars(raw[(m, "unadjusted")]) if (m, "unadjusted") in raw else None
            rolls = load_rolls(raw[(m, "rolls")])
            fl = audit.flag_bars(adj, ta["gap_minutes"], th["session"]["halt_hour_et"])
            cleaned, dropped = clean(fl)
            loaded[m] = dict(adj=adj, unadj=unadj, rolls=rolls, flagged=fl, clean=cleaned, dropped=dropped)

        # windows from the sessions both markets actually have
        all_sessions = sorted(set().union(*[set(v["clean"]["session"]) for v in loaded.values()]))
        win = windows_override or derive_windows(all_sessions[0], all_sessions[-1])
        io.write_json({**win.to_json(), **stamp()}, P.windows_file())
        final0 = win.final[0]

        def label(sessions: pd.Series) -> pd.Series:
            return pd.Series([win.label(d) for d in sessions], index=sessions.index)

        P.results().joinpath("audit").mkdir(parents=True, exist_ok=True)
        passes: dict[str, dict] = {}
        counts_rows, sealed_files, sealed_audit = [], {}, {}
        session_sets = {}
        for m, v in loaded.items():
            fl = v["flagged"]
            lab = label(fl["session"])
            summ = audit.summarize(fl, lab)
            open_summ = summ.drop(index=[i for i in summ.index if i == "final"])
            io.write_table(open_summ.reset_index(names="window"), P.results() / "audit" / f"{m}_flags_by_window.csv")
            sealed_audit[m] = {"flags": summ.loc[["final"]].to_dict(orient="index") if "final" in summ.index else {}}

            contracts = audit.audit_contracts(v["clean"], v["rolls"])
            adjust = (audit.audit_adjustment(v["adj"], v["unadj"], v["rolls"],
                                             ta["adjustment_step_tolerance_points"],
                                             ta["roll_spread_match_tolerance_points"])
                      if v["unadj"] is not None else {"skipped": "no unadjusted file"})

            # pass/fail checks (counts for the final window stay sealed; only the verdict is public)
            n = len(fl)
            checks = {
                "conflicting_duplicates": int(fl["f_duplicate_conflict"].sum()) <= ta["max_conflicting_duplicates"],
                "ohlc_invalid_frac": (fl["f_ohlc_invalid"].sum() / max(n, 1)) <= ta["max_ohlc_invalid_frac"],
                "contract_changes_off_roll": len(contracts["changes_off_roll"]) + len(contracts["changes_wrong_ids"]) <= ta["max_contract_changes_off_roll"],
                "adjustment_steps_only_at_rolls": ("skipped" in adjust) or (
                    len(adjust["unexplained_steps"]) <= ta["max_unexplained_adjustment_steps"]
                    and len(adjust["spread_mismatch"]) == 0
                    and adjust["bars_inconsistent_ohlc_offset"] == 0
                    and adjust["row_for_row"]),
                "no_weekend_sessions_after_clean": not v["clean"]["session"].map(lambda d: d.weekday() >= 5).any(),
            }
            checks = {k: bool(v) for k, v in checks.items()}
            passes[m] = checks

            def public(rows):  # strip final-window detail from lists before saving publicly
                return [r for r in rows
                        if session_date(pd.Series([pd.Timestamp(r["ts_event"] if isinstance(r, dict) else r)])).iat[0] < final0]
            pub_contracts = {**contracts, "changes_off_roll": public(contracts["changes_off_roll"]),
                             "changes_wrong_ids": public(contracts["changes_wrong_ids"])}
            pub_adjust = adjust if "skipped" in adjust else {
                **adjust, **{k: public(adjust[k]) for k in ("unexplained_steps", "spread_mismatch", "rolls_without_step")}}
            gaps = fl.loc[fl["session"] < final0, "gap_minutes"].dropna()
            io.write_json({"market": m, "checks": checks, "dropped_in_cleaning": v["dropped"],
                           "contracts": pub_contracts, "adjustment": pub_adjust,
                           "gap_minutes_distribution_open_windows": gaps[gaps > 1].describe().to_dict(),
                           "note": "counts for the final window are in data/sealed/audit_final.json",
                           **stamp()}, P.results() / "audit" / f"{m}_audit.json")
            sealed_audit[m].update({"contracts": contracts, "adjustment": adjust})

            # session counts per window
            sess = pd.Series(sorted(set(v["clean"]["session"])))
            session_sets[m] = set(sess)
            lab_s = label(sess)
            for name in ("warmup", "discovery", "era1", "era2", "final", "outside"):
                if name in ("era1", "era2"):
                    k = sum(1 for d in sess if win.era(d) == name)
                    a, b = getattr(win, name)
                else:
                    k = int((lab_s == name).sum())
                    a, b = getattr(win, name) if name != "outside" else (None, None)
                exp = len(weekday_sessions(a, b)) if a else None
                counts_rows.append({"market": m, "window": name, "start": a, "end": b,
                                    "sessions": k, "weekdays": exp})

            # split and write
            c = v["clean"]
            keep_open = c["session"].map(lambda d: win.warmup[0] <= d < final0)
            io.write_table(c[keep_open].reset_index(drop=True), P.clean() / f"{m}_1m.parquet")
            fin = c[c["session"] >= final0].reset_index(drop=True)
            sealed_files[f"{m}_1m.parquet"] = io.write_table(fin, P.sealed() / f"{m}_1m.parquet")
            if v["unadj"] is not None:
                u = v["unadj"].drop_duplicates("ts_event").merge(c[["ts_event", "session"]], on="ts_event")
                io.write_table(u[u["session"] < final0].pipe(lambda x: x[x["session"] >= win.warmup[0]]).reset_index(drop=True),
                               P.clean() / f"{m}_1m_unadjusted.parquet")
                sealed_files[f"{m}_1m_unadjusted.parquet"] = io.write_table(
                    u[u["session"] >= final0].reset_index(drop=True), P.sealed() / f"{m}_1m_unadjusted.parquet")
            r = v["rolls"].assign(session=session_date(v["rolls"]["roll_time_utc"]))
            io.write_table(r[r["session"] < final0].reset_index(drop=True), P.clean() / f"{m}_rolls.parquet")
            sealed_files[f"{m}_rolls.parquet"] = io.write_table(
                r[r["session"] >= final0].reset_index(drop=True), P.sealed() / f"{m}_rolls.parquet")

        sealed_files["audit_final.json"] = io.write_json({**sealed_audit, **stamp()}, P.sealed() / "audit_final.json")
        manifest = {name: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
                    for name, p in sealed_files.items()}
        mpath = io.write_json({"window": [win.final[0].isoformat(), win.final[1].isoformat()],
                               "files": manifest, **stamp()}, P.sealed() / "MANIFEST.json")
        for p in list(sealed_files.values()) + [mpath]:
            _readonly(p)

    # ----- session-count checks (public)
    counts = pd.DataFrame(counts_rows)
    io.write_table(counts, P.results() / "session_counts.csv")
    mism = session_sets[markets[0]].symmetric_difference(session_sets[markets[-1]]) if len(markets) > 1 else set()
    mism_open = sorted(d for d in mism if d < final0)
    sess_checks = {
        "every_window_has_sessions": bool(all(
            counts.loc[(counts.window == w), "sessions"].min() > 0
            for w in ("warmup", "discovery", "era1", "era2", "final"))),
        "nq_es_same_sessions": len(mism) <= ta["max_session_set_mismatch_nq_es"],
        "sessions_never_exceed_weekdays": bool((counts.dropna(subset=["weekdays"])
                                                .eval("sessions <= weekdays")).all()),
    }
    verdict = {"markets": passes, "sessions": sess_checks,
               "nq_es_session_mismatch_open_windows": [str(d) for d in mism_open],
               "nq_es_session_mismatch_total": len(mism)}
    verdict["pass"] = bool(all(all(c.values()) for c in passes.values()) and all(sess_checks.values()))
    io.write_json({**verdict, **stamp()}, P.results() / "audit" / "audit_pass.json")
    print(counts.to_string(index=False))
    print(json.dumps(verdict, indent=2, default=str))
    return 0 if verdict["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path, help="folder with the NQ/ES files")
    args = ap.parse_args(argv)
    return run(args.src)


if __name__ == "__main__":
    sys.exit(main())
