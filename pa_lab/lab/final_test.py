"""The final test: the one run on data no rule has seen.

    LAB_ROOT=... python scripts/run_final_test.py rehearse        # seal closed
    LAB_ROOT=... LAB_UNLOCK=final_test python scripts/run_final_test.py run

Order of work (prompt 4):
  1. pre-flight: every hash of the funnel's configurations and selections, the
     lock ledger, and the access log (the seal must never have been opened by
     this step). Stop if anything differs.
  2. rehearsal: the last month of discovery, shifted in price, through this
     exact code path (`run(source="rehearsal")`); only where the bars come
     from changes. It must finish without errors before the real run.
  3. the run: ONE unlock ("final_test") reads both markets' sealed bars and
     rolls and checks them against data/sealed/MANIFEST.json, then relocks.
     Discovery bars from three months before the final window warm the
     detectors. Only complete sessions (a bar opening at 15:59 ET or later)
     are kept; a dropped session is treated like a roll. Every version runs on
     NQ and ES with the discovery engine and costs.
  4. results/final/: every version's metrics and daily P&L, the held-up
     tables, and DONE.json (sha256 of every result file). Later analyses read
     only these files (`load_final_results`), never the sealed data.

Dates in saved final tables are in a column named `day`, not `session`:
the guard treats a `session`/`ts_event` column dated in the final window as
sealed market data.
"""
from __future__ import annotations

import datetime as dt
import json
import multiprocessing as mp
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import engine, guard, io
from . import strategy as sg
from .config import P, load_windows, sha256_file, stamp, verify_locks
from .market import Market
from .seed import rng

MARKETS = ("NQ", "ES")
HELD_SHARPE = 0.5
REHEARSAL_SHIFT_POINTS = 1000.0
REHEARSAL_VERSIONS = 60
COMPLETE_FROM_ET_MIN = 15 * 60 + 59          # a bar opening at 15:59 ET or later
TWIN_SETS = 1000
TWIN_MAX_TRADES = 3000
TWIN_MAX_VERSIONS = 40
SELECTION_FILES = ("versions.jsonl", "stages.json", "candidates.json", "working_setups.json",
                   "named_versions.json")
NON_DIAL_KEYS = {"id", "set", "name", "group", "config", "hash"}


class PreflightError(RuntimeError):
    pass


# =========================================================================== paths
def funnel_dir() -> Path:
    return P.results() / "funnel"


def out_dir(source: str) -> Path:
    return P.results() / ("final" if source == "final" else "final_rehearsal")


# =========================================================================== versions
def read_versions(path: Path | None = None) -> list[dict]:
    path = path or funnel_dir() / "versions.jsonl"
    text = io.read_bytes(path).decode()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def version_config(rec: dict) -> dict:
    """A version record is either {"id", ..., "config": {...}} or flat dial values."""
    if isinstance(rec.get("config"), dict):
        return dict(rec["config"])
    return {k: v for k, v in rec.items() if k not in NON_DIAL_KEYS}


def version_set(rec: dict) -> str:
    return str(rec.get("set", rec.get("group", "")))


# =========================================================================== pre-flight
_HEX = re.compile(r"\b[0-9a-f]{64}\b")


def _manifest_hashes(obj) -> dict[str, str]:
    files = obj.get("files", obj)
    out = {}
    for name, v in files.items():
        h = v.get("sha256") if isinstance(v, dict) else v
        if isinstance(h, str) and _HEX.fullmatch(h):
            out[name] = h
    return out


def preflight() -> dict:
    """Stop before any unlock if a configuration, selection or lock differs."""
    fd = funnel_dir()
    problems = []
    try:
        verify_locks()
    except Exception as e:  # noqa: BLE001
        problems.append(f"locks: {e}")
    man_path = fd / "selection_manifest.json"
    if not man_path.exists():
        raise PreflightError(f"missing {man_path}; the funnel must save and hash its selections first")
    man = _manifest_hashes(io.read_json(man_path))
    for name in SELECTION_FILES:
        if name not in man:
            problems.append(f"selection_manifest.json has no hash for {name}")
            continue
        f = fd / name
        if not f.exists():
            problems.append(f"{name} is missing")
        elif sha256_file(f) != man[name]:
            problems.append(f"{name} changed since it was hashed")
    vs = fd / "versions.sha256"
    if vs.exists():
        found = _HEX.findall(io.read_bytes(vs).decode())
        if not found or sha256_file(fd / "versions.jsonl") != found[0]:
            problems.append("versions.jsonl does not match versions.sha256")
    else:
        problems.append("versions.sha256 is missing")
    if problems:
        raise PreflightError("pre-flight failed:\n  " + "\n  ".join(problems))
    return man


