"""First Candle Rule backtest. See DECLARATION.md. Run from pa_lab with LAB_UNLOCK=final_test."""
import datetime as dt, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
LAB = Path("/home/user/for-claude/pa_lab"); sys.path.insert(0, str(LAB)); sys.path.insert(0, str(LAB / "scripts"))
import noise_band_qqq as nb  # noqa: E402
from lab.seed import rng  # noqa: E402
OUT = LAB / "results" / "first_candle_rule"
TICK, PV, COMM = 0.25, 20.0, 4.0
LAST_ENTRY = 149            # bar closing at 12:00
EXIT = 384                  # bar closing at 15:55

def day_trades(O, H, L, C):
    fh, fl = H[:5].max(), L[:5].min()
    side = 0; gap_lo = gap_hi = None; start = None
    for c in range(7, LAST_ENTRY + 1):          # gap needs bars c-2..c, all after 09:35 (index >= 5)
        a = c - 2
        if a < 5: continue
        if H[c] < L[a] and C[c] < fl: side, gap_lo, gap_hi, start = -1, H[c], L[a], c; break
        if L[c] > H[a] and C[c] > fh: side, gap_lo, gap_hi, start = 1, H[a], L[c], c; break
    if not side: return None
    retested = False
    for i in range(start + 1, LAST_ENTRY + 1):
        if side == -1:
            if C[i] > gap_hi: return None                 # closed beyond the far side: cancelled
            if H[i] >= gap_lo: retested = True
            eng = C[i-1] > O[i-1] and C[i] < O[i] and O[i] >= C[i-1] and C[i] <= O[i-1]
        else:
            if C[i] < gap_lo: return None
            if L[i] <= gap_hi: retested = True
            eng = C[i-1] < O[i-1] and C[i] > O[i] and O[i] <= C[i-1] and C[i] >= O[i-1]
        if retested and eng:
            entry = C[i]
            stop = (max(H[i], H[i-1]) + TICK) if side == -1 else (min(L[i], L[i-1]) - TICK)
            risk = abs(entry - stop)
            if risk < TICK: return None
            return {"side": side, "e": i, "entry": entry, "stop": stop, "risk": risk}
    return None

def run_exit(H, L, C, t, side):
    tgt = t["entry"] + side * 3 * t["risk"]
    for j in range(t["e"] + 1, EXIT + 1):
        hit_stop = (H[j] >= t["stop"]) if side == -1 else (L[j] <= t["stop"])
        hit_tgt = (L[j] <= tgt) if side == -1 else (H[j] >= tgt)
        if hit_stop: return t["stop"], j, "stop"
        if hit_tgt: return tgt, j, "target"
    return C[EXIT], EXIT, "15:55"

def pnl(side, entry, exitp):
    pts = side * (exitp - entry) - 2 * TICK        # one tick slippage each side
    return pts * PV - COMM, pts

def main(market):
    m = nb.load_minutes(market)
    days, A, _ = nb.rth_grid(m)
    O, H, L, C = (A[k] for k in ("open", "high", "low", "close"))
    rows = []
    for d in range(len(days)):
        if nb.period_of(days[d]) is None: continue
        t = day_trades(O[d], H[d], L[d], C[d])
        if t is None: continue
        xp, j, why = run_exit(H[d], L[d], C[d], t, t["side"])
        usd, pts = pnl(t["side"], t["entry"], xp)
        # the same entry the other way round (for the random-direction test)
        t2 = dict(t); s2 = -t["side"]
        t2["stop"] = t["entry"] - s2 * t["risk"]
        xp2, _, _ = run_exit(H[d], L[d], C[d], t2, s2)
        usd2, _ = pnl(s2, t["entry"], xp2)
        rows.append({"day": days[d], "period": nb.period_of(days[d]), "side": "long" if t["side"] > 0 else "short",
                     "entry_time": f"{(570 + t['e'] + 1)//60:02d}:{(570 + t['e'] + 1)%60:02d}", "entry": t["entry"],
                     "stop": t["stop"], "risk_pts": t["risk"], "exit": xp, "exit_reason": why, "usd": usd,
                     "R": usd / (t["risk"] * PV), "usd_other_way": usd2})
    tr = pd.DataFrame(rows); tr.to_csv(OUT / f"trades_{market}.csv", index=False)
    res = {}
    cal = {k: [x for x in days if nb.period_of(x) == k] for k in nb.PERIODS}
    for k in nb.PERIODS:
        g = tr[tr.period == k]
        daily = g.set_index("day")["usd"].reindex(cal[k], fill_value=0.0)
        eq = daily.cumsum()
        res[k] = {"days": len(cal[k]), "trades": int(len(g)), "win_rate": round(float((g.usd > 0).mean()), 3),
                  "targets": int((g.exit_reason == "target").sum()), "stops": int((g.exit_reason == "stop").sum()),
                  "net_usd_1_NQ": round(float(g.usd.sum())), "avg_R": round(float(g.R.mean()), 3),
                  "sharpe": round(float(daily.mean() / daily.std(ddof=1) * math.sqrt(252)), 2) if daily.std() > 0 else 0.0,
                  "max_dd_usd": round(float((eq.cummax().clip(lower=0) - eq).max())),
                  "longs": int((g.side == "long").sum()), "shorts": int((g.side == "short").sum())}
    g = rng(f"fcr_null_{market}")
    flips = g.integers(0, 2, size=(1000, len(tr)))
    tot = np.where(flips == 1, tr["usd"].to_numpy()[None, :], tr["usd_other_way"].to_numpy()[None, :]).sum(axis=1)
    res["random_direction"] = {"real": round(float(tr.usd.sum())), "random_mean": round(float(tot.mean())),
                               "p95": round(float(np.percentile(tot, 95))), "p_value": float((tot >= tr.usd.sum()).mean())}
    tr["year"] = tr["day"].map(lambda x: x.year)
    res["by_year_usd"] = {int(y): round(float(v)) for y, v in tr.groupby("year")["usd"].sum().items()}
    res["works"] = bool(all(res[k]["net_usd_1_NQ"] > 0 for k in nb.PERIODS) and res["random_direction"]["p_value"] < 0.05)
    return res

if __name__ == "__main__":
    out = {m: main(m) for m in ("NQ", "ES")}
    (OUT / "results.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))
