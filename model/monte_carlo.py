#!/usr/bin/env python3
"""Monte Carlo simulation of the PLS Group valuation.

Mirrors the Scenario Engine's FCFF mechanics exactly, then randomises the inputs the
model treats as point estimates. The point of the exercise is not a prettier number:
it is to ask how often the recommendation is right, given that every input is uncertain.

Random variables, and why each is drawn the way it is:
  price level      lognormal. A commodity price forecast is wrong by a MULTIPLE, not by
                   an increment, and the error persists across the path rather than
                   resetting each year, so one persistent factor plus small annual noise.
  unit cost        normal, tight. Costs are disclosed and guided within a A$50/t band.
  P2000 proceeds   Bernoulli, but CONDITIONED ON THE PRICE DRAW. A board sanctions a
                   A$1.2bn expansion when the price supports it. Drawing the decision
                   independently of price would destroy real option value, by letting the
                   project fail in exactly the states where it is worth most. The
                   conditional probability is calibrated so the unconditional rate is 70%,
                   matching the risking used in the sum-of-the-parts.
  Colina proceeds  Same treatment at a lower base rate, and only after P2000.
  WACC             normal. The CAPM inputs are prescribed; the gearing assumption is not.
  conversion       normal on the resource-to-reserve rate, which sets the terminal life.

Run:  python3 model/monte_carlo.py [trials]
"""
import json, sys, statistics as st
import numpy as np

sys.path.insert(0, 'model')
import params as P

N        = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
SEED     = 20260906
SHARES   = P.SHARES_OUT_M
NETCASH  = P.CASH_FY26 - P.DEBT_FY26
LASTCLOSE= P.SHARE_PRICE
TARGET   = 6.1381
FCST     = P.FCST
NY       = len(FCST)
ADJ, ROY, TAX, NWC, INFL = 0.054, P.ROYALTY_RATE, P.TAX_RATE, P.NWC_PCT_REVENUE, P.INFLATION
DA_RATE, PPE0, CORP      = 0.115, 3813.0, P.CORP_COST_AM
MASSPULL                 = P.RESERVE_GRADE * 0.765 / 0.052
FX    = np.array([P.AUDUSD[y] for y in FCST])
BASEP = np.array([P.PRICE_DECK["base"][y] for y in FCST], dtype=float)
BASEC = np.array([P.COST_DECK["base"][y]  for y in FCST], dtype=float)
BASEK = np.array([P.CAPEX_DECK["base"][y] for y in FCST], dtype=float)
VOL_CORE   = np.array([P.PRODUCTION["base"]["pilgan"][y] + P.PRODUCTION["base"]["ngungaju"][y] for y in FCST], float)
VOL_P2000  = np.array([P.PRODUCTION["base"]["p2000"][y]  for y in FCST], float)
VOL_COLINA = np.array([P.PRODUCTION["base"]["colina"][y] for y in FCST], float)
# capital attributable to each growth project, so declining it removes its spend too
CAPEX_P2000  = np.array([0,300,420,240,60,40,20,10,10,10], float)
CAPEX_COLINA = np.array([0,0,0,90,150,120,60,30,20,20], float)

rng = np.random.default_rng(SEED)
price_factor = rng.lognormal(mean=-0.5*0.28**2, sigma=0.28, size=N)          # persistent level error
price_noise  = rng.normal(1.0, 0.10, size=(N, NY))                            # year-to-year noise
cost_factor  = rng.normal(1.0, 0.07, size=N)
# logistic in the price factor, centred so the unconditional rates land on 70% and 40%
_z           = np.log(price_factor) / 0.28
p2000_p      = 1.0 / (1.0 + np.exp(-(1.05 + 1.25 * _z)))
colina_p     = 1.0 / (1.0 + np.exp(-(0.05 + 1.25 * _z)))
p2000_go     = rng.random(N) < p2000_p
colina_go    = (rng.random(N) < colina_p) & p2000_go
wacc         = np.clip(rng.normal(0.0888, 0.006, size=N), 0.06, 0.13)
conversion   = np.clip(rng.normal(0.75, 0.08, size=N), 0.45, 0.95)

