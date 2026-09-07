#!/usr/bin/env python3
"""Cross-check the deck against the recalculated model.

Expected strings are DERIVED from the model, then asserted to appear in the slide text.
That catches the real failure mode: the model moves and the slide copy does not.
"""
import json, re, subprocess, sys
from openpyxl import load_workbook

wb  = load_workbook('model/PLS_Valuation_Model_FMAA_2026.xlsx', data_only=True)
F   = json.load(open('deck/model_facts.json'))
txt = subprocess.run(['markitdown', 'deck/PLS_Group_FMAA_2026.pptx'],
                     capture_output=True, text=True).stdout
txt = re.sub(r'<!--.*?-->', '', txt, flags=re.S)

def d2(v):  return "A$%.2f" % v
def pc(v, dp=1): return ("%." + str(dp) + "f%%") % (v * 100)
def bn(v):  return "A$%.1fbn" % (v / 1000)

# (label, expected string built from the model, whether it must appear verbatim)
CHECKS = [
 ("12-month target",             d2(F['target'])),
 ("implied upside",              pc(F['upside'])),
 ("total shareholder return",    pc(F['tsr'])),
 ("outperformance",              pc(F['outperf'])),
 ("WACC",                        pc(F['wacc'], 2)),
 ("cost of equity",              pc(F['ke'], 2)),
 ("bear value per share",        d2(F['vps_bear'])),
 ("base value per share",        d2(F['vps_base'])),
 ("bull value per share",        d2(F['vps_bull'])),
 ("ESG bridge per share",        d2(F['esg_ps'])),
 ("downstream option per share", d2(F['do_ps'])),
 ("ESG share of upside",         pc(F['esg_pct_upside'], 0)),
 ("upside in dollars",           d2(F['upside_dollars'])),
 ("remaining mine life",         "%.1f" % F['life_base']),
 ("terminal value share of EV",  pc(F['tv_pct'])),
 ("perpetuity terminal value",   bn(F['tv_perp'])),
 ("annuity terminal value",      bn(F['tv_annuity'])),
 ("reward to risk",              "%.2fx" % F['rr']),
 ("net cash",                    "A$%.2fbn" % (F["netcash"]/1000)),
 ("mineable ore base",           "%.1f" % F['minebase']),
 ("mass pull",                   pc(F['masspull'])),
 ("comps low",                   "%.2f" % F['comps_lo']),
 ("comps high",                  "%.2f" % F['comps_hi']),
]
# reported actuals that must appear verbatim on the slides
ACTUALS = ["A$1,934m","A$1,137m","A$526m","879.5kt","US$1,488/t","A$569/t","A$2.29bn",
           "1,030-1,100kt","A$575-625/t","A$620-685m","US$2,107/t","446Mt","214Mt",
           "A$2.6bn","55%","A$175m","5.48","1.91","6.81","A$853m","2.77","21.9%","10.09%"]

# Figures the model superseded. Presence checks alone will not catch a stale number
# sitting beside its replacement, which is how A$828m survived a borrowings correction.
FORBIDDEN = [
 ("A$828m",  "superseded borrowings estimate; reported figure is A$853m"),
 ("A$6.12",  "superseded target; the target is A$6.14"),
 ("11.7%",   "superseded upside; upside is 12.0%"),
 ("A$6,258m less cash", None),   # allowed: this phrasing is correct
]
stale = [(f, why) for f, why in FORBIDDEN if why and f in txt]

print(f"{'figure':30s} {'expected from model':>22s}   on slides")
print("-" * 68)
missing = []
for label, expect in CHECKS:
    ok = expect in txt
    if not ok: missing.append((label, expect))
    print(f"{label:30s} {expect:>22s}   {'yes' if ok else 'NOT FOUND'}")
print("-" * 68)
absent = [a for a in ACTUALS if a not in txt]
print(f"reported actuals present: {len(ACTUALS)-len(absent)}/{len(ACTUALS)}")
if absent: print("  NOT FOUND:", ", ".join(absent))
print()
if stale:
    print("SUPERSEDED FIGURES STILL ON THE SLIDES:")
    for f, why in stale: print(f"  {f}: {why}")
if missing:
    print("DECK IS OUT OF SYNC WITH THE MODEL:")
    for l, e in missing: print(f"  {l}: model says {e}, not found in slide text")
print("RESULT:", "FAIL" if (missing or absent or stale) else "PASS - deck ties to the model")
sys.exit(1 if (missing or absent) else 0)
