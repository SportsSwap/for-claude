"""Prompt 3: build the version sets, run them on NQ and ES discovery, funnel, judge.

    LAB_ROOT=... python scripts/run_funnel.py gen    [--scale 1.0] [--workers 4]
    LAB_ROOT=... python scripts/run_funnel.py run    [--workers 4]
    LAB_ROOT=... python scripts/run_funnel.py report

`gen` writes versions.jsonl, versions.sha256, stages.json and stages.sha256 and
computes only NQ signal counts (no P&L). `run` refuses to start unless both
hashes still match. `report` writes the funnel, judgment, tables and the
selection manifest that Prompt 4 checks before unlocking.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import engine, funnel as fn, io  # noqa: E402
from lab import strategy as sg  # noqa: E402
from lab.config import P, stamp  # noqa: E402
from lab.market import Market  # noqa: E402
from lab.seed import rng  # noqa: E402

FULL_SPREAD_PER_SETUP = 4000
FULL_SAMPLED_PER_SETUP = 4733          # the reference lab drew 47,329 over 10 setups
CHUNK = 60


def out_dir() -> Path:
    d = P.results() / "funnel"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# =========================================================================== workers
_MK: dict = {}


def _init(markets):
    for m in markets:
        _MK[m] = Market.load(m)


def _evict(limit=300):
    c = sg._CACHE
    keys = [k for k in c if len(k) > 1 and k[1] in ("cand", "obj")]
    if len(keys) > limit:
        for k in keys:
            del c[k]


def cache_sort_key(v):
    keys = sg._setup_keys(v["setup"])
    return (v["setup"], v["setup_chart"], tuple(str(v[k]) for k in keys), v["trigger_chart"],
            v["confirmation"], v["entry"])


def _signals_chunk(chunk):
    mk = _MK["NQ"]
    out = []
    for vid, v in chunk:
        out.append((vid, sg.signals(mk, v)))
        _evict()
    return out


def _run_chunk(args):
    chunk, part = args
    rows = {"NQ": [], "ES": []}
    daily = {"NQ": [], "ES": []}
    twins = []
    st = fn.STAGES
    for vid, v in chunk:
        for m in ("NQ", "ES"):
            mk = _MK[m]
            tr = sg.run_version(mk, v)
            met, d = fn.version_metrics(mk, tr)
            rows[m].append({"id": vid, **met})
            nz = d[d != 0]
            if len(nz):
                daily[m].append(pd.DataFrame({"id": vid, "session": nz.index, "pnl": nz.to_numpy()}))
            if m == "NQ" and met["trades"] >= st["stage1_min_trades"] and met["net"] > 0 \
                    and met["sharpe"] >= st["stage3_min_sharpe"]:
                t = fn.twin_test(mk, v, tr, st["stage4_twin_sets"], st["stage4_twins_per_trade"], f"twins:{vid}")
                twins.append({"id": vid, "twin_p": t["p"], "twin_mean": t["twin_mean"], "twin_p95": t["twin_p95"]})
        _evict()
    for m in ("NQ", "ES"):
        if daily[m]:
            io.write_table(pd.concat(daily[m], ignore_index=True),
                           out_dir() / "daily_parts" / m / f"part_{part:05d}.parquet")
    return rows, twins


def _pool(workers, markets):
    ctx = mp.get_context("fork")
    return ctx.Pool(workers, initializer=_init, initargs=(markets,))


# =========================================================================== gen
def gen(scale: float, workers: int, pool_factor: float = 1.5, max_rounds: int = 8):
    t_start = time.time()
    n_spread = max(10, int(round(FULL_SPREAD_PER_SETUP * scale)))
    n_sampled = max(10, int(round(FULL_SAMPLED_PER_SETUP * scale)))
    spaces = {s: fn.Space.build(s) for s in fn.SETUPS}
    g = rng("funnel:gen")
    sig_cache: dict[str, int] = {}
    pool_rows = {s: np.zeros((0, len(spaces[s].dials)), np.int64) for s in fn.SETUPS}
    pool_keys = {s: {} for s in fn.SETUPS}   # canonical key -> the version as drawn
    eligible = {s: [] for s in fn.SETUPS}
    drawn = {s: 0 for s in fn.SETUPS}
    with _pool(workers, ["NQ"]) as pool:
        def count(versions):
            todo = [(fn.key_of(v), v) for v in versions if fn.key_of(v) not in sig_cache]
            todo.sort(key=lambda kv: cache_sort_key(kv[1]))
            chunks = [todo[i:i + CHUNK] for i in range(0, len(todo), CHUNK)]
            for res in pool.imap_unordered(_signals_chunk, chunks):
                for k, n in res:
                    sig_cache[k] = n
        # spread: rounds of uniform random draws until each setup has enough eligible versions
        for r in range(max_rounds):
            need = [s for s in fn.SETUPS if len(eligible[s]) < pool_factor * n_spread]
            if not need:
                break
            batch = []
            for s in need:
                rows = spaces[s].draw(g, n_spread)
                for row in rows:
                    v = spaces[s].to_version(row)
                    k = fn.key_of(v)
                    if k in pool_keys[s]:
                        continue
                    pool_keys[s][k] = v
                    drawn[s] += 1
                    batch.append(v)
            log(f"spread round {r}: counting signals for {len(batch)} draws")
            count(batch)
            for s in need:
                eligible[s] = [k for k in pool_keys[s] if sig_cache[k] >= fn.STAGES["min_signals_to_grade"]]
            log("eligible: " + ", ".join(f"{s}={len(eligible[s])}/{drawn[s]}" for s in fn.SETUPS))
        spread = {}
        for s in fn.SETUPS:
            vs = [pool_keys[s][k] for k in sorted(eligible[s])]
            rows = spaces[s].rows_of(vs)
            pick = fn.greedy_fill(spaces[s], rows, n_spread, rng(f"funnel:greedy:{s}"))
            spread[s] = [vs[i] for i in pick]
        # sampled: as people trade them
        sampled = {}
        for s in fn.SETUPS:
            sampled[s] = fn.sampled_versions(spaces[s], n_sampled, rng(f"funnel:sampled:{s}"), set())
        log("counting signals for the sampled set")
        count([v for s in fn.SETUPS for v in sampled[s]])
        common = fn.common_versions()
        named = {name: v for name, (_, v) in fn.NAMED.items()}
        log(f"counting signals for the common set ({len(common)}) and named versions")
        count(common + list(named.values()))
    # write versions.jsonl
    lines = []
    def add(vid, set_, v, name=None):
        assert fn.dials.is_valid(fn.SPEC, v), v
        n = sig_cache[fn.key_of(v)]
        rec = {"id": vid, "set": set_, **({"name": name} if name else {}), "nq_signals": n,
               "graded": bool(set_ in ("common", "named") or n >= fn.STAGES["min_signals_to_grade"]),
               **fn.config_of(v)}
        lines.append(json.dumps(rec, sort_keys=True, default=str))
    for s in fn.SETUPS:
        for i, v in enumerate(spread[s], 1):
            add(f"S-{s}-{i:05d}", "spread", v)
    for name, v in named.items():
        add("N-" + name.lower().replace(" ", "_"), "named", v, name)
    per = {}
    for v in common:
        per[v["setup"]] = per.get(v["setup"], 0) + 1
        add(f"C-{v['setup']}-{per[v['setup']]:05d}", "common", v)
    for s in fn.SETUPS:
        for i, v in enumerate(sampled[s], 1):
            add(f"R-{s}-{i:05d}", "sampled", v)
    body = ("\n".join(lines) + "\n").encode()
    (out_dir() / "versions.jsonl").write_bytes(body)
    (out_dir() / "versions.sha256").write_text(fn.sha256_bytes(body) + "  versions.jsonl\n")
    st = json.dumps(fn.STAGES, indent=2, sort_keys=True).encode()
    (out_dir() / "stages.json").write_bytes(st)
    (out_dir() / "stages.sha256").write_text(fn.sha256_bytes(st) + "  stages.json\n")
    shares = []
    for s in fn.SETUPS:
        sp = spaces[s]
        got = sp.shares(sp.rows_of(spread[s]))
        rnd = sp.shares(sp.draw(rng(f"funnel:sharecheck:{s}"), len(spread[s])))
        for i, (d, x) in enumerate(sp.slots):
            shares.append({"setup": s, "dial": d, "value": str(x), "target": sp.target[i], "spread": got[i],
                           "random_draw_same_n": rnd[i]})
    io.write_table(pd.DataFrame(shares), out_dir() / "spread_shares.csv")
    summary = {"scale": scale, "spread_per_setup": n_spread, "sampled_per_setup": n_sampled,
               "spread_draws_checked": drawn, "spread_eligible": {s: len(eligible[s]) for s in fn.SETUPS},
               "counts": {k: sum(1 for l in lines if json.loads(l)["set"] == k) for k in ("spread", "named", "common", "sampled")},
               "graded": sum(1 for l in lines if json.loads(l)["graded"]),
               "versions_sha256": fn.sha256_bytes(body), "stages_sha256": fn.sha256_bytes(st),
               "wall_seconds": round(time.time() - t_start, 1), **stamp()}
    io.write_json(summary, out_dir() / "gen_summary.json")
    log(json.dumps(summary["counts"]) + f" graded={summary['graded']} in {summary['wall_seconds']}s")


# =========================================================================== run
def load_versions(check=True):
    body = (out_dir() / "versions.jsonl").read_bytes()
    if check:
        want = (out_dir() / "versions.sha256").read_text().split()[0]
        if fn.sha256_bytes(body) != want:
            raise SystemExit("versions.jsonl changed after it was hashed; refusing to run")
        st = (out_dir() / "stages.json").read_bytes()
        if fn.sha256_bytes(st) != (out_dir() / "stages.sha256").read_text().split()[0]:
            raise SystemExit("stages.json changed after it was hashed; refusing to run")
    return [json.loads(l) for l in body.decode().splitlines() if l.strip()]


def run(workers: int, limit: int | None = None):
    t0 = time.time()
    vs = [r for r in load_versions() if r["graded"]]
    if limit:
        vs = vs[:limit]
    items = [(r["id"], fn.config_of(r)) for r in vs]
    items.sort(key=lambda kv: cache_sort_key(kv[1]))
    chunks = [(items[i:i + CHUNK], i // CHUNK) for i in range(0, len(items), CHUNK)]
    rows = {"NQ": [], "ES": []}
    twins = []
    import shutil
    shutil.rmtree(out_dir() / "daily_parts", ignore_errors=True)
    done = 0
    with _pool(workers, ["NQ", "ES"]) as pool:
        for r, tw in pool.imap_unordered(_run_chunk, chunks):
            for m in rows:
                rows[m] += r[m]
            twins += tw
            done += len(r["NQ"])
            if done % (CHUNK * 20) < CHUNK:
                el = time.time() - t0
                log(f"ran {done}/{len(items)} versions, {el:.0f}s, eta {el / done * (len(items) - done):.0f}s")
    for m in rows:
        io.write_table(pd.DataFrame(rows[m]), out_dir() / f"metrics_{m}.parquet")
    io.write_table(pd.DataFrame(twins, columns=["id", "twin_p", "twin_mean", "twin_p95"]), out_dir() / "twins.parquet")
    # daily P&L per market and setup
    setup_of = {r["id"]: r["setup"] for r in vs}
    for m in ("NQ", "ES"):
        parts = sorted((out_dir() / "daily_parts" / m).glob("*.parquet"))
        df = pd.concat([io.read_table(p) for p in parts], ignore_index=True) if parts else pd.DataFrame(columns=["id", "session", "pnl"])
        df["setup"] = df["id"].map(setup_of)
        for s, g in df.groupby("setup"):
            io.write_table(g.drop(columns="setup").reset_index(drop=True), out_dir() / "daily" / m / f"{s}.parquet")
    shutil.rmtree(out_dir() / "daily_parts", ignore_errors=True)
    io.write_json({"versions_run": len(items), "wall_seconds": round(time.time() - t0, 1),
                   "twin_tests": len(twins), **stamp()}, out_dir() / "run_summary.json")
    log(f"run done: {len(items)} versions in {time.time() - t0:.0f}s")


# =========================================================================== report
def report():
    vs = load_versions()
    conf = pd.DataFrame(vs).set_index("id")
    graded = conf[conf.graded]
    nq = io.read_table(out_dir() / "metrics_NQ.parquet")
    es = io.read_table(out_dir() / "metrics_ES.parquet")
    tw = io.read_table(out_dir() / "twins.parquet")
    df = fn.apply_stages(nq, es, tw).set_index("id").join(conf)
    df.reset_index().to_parquet(out_dir() / "funnel.parquet", index=False)
    stages = ["s1", "s2", "s3", "s4", "candidate"]
    def shares(by):
        g = df.groupby(by)
        t = g[stages + ["s5", "both_eras"]].mean()
        t.insert(0, "versions", g.size())
        return t.reset_index()
    io.write_table(shares("setup"), out_dir() / "stage_share_by_setup.csv")
    io.write_table(shares(["setup", "setup_chart"]).rename(columns={"setup_chart": "chart"}),
                   out_dir() / "stage_share_by_setup_chart.csv")
    io.write_table(shares("setup_chart").rename(columns={"setup_chart": "chart"}), out_dir() / "stage_share_by_chart.csv")
    io.write_table(shares("set"), out_dir() / "stage_share_by_set.csv")
    dial_cols = [c for c in fn.SPEC["dials"] if c in df.columns]
    long = []
    for d in dial_cols + ["trigger_chart"]:
        sub = df[df[d].notna()]
        g = sub.groupby(sub[d].astype(str))
        t = g[stages].mean()
        t.insert(0, "versions", g.size())
        t = t.reset_index().rename(columns={d: "value"})
        t.insert(0, "dial", d)
        t.insert(1, "is_filter", d in fn.FILTER_OFF)
        long.append(t)
    io.write_table(pd.concat(long, ignore_index=True), out_dir() / "stage_share_by_dial.csv")
    # win rate against profit
    w = df[df.nq_trades >= 30].copy()
    w["win_rate_bin"] = pd.cut(w.nq_win_rate, np.linspace(0, 1, 11), include_lowest=True).astype(str)
    g = w.groupby("win_rate_bin")
    wr = pd.DataFrame({"versions": g.size(), "mean_net": g.nq_net.mean(), "share_profitable": g.nq_net.gt(0).mean(),
                       "mean_sharpe": g.nq_sharpe.mean(), "mean_avg_R": g.nq_avg_R.mean()}).reset_index()
    io.write_table(wr, out_dir() / "win_rate_vs_profit.csv")
    corr = float(np.corrcoef(w.nq_win_rate, w.nq_net)[0, 1]) if len(w) > 2 else float("nan")
    # effect of each rule, everything else equal (common set)
    cm = df[df.set == "common"]
    eff = []
    for d in ["entry", "confirmation", "stop_ref", "target", "trend_filter", "session", "news", "setup_chart"]:
        others = [c for c in ["setup", "setup_chart", "trigger_chart"] + [x for x in dial_cols]
                  if c != d and c in cm.columns and not (d == "setup_chart" and c == "trigger_chart")]
        if d == "entry":
            others = [c for c in others if c != "confirmation"]
            col = cm["entry"].astype(str) + "/" + cm["confirmation"].astype(str)
        elif d == "confirmation":
            continue
        else:
            col = cm[d].astype(str)
        key = cm[others].astype(str).agg("|".join, axis=1)
        tab = pd.DataFrame({"key": key, "val": col, "net": cm.nq_net, "sharpe": cm.nq_sharpe, "es_net": cm.es_net})
        base_val = sorted(tab.val.unique())[0]
        base = tab[tab.val == base_val].set_index("key")
        for val in sorted(tab.val.unique()):
            if val == base_val:
                continue
            o = tab[tab.val == val].set_index("key").join(base, rsuffix="_base", how="inner")
            if not len(o):
                continue
            eff.append({"rule": "entry/confirmation" if d == "entry" else d, "baseline": base_val, "value": val,
                        "pairs": len(o), "mean_net_change_NQ": float((o.net - o.net_base).mean()),
                        "mean_sharpe_change_NQ": float((o.sharpe - o.sharpe_base).mean()),
                        "share_better_NQ": float((o.net > o.net_base).mean()),
                        "mean_net_change_ES": float((o.es_net - o.es_net_base).mean())})
    io.write_table(pd.DataFrame(eff), out_dir() / "rule_effects.csv")
    # named versions
    named = df[df.set == "named"]
    nm_cols = ["name", "setup", "setup_chart", "trigger_chart", "nq_trades", "nq_net", "nq_sharpe", "nq_win_rate",
               "nq_net_era1", "nq_net_era2", "es_trades", "es_net", "es_sharpe", "s1", "s2", "s3", "s4", "s5", "candidate"]
    io.write_table(named.reset_index()[["id"] + nm_cols], out_dir() / "named_versions.csv")
    # judge each setup as a whole
    era_of, daily_avg = {}, {}
    for m in ("NQ", "ES"):
        mk_sessions = None
        met = nq if m == "NQ" else es
        for s in fn.SETUPS:
            p = out_dir() / "daily" / m / f"{s}.parquet"
            if not p.exists():
                continue
            d = io.read_table(p)
            d["session"] = pd.to_datetime(d["session"]).dt.date
            d["chart"] = d["id"].map(graded["setup_chart"])
            for ch, gg in d.groupby("chart"):
                ids = graded[(graded.setup == s) & (graded.setup_chart == ch)].index
                daily_avg[(s, ch, m)] = gg.groupby("session")["pnl"].sum() / len(ids)
        era_of[m] = {}
    # full session calendar and eras from a market load (sessions with zero P&L must count)
    from lab.config import load_windows
    w = load_windows()
    sess_all = {}
    for m in ("NQ", "ES"):
        c = io.read_table(P.clean() / f"{m}_1m.parquet", columns=["session"])
        days = sorted(set(pd.to_datetime(c["session"]).dt.date))
        days = [d for d in days if w.discovery[0] <= d <= w.discovery[1]]
        sess_all[m] = days
        era_of[m] = {d: (1 if d <= w.era1[1] else 2) for d in days}
    for k in list(daily_avg):
        daily_avg[k] = daily_avg[k].reindex(sess_all[k[2]], fill_value=0.0)
    judg = fn.judge_setups(daily_avg, era_of)
    io.write_table(judg, out_dir() / "setup_judgment.csv")
    # candidates, working setups, named versions, manifest
    cands = df[df.candidate].reset_index()
    cand_json = {"rule": fn.STAGES["candidate_rule"], "count": int(len(cands)),
                 "candidates": [{"id": r["id"], "config": fn.config_of(r.to_dict()),
                                 "nq": {k: r[f"nq_{k}"] for k in ("trades", "net", "sharpe", "net_era1", "net_era2")},
                                 "es": {k: r[f"es_{k}"] for k in ("trades", "net", "sharpe")}, "twin_p": r["twin_p"]}
                                for _, r in cands.iterrows()]}
    work = judg[judg.works]
    work_json = {"rule": fn.STAGES["setup_works_rule"], "count": int(len(work)),
                 "working": work[["setup", "chart", "market", "net", "sharpe"]].to_dict(orient="records"),
                 "all": judg.to_dict(orient="records")}
    named_json = {"named": [{"id": i, "name": r["name"], "definition": fn.NAMED[r["name"]][0],
                             "config": fn.config_of(r.to_dict())} for i, r in named.iterrows()]}
    files = {"candidates.json": cand_json, "working_setups.json": work_json, "named_versions.json": named_json}
    for name, obj in files.items():
        (out_dir() / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=float) + "\n")
    man = {name: fn.sha256_bytes((out_dir() / name).read_bytes())
           for name in ("versions.jsonl", "stages.json", "candidates.json", "working_setups.json", "named_versions.json")}
    funnel_counts = {"graded": int(len(df)), **{st_: int(df[st_].sum()) for st_ in stages + ["s5", "both_eras"]}}
    io.write_json({"files": man, "funnel_counts_nq": funnel_counts, "win_rate_profit_corr": corr,
                   "working_setups": int(len(work)), **stamp()}, out_dir() / "selection_manifest.json")
    print(json.dumps(funnel_counts, indent=1))
    print(judg.sort_values("sharpe", ascending=False).head(12).to_string(index=False))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["gen", "run", "report"])
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    if a.phase == "gen":
        gen(a.scale, a.workers)
    elif a.phase == "run":
        run(a.workers, a.limit)
    else:
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