vals = np.empty(N)
for i in range(N):
    vol   = VOL_CORE + (VOL_P2000 if p2000_go[i] else 0) + (VOL_COLINA if colina_go[i] else 0)
    capex = BASEK.copy()
    if not p2000_go[i]:  capex = capex - CAPEX_P2000
    if not colina_go[i]: capex = capex - CAPEX_COLINA
    capex = np.maximum(capex, 250.0)
    price = BASEP * price_factor[i] * price_noise[i]
    cost  = BASEC * cost_factor[i]
    rev   = vol * (price / FX) / 1000.0 * (1 - ADJ)
    corp  = CORP * (1 + INFL) ** np.arange(NY)
    ebitda = rev - vol * cost / 1000.0 - rev * ROY - corp
    ppe, da = PPE0, np.empty(NY)
    for t in range(NY):
        da[t] = ppe * DA_RATE
        ppe   = ppe + capex[t] - da[t]
    nopat = (ebitda - da) * (1 - TAX)
    nwc   = rev * NWC
    dnwc  = -(nwc - np.concatenate(([1934.0 * NWC], nwc[:-1])))   # FY26A revenue is the opening base
    fcff  = nopat + da - capex + dnwc
    df    = 1.0 / (1.0 + wacc[i]) ** (np.arange(NY) + 0.5)
    pv    = float(np.sum(fcff * df))
    # terminal: annuity over the ore actually left, at this trial's conversion rate
    minebase  = P.RESOURCE_MT * conversion[i]
    ore_used  = float(np.sum(vol)) / 1000.0 / MASSPULL
    ore_left  = max(0.0, minebase - ore_used)
    exit_rate = vol[-1] / 1000.0 / MASSPULL
    life      = min(25.0, ore_left / exit_rate if exit_rate > 0 else 0.0)
    ann       = (1 - (1 + wacc[i]) ** -life) / wacc[i] if life > 0 else 0.0
    pv       += fcff[-1] * ann * df[-1]
    vals[i]   = (pv + NETCASH) / SHARES

pct = lambda q: float(np.percentile(vals, q))
out = {
 "trials": N, "seed": SEED,
 "mean": float(vals.mean()), "median": pct(50), "stdev": float(vals.std(ddof=1)),
 "p5": pct(5), "p10": pct(10), "p25": pct(25), "p75": pct(75), "p90": pct(90), "p95": pct(95),
 "prob_above_lastclose": float((vals > LASTCLOSE).mean()),
 "prob_above_target":    float((vals > TARGET).mean()),
 "prob_loss_20pc":       float((vals < LASTCLOSE * 0.8).mean()),
 "prob_double":          float((vals > LASTCLOSE * 2).mean()),
 "p2000_rate": float(p2000_go.mean()), "colina_rate": float(colina_go.mean()),
}
# histogram for the slide
lo, hi = 0.0, 16.0
counts, edges = np.histogram(np.clip(vals, lo, hi), bins=32, range=(lo, hi))
out["hist_centres"] = [round(float(x), 2) for x in (edges[:-1] + edges[1:]) / 2]
out["hist_counts"]  = [int(c) for c in counts]
out["hist_pct"]     = [round(100.0 * c / N, 2) for c in counts]
json.dump(out, open('deck/montecarlo.json', 'w'), indent=1)

print(f"Monte Carlo, {N:,} trials, seed {SEED}")
print(f"  mean            A${out['mean']:.2f}")
print(f"  median          A${out['median']:.2f}")
print(f"  std deviation   A${out['stdev']:.2f}")
print(f"  P5  / P95       A${out['p5']:.2f} / A${out['p95']:.2f}")
print(f"  P10 / P90       A${out['p10']:.2f} / A${out['p90']:.2f}")
print(f"  P25 / P75       A${out['p25']:.2f} / A${out['p75']:.2f}")
print(f"  P(value > last close A${LASTCLOSE:.2f})   {out['prob_above_lastclose']*100:.1f}%")
print(f"  P(value > target A${TARGET:.2f})       {out['prob_above_target']*100:.1f}%")
print(f"  P(20%+ below last close)          {out['prob_loss_20pc']*100:.1f}%")
print(f"  P(more than doubles)              {out['prob_double']*100:.1f}%")