def seal_ever_opened() -> bool:
    log = P.access_log()
    if not log.exists():
        return False
    for line in log.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("event") == "unlock_open" and r.get("step") == "final_test":
            return True
    return False


def refuse_if_done() -> None:
    d = out_dir("final")
    if (d / "DONE.json").exists() or (d.exists() and any(d.iterdir())):
        raise PreflightError(f"{d} already holds final results; the final test runs once")
    if seal_ever_opened():
        raise PreflightError("the access log shows an earlier final_test unlock; the final test runs once")


# =========================================================================== sessions
def complete_sessions(m1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep sessions with a bar opening at 15:59 ET or later. Returns (kept bars,
    dropped sessions with their first bar time)."""
    et = pd.to_datetime(m1["ts_event"], utc=True).dt.tz_convert("America/New_York")
    mins = et.dt.hour * 60 + et.dt.minute
    late = (mins >= COMPLETE_FROM_ET_MIN) & (mins < 17 * 60)
    ok_sessions = set(m1.loc[late.to_numpy(), "session"])
    keep = m1["session"].isin(ok_sessions).to_numpy()
    dropped = (m1.loc[~keep].groupby("session")["ts_event"].min().rename("first_bar_utc").reset_index())
    return m1.loc[keep].reset_index(drop=True), dropped


def dropped_as_rolls(dropped: pd.DataFrame) -> pd.DataFrame:
    """A dropped session works like a roll: no entries in the hour before it and an
    open position closes at the last bar before it."""
    return pd.DataFrame({"roll_time_utc": pd.to_datetime(dropped["first_bar_utc"], utc=True),
                         "old_contract": "dropped_session", "new_contract": "dropped_session", "spread": 0.0})


def _first_of_month(d: dt.date, back: int = 0) -> dt.date:
    y, m = divmod(d.month - 1 - back, 12)
    return dt.date(d.year + y, m + 1, 1)


def window_for(source: str) -> tuple[dt.date, dt.date, dt.date]:
    """(warm-up start, window start, window end)."""
    w = load_windows()
    if source == "final":
        start, end = w.final
    else:
        end = w.discovery[1]
        start = max(_first_of_month(end), w.discovery[0])
    return _first_of_month(start, 3), start, end


# =========================================================================== where the bars come from
def _rolls_frame(df):
    cols = ["roll_time_utc", "old_contract", "new_contract", "spread"]
    df = df[cols].copy()
    df["roll_time_utc"] = pd.to_datetime(df["roll_time_utc"], utc=True)
    return df


def _news():
    from .news import news_days
    try:
        return frozenset(news_days(require_verified=False))
    except FileNotFoundError:
        return frozenset()


def load_frames(source: str) -> dict:
    """The only place `source` matters. Returns {market: (bars, rolls)} covering
    warm-up start .. window end, plus the data provenance."""
    warm, start, end = window_for(source)
    frames, prov = {}, {"source": source, "warmup_start": str(warm), "window": [str(start), str(end)]}
    disc = {}
    for m in MARKETS:
        b = io.read_table(P.clean() / f"{m}_1m.parquet")
        b = b[(b["session"] >= warm) & (b["session"] <= min(end, load_windows().discovery[1]))]
        r = io.read_table(P.clean() / f"{m}_rolls.parquet")
        disc[m] = (b, _rolls_frame(r))
    if source == "rehearsal":
        for m, (b, r) in disc.items():
            b = b.copy()
            for c in ("open", "high", "low", "close"):
                b[c] = b[c] + REHEARSAL_SHIFT_POINTS
            frames[m] = (b.reset_index(drop=True), r)
        prov["price_shift_points"] = REHEARSAL_SHIFT_POINTS
        return {"frames": frames, "prov": prov}
    if source != "final":
        raise ValueError(source)
    # ---- the one unlock: verify the seal, read both markets, relock
    sealed = {}
    with guard.unlock("final_test"):
        manifest = io.read_json(P.sealed() / "MANIFEST.json")
        bad = [n for n, h in _manifest_hashes(manifest).items() if sha256_file(P.sealed() / n) != h]
        if bad:
            raise PreflightError(f"sealed files differ from their manifest: {bad}")
        for m in MARKETS:
            sealed[m] = (io.read_table(P.sealed() / f"{m}_1m.parquet"),
                         io.read_table(P.sealed() / f"{m}_rolls.parquet"))
    prov["sealed_manifest_sha256"] = {n: h for n, h in _manifest_hashes(manifest).items()}
    for m in MARKETS:
        b, r = disc[m]
        sb, sr = sealed[m]
        sb = sb[sb["session"] <= end]
        cols = ["ts_event", "open", "high", "low", "close", "volume", "contract", "session"]
        bars = pd.concat([b[cols], sb[cols]], ignore_index=True)
        rolls = pd.concat([r, _rolls_frame(sr)], ignore_index=True) if len(sr) else r
        frames[m] = (bars, rolls)
    return {"frames": frames, "prov": prov}


def build_market(name: str, bars: pd.DataFrame, rolls: pd.DataFrame, window_start: dt.date) -> tuple[Market, list]:
    bars, dropped = complete_sessions(bars)
    extra = dropped_as_rolls(dropped)
    all_rolls = pd.concat([rolls, extra], ignore_index=True).sort_values("roll_time_utc").reset_index(drop=True)
    mk = Market.from_frames(name, bars, all_rolls, _news(), window_start - dt.timedelta(days=1), None)
    mk.era = np.array([d.year if t else 0 for d, t in zip(mk.sessions, mk.tradable)])
    return mk, [str(d) for d in dropped["session"]]


# =========================================================================== running versions
_MK: dict = {}


def _per_year(daily: pd.Series) -> dict:
    if not len(daily):
        return {}
    years = pd.Index([d.year for d in daily.index])
    return {f"net_{y}": float(v) for y, v in daily.groupby(years).sum().items()}


def _one(mk, rec) -> tuple[dict, np.ndarray, np.ndarray]:
    cfg = version_config(rec)
    base = {"id": rec.get("id"), "set": version_set(rec), "setup": cfg.get("setup"),
            "setup_chart": cfg.get("setup_chart"), "trigger_chart": cfg.get("trigger_chart"),
            "market": mk.name}
    try:
        tr = sg.run_version(mk, cfg)
        d = engine.daily_pnl(mk, tr)
        m = engine.metrics(mk, tr, d)
        m.update(_per_year(d))
        nz = np.flatnonzero(d.to_numpy() != 0)
        return {**base, **m, "error": ""}, nz, d.to_numpy()[nz].astype(np.float32)
    except Exception as e:  # noqa: BLE001
        return {**base, "trades": 0, "net": 0.0, "sharpe": 0.0, "error": f"{type(e).__name__}: {e}"}, \
            np.zeros(0, np.int64), np.zeros(0, np.float32)


def _work(args):
    market, recs = args
    sg.clear_cache()
    mk = _MK[market]
    return [_one(mk, r) for r in recs]


def _sort_key(rec):
    c = version_config(rec)
    return (str(c.get("setup")), str(c.get("setup_chart")), str(c.get("trigger_chart")),
            str(c.get("swing_strength")), json.dumps(c, sort_keys=True, default=str))


def run_all(markets: dict, versions: list[dict], workers: int | None = None, chunk: int = 150):
    """Every version on every market. Returns {market: (metrics frame, [(id, nz idx, values)])}."""
    global _MK
    _MK = markets
    recs = sorted(versions, key=_sort_key)
    jobs = [(m, recs[i:i + chunk]) for m in markets for i in range(0, len(recs), chunk)]
    workers = workers or max(1, min(os.cpu_count() or 1, len(jobs)))
    if workers > 1 and len(jobs) > 1:
        with mp.get_context("fork").Pool(workers) as pool:
            parts = pool.map(_work, jobs, chunksize=1)
    else:
        parts = [_work(j) for j in jobs]
    out = {m: ([], []) for m in markets}
    for (m, _), res in zip(jobs, parts):
        for met, nz, val in res:
            out[m][0].append(met)
            out[m][1].append((met["id"], nz, val))
    return {m: (pd.DataFrame(rows), daily) for m, (rows, daily) in out.items()}


# =========================================================================== matched random twins
def twins_test(mk: Market, trades: pd.DataFrame, stream: str, n_sets: int = TWIN_SETS) -> dict:
    """Give each real trade a twin: same direction, a random entry minute in the
    same 30 minutes of the day (window sessions, outside roll blackouts), the
    same stop and target distances in 5m ATR, the same holding time and the
    same engine costs. Returns the real total and the share of twin sets that
    made at least as much."""
    if not len(trades):
        return {"real_trades": 0, "real_net": 0.0, "p_value": np.nan, "twin_mean_net": np.nan}
    g = rng(stream)
    tr = trades
    if len(tr) > TWIN_MAX_TRADES:
        tr = tr.iloc[np.sort(g.choice(len(tr), TWIN_MAX_TRADES, replace=False))]
    ch = mk.charts["5m"]
    def atr_at(idx):
        i5 = np.searchsorted(ch.avail_ns, mk.ts_ns[idx] + 60_000_000_000, side="right") - 1
        return np.where(i5 >= 0, ch.atr[np.maximum(i5, 0)], np.nan)
    e = tr["entry_idx"].to_numpy(np.int64)
    a = atr_at(e)
    ok = np.isfinite(a) & (a > 0)
    tr, e, a = tr[ok], e[ok], a[ok]
    side = tr["side"].to_numpy(np.int64)
    d_stop = np.abs(tr["entry_px"].to_numpy() - tr["stop"].to_numpy()) / a
    tg = tr["target"].to_numpy(float)
    d_tgt = np.abs(tg - tr["entry_px"].to_numpy()) / a
    hold = np.maximum(tr["exit_idx"].to_numpy(np.int64) - e, 1)
    bucket = mk.et_min[e] // 30
    pool_ok = mk.tradable[mk.sess] & ~mk.no_entry
    pool_ok[-2:] = False
    all_b = mk.et_min // 30
    pools = {b: np.flatnonzero(pool_ok & (all_b == b)) for b in np.unique(bucket)}
    n = len(tr)
    T = np.empty((n_sets, n), np.int64)
    for k in range(n):
        p = pools[bucket[k]]
        T[:, k] = g.choice(p, n_sets) if len(p) else -1
    t = T.ravel()
    good = t >= 0
    S = np.repeat(side[None, :], n_sets, 0).ravel()
    at = atr_at(np.maximum(t, 0))
    good &= np.isfinite(at) & (at > 0)
    px = mk.c[np.maximum(t, 0)]
    stop = px - S * np.repeat(d_stop[None, :], n_sets, 0).ravel() * at
    dt_ = np.repeat(d_tgt[None, :], n_sets, 0).ravel()
    target = np.where(np.isfinite(dt_), px + S * dt_ * at, np.nan)
    te = np.minimum(t + np.repeat(hold[None, :], n_sets, 0).ravel(), mk.n - 1)
    set_id = np.repeat(np.arange(n_sets)[:, None], n, 1).ravel()
    o = dict(t=t[good], side=S[good], stop=stop[good], target=target[good], time_exit=te[good],
             size=np.repeat(tr["size"].to_numpy(float)[None, :], n_sets, 0).ravel()[good],
             tag=set_id[good])
    res = engine.run(mk, o, independent=True)
    totals = res.groupby("tag")["dollars"].sum().reindex(range(n_sets), fill_value=0.0).to_numpy()
    real = float(tr["dollars"].sum())
    return {"real_trades": int(n), "real_net": real, "twin_mean_net": float(totals.mean()),
            "twin_p95_net": float(np.percentile(totals, 95)), "p_value": float((totals >= real).mean()),
            "beats_random": bool((totals >= real).mean() < 0.05), "sets": int(n_sets)}


# =========================================================================== the run
def _daily_matrix(mk, daily_list, ids):
    """Rebuild full daily vectors for a list of version ids."""
    pos = {vid: (nz, val) for vid, nz, val in daily_list}
    S = int(mk.tradable.sum())
    M = np.zeros((len(ids), S), np.float64)
    for i, vid in enumerate(ids):
        nz, val = pos.get(vid, (np.zeros(0, np.int64), np.zeros(0)))
        M[i, nz] = val
    return M


def _equal_weight(mk, metrics: pd.DataFrame, daily_list) -> pd.DataFrame:
    days = mk.sessions[mk.tradable]
    years = np.array([d.year for d in days])
    rows = []
    for (setup, chart), grp in metrics.groupby(["setup", "setup_chart"]):
        M = _daily_matrix(mk, daily_list, grp["id"].tolist())
        avg = M.mean(axis=0)
        s = pd.Series(avg, index=days)
        r = {"market": mk.name, "setup": setup, "setup_chart": chart, "versions": int(len(grp)),
             "net": float(avg.sum()), "sharpe": engine.sharpe(s)}
        per_year_ok = True
        for y in np.unique(years):
            ys = s[years == y]
            r[f"net_{y}"] = float(ys.sum())
            r[f"sharpe_{y}"] = engine.sharpe(ys)
            per_year_ok &= ys.sum() > 0
        r["held"] = bool(per_year_ok and r["sharpe"] >= HELD_SHARPE)
        rows.append(r)
    return pd.DataFrame(rows)


def _dial_shares(versions: list[dict], held_ids: set, market: str) -> pd.DataFrame:
    cfgs = pd.DataFrame([{**version_config(r), "id": r.get("id")} for r in versions])
    if cfgs.empty:
        return pd.DataFrame()
    held = cfgs["id"].isin(held_ids)
    rows = []
    for dial in [c for c in cfgs.columns if c != "id"]:
        allv = cfgs[dial].astype(str).value_counts(normalize=True)
        hv = cfgs.loc[held, dial].astype(str).value_counts(normalize=True) if held.any() else pd.Series(dtype=float)
        for val, share in allv.items():
            hs = float(hv.get(val, 0.0))
            rows.append({"market": market, "dial": dial, "value": val, "share_all": float(share),
                         "share_held": hs, "lift": hs / share if share else np.nan,
                         "held_versions": int(held.sum())})
    return pd.DataFrame(rows)


def _read_optional_json(path: Path, default):
    return io.read_json(path) if path.exists() else default


def read_selections(fd: Path | None = None) -> tuple[set, list, list]:
    """Candidates (ids), working setups ({setup, chart, market}) and named versions
    ({name, id}), accepting the funnel's wrapped shapes ({"candidates": [...]},
    {"working": [...]}, {"named": [...]}) or bare lists."""
    fd = fd or funnel_dir()
    c = _read_optional_json(fd / "candidates.json", [])
    c = c.get("candidates", []) if isinstance(c, dict) else c
    cand = {x["id"] if isinstance(x, dict) else x for x in c}
    w = _read_optional_json(fd / "working_setups.json", [])
    w = w.get("working", []) if isinstance(w, dict) else w
    work = [{"setup": x["setup"], "chart": x["chart"], "market": x["market"]} for x in w]
    n = _read_optional_json(fd / "named_versions.json", [])
    n = n.get("named", []) if isinstance(n, dict) else n
    named = [{"name": x.get("name"), "id": x.get("id")} for x in n]
    return cand, work, named


def run(source: str = "final", versions: list[dict] | None = None, workers: int | None = None,
        twin_sets: int = TWIN_SETS) -> dict:
    """The final test. source="rehearsal" changes only where the bars come from
    (last discovery month, shifted) and where results go."""
    if source == "final":
        refuse_if_done()
    man = preflight()
    od = out_dir(source)
    if source == "final":
        reh = od.parent / "final_rehearsal" / "REHEARSAL_OK.json"
        if not reh.exists() or io.read_json(reh).get("selection_hashes") != man:
            raise PreflightError("no passing rehearsal for these selections; run `rehearse` first")
    all_versions = read_versions()
    if versions is None:
        versions = all_versions
    fd = funnel_dir()
    candidates, working, named = read_selections(fd)

    loaded = load_frames(source)                      # the only switch on `source`
    warm, start, end = window_for(source)
    markets, dropped = {}, {}
    for m, (bars, rolls) in loaded["frames"].items():
        markets[m], dropped[m] = build_market(m, bars, rolls, start)
    del loaded["frames"]

    results = run_all(markets, versions, workers)
    od.mkdir(parents=True, exist_ok=True)
    written = []
    errors = 0
    tables = {}
    for m, (met, daily_list) in results.items():
        mk = markets[m]
        met["held"] = (met["net"] > 0) & (met["sharpe"] >= HELD_SHARPE)
        met["candidate"] = met["id"].isin(candidates)
        errors += int((met["error"] != "").sum())
        written.append(io.write_table(met, od / f"metrics_{m}.parquet"))
        days = mk.sessions[mk.tradable]
        for setup in sorted(met["setup"].dropna().unique()):
            ids = set(met.loc[met["setup"] == setup, "id"])
            rows = [(vid, days[nz], val) for vid, nz, val in daily_list if vid in ids and len(nz)]
            df = pd.DataFrame({"id": np.concatenate([[r[0]] * len(r[1]) for r in rows]) if rows else [],
                               "day": np.concatenate([r[1] for r in rows]) if rows else [],
                               "pnl": np.concatenate([r[2] for r in rows]).astype(np.float32) if rows else []})
            written.append(io.write_table(df, od / "daily" / m / f"{setup}.parquet"))
        tables[m] = met
        ew = _equal_weight(mk, met, daily_list)
        tables[f"setup_{m}"] = ew
        written.append(io.write_table(ew, od / f"setup_chart_year_{m}.csv"))

    # ---- what held up
    share_rows, chart_rows = [], []
    for m in MARKETS:
        met = tables[m]
        for label, sel in [("all", np.ones(len(met), bool)), ("candidates", met["candidate"].to_numpy())] + \
                [(f"set:{s}", (met["set"] == s).to_numpy()) for s in sorted(met["set"].unique()) if s]:
            n = int(sel.sum())
            share_rows.append({"market": m, "group": label, "versions": n,
                               "held": int(met.loc[sel, "held"].sum()),
                               "share_held": float(met.loc[sel, "held"].mean()) if n else np.nan})
        for chart, grp in met.groupby("setup_chart"):
            chart_rows.append({"market": m, "setup_chart": chart, "versions": int(len(grp)),
                               "share_made_money": float((grp["net"] > 0).mean())})
    written.append(io.write_table(pd.DataFrame(share_rows), od / "share_held.csv"))
    written.append(io.write_table(pd.DataFrame(chart_rows), od / "chart_made_money.csv"))

    by_id = {r.get("id"): r for r in all_versions}
    # working setups against matched random trades over the same window
    twin_rows = []
    pairs = sorted({(w["setup"], w["chart"]) for w in working if "setup" in w and "chart" in w})
    for setup, chart in pairs:
        ids = [r.get("id") for r in versions
               if version_config(r).get("setup") == setup and version_config(r).get("setup_chart") == chart]
        if not ids:
            continue
        g = rng(f"final:twins:pick:{setup}:{chart}")
        if len(ids) > TWIN_MAX_VERSIONS:
            ids = list(g.choice(np.array(ids, dtype=object), TWIN_MAX_VERSIONS, replace=False))
        for m, mk in markets.items():
            sg.clear_cache()
            trs = [sg.run_version(mk, version_config(by_id[i])) for i in ids]
            trs = [t for t in trs if len(t)]
            tr = pd.concat(trs, ignore_index=True) if trs else pd.DataFrame()
            r = twins_test(mk, tr, f"final:twins:{setup}:{chart}:{m}", twin_sets)
            twin_rows.append({"market": m, "setup": setup, "setup_chart": chart, "versions_used": len(ids), **r})
    written.append(io.write_table(pd.DataFrame(twin_rows), od / "working_vs_random.csv"))

    # best usual-settings version of each setup, picked by its discovery result
    best_rows = []
    disc_path = fd / "metrics_NQ.parquet"
    if disc_path.exists():
        disc = io.read_table(disc_path)
        common_ids = {r.get("id") for r in all_versions if version_set(r) == "common"}
        disc = disc[disc["id"].isin(common_ids)]
        if "setup" not in disc.columns:
            disc["setup"] = disc["id"].map(lambda i: version_config(by_id[i]).get("setup"))
        sort_col = "sharpe" if "sharpe" in disc.columns else "net"
        for setup, grp in disc.groupby("setup"):
            best = grp.sort_values([sort_col, "net"] if "net" in grp.columns else [sort_col]).iloc[-1]
            for m in MARKETS:
                fm = tables[m].set_index("id")
                if best["id"] in fm.index:
                    best_rows.append({"setup": setup, "id": best["id"], "discovery_nq_sharpe": float(best[sort_col]),
                                      "market": m, **fm.loc[best["id"]][["trades", "net", "sharpe", "held"]].to_dict()})
    written.append(io.write_table(pd.DataFrame(best_rows), od / "best_common_by_setup.csv"))

    named_rows = []
    for nv in named:
        for m in MARKETS:
            fm = tables[m].set_index("id")
            if nv.get("id") in fm.index:
                named_rows.append({"name": nv.get("name"), "id": nv["id"], "market": m,
                                   **fm.loc[nv["id"]][["trades", "net", "sharpe", "held"]].to_dict()})
    written.append(io.write_table(pd.DataFrame(named_rows), od / "named_versions.csv"))

    dial_tabs = [_dial_shares(versions, set(tables[m].loc[tables[m]["held"], "id"]), m) for m in MARKETS]
    written.append(io.write_table(pd.concat(dial_tabs, ignore_index=True), od / "dials_held_in_common.csv"))

    summary = {"source": source, **loaded["prov"], "versions": len(versions), "errors": errors,
               "dropped_sessions": dropped, "selection_hashes": man,
               "share_held": share_rows, **stamp()}
    written.append(io.write_json(summary, od / "summary.json"))
    if source == "rehearsal":
        if errors:
            raise RuntimeError(f"rehearsal: {errors} version runs failed; fix them before unlocking "
                               f"(see {od / 'metrics_NQ.parquet'} column 'error')")
        io.write_json({"selection_hashes": man, "versions": len(versions), **stamp()}, od / "REHEARSAL_OK.json")
    else:
        files = {str(p.relative_to(od)): sha256_file(p) for p in written}
        io.write_json({"files": files, "errors": errors, **stamp()}, od / "DONE.json")
    return summary


def rehearsal_subset(n: int = REHEARSAL_VERSIONS) -> list[dict]:
    """Named versions plus an even, seeded spread across setups."""
    vs = read_versions()
    named = {x["id"] for x in read_selections()[2]}
    out = [v for v in vs if v.get("id") in named]
    rest = [v for v in vs if v.get("id") not in named]
    by_setup: dict = {}
    for v in rest:
        by_setup.setdefault(version_config(v).get("setup"), []).append(v)
    g = rng("final:rehearsal_subset")
    per = max(1, (n - len(out)) // max(1, len(by_setup)))
    for s in sorted(by_setup, key=str):
        grp = by_setup[s]
        take = g.choice(len(grp), min(per, len(grp)), replace=False)
        out += [grp[i] for i in sorted(take)]
    return out


# =========================================================================== for later analyses
def load_final_results() -> dict:
    """Prompt 5 and every later analysis: the saved final results only."""
    od = out_dir("final")
    if not (od / "DONE.json").exists():
        raise FileNotFoundError("no completed final test in results/final/")
    done = io.read_json(od / "DONE.json")
    for rel, h in done["files"].items():
        if sha256_file(od / rel) != h:
            raise RuntimeError(f"results/final/{rel} changed after the final test")
    out = {"done": done, "summary": io.read_json(od / "summary.json")}
    for rel in done["files"]:
        if rel.endswith((".csv", ".parquet")):
            out[rel] = io.read_table(od / rel)
    return out
