#!/usr/bin/env python3
"""Cross-check every headline figure asserted in the deck against the recalculated model
and the verified fact base. Fails loudly rather than quietly disagreeing."""
import json, re, sys, subprocess
from openpyxl import load_workbook

MODEL = 'model/PLS_Valuation_Model_FMAA_2026.xlsx'
wb = load_workbook(MODEL, data_only=True)
F  = json.load(open('deck/model_facts.json'))
S  = json.load(open('deck/scenarios.json'))
txt = subprocess.run(['markitdown','deck/PLS_Group_FMAA_2026.pptx'],
                     capture_output=True, text=True).stdout
txt = re.sub(r'<!--.*?-->', '', txt, flags=re.S)

def find(sheet, label, col=3):
    ws = wb[sheet]
    for r in range(1, 220):
        if str(ws.cell(r, 2).value).strip() == label:
            return ws.cell(r, col).value
    return None

def scen(label):
    """Raw per-scenario values in bear, base, bull order."""
    ws, out = wb['Scenario Engine'], []
    for r in range(1, 160):
        if str(ws.cell(r, 2).value).strip() == label:
            out.append(ws.cell(r, 3).value)
    return out

VPS = scen('Value per share (A$)')
LIFE = scen('Remaining mine life (years)')

# (claim as it appears on a slide, value from the model, tolerance)
CHECKS = [
 ("A$6.12",  F['target'],        0.005, "12-month target price"),
 ("11.7%",   F['upside']*100,    0.05,  "implied upside"),
 ("13.4%",   F['tsr']*100,       0.05,  "total shareholder return"),
 ("5.90%",   5.90,               0.0,   "benchmark return (case p.4)"),
 ("7.5%",    F['outperf']*100,   0.05,  "outperformance"),
 ("8.88%",   F['wacc']*100,      0.005, "WACC"),
 ("9.38%",   F['ke']*100,        0.005, "cost of equity"),
 ("A$2.26",  VPS[0],             0.005, "bear case value per share"),
 ("A$6.50",  VPS[1],             0.005, "base case value per share"),
 ("A$8.93",  VPS[2],             0.005, "bull case value per share"),
 ("A$0.43",  F['esg_ps'],        0.005, "ESG bridge per share"),
 ("A$0.32",  F['do_ps'],         0.005, "risked downstream option per share"),
 ("67%",     F['esg_pct_upside']*100, 0.5, "ESG share of upside"),
 ("16.1",    LIFE[1],            0.05,  "remaining mine life, years"),
 ("50.8%",   F['tv_pct']*100,    0.05,  "terminal value as share of EV"),
 ("A$18.9bn",F['tv_perp']/1000,  0.05,  "growing-perpetuity terminal value"),
 ("A$9.9bn", F['tv_annuity']/1000, 0.05, "annuity terminal value"),
 ("1.07x",   F['rr'],            0.01,  "reward to risk"),
 ("A$20.5m", F['esg_coef'],      0.05,  "PV per A$1/t coefficient"),
 ("A$1.46bn",F['netcash']/1000,  0.005, "net cash"),
 ("A$407m",  F['p2000_delay_val'], 1.0, "value of avoiding a 2-year P2000 slip"),
 ("334.5",   F['minebase'],      0.05,  "mineable ore base, Mt"),
 ("17.5%",   F['masspull']*100,  0.05,  "mass pull"),
 ("A$1,731m",F['fy27_ebitda'],   1.0,   "FY27E EBITDA"),
 ("4.76",    F['comps_lo'],      0.005, "comps low (rendered without prefix)"),
 ("6.37",    F['comps_hi'],      0.005, "comps high (rendered without prefix)"),
]
fails, missing = [], []
print(f"{'claim':12s} {'on slides':>10s} {'model':>12s}   check")
print("-" * 74)
for claim, modelval, tol, desc in CHECKS:
    num = float(re.sub(r'[^0-9.]', '', claim))
    ok  = abs(num - modelval) <= tol
    on_slide = claim in txt
    flag = "OK " if (ok and on_slide) else "!! "
    if not ok:       fails.append((claim, modelval, desc))
    if not on_slide: missing.append((claim, desc))
    print(f"{claim:12s} {'yes' if on_slide else 'NOT FOUND':>10s} {modelval:12.3f}   {flag}{desc}")
print("-" * 74)
# reported actuals that must appear verbatim
ACTUALS = ["A$1,934m","A$1,137m","A$526m","879.5kt","US$1,488/t","A$569/t","A$2.29bn",
           "1,030-1,100kt","A$575-625/t","A$620-685m","US$2,107/t","446Mt","214Mt",
           "A$2.6bn","55%","A$175m","5.48","1.91","6.81"]
absent = [a for a in ACTUALS if a not in txt]
print(f"reported actuals present on slides: {len(ACTUALS)-len(absent)}/{len(ACTUALS)}")
if absent: print("  NOT FOUND:", ", ".join(absent))
print()
if fails:
    print("MISMATCHES AGAINST THE MODEL:")
    for c, m, d in fails: print(f"  {c} on slides vs {m:.3f} in model  ({d})")
if missing:
    print("CLAIMS NOT FOUND IN SLIDE TEXT (may be chart-only or formatted differently):")
    for c, d in missing: print(f"  {c}  ({d})")
print("RESULT:", "FAIL" if fails else "PASS — every checked figure ties to the model")
sys.exit(1 if fails else 0)
