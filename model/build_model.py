# -*- coding: utf-8 -*-
"""
Builds the PLS Group (ASX:PLS) valuation workbook for the FMAA 2026 case.
Every projected figure is a live Excel formula driven off the Assumptions sheet.
Run:  python3 model/build_model.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as gcl
from openpyxl.worksheet.datavalidation import DataValidation

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "PLS_Valuation_Model_FMAA_2026.xlsx")

# ------------------------------------------------------------------ palette
NAVY   = "0B2545"; TEAL = "0E7C7B"; LIME = "8FBF3F"; GREY = "5A6472"
LGREY  = "EEF1F4"; WHITE = "FFFFFF"; AMBER = "C77D02"; RED = "B3261E"
BLUE_IN  = "0000FF"   # hardcoded input
BLACK_F  = "000000"   # formula
GREEN_L  = "008000"   # cross-sheet link
YELLOW   = "FFFF00"   # key assumption

FONT = "Arial"
def F(sz=10, b=False, color=BLACK_F, i=False):
    return Font(name=FONT, size=sz, bold=b, color=color, italic=i)
def fill(c):  return PatternFill("solid", fgColor=c)
def thin(color="B8C0CC"):
    s = Side(style="thin", color=color); return Border(left=s,right=s,top=s,bottom=s)
def botline(color=NAVY, style="medium"):
    return Border(bottom=Side(style=style, color=color))

NUM_A   = '#,##0;(#,##0);"-"'
NUM_A1  = '#,##0.0;(#,##0.0);"-"'
NUM_A2  = '#,##0.00;(#,##0.00);"-"'
CUR     = '$#,##0;($#,##0);"-"'
CUR2    = '$#,##0.00;($#,##0.00);"-"'
PCT     = '0.0%;(0.0%);"-"'
PCT2    = '0.00%;(0.00%);"-"'
MULT    = '0.0x;(0.0x);"-"'

YEARS = P.YEARS
NY    = len(YEARS)
C0    = 3                       # first year column (C)
def ycol(i):  return C0 + i     # 1-based column index of year i
def yl(i):    return gcl(ycol(i))
FCST_I = [i for i,y in enumerate(YEARS) if y.endswith("F")]
HIST_I = [i for i,y in enumerate(YEARS) if y.endswith("A")]
F0     = FCST_I[0]              # index of FY27F

wb = Workbook(); wb.remove(wb.active)

# ------------------------------------------------------------------ helpers
def newsheet(name, tab=NAVY, widths=None, freeze="C6"):
    ws = wb.create_sheet(name); ws.sheet_properties.tabColor = tab
    ws.sheet_view.showGridLines = False
    ws.column_dimensions['A'].width = 3
    ws.column_dimensions['B'].width = 46
    for i in range(NY):
        ws.column_dimensions[yl(i)].width = 11.5
    if widths:
        for col,w in widths.items(): ws.column_dimensions[col].width = w
    if freeze: ws.freeze_panes = freeze
    return ws

def title(ws, t, sub=""):
    ws["B2"] = t;  ws["B2"].font = F(16, True, NAVY)
    ws["B3"] = sub; ws["B3"].font = F(9, False, GREY, True)
    ws["B4"] = f"{P.COMPANY} ({P.TICKER})  |  Valuation date {P.VALN_DATE}  |  All figures A$ unless stated"
    ws["B4"].font = F(8, False, GREY, True)

def hdr(ws, row, label="A$m unless stated", years=True, note=""):
    ws.cell(row, 2, label).font = F(9, True, WHITE)
    ws.cell(row, 2).fill = fill(NAVY)
    ws.cell(row, 2).alignment = Alignment(horizontal="left", vertical="center")
    if years:
        for i,y in enumerate(YEARS):
            c = ws.cell(row, ycol(i), y)
            c.font = F(9, True, WHITE); c.fill = fill(NAVY)
            c.alignment = Alignment(horizontal="center")
    if note:
        ws.cell(row, ycol(NY)+1, note).font = F(8, False, GREY, True)
    ws.row_dimensions[row].height = 18
    return row+1

def section(ws, row, text, col=2, span=NY):
    c = ws.cell(row, col, text); c.font = F(10, True, NAVY)
    c.fill = fill(LGREY)
    for k in range(span):
        ws.cell(row, ycol(k)).fill = fill(LGREY)
    return row+1

def label(ws, row, text, bold=False, indent=0, italic=False, color=BLACK_F):
    c = ws.cell(row, 2, ("   "*indent)+text)
    c.font = F(9, bold, color, italic)
    return c

def putrow(ws, row, text, values, fmt=NUM_A, bold=False, indent=0,
           color=BLACK_F, italic=False, note=""):
    """values: dict {year_index: formula-or-number} or list of length NY."""
    label(ws, row, text, bold, indent, italic)
    if isinstance(values, list):
        values = {i:v for i,v in enumerate(values) if v is not None}
    for i,v in values.items():
        c = ws.cell(row, ycol(i), v)
        c.number_format = fmt
        col = color
        if isinstance(v,(int,float)): col = BLUE_IN if color==BLACK_F else color
        c.font = F(9, bold, col)
    if note:
        ws.cell(row, ycol(NY)+1, note).font = F(8, False, GREY, True)
    return row+1

def kv(ws, row, k, v, fmt=None, bold=False, color=None, note="", kcol=2, vcol=3):
    ws.cell(row, kcol, k).font = F(9, bold)
    c = ws.cell(row, vcol, v)
    if fmt: c.number_format = fmt
    auto = BLUE_IN if isinstance(v,(int,float)) else BLACK_F
    c.font = F(9, bold, color or auto)
    if note: ws.cell(row, vcol+1, note).font = F(8, False, GREY, True)
    return row+1

def srcnote(ws, row, text):
    c = ws.cell(row, 2, text); c.font = F(8, False, GREY, True)
    return row+1

# ==================================================================
# 1. COVER
# ==================================================================
cv = newsheet("Cover", NAVY, widths={"B":30,"C":58}, freeze=None)
cv["B2"] = "PLS GROUP LIMITED"; cv["B2"].font = Font(name=FONT, size=26, bold=True, color=NAVY)
cv["B3"] = "ASX: PLS  |  Spodumene concentrate  |  Pilgangoora, Western Australia"
cv["B3"].font = F(11, False, TEAL)
cv["B5"] = "Equity valuation model"; cv["B5"].font = Font(name=FONT, size=15, bold=True, color=TEAL)
cv["B6"] = "FMAA x Shared Value Project - Investing for the Future Case Competition 2026"
cv["B6"].font = F(10, False, GREY, True)

r = 8
r = kv(cv, r, "Prepared for", "FMAA Asset Management - Australian ASX 200 long-only fund", bold=True)
r = kv(cv, r, "Coverage team", "Shared Value Coverage")
r = kv(cv, r, "Valuation date", P.VALN_DATE)
r = kv(cv, r, "Reporting currency", "A$ (Australian dollars), millions unless stated")
r = kv(cv, r, "Fiscal year end", "30 June")
r += 1
cv.cell(r,2,"HOW TO USE THIS MODEL").font = F(11, True, NAVY); r += 1
for t in [
  "1.  Assumptions!C7 holds the scenario switch. Change it to Bear / Base / Bull and the entire",
  "     model - production, prices, costs, capex, statements, DCF and target price - repoints.",
  "2.  Every projected cell is a live formula. Nothing downstream of Assumptions is typed in.",
  "3.  Blue text = hardcoded input.  Black = formula.  Green = link to another sheet.",
  "     Yellow fill = key judgement the reviewer should interrogate first.",
  "4.  Sources lists the provenance of every input, tagged A (actual) / G (guidance) /",
  "     M (market) / D (derived) / E (our estimate) / C (prescribed by the case).",
]:
    cv.cell(r,2,t).font = F(9, False, GREY); r += 1

r += 1
cv.cell(r,2,"CONTENTS").font = F(11, True, NAVY); r += 1
contents = [
 ("Assumptions",          "Scenario switch, market data, CAPM and WACC build, operating drivers"),
 ("Deck",                 "Production by asset, realised price, unit cost and capex - all three scenarios"),
 ("Revenue Build",        "Volume x price bridge by asset, royalties, freight"),
 ("Income Statement",     "FY24A-FY36F P&L"),
 ("Balance Sheet",        "FY24A-FY36F balance sheet"),
 ("Cash Flow",            "FY24A-FY36F cash flow and net working capital"),
 ("DCF",                  "Unlevered FCFF, WACC discounting, terminal value, equity bridge"),
 ("Sensitivity",          "WACC x TGR, price x cost, price x volume data tables"),
 ("Scenario Summary",     "Bear / Base / Bull outputs side by side and probability weighting"),
 ("SOTP NAV",             "Risked asset-by-asset net asset value cross-check"),
 ("Trading Comps",        "ASX diversified peers and global lithium pure-plays"),
 ("Precedents",           "Lithium M&A precedent transaction multiples"),
 ("Football Field",       "Valuation range by methodology and weighted target price"),
 ("ESG Value Bridge",     "Shared-value levers converted to A$/share of the target"),
 ("Downstream Option",    "The low-carbon downstream prize, sized and risked, held outside the target"),
 ("Returns",              "IRR, MoM and TSR against the S&P/ASX 200 benchmark"),
 ("Sources",              "Provenance register for every input"),
]
for nm, desc in contents:
    cv.cell(r,2,nm).font = F(9, True, TEAL)
    cv.cell(r,3,desc).font = F(9, False, GREY)
    r += 1

r += 1
cv.cell(r,2,"IMPORTANT").font = F(10, True, RED); r += 1
for t in ["Prepared as a university case-competition submission using publicly available information.",
          "Not investment advice and not a substitute for independent professional research.",
          "Forecasts are the authors' estimates and will differ from outcomes."]:
    cv.cell(r,2,t).font = F(8, False, GREY, True); r += 1

# ==================================================================
# 2. ASSUMPTIONS
# ==================================================================
a = newsheet("Assumptions", TEAL, widths={"B":44,"C":16,"D":14,"E":14,"F":52}, freeze=None)
title(a, "Assumptions and WACC", "Every driver in the model resolves to a cell on this sheet")

# scenario helper list (kept to the right)
a["S3"] = "Bear"; a["S4"] = "Base"; a["S5"] = "Bull"
for c in ("S3","S4","S5"): a[c].font = F(9, False, GREY)

r = 6
a.cell(r,2,"SCENARIO SWITCH").font = F(11, True, WHITE); a.cell(r,2).fill = fill(NAVY)
for cc in range(3,7): a.cell(r,cc).fill = fill(NAVY)
r += 1
a.cell(r,2,"Active scenario").font = F(10, True)
a["C7"] = "Base"; a["C7"].font = F(11, True, BLUE_IN); a["C7"].fill = fill(YELLOW)
a["C7"].alignment = Alignment(horizontal="center")
a["C7"].border = thin(NAVY)
dv = DataValidation(type="list", formula1="$S$3:$S$5", allow_blank=False)
a.add_data_validation(dv); dv.add(a["C7"])
a.cell(r,6,"Change this cell to repoint the whole model. Bear / Base / Bull.").font = F(9, False, GREY, True)
r += 1
a.cell(r,2,"Scenario index").font = F(9)
a["C8"] = "=MATCH($C$7,$S$3:$S$5,0)"; a["C8"].font = F(9, True); a["C8"].alignment = Alignment(horizontal="center")
a.cell(r,6,"1 = Bear, 2 = Base, 3 = Bull. Drives every CHOOSE() in the model.").font = F(9, False, GREY, True)
r += 2

r = section(a, r, "MARKET DATA", span=4)
PRICE_R = r
r = kv(a, r, "Last close (A$/share)", P.SHARE_PRICE, CUR2, note="M  Market Index / Google Finance, early Sep-26", vcol=3)
SHARES_R = r
r = kv(a, r, "Shares on issue (m)", P.SHARES_OUT_M, NUM_A, note="M  stockanalysis.com", vcol=3)
MKTCAP_R = r
r = kv(a, r, "Market capitalisation (A$m)", f"=C{PRICE_R}*C{SHARES_R}", CUR, bold=True, color=BLACK_F, vcol=3)
HI_R = r
r = kv(a, r, "52-week high (A$)", P.WK52_HIGH, CUR2, vcol=3)
LO_R = r
r = kv(a, r, "52-week low (A$)", P.WK52_LOW, CUR2, vcol=3)
r = kv(a, r, "Move off 52-week low", f"=C{PRICE_R}/C{LO_R}-1", PCT, color=BLACK_F, vcol=3,
       note="The central objection this pitch must answer")
r += 1

r = section(a, r, "CAPITAL STRUCTURE", span=4)
CASH_R = r
r = kv(a, r, "Cash and equivalents, FY26A (A$m)", P.CASH_FY26, CUR, note="A  FY26 result, 24-Aug-26", vcol=3)
DEBT_R = r
r = kv(a, r, "Borrowings, FY26A (A$m)", P.DEBT_FY26, CUR, note="E  US$600m senior notes translated at spot - VERIFY", vcol=3)
NETCASH_R = r
r = kv(a, r, "Net cash / (net debt) (A$m)", f"=C{CASH_R}-C{DEBT_R}", CUR, bold=True, color=BLACK_F, vcol=3)
EV_R = r
r = kv(a, r, "Enterprise value (A$m)", f"=C{MKTCAP_R}-C{NETCASH_R}", CUR, bold=True, color=BLACK_F, vcol=3)
r = kv(a, r, "Target gearing D/(D+E)", P.TARGET_D_RATIO, PCT, vcol=3,
       note="E  through-cycle target; PLS is currently net cash")
GEAR_R = r-1
r += 1

r = section(a, r, "COST OF CAPITAL  (CAPM inputs prescribed by the case)", span=4)
RF_R = r
r = kv(a, r, "Risk-free rate", P.RISK_FREE, PCT2, vcol=3, note="C  FMAA case p.6 - prescribed")
MRP_R = r
r = kv(a, r, "Market risk premium", P.MRP, PCT2, vcol=3, note="C  FMAA case p.6 - prescribed")
BETA_R = r
r = kv(a, r, "Equity beta", P.BETA, '0.00', vcol=3, note="C  FMAA case p.6 - Yahoo 5Y monthly")
a.cell(BETA_R,3).fill = fill(YELLOW)
KE_R = r
r = kv(a, r, "Cost of equity  = Rf + B x MRP", f"=C{RF_R}+C{BETA_R}*C{MRP_R}", PCT2, bold=True, color=BLACK_F, vcol=3)
KD_R = r
r = kv(a, r, "Pre-tax cost of debt", P.COST_OF_DEBT, PCT2, vcol=3, note="E  indicative senior note coupon - VERIFY")
TAX_R = r
r = kv(a, r, "Corporate tax rate", P.TAX_RATE, PCT2, vcol=3, note="Australian statutory rate")
KDAT_R = r
r = kv(a, r, "After-tax cost of debt", f"=C{KD_R}*(1-C{TAX_R})", PCT2, color=BLACK_F, vcol=3)
WACC_R = r
r = kv(a, r, "WACC", f"=(1-C{GEAR_R})*C{KE_R}+C{GEAR_R}*C{KDAT_R}", PCT2, bold=True, color=BLACK_F, vcol=3)
a.cell(WACC_R,3).fill = fill(YELLOW); a.cell(WACC_R,3).border = thin(NAVY)
r += 1

r = section(a, r, "TERMINAL VALUE", span=4)
TGR_R = r
r = kv(a, r, "Terminal growth rate (scenario-driven)",
       f'=CHOOSE($C$8,{P.TGR_BEAR},{P.TGR_BASE},{P.TGR_BULL})', PCT2, bold=True, color=BLACK_F, vcol=3,
       note="E  below long-run Australian nominal GDP growth")
r = kv(a, r, "Terminal FCFF basis", "Final forecast year FCFF grown at TGR", vcol=3)
r += 1

r = section(a, r, "OPERATING DRIVERS", span=4)
CORP_R = r
r = kv(a, r, "Corporate and admin cost (A$m p.a., FY27 base)", P.CORP_COST_AM, CUR, vcol=3, note="E")
INFL_R = r
r = kv(a, r, "Cost inflation p.a.", P.INFLATION, PCT, vcol=3, note="E")
ROY_R = r
r = kv(a, r, "WA State royalty (% of realised revenue)", P.ROYALTY_RATE, PCT, vcol=3,
       note="WA ad valorem royalty on concentrate - VERIFY rate and basis")
DA_R = r
r = kv(a, r, "D&A as % of prior-year capex (steady state)", P.DA_PCT_OF_CAPEX, PCT, vcol=3, note="E")
NWC_R = r
r = kv(a, r, "Net working capital as % of revenue", P.NWC_PCT_REVENUE, PCT, vcol=3, note="E")
r += 1

r = section(a, r, "OREBODY AND MINE LIFE  (drives the terminal value)", span=4)
RES_R = r
r = kv(a, r, "Mineral Resource (Mt)", P.RESOURCE_MT, NUM_A1, vcol=3, note="A  446Mt at 1.28% Li2O, June-2025 update")
RESV_R = r
r = kv(a, r, "Ore Reserve (Mt)", P.RESERVE_MT, NUM_A1, vcol=3, note="A  Aug-2023 statement - not restated since the 2025 resource upgrade")
CONV_R = r
r = kv(a, r, "Assumed resource-to-reserve conversion", 0.75, PCT, vcol=3,
       note="E  KEY JUDGEMENT: the reserve alone does not support the modelled expansion")
a.cell(CONV_R,3).fill = fill(YELLOW)
MINE_R = r
r = kv(a, r, "Mineable ore base (Mt)", f"=C{RES_R}*C{CONV_R}", NUM_A1, bold=True, color=BLACK_F, vcol=3)
RGR_R = r
r = kv(a, r, "Reserve grade (% Li2O)", P.RESERVE_GRADE, PCT2, vcol=3, note="A  1.19% Li2O")
REC_R = r
r = kv(a, r, "Lithia recovery", 0.765, PCT, vcol=3, note="A  ~76.5% reported for FY26")
CGR_R = r
r = kv(a, r, "Concentrate grade (% Li2O)", 0.052, PCT2, vcol=3, note="A  PLS ships ~SC5.2")
MP_R = r
r = kv(a, r, "Mass pull (t concentrate per t ore)", f"=C{RGR_R}*C{REC_R}/C{CGR_R}", PCT, bold=True, color=BLACK_F, vcol=3)
TVY_R = r
r = kv(a, r, "Cap on terminal life (years)", 25.0, '0.0', vcol=3,
       note="E  beyond 25 years the discounted contribution is negligible")
r += 1

r = section(a, r, "BENCHMARK AND MANDATE (from the case)", span=4)
BENCH_R = r
r = kv(a, r, "S&P/ASX 200 return, FY26", P.BENCH_RET_FY26, PCT, vcol=3, note="C  FMAA case p.4")
r = kv(a, r, "Fund return, FY25", P.FUND_RET_FY25, PCT, vcol=3, note="C  FMAA case p.4 - index +2.0%")
r = kv(a, r, "Required outperformance", "=C"+str(r-1)+"-C"+str(BENCH_R), PCT, color=BLACK_F, vcol=3)
r += 1
srcnote(a, r, "Tags: A = reported actual  |  G = company guidance  |  M = market data  |  D = derived  |  E = our estimate  |  C = prescribed by the case")

ASSUM = "Assumptions"
REF = {  # named references used across sheets
 "switch": f"{ASSUM}!$C$8", "price": f"{ASSUM}!$C${PRICE_R}", "shares": f"{ASSUM}!$C${SHARES_R}",
 "mktcap": f"{ASSUM}!$C${MKTCAP_R}", "cash": f"{ASSUM}!$C${CASH_R}", "debt": f"{ASSUM}!$C${DEBT_R}",
 "netcash": f"{ASSUM}!$C${NETCASH_R}", "ev": f"{ASSUM}!$C${EV_R}", "ke": f"{ASSUM}!$C${KE_R}",
 "wacc": f"{ASSUM}!$C${WACC_R}", "tgr": f"{ASSUM}!$C${TGR_R}", "tax": f"{ASSUM}!$C${TAX_R}",
 "corp": f"{ASSUM}!$C${CORP_R}", "infl": f"{ASSUM}!$C${INFL_R}", "roy": f"{ASSUM}!$C${ROY_R}",
 "da": f"{ASSUM}!$C${DA_R}", "nwc": f"{ASSUM}!$C${NWC_R}", "bench": f"{ASSUM}!$C${BENCH_R}",
 "beta": f"{ASSUM}!$C${BETA_R}", "rf": f"{ASSUM}!$C${RF_R}", "mrp": f"{ASSUM}!$C${MRP_R}",
 "minebase": f"{ASSUM}!$C${MINE_R}", "masspull": f"{ASSUM}!$C${MP_R}", "tvcap": f"{ASSUM}!$C${TVY_R}",
}

# ==================================================================
# 3. DECK  (production / price / cost / capex, all three scenarios)
# ==================================================================
d = newsheet("Deck", TEAL)
title(d, "Operating deck", "Three scenarios held side by side; the ACTIVE block is what the model reads")
ASSETS = [("pilgan","Pilgangoora (Pilgan plant)"),
          ("ngungaju","Ngungaju plant"),
          ("p2000","P2000 expansion"),
          ("colina","Colina, Brazil")]
SC = [("bear","Bear"),("base","Base"),("bull","Bull")]

r = 6
r = hdr(d, r, "Spodumene concentrate production (kt)")
prod_rows = {}
for key,nm in SC:
    r = section(d, r, f"{nm} case")
    prod_rows[key] = {}
    for ak,an in ASSETS:
        prod_rows[key][ak] = r
        r = putrow(d, r, an, {i: P.PRODUCTION[key][ak][YEARS[i]] for i in FCST_I}, NUM_A, indent=1)
    prod_rows[key]["total"] = r
    fs = {i: f"=SUM({yl(i)}{prod_rows[key]['pilgan']}:{yl(i)}{prod_rows[key]['colina']})" for i in FCST_I}
    r = putrow(d, r, f"Total - {nm}", fs, NUM_A, bold=True, color=BLACK_F)
    r += 1

r = section(d, r, "ACTIVE  (driven by Assumptions!C7)")
act_prod = {}
for ak,an in ASSETS:
    act_prod[ak] = r
    fs = {i: f"=CHOOSE({REF['switch']},{yl(i)}{prod_rows['bear'][ak]},{yl(i)}{prod_rows['base'][ak]},{yl(i)}{prod_rows['bull'][ak]})" for i in FCST_I}
    r = putrow(d, r, an, fs, NUM_A, indent=1, color=BLACK_F)
PROD_TOT_R = r
vals = {i: P.HIST_DATA["production_kt"][YEARS[i]] for i in HIST_I}
vals.update({i: f"=SUM({yl(i)}{act_prod['pilgan']}:{yl(i)}{act_prod['colina']})" for i in FCST_I})
r = putrow(d, r, "Total production (kt)", vals, NUM_A, bold=True, color=BLACK_F)
SALES_R = r
sv = {i: P.HIST_DATA["sales_kt"][YEARS[i]] for i in HIST_I}
sv.update({i: f"={yl(i)}{PROD_TOT_R}" for i in FCST_I})
r = putrow(d, r, "Concentrate sold (kt)", sv, NUM_A, bold=True, color=BLACK_F,
           note="Forecast assumes sales = production (no inventory build)")
r = putrow(d, r, "Growth in production", {i: f"={yl(i)}{PROD_TOT_R}/{yl(i-1)}{PROD_TOT_R}-1" for i in range(1,NY)},
           PCT, indent=1, color=BLACK_F, italic=True)
r += 1

# ---- realised price
r = hdr(d, r, "Realised price (US$/dmt of concentrate)")
price_rows = {}
for key,nm in SC:
    price_rows[key] = r
    r = putrow(d, r, f"{nm} case", {i: P.PRICE_DECK[key][YEARS[i]] for i in FCST_I}, CUR, indent=1)
PRICE_R = r
pv = {i: P.HIST_DATA["realised_usd_t"][YEARS[i]] for i in HIST_I}
pv.update({i: f"=CHOOSE({REF['switch']},{yl(i)}{price_rows['bear']},{yl(i)}{price_rows['base']},{yl(i)}{price_rows['bull']})" for i in FCST_I})
r = putrow(d, r, "ACTIVE realised price (US$/t)", pv, CUR, bold=True, color=BLACK_F)
d.cell(PRICE_R,2).fill = fill(YELLOW)
FX_R = r
r = putrow(d, r, "AUD/USD", [P.AUDUSD[y] for y in YEARS], '0.000', indent=1)
PRICE_A_R = r
r = putrow(d, r, "Realised price (A$/t)", {i: f"={yl(i)}{PRICE_R}/{yl(i)}{FX_R}" for i in range(NY)},
           CUR, bold=True, color=BLACK_F)
r += 1

# ---- unit cost
r = hdr(d, r, "Unit operating cost, FOB (A$/dmt)")
cost_rows = {}
for key,nm in SC:
    cost_rows[key] = r
    r = putrow(d, r, f"{nm} case", {i: P.COST_DECK[key][YEARS[i]] for i in FCST_I}, CUR, indent=1)
COST_R = r
cv2 = {i: P.HIST_DATA["unit_cost_aud_t"][YEARS[i]] for i in HIST_I}
cv2.update({i: f"=CHOOSE({REF['switch']},{yl(i)}{cost_rows['bear']},{yl(i)}{cost_rows['base']},{yl(i)}{cost_rows['bull']})" for i in FCST_I})
r = putrow(d, r, "ACTIVE unit cost (A$/t FOB)", cv2, CUR, bold=True, color=BLACK_F)
d.cell(COST_R,2).fill = fill(YELLOW)
MARGIN_R = r
r = putrow(d, r, "Unit cash margin (A$/t)", {i: f"={yl(i)}{PRICE_A_R}-{yl(i)}{COST_R}" for i in range(NY)},
           CUR, bold=True, color=BLACK_F)
r = putrow(d, r, "Unit cash margin (%)", {i: f"=IFERROR({yl(i)}{MARGIN_R}/{yl(i)}{PRICE_A_R},0)" for i in range(NY)},
           PCT, indent=1, color=BLACK_F, italic=True)
r += 1

# ---- capex
r = hdr(d, r, "Capital expenditure (A$m)")
capex_rows = {}
for key,nm in SC:
    capex_rows[key] = r
    r = putrow(d, r, f"{nm} case", {i: P.CAPEX_DECK[key][YEARS[i]] for i in FCST_I}, CUR, indent=1)
CAPEX_R = r
kv2 = {i: P.HIST_DATA['capex_am'][YEARS[i]] for i in HIST_I}
kv2.update({i: f"=CHOOSE({REF['switch']},{yl(i)}{capex_rows['bear']},{yl(i)}{capex_rows['base']},{yl(i)}{capex_rows['bull']})" for i in FCST_I})
r = putrow(d, r, "ACTIVE capex (A$m)", kv2, CUR, bold=True, color=BLACK_F)
r += 1
srcnote(d, r, "FY27 ACTIVE production 1,065kt and capex A$652m sit at the midpoints of company guidance of 1,030-1,100kt and A$620-685m.")
r = srcnote(d, r+1, "Realised price is below the SC6 benchmark because PLS ships a lower-grade concentrate on an FOB basis. FY26A realised US$1,488/t against an SC6 CIF China benchmark near US$2,200/t.")

DECK = "Deck"
DR = {"prod":PROD_TOT_R, "sales":SALES_R, "price_usd":PRICE_R, "fx":FX_R, "price_aud":PRICE_A_R,
      "cost":COST_R, "margin":MARGIN_R, "capex":CAPEX_R, "act_prod":act_prod}

# ==================================================================
# 4. REVENUE BUILD
# ==================================================================
rb = newsheet("Revenue Build", TEAL)
title(rb, "Revenue build", "Volume x realised price by asset, reconciled to reported revenue")
r = 6
r = hdr(rb, r, "Volumes by asset (kt)")
rb_asset = {}
for ak,an in ASSETS:
    rb_asset[ak] = r
    r = putrow(rb, r, an, {i: f"={DECK}!{yl(i)}{DR['act_prod'][ak]}" for i in FCST_I},
               NUM_A, indent=1, color=GREEN_L)
RB_VOL = r
r = putrow(rb, r, "Total concentrate sold (kt)", {i: f"={DECK}!{yl(i)}{DR['sales']}" for i in range(NY)},
           NUM_A, bold=True, color=GREEN_L)
r += 1
r = hdr(rb, r, "Price realisation")
RB_PU = r
r = putrow(rb, r, "Realised price (US$/t)", {i: f"={DECK}!{yl(i)}{DR['price_usd']}" for i in range(NY)}, CUR, color=GREEN_L)
RB_FX = r
r = putrow(rb, r, "AUD/USD", {i: f"={DECK}!{yl(i)}{DR['fx']}" for i in range(NY)}, '0.000', color=GREEN_L)
RB_PA = r
r = putrow(rb, r, "Realised price (A$/t)", {i: f"={yl(i)}{RB_PU}/{yl(i)}{RB_FX}" for i in range(NY)}, CUR, color=BLACK_F)
r += 1
r = hdr(rb, r, "Revenue (A$m)")
RB_GROSS = r
r = putrow(rb, r, "Gross concentrate revenue", {i: f"={yl(i)}{RB_VOL}*{yl(i)}{RB_PA}/1000" for i in range(NY)},
           CUR, bold=True, color=BLACK_F)
RB_ADJ = r
adjv = {0: 0.000, 1: 0.036, 2: 0.0525}
adjv.update({i: 0.054 for i in FCST_I})
r = putrow(rb, r, "Freight, moisture and timing adjustment (% of gross)", adjv,
           PCT, indent=1, note="Calibrated to reported revenue in FY25A and FY26A; held flat at 5.4% across the forecast")
RB_NET = r
r = putrow(rb, r, "Revenue", {i: f"={yl(i)}{RB_GROSS}*(1-{yl(i)}{RB_ADJ})" for i in range(NY)},
           CUR, bold=True, color=BLACK_F)
RB_CHK = r
r = putrow(rb, r, "Memo: reported revenue (A$m)", {i: P.HIST_DATA["revenue_am"][YEARS[i]] for i in HIST_I},
           CUR, indent=1, italic=True)
r = putrow(rb, r, "Variance to reported", {i: f"=IFERROR({yl(i)}{RB_NET}/{yl(i)}{RB_CHK}-1,\"\")" for i in HIST_I},
           PCT, indent=1, color=BLACK_F, italic=True)
r += 1
srcnote(rb, r, "The realisation adjustment captures freight to the customer's port, moisture and grade adjustments, and the timing lag between the reference price and shipment.")
RBS = "Revenue Build"

# ==================================================================
# 5. INCOME STATEMENT
# ==================================================================
inc = newsheet("Income Statement", NAVY)
title(inc, "Income statement", "FY24A-FY36F, A$m")
r = 6
r = hdr(inc, r, "A$m")
IS_REV = r
r = putrow(inc, r, "Revenue", {i: f"='{RBS}'!{yl(i)}{RB_NET}" for i in range(NY)}, CUR, bold=True, color=GREEN_L)
IS_OPEX = r
r = putrow(inc, r, "Operating costs (FOB)",
           {i: f"=-{DECK}!{yl(i)}{DR['sales']}*{DECK}!{yl(i)}{DR['cost']}/1000" for i in range(NY)}, CUR, indent=1, color=BLACK_F)
IS_ROY = r
r = putrow(inc, r, "State royalties", {i: f"=-{yl(i)}{IS_REV}*{REF['roy']}" for i in range(NY)}, CUR, indent=1, color=BLACK_F)
IS_CORP = r
cc = {i: f"=-{REF['corp']}*(1+{REF['infl']})^({i-F0})" for i in FCST_I}
cc.update({i: -70.0 for i in HIST_I})
r = putrow(inc, r, "Corporate, administration and cost-definition reconciliation", cc, CUR, indent=1, color=BLACK_F)
IS_EBITDA = r
r = putrow(inc, r, "EBITDA", {i: f"=SUM({yl(i)}{IS_REV}:{yl(i)}{IS_CORP})" for i in range(NY)}, CUR, bold=True, color=BLACK_F)
inc.cell(IS_EBITDA,2).fill = fill(LGREY)
IS_MARG = r
r = putrow(inc, r, "EBITDA margin", {i: f"=IFERROR({yl(i)}{IS_EBITDA}/{yl(i)}{IS_REV},0)" for i in range(NY)},
           PCT, indent=1, color=BLACK_F, italic=True)
IS_DA = r
r = putrow(inc, r, "Depreciation and amortisation", {i: f"=-'Balance Sheet'!{yl(i)}$0" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
IS_EBIT = r
r = putrow(inc, r, "EBIT", {i: f"={yl(i)}{IS_EBITDA}+{yl(i)}{IS_DA}" for i in range(NY)}, CUR, bold=True, color=BLACK_F)
IS_INT = r
r = putrow(inc, r, "Net interest income / (expense)", {}, CUR, indent=1, color=BLACK_F)
IS_PBT = r
r = putrow(inc, r, "Profit before tax", {i: f"={yl(i)}{IS_EBIT}+{yl(i)}{IS_INT}" for i in range(NY)}, CUR, color=BLACK_F)
IS_TAX = r
r = putrow(inc, r, "Income tax expense", {i: f"=-MAX(0,{yl(i)}{IS_PBT})*{REF['tax']}" for i in range(NY)}, CUR, indent=1, color=BLACK_F)
IS_NPAT = r
r = putrow(inc, r, "NPAT", {i: f"={yl(i)}{IS_PBT}+{yl(i)}{IS_TAX}" for i in range(NY)}, CUR, bold=True, color=BLACK_F)
inc.cell(IS_NPAT,2).fill = fill(LGREY)
r += 1
r = hdr(inc, r, "Per share and returns", years=True)
IS_EPS = r
r = putrow(inc, r, "EPS (A$)", {i: f"={yl(i)}{IS_NPAT}/{REF['shares']}" for i in range(NY)}, CUR2, color=BLACK_F)
IS_PAY = r
r = putrow(inc, r, "Dividend payout ratio", {i: (0.30 if i < 6 else 0.50) for i in FCST_I}, PCT, indent=1,
           note="Policy is 20-30% of free cash flow; we step up to 50% from FY30 once the P2000 build is funded")
IS_DPS = r
r = putrow(inc, r, "DPS (A$)", {i: f"=MAX(0,{yl(i)}{IS_EPS})*{yl(i)}{IS_PAY}" for i in FCST_I}, CUR2, color=BLACK_F)
IS_DIV = r
r = putrow(inc, r, "Total dividends (A$m)", {i: f"={yl(i)}{IS_DPS}*{REF['shares']}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
IS_YLD = r
r = putrow(inc, r, "Dividend yield on last close", {i: f"={yl(i)}{IS_DPS}/{REF['price']}" for i in FCST_I}, PCT, indent=1, color=BLACK_F, italic=True)
r += 1
IS_MEMO_EBITDA = r
r = putrow(inc, r, "Memo: reported underlying EBITDA (A$m)", {i: P.HIST_DATA["ebitda_am"][YEARS[i]] for i in HIST_I}, CUR, indent=1, italic=True)
IS_MEMO_NPAT = r
r = putrow(inc, r, "Memo: reported NPAT (A$m)", {i: P.HIST_DATA["npat_am"][YEARS[i]] for i in HIST_I}, CUR, indent=1, italic=True)
IS = "Income Statement"

# ==================================================================
# 6. BALANCE SHEET
# ==================================================================
BSI = [2] + FCST_I           # FY26A opening actual, then forecasts
bs = newsheet("Balance Sheet", NAVY)
title(bs, "Balance sheet", "FY26A opening position rolled forward to FY36F, A$m")
r = 6
r = hdr(bs, r, "A$m")
r = section(bs, r, "Drivers")
BS_DARATE = r
r = putrow(bs, r, "D&A rate on opening PP&E", {i: 0.115 for i in FCST_I}, PCT, indent=1,
           note="E  approximates an 8-9 year average remaining asset life")
BS_IRATE = r
r = putrow(bs, r, "Interest earned on opening cash", {i: 0.040 for i in FCST_I}, PCT, indent=1, note="E")
BS_KD = r
r = putrow(bs, r, "Interest paid on opening debt", {i: f"={REF['ke']}*0+{P.COST_OF_DEBT}" for i in FCST_I}, PCT, indent=1, color=BLACK_F)
r += 1

r = section(bs, r, "Assets")
BS_CASH = r
cash = {2: f"={REF['cash']}"}
r = putrow(bs, r, "Cash and cash equivalents", cash, CUR, indent=1, color=GREEN_L)
BS_NWC = r
r = putrow(bs, r, "Net working capital", {i: f"='{IS}'!{yl(i)}{IS_REV}*{REF['nwc']}" for i in BSI}, CUR, indent=1, color=BLACK_F)
BS_PPE = r
ppe = {2: 3200.0}
r = putrow(bs, r, "Property, plant and equipment (net)", ppe, CUR, indent=1, color=BLACK_F,
           note="E  FY26A net book value - VERIFY against the annual report")
BS_TA = r
r = putrow(bs, r, "Total assets", {i: f"=SUM({yl(i)}{BS_CASH}:{yl(i)}{BS_PPE})" for i in BSI}, CUR, bold=True, color=BLACK_F)
r += 1
r = section(bs, r, "Liabilities and equity")
BS_DEBT = r
r = putrow(bs, r, "Borrowings", {2: f"={REF['debt']}"}, CUR, indent=1, color=GREEN_L)
BS_EQ = r
r = putrow(bs, r, "Shareholders' equity", {2: f"={yl(2)}{BS_TA}-{yl(2)}{BS_DEBT}"}, CUR, indent=1, color=BLACK_F)
BS_TLE = r
r = putrow(bs, r, "Total liabilities and equity", {i: f"={yl(i)}{BS_DEBT}+{yl(i)}{BS_EQ}" for i in BSI}, CUR, bold=True, color=BLACK_F)
BS_CHK = r
r = putrow(bs, r, "Balance check (must be nil)", {i: f"={yl(i)}{BS_TA}-{yl(i)}{BS_TLE}" for i in BSI}, NUM_A2, bold=True, color=BLACK_F)
r += 1
r = section(bs, r, "Memo")
BS_DA = r
r = putrow(bs, r, "D&A charge", {i: f"={yl(i-1)}{BS_PPE}*{yl(i)}{BS_DARATE}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
BS_NETI = r
r = putrow(bs, r, "Net interest income / (expense)",
           {i: f"={yl(i-1)}{BS_CASH}*{yl(i)}{BS_IRATE}-{yl(i-1)}{BS_DEBT}*{yl(i)}{BS_KD}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
BS_NETCASH = r
r = putrow(bs, r, "Net cash / (net debt)", {i: f"={yl(i)}{BS_CASH}-{yl(i)}{BS_DEBT}" for i in BSI}, CUR, indent=1, color=BLACK_F)
BS_ROE = r
r = putrow(bs, r, "Return on equity", {i: f"=IFERROR('{IS}'!{yl(i)}{IS_NPAT}/{yl(i-1)}{BS_EQ},0)" for i in FCST_I}, PCT, indent=1, color=BLACK_F, italic=True)
BS_ROIC = r
r = putrow(bs, r, "Return on invested capital (after tax)",
           {i: f"=IFERROR('{IS}'!{yl(i)}{IS_EBIT}*(1-{REF['tax']})/({yl(i-1)}{BS_PPE}+{yl(i-1)}{BS_NWC}),0)" for i in FCST_I},
           PCT, indent=1, color=BLACK_F, italic=True)
r += 1
srcnote(bs, r, "FY24A and FY25A balance sheets are not modelled; the DCF runs off the FY26A closing position.")
BSN = "Balance Sheet"

# ==================================================================
# 7. CASH FLOW
# ==================================================================
cf = newsheet("Cash Flow", NAVY)
title(cf, "Cash flow statement", "FY26A opening cash rolled forward to FY36F, A$m")
r = 6
r = hdr(cf, r, "A$m")
r = section(cf, r, "Operating")
CF_EBITDA = r
r = putrow(cf, r, "EBITDA", {i: f"='{IS}'!{yl(i)}{IS_EBITDA}" for i in BSI}, CUR, indent=1, color=GREEN_L)
CF_INT = r
r = putrow(cf, r, "Net interest received / (paid)", {i: f"='{BSN}'!{yl(i)}{BS_NETI}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
CF_TAX = r
r = putrow(cf, r, "Tax paid", {i: f"='{IS}'!{yl(i)}{IS_TAX}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
CF_NWC = r
r = putrow(cf, r, "Movement in net working capital", {i: f"=-('{BSN}'!{yl(i)}{BS_NWC}-'{BSN}'!{yl(i-1)}{BS_NWC})" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
CF_CFO = r
r = putrow(cf, r, "Operating cash flow", {i: f"=SUM({yl(i)}{CF_EBITDA}:{yl(i)}{CF_NWC})" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
r += 1
r = section(cf, r, "Investing")
CF_CAPEX = r
r = putrow(cf, r, "Capital expenditure", {i: f"=-{DECK}!{yl(i)}{DR['capex']}" for i in BSI}, CUR, indent=1, color=BLACK_F)
CF_FCF = r
r = putrow(cf, r, "Free cash flow to the firm (pre-financing)", {i: f"={yl(i)}{CF_CFO}+{yl(i)}{CF_CAPEX}" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
r += 1
r = section(cf, r, "Financing")
CF_DIV = r
r = putrow(cf, r, "Dividends paid", {i: f"=-'{IS}'!{yl(i)}{IS_DIV}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
CF_DEBT = r
r = putrow(cf, r, "Net debt drawn / (repaid)", {i: 0.0 for i in FCST_I}, CUR, indent=1,
           note="E  base case assumes the US$600m notes are refinanced at maturity")
CF_NET = r
r = putrow(cf, r, "Net movement in cash", {i: f"={yl(i)}{CF_FCF}+{yl(i)}{CF_DIV}+{yl(i)}{CF_DEBT}" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
CF_OPEN = r
r = putrow(cf, r, "Opening cash", {i: f"='{BSN}'!{yl(i-1)}{BS_CASH}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
CF_CLOSE = r
r = putrow(cf, r, "Closing cash", {i: f"={yl(i)}{CF_OPEN}+{yl(i)}{CF_NET}" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
r += 1
srcnote(cf, r, "Tax paid is shown equal to the accrued charge; PLS carries franking credits and tax losses that in practice defer cash tax.")
CFN = "Cash Flow"

# ------------------------------------------------------------------ wire the loops closed
for i in FCST_I:
    bs.cell(BS_CASH,  ycol(i), f"='{CFN}'!{yl(i)}{CF_CLOSE}").font = F(9, False, GREEN_L)
    bs.cell(BS_CASH,  ycol(i)).number_format = CUR
    bs.cell(BS_PPE,   ycol(i), f"={yl(i-1)}{BS_PPE}+{DECK}!{yl(i)}{DR['capex']}-{yl(i)}{BS_DA}").font = F(9, False, BLACK_F)
    bs.cell(BS_PPE,   ycol(i)).number_format = CUR
    bs.cell(BS_DEBT,  ycol(i), f"={yl(i-1)}{BS_DEBT}+'{CFN}'!{yl(i)}{CF_DEBT}").font = F(9, False, BLACK_F)
    bs.cell(BS_DEBT,  ycol(i)).number_format = CUR
    bs.cell(BS_EQ,    ycol(i), f"={yl(i-1)}{BS_EQ}+'{IS}'!{yl(i)}{IS_NPAT}-'{IS}'!{yl(i)}{IS_DIV}").font = F(9, False, BLACK_F)
    bs.cell(BS_EQ,    ycol(i)).number_format = CUR
    inc.cell(IS_DA,   ycol(i), f"=-'{BSN}'!{yl(i)}{BS_DA}").font = F(9, False, BLACK_F)
    inc.cell(IS_DA,   ycol(i)).number_format = CUR
    inc.cell(IS_INT,  ycol(i), f"='{BSN}'!{yl(i)}{BS_NETI}").font = F(9, False, BLACK_F)
    inc.cell(IS_INT,  ycol(i)).number_format = CUR
# historical D&A / interest so PBT and NPAT are meaningful in FY24A-FY26A
for i,(da,ni) in zip(HIST_I, [(-300.0,-10.0),(-330.0,25.0),(-360.0,40.0)]):
    inc.cell(IS_DA,  ycol(i), da).font = F(9, False, BLUE_IN); inc.cell(IS_DA, ycol(i)).number_format = CUR
    inc.cell(IS_INT, ycol(i), ni).font = F(9, False, BLUE_IN); inc.cell(IS_INT, ycol(i)).number_format = CUR
# historical corporate line forces EBITDA to tie to reported underlying EBITDA
for i in HIST_I:
    inc.cell(IS_CORP, ycol(i),
             f"={yl(i)}{IS_MEMO_EBITDA}-{yl(i)}{IS_REV}-{yl(i)}{IS_OPEX}-{yl(i)}{IS_ROY}").font = F(9, False, BLACK_F)
    inc.cell(IS_CORP, ycol(i)).number_format = CUR
inc.cell(IS_CORP, ycol(NY)+1,
         "Historical columns absorb the difference between this simplified cost build and reported underlying EBITDA, so FY24A-FY26A tie exactly.").font = F(8, False, GREY, True)

# ==================================================================
# 8. DCF  (active scenario, tied to the statements)
# ==================================================================
dc = newsheet("DCF", LIME)
title(dc, "Discounted cash flow", "Unlevered FCFF for the ACTIVE scenario, discounted at WACC on a mid-year convention")
r = 6
r = hdr(dc, r, "A$m")
D_EBIT = r
r = putrow(dc, r, "EBIT", {i: f"='{IS}'!{yl(i)}{IS_EBIT}" for i in FCST_I}, CUR, color=GREEN_L)
D_NOPAT = r
r = putrow(dc, r, "Less: tax on EBIT", {i: f"=-MAX(0,{yl(i)}{D_EBIT})*{REF['tax']}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
D_NOP = r
r = putrow(dc, r, "NOPAT", {i: f"={yl(i)}{D_EBIT}+{yl(i)}{D_NOPAT}" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
D_DA = r
r = putrow(dc, r, "Add back: D&A", {i: f"='{BSN}'!{yl(i)}{BS_DA}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
D_CAP = r
r = putrow(dc, r, "Less: capital expenditure", {i: f"=-{DECK}!{yl(i)}{DR['capex']}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
D_NWC = r
r = putrow(dc, r, "Less: increase in net working capital", {i: f"='{CFN}'!{yl(i)}{CF_NWC}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
D_FCFF = r
r = putrow(dc, r, "Free cash flow to the firm", {i: f"=SUM({yl(i)}{D_NOP}:{yl(i)}{D_NWC})-{yl(i)}{D_NOP}+{yl(i)}{D_NOP}" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
for i in FCST_I:
    dc.cell(D_FCFF, ycol(i), f"={yl(i)}{D_NOP}+{yl(i)}{D_DA}+{yl(i)}{D_CAP}+{yl(i)}{D_NWC}")
    dc.cell(D_FCFF, ycol(i)).number_format = CUR; dc.cell(D_FCFF, ycol(i)).font = F(9, True, BLACK_F)
dc.cell(D_FCFF,2).fill = fill(LGREY)
D_TEXP = r
r = putrow(dc, r, "Discount period (mid-year, years)", {i: (i-F0)+0.5 for i in FCST_I}, '0.0', indent=1, italic=True)
D_DF = r
r = putrow(dc, r, "Discount factor", {i: f"=1/(1+{REF['wacc']})^{yl(i)}{D_TEXP}" for i in FCST_I}, '0.000', indent=1, color=BLACK_F)
D_PV = r
r = putrow(dc, r, "PV of FCFF", {i: f"={yl(i)}{D_FCFF}*{yl(i)}{D_DF}" for i in FCST_I}, CUR, color=BLACK_F)
r += 1

LASTF = FCST_I[-1]
r = section(dc, r, "Enterprise and equity value", span=4)
V = {}
def vrow(rr, k, formula, fmt=CUR, bold=False, note="", fillc=None):
    dc.cell(rr,2,k).font = F(9, bold)
    c = dc.cell(rr,3,formula); c.number_format = fmt
    c.font = F(9, bold, BLACK_F if isinstance(formula,str) else BLUE_IN)
    if fillc: c.fill = fill(fillc)
    if note: dc.cell(rr,5,note).font = F(8, False, GREY, True)
    V[k] = rr
    return rr+1
r = vrow(r, "Sum of PV of explicit forecast FCFF", f"=SUM({yl(F0)}{D_PV}:{yl(LASTF)}{D_PV})")
r = vrow(r, "Terminal growth rate", f"={REF['tgr']}", PCT2)
r = vrow(r, "Terminal year FCFF", f"={yl(LASTF)}{D_FCFF}")
r = vrow(r, "Cumulative ore mined to FY36 (Mt)", f"=SUM({DECK}!{yl(F0)}{DR['sales']}:{yl(LASTF)}{DR['sales']})/1000/{REF['masspull']}", NUM_A1)
r = vrow(r, "Ore base remaining after FY36 (Mt)", f"=MAX(0,{REF['minebase']}-C{V['Cumulative ore mined to FY36 (Mt)']})", NUM_A1)
r = vrow(r, "Terminal mining rate (Mt ore p.a.)", f"={DECK}!{yl(LASTF)}{DR['sales']}/1000/{REF['masspull']}", NUM_A1)
r = vrow(r, "Remaining mine life (years)", f"=MIN({REF['tvcap']},IFERROR(C{V['Ore base remaining after FY36 (Mt)']}/C{V['Terminal mining rate (Mt ore p.a.)']},0))", '0.0', bold=True,
         note="The terminal value is an annuity over remaining ore, not a perpetuity: an orebody is finite")
r = vrow(r, "Terminal annuity factor", f"=(1-(1+{REF['wacc']})^-C{V['Remaining mine life (years)']})/{REF['wacc']}", '0.00"x"')
r = vrow(r, "Terminal value at end of forecast", f"=C{V['Terminal year FCFF']}*C{V['Terminal annuity factor']}")
r = vrow(r, "PV of terminal value", f"=C{V['Terminal value at end of forecast']}*{yl(LASTF)}{D_DF}")
r = vrow(r, "Enterprise value", f"=C{V['Sum of PV of explicit forecast FCFF']}+C{V['PV of terminal value']}", bold=True)
r = vrow(r, "Terminal value as % of EV", f"=C{V['PV of terminal value']}/C{V['Enterprise value']}", PCT,
         note="A lower share means less of the answer rests on the terminal assumption")
r = vrow(r, "Add: net cash / (net debt)", f"={REF['netcash']}")
r = vrow(r, "Equity value", f"=C{V['Enterprise value']}+C{V['Add: net cash / (net debt)']}", bold=True)
r = vrow(r, "Shares on issue (m)", f"={REF['shares']}", NUM_A)
r = vrow(r, "Value per share (A$)", f"=C{V['Equity value']}/C{V['Shares on issue (m)']}", CUR2, bold=True, fillc=YELLOW)
r = vrow(r, "Last close (A$)", f"={REF['price']}", CUR2)
r = vrow(r, "Implied upside / (downside)", f"=C{V['Value per share (A$)']}/C{V['Last close (A$)']}-1", PCT, bold=True, fillc=YELLOW)
DCF_VPS = V["Value per share (A$)"]
r += 1
srcnote(dc, r, "Mid-year convention assumes cash flows arrive evenly through each financial year. The stub from the 5-Sep-26 valuation date to 30-Jun-27 is not discounted separately; the effect is immaterial at this WACC.")
DCFN = "DCF"

# ==================================================================
# 9. SCENARIO ENGINE  (all three cases computed live, side by side)
# ==================================================================
se = newsheet("Scenario Engine", LIME)
title(se, "Scenario engine",
      "A compact FCFF for each case, computed directly off the Deck's three scenario blocks, so all "
      "three values are live at once. The detailed statements show whichever case the switch selects.")
TGRS = {"bear": P.TGR_BEAR, "base": P.TGR_BASE, "bull": P.TGR_BULL}
SE_RES = {}
r = 6
for key, nm in SC:
    r = hdr(se, r, f"{nm.upper()} CASE  (A$m unless stated)")
    v = {}
    v["vol"] = r
    r = putrow(se, r, "Concentrate sold (kt)",
               {i: f"={DECK}!{yl(i)}{prod_rows[key]['total']}" for i in FCST_I}, NUM_A, color=GREEN_L)
    v["pu"] = r
    r = putrow(se, r, "Realised price (US$/t)", {i: f"={DECK}!{yl(i)}{price_rows[key]}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
    v["pa"] = r
    r = putrow(se, r, "Realised price (A$/t)", {i: f"={yl(i)}{v['pu']}/{DECK}!{yl(i)}{DR['fx']}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
    v["cost"] = r
    r = putrow(se, r, "Unit operating cost (A$/t)", {i: f"={DECK}!{yl(i)}{cost_rows[key]}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
    v["rev"] = r
    r = putrow(se, r, "Revenue", {i: f"={yl(i)}{v['vol']}*{yl(i)}{v['pa']}/1000*(1-'{RBS}'!{yl(i)}{RB_ADJ})" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
    v["opex"] = r
    r = putrow(se, r, "Operating costs", {i: f"=-{yl(i)}{v['vol']}*{yl(i)}{v['cost']}/1000" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
    v["roy"] = r
    r = putrow(se, r, "Royalties", {i: f"=-{yl(i)}{v['rev']}*{REF['roy']}" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
    v["corp"] = r
    r = putrow(se, r, "Corporate and admin", {i: f"=-{REF['corp']}*(1+{REF['infl']})^({i-F0})" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
    v["ebitda"] = r
    r = putrow(se, r, "EBITDA", {i: f"=SUM({yl(i)}{v['rev']}:{yl(i)}{v['corp']})" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
    v["capex"] = r
    r = putrow(se, r, "Capital expenditure", {i: f"={DECK}!{yl(i)}{capex_rows[key]}" for i in FCST_I}, CUR, indent=1, color=GREEN_L)
    v["ppe"] = r
    r = putrow(se, r, "PP&E (closing)", {}, CUR, indent=1, color=BLACK_F)
    v["da"] = r
    r = putrow(se, r, "D&A", {}, CUR, indent=1, color=BLACK_F)
    # PP&E and D&A are mutually recursive within the year, so write them explicitly:
    for i in FCST_I:
        prev = f"{yl(i-1)}{v['ppe']}" if i > F0 else f"'{BSN}'!{yl(2)}{BS_PPE}"
        se.cell(v["da"], ycol(i), f"={prev}*'{BSN}'!{yl(F0)}{BS_DARATE}")
        se.cell(v["da"], ycol(i)).number_format = CUR; se.cell(v["da"], ycol(i)).font = F(9, False, BLACK_F)
        se.cell(v["ppe"], ycol(i), f"={prev}+{yl(i)}{v['capex']}-{yl(i)}{v['da']}")
        se.cell(v["ppe"], ycol(i)).number_format = CUR; se.cell(v["ppe"], ycol(i)).font = F(9, False, BLACK_F)
    v["ebit"] = r
    r = putrow(se, r, "EBIT", {i: f"={yl(i)}{v['ebitda']}-{yl(i)}{v['da']}" for i in FCST_I}, CUR, color=BLACK_F)
    v["nopat"] = r
    r = putrow(se, r, "NOPAT", {i: f"={yl(i)}{v['ebit']}*(1-{REF['tax']})" for i in FCST_I}, CUR, indent=1, color=BLACK_F)
    v["dnwc"] = r
    dn = {}
    for i in FCST_I:
        prev = f"{yl(i-1)}{v['rev']}*{REF['nwc']}" if i > F0 else f"'{BSN}'!{yl(2)}{BS_NWC}"
        dn[i] = f"=-({yl(i)}{v['rev']}*{REF['nwc']}-{prev})"
    r = putrow(se, r, "Movement in net working capital", dn, CUR, indent=1, color=BLACK_F)
    v["fcff"] = r
    r = putrow(se, r, "FCFF", {i: f"={yl(i)}{v['nopat']}+{yl(i)}{v['da']}-{yl(i)}{v['capex']}+{yl(i)}{v['dnwc']}" for i in FCST_I}, CUR, bold=True, color=BLACK_F)
    se.cell(v["fcff"],2).fill = fill(LGREY)
    v["df"] = r
    r = putrow(se, r, "Discount factor", {i: f"=1/(1+{REF['wacc']})^({DCFN}!{yl(i)}{D_TEXP})" for i in FCST_I}, '0.000', indent=1, color=BLACK_F)
    v["pv"] = r
    r = putrow(se, r, "PV of FCFF", {i: f"={yl(i)}{v['fcff']}*{yl(i)}{v['df']}" for i in FCST_I}, CUR, color=BLACK_F)

    # valuation block for this scenario, laid out to the right of the labels
    lab, val = 2, 3
    def sv(rr, k, formula, fmt=CUR, bold=False, fillc=None):
        se.cell(rr,lab,k).font = F(9, bold)
        c = se.cell(rr,val,formula); c.number_format = fmt; c.font = F(9, bold, BLACK_F)
        if fillc: c.fill = fill(fillc)
        v[k] = rr
        return rr+1
    r = sv(r, "PV of explicit FCFF", f"=SUM({yl(F0)}{v['pv']}:{yl(LASTF)}{v['pv']})")
    r = sv(r, "Terminal growth", TGRS[key], PCT2)
    se.cell(v["Terminal growth"], val).font = F(9, False, BLUE_IN)
    r = sv(r, "Cumulative ore mined to FY36 (Mt)",
           f"=SUM({yl(F0)}{v['vol']}:{yl(LASTF)}{v['vol']})/1000/{REF['masspull']}", NUM_A1)
    r = sv(r, "Ore base remaining after FY36 (Mt)",
           f"=MAX(0,{REF['minebase']}-C{v['Cumulative ore mined to FY36 (Mt)']})", NUM_A1)
    r = sv(r, "Terminal mining rate (Mt ore p.a.)",
           f"={yl(LASTF)}{v['vol']}/1000/{REF['masspull']}", NUM_A1)
    r = sv(r, "Remaining mine life (years)",
           f"=MIN({REF['tvcap']},IFERROR(C{v['Ore base remaining after FY36 (Mt)']}/C{v['Terminal mining rate (Mt ore p.a.)']},0))",
           '0.0', bold=True)
    r = sv(r, "Terminal annuity factor",
           f"=(1-(1+{REF['wacc']})^-C{v['Remaining mine life (years)']})/{REF['wacc']}", '0.00"x"')
    r = sv(r, "PV of terminal value",
           f"={yl(LASTF)}{v['fcff']}*C{v['Terminal annuity factor']}*{yl(LASTF)}{v['df']}")
    r = sv(r, "Memo: growing perpetuity alternative",
           f"={yl(LASTF)}{v['fcff']}*(1+C{v['Terminal growth']})/({REF['wacc']}-C{v['Terminal growth']})*{yl(LASTF)}{v['df']}")
    r = sv(r, "Enterprise value", f"=C{v['PV of explicit FCFF']}+C{v['PV of terminal value']}", bold=True)
    r = sv(r, "Net cash", f"={REF['netcash']}")
    r = sv(r, "Equity value", f"=C{v['Enterprise value']}+C{v['Net cash']}", bold=True)
    r = sv(r, "Value per share (A$)", f"=C{v['Equity value']}/{REF['shares']}", CUR2, bold=True, fillc=YELLOW)
    r = sv(r, "Upside to last close", f"=C{v['Value per share (A$)']}/{REF['price']}-1", PCT, bold=True)
    SE_RES[key] = v
    r += 2
SEN = "Scenario Engine"

# ==================================================================
# 10. SENSITIVITY
# ==================================================================
sn = newsheet("Sensitivity", LIME, widths={"B":40}, freeze=None)
title(sn, "Sensitivity analysis", "Base-case value per share under alternative cost of capital, growth, price and cost")
B = SE_RES["base"]
FR = f"'{SEN}'!{yl(F0)}{B['fcff']}:{yl(LASTF)}{B['fcff']}"
TR = f"{DCFN}!{yl(F0)}{D_TEXP}:{yl(LASTF)}{D_TEXP}"
FN = f"'{SEN}'!{yl(LASTF)}{B['fcff']}"
TN = f"{DCFN}!{yl(LASTF)}{D_TEXP}"

r = 6
r = section(sn, r, "1.  Value per share (A$) - WACC vs remaining mine life", span=8)
waccs = [0.0788, 0.0838, 0.0888, 0.0938, 0.0988]
tgrs  = [10.0, 15.0, 20.0, 25.0, 30.0]
sn.cell(r,2,"Remaining mine life (yrs)  \\  WACC").font = F(9, True, WHITE); sn.cell(r,2).fill = fill(NAVY)
for j,w in enumerate(waccs):
    c = sn.cell(r, 3+j, w); c.number_format = PCT2; c.font = F(9, True, WHITE); c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="center")
r += 1
G1 = r
for g in tgrs:
    c = sn.cell(r,2,g); c.number_format = '0.0'; c.font = F(9, True, WHITE); c.fill = fill(NAVY)
    for j,w in enumerate(waccs):
        wc = f"{gcl(3+j)}${G1-1}"; gc = f"$B{r}"
        f_ = (f"=(SUMPRODUCT({FR},1/(1+{wc})^{TR})"
              f"+{FN}*(1-(1+{wc})^-{gc})/{wc}/(1+{wc})^{TN}"
              f"+{REF['netcash']})/{REF['shares']}")
        cc = sn.cell(r, 3+j, f_); cc.number_format = CUR2; cc.font = F(9, False, BLACK_F)
        cc.border = thin()
    r += 1
sn.cell(G1+2, 3+3).fill = fill(YELLOW)   # base WACC / base TGR intersection
r += 1
sn.cell(r,2,"Base case sits at WACC 8.88% and a terminal life derived from the remaining ore base (highlighted).").font = F(8, False, GREY, True)
r += 2

r = section(sn, r, "2.  Linear price and cost sensitivity coefficients", span=8)
r = hdr(sn, r, "Base case, per forecast year")
S_VOL = r
r = putrow(sn, r, "Concentrate sold (kt)", {i: f"='{SEN}'!{yl(i)}{B['vol']}" for i in FCST_I}, NUM_A, color=GREEN_L)
S_PA = r
r = putrow(sn, r, "Realised price (A$/t)", {i: f"='{SEN}'!{yl(i)}{B['pa']}" for i in FCST_I}, CUR, color=GREEN_L)
S_CO = r
r = putrow(sn, r, "Unit cost (A$/t)", {i: f"='{SEN}'!{yl(i)}{B['cost']}" for i in FCST_I}, CUR, color=GREEN_L)
S_DF = r
r = putrow(sn, r, "Discount factor", {i: f"='{SEN}'!{yl(i)}{B['df']}" for i in FCST_I}, '0.000', color=GREEN_L)
S_KP = r
r = putrow(sn, r, "PV of a 100% price change (A$m)",
           {i: f"={yl(i)}{S_VOL}/1000*{yl(i)}{S_PA}*(1-'{RBS}'!{yl(i)}{RB_ADJ})*(1-{REF['roy']})*(1-{REF['tax']})*{yl(i)}{S_DF}" for i in FCST_I},
           CUR, indent=1, color=BLACK_F)
S_KC = r
r = putrow(sn, r, "PV of a 100% unit-cost change (A$m)",
           {i: f"={yl(i)}{S_VOL}/1000*{yl(i)}{S_CO}*(1-{REF['tax']})*{yl(i)}{S_DF}" for i in FCST_I},
           CUR, indent=1, color=BLACK_F)
r += 1
KP = r; sn.cell(r,2,"Price coefficient K(price), incl. terminal value").font = F(9)
sn.cell(r,3, f"=SUM({yl(F0)}{S_KP}:{yl(LASTF)}{S_KP})+{yl(LASTF)}{S_KP}*(1+{REF['tgr']})/({REF['wacc']}-{REF['tgr']})").number_format = CUR
sn.cell(r,3).font = F(9, True, BLACK_F); r += 1
KC = r; sn.cell(r,2,"Cost coefficient K(cost), incl. terminal value").font = F(9)
sn.cell(r,3, f"=SUM({yl(F0)}{S_KC}:{yl(LASTF)}{S_KC})+{yl(LASTF)}{S_KC}*(1+{REF['tgr']})/({REF['wacc']}-{REF['tgr']})").number_format = CUR
sn.cell(r,3).font = F(9, True, BLACK_F); r += 2

r = section(sn, r, "3.  Value per share (A$) - realised price vs unit operating cost", span=8)
pflex = [-0.20,-0.10,0.0,0.10,0.20]
cflex = [-0.10,-0.05,0.0,0.05,0.10]
sn.cell(r,2,"Unit cost change  \\  Realised price change").font = F(9, True, WHITE); sn.cell(r,2).fill = fill(NAVY)
for j,pf in enumerate(pflex):
    c = sn.cell(r, 3+j, pf); c.number_format = PCT; c.font = F(9, True, WHITE); c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="center")
r += 1
G2 = r
for cf in cflex:
    c = sn.cell(r,2,cf); c.number_format = PCT; c.font = F(9, True, WHITE); c.fill = fill(NAVY)
    for j,pf in enumerate(pflex):
        pc = f"{gcl(3+j)}${G2-1}"; cc_ = f"$B{r}"
        f_ = (f"='{SEN}'!$C${B['Value per share (A$)']}"
              f"+($C${KP}*{pc}-$C${KC}*{cc_})/{REF['shares']}")
        cc = sn.cell(r, 3+j, f_); cc.number_format = CUR2; cc.font = F(9, False, BLACK_F); cc.border = thin()
    r += 1
sn.cell(G2+2, 3+2).fill = fill(YELLOW)
r += 1
srcnote(sn, r, "Grid 3 applies a proportional shift to every forecast year. It flows price through the realisation adjustment, royalty and tax, and captures the effect on terminal value; it holds volume, capex and working capital unchanged.")
r = srcnote(sn, r+1, "Read across the top row of grid 3 for the commodity call, and down the left column for operational delivery. The pitch stands or falls on the top-left quadrant.")
SNN = "Sensitivity"

# ==================================================================
# 11. SCENARIO SUMMARY
# ==================================================================
ss = newsheet("Scenario Summary", LIME, widths={"B":40,"C":16,"D":16,"E":16,"F":18}, freeze=None)
title(ss, "Scenario summary", "All three cases valued live, then probability weighted")
r = 6
for j,(k,nm) in enumerate(SC):
    c = ss.cell(r, 3+j, nm); c.font = F(10, True, WHITE); c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="center")
ss.cell(r,6,"Weighted").font = F(10, True, WHITE); ss.cell(r,6).fill = fill(NAVY)
ss.cell(r,6).alignment = Alignment(horizontal="center")
ss.cell(r,2,"").fill = fill(NAVY)
r += 1
PROB_R = r
ss.cell(r,2,"Probability weighting").font = F(9, True)
for j,(k,nm) in enumerate(SC):
    c = ss.cell(r, 3+j, [0.25,0.50,0.25][j]); c.number_format = PCT; c.font = F(9, True, BLUE_IN); c.fill = fill(YELLOW)
ss.cell(r,6, f"=SUM(C{r}:E{r})").number_format = PCT; ss.cell(r,6).font = F(9, True, BLACK_F)
r += 1
def srow(rr, lbl, key, fmt=CUR2, weighted=True, bold=False):
    ss.cell(rr,2,lbl).font = F(9, bold)
    for j,(k,nm) in enumerate(SC):
        c = ss.cell(rr, 3+j, f"='{SEN}'!$C${SE_RES[k][key]}"); c.number_format = fmt; c.font = F(9, bold, BLACK_F)
    if weighted:
        c = ss.cell(rr,6, f"=SUMPRODUCT(C{rr}:E{rr},C${PROB_R}:E${PROB_R})")
        c.number_format = fmt; c.font = F(9, True, BLACK_F)
    return rr+1
r = srow(r, "Enterprise value (A$m)", "Enterprise value", CUR)
r = srow(r, "Equity value (A$m)", "Equity value", CUR)
VPS_R = r
r = srow(r, "Value per share (A$)", "Value per share (A$)", CUR2, bold=True)
for j in range(3): ss.cell(VPS_R, 3+j).fill = fill(LGREY)
ss.cell(VPS_R, 6).fill = fill(YELLOW); ss.cell(VPS_R,6).border = thin(NAVY)
UPS_R = r
r = srow(r, "Upside / (downside) to last close", "Upside to last close", PCT, bold=True)
ss.cell(UPS_R, 6).fill = fill(YELLOW); ss.cell(UPS_R,6).border = thin(NAVY)
r += 1
ss.cell(r,2,"Operating metrics at FY30").font = F(10, True, NAVY); r += 1
for lbl, key, fmt in [("Concentrate sold (kt)","vol",NUM_A), ("Realised price (US$/t)","pu",CUR),
                      ("Unit cost (A$/t)","cost",CUR), ("EBITDA (A$m)","ebitda",CUR)]:
    ss.cell(r,2,lbl).font = F(9)
    for j,(k,nm) in enumerate(SC):
        c = ss.cell(r, 3+j, f"='{SEN}'!{yl(6)}{SE_RES[k][key]}"); c.number_format = fmt; c.font = F(9, False, BLACK_F)
    r += 1
r += 1
ss.cell(r,2,"Narrative").font = F(10, True, NAVY); r += 1
narr = {
 "bear":"Restart supply from Bald Hill, Finniss and Jianxiawo overwhelms demand. Price reverts toward the "
        "90th-percentile cash cost. No P2000 FID, no Colina, Ngungaju re-idled from FY30.",
 "base":"Prices ease from the June-2026 quarter peak as restart tonnes land, then recover as the surplus "
        "narrows. P2000 is sanctioned in late 2026 for first ore mid-2029; Colina follows the Dec-2027 study.",
 "bull":"The 2027-29 deficit called by Fastmarkets, Morgan Stanley and UBS arrives. Prices clear at the level "
        "needed to fund new supply. P2000 and Colina both proceed, on schedule.",
}
for j,(k,nm) in enumerate(SC):
    ss.cell(r+j,2,nm).font = F(9, True, TEAL)
    c = ss.cell(r+j,3,narr[k]); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    ss.row_dimensions[r+j].height = 42
    ss.merge_cells(start_row=r+j, start_column=3, end_row=r+j, end_column=8)
SSN = "Scenario Summary"

# ==================================================================
# 12. ESG VALUE BRIDGE   (the differentiator)
# ==================================================================
eb = newsheet("ESG Value Bridge", TEAL, widths={"B":38,"C":52,"D":13,"E":13,"F":13,"G":13,"H":48}, freeze=None)
title(eb, "Shared value bridge",
      "Converting each ESG lever into A$ per share, so the shared-value case is priced rather than asserted")
r = 6
eb.cell(r,2,"PV of A$1/t of sustained unit-margin improvement").font = F(10, True, NAVY)
r += 1
E_VOLR = r
r = putrow(eb, r, "Concentrate sold, base case (kt)", {i: f"='{SEN}'!{yl(i)}{B['vol']}" for i in FCST_I}, NUM_A, color=GREEN_L)
E_DFR = r
r = putrow(eb, r, "Discount factor", {i: f"='{SEN}'!{yl(i)}{B['df']}" for i in FCST_I}, '0.000', color=GREEN_L)
E_UNIT = r
r = putrow(eb, r, "PV of A$1/t in that year (A$m)",
           {i: f"={yl(i)}{E_VOLR}/1000*(1-{REF['tax']})*{yl(i)}{E_DFR}" for i in FCST_I}, NUM_A2, indent=1, color=BLACK_F)
r += 1
E_COEF = r
eb.cell(r,2,"Coefficient: A$m of equity value per A$1/t, incl. terminal value").font = F(9, True)
eb.cell(r,4, f"=SUM({yl(F0)}{E_UNIT}:{yl(LASTF)}{E_UNIT})+{yl(LASTF)}{E_UNIT}*(1+{REF['tgr']})/({REF['wacc']}-{REF['tgr']})").number_format = NUM_A1
eb.cell(r,4).font = F(10, True, BLACK_F); eb.cell(r,4).fill = fill(YELLOW)
r += 2

hdrs = ["Lever","Mechanism","A$/t","A$m","A$/sh","Evidence","Source anchor"]
for j,h in enumerate(hdrs):
    c = eb.cell(r, 2+j, h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
    c.alignment = Alignment(horizontal="center" if j>=2 else "left")
eb.row_dimensions[r].height = 18
r += 1
LEV0 = r
for nm, mech, val, unit, conf, src in P.ESG_LEVERS:
    eb.cell(r,2,nm).font = F(9, True, TEAL)
    c = eb.cell(r,3,mech); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    if unit == "A$/t":
        eb.cell(r,4,val).number_format = CUR; eb.cell(r,4).font = F(9, False, BLUE_IN)
        eb.cell(r,5, f"=D{r}*$D${E_COEF}").number_format = CUR; eb.cell(r,5).font = F(9, False, BLACK_F)
        eb.cell(r,6, f"=E{r}/{REF['shares']}").number_format = CUR2; eb.cell(r,6).font = F(9, True, BLACK_F)
    else:
        eb.cell(r,4,"-").font = F(9, False, GREY); eb.cell(r,4).alignment = Alignment(horizontal="center")
        eb.cell(r,5,"see below").font = F(8, False, GREY, True)
        eb.cell(r,6,"-").font = F(9, False, GREY); eb.cell(r,6).alignment = Alignment(horizontal="center")
    eb.cell(r,7,conf).font = F(9, False, {"Strong":TEAL,"Moderate":AMBER,"Weak":RED}.get(conf, GREY))
    eb.cell(r,7).alignment = Alignment(horizontal="center")
    c = eb.cell(r,8,src); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    eb.row_dimensions[r].height = 40
    r += 1
LEV1 = r-1
eb.cell(r,2,"Total quantified unit-margin levers").font = F(10, True, NAVY)
eb.cell(r,4, f"=SUM(D{LEV0}:D{LEV1})").number_format = CUR; eb.cell(r,4).font = F(10, True, BLACK_F)
eb.cell(r,5, f"=SUM(E{LEV0}:E{LEV1})").number_format = CUR; eb.cell(r,5).font = F(10, True, BLACK_F)
ESG_PS = r
eb.cell(r,6, f"=SUM(F{LEV0}:F{LEV1})").number_format = CUR2; eb.cell(r,6).font = F(10, True, BLACK_F)
eb.cell(r,6).fill = fill(YELLOW); eb.cell(r,6).border = thin(NAVY)
r += 2

r = section(eb, r, "Schedule protection: what social licence is worth on the P2000 option", span=6)
eb.cell(r,2,"P2000 incremental NPV (PFS, June 2024)").font = F(9)
P2NPV = r; eb.cell(r,4, 2600.0).number_format = CUR; eb.cell(r,4).font = F(9, False, BLUE_IN)
eb.cell(r,8,"PLS P2000 Pre-Feasibility Study: A$2.6bn incremental NPV, 55% IRR").font = F(8, False, GREY, True); r += 1
eb.cell(r,2,"Permitting / heritage delay avoided (years)").font = F(9)
P2DEL = r; eb.cell(r,4, 2.0).number_format = '0.0'; eb.cell(r,4).font = F(9, False, BLUE_IN)
eb.cell(r,8,"A two-year slip is the observed order of magnitude for WA heritage and approvals disputes").font = F(8, False, GREY, True); r += 1
eb.cell(r,2,"Value of avoiding that delay (A$m)").font = F(9, True)
P2VAL = r; eb.cell(r,4, f"=D{P2NPV}*(1-1/(1+{REF['wacc']})^D{P2DEL})").number_format = CUR
eb.cell(r,4).font = F(9, True, BLACK_F); r += 1
eb.cell(r,2,"Per share (A$)").font = F(9, True)
P2PS = r; eb.cell(r,4, f"=D{P2VAL}/{REF['shares']}").number_format = CUR2; eb.cell(r,4).font = F(9, True, BLACK_F)
eb.cell(r,4).fill = fill(YELLOW); r += 2

r = section(eb, r, "Total shared-value contribution", span=6)
eb.cell(r,2,"Unit-margin levers (A$/share)").font = F(9)
eb.cell(r,4, f"=F{ESG_PS}").number_format = CUR2; eb.cell(r,4).font = F(9, False, BLACK_F); r += 1
eb.cell(r,2,"Growth-option schedule protection (A$/share)").font = F(9)
eb.cell(r,4, f"=D{P2PS}").number_format = CUR2; eb.cell(r,4).font = F(9, False, BLACK_F); r += 1
ESG_TOT = r
eb.cell(r,2,"Shared value embedded in the target price (A$/share)").font = F(10, True, NAVY)
eb.cell(r,4, f"=D{r-2}+D{r-1}").number_format = CUR2; eb.cell(r,4).font = F(11, True, BLACK_F)
eb.cell(r,4).fill = fill(YELLOW); eb.cell(r,4).border = thin(NAVY); r += 1
eb.cell(r,2,"Base-case value per share (A$)").font = F(9)
eb.cell(r,4, f"='{SEN}'!$C${B['Value per share (A$)']}").number_format = CUR2; eb.cell(r,4).font = F(9, False, BLACK_F); r += 1
eb.cell(r,2,"Shared value as a share of the target price").font = F(9, True)
eb.cell(r,4, f"=D{ESG_TOT}/D{r-1}").number_format = PCT; eb.cell(r,4).font = F(10, True, BLACK_F); r += 2

eb.cell(r,2,"THIS IS AN ATTRIBUTION, NOT AN ADDITION.").font = F(11, True, RED)
r += 1
for t in [
 "Nothing on this sheet is added to the DCF. The ore-sorting and power benefits are already inside the",
 "A$569/t FY26 unit cost and the A$575-625/t FY27 guidance that the model discounts, and the P2000 schedule",
 "is already in the production profile. Adding them again would double-count the same cash flow once through",
 "FCFF and once through narrative. What the bridge does is decompose the valuation we have already struck and",
 "ask: how much of it exists because of ESG-linked operating decisions? The answer is A$0.43 per share - which",
 "is 4.6% of the A$6.12 target, but 67% of the A$0.64 of upside between the last close and that target.",
 "",
 "",
 "Two levers are deliberately carried at nil. The Calix mid-stream plant is real and opened in June 2026, but",
 "first production is only guided for the September 2026 quarter, so we do not capitalise a margin we have not",
 "seen. A carbon-linked price premium is frequently claimed across this sector; we found no verified premium in",
 "PLS's disclosed contracts, so we score it as unproven and value it at zero rather than manufacture a number.",
]:
    eb.cell(r,2,t).font = F(8, False, GREY, True); r += 1
EBN = "ESG Value Bridge"

# ==================================================================
# 13. TRADING COMPS
# ==================================================================
tc = newsheet("Trading Comps", GREY, widths={"B":30,"C":34,"D":13,"E":13,"F":13,"G":12,"H":12,"I":14,"J":22}, freeze=None)
title(tc, "Trading comparables", "The case's own six-stock peer set, then lithium pure-plays")
COMPS_CASE = [
 # name, exposure, mkt cap A$m, EV A$m, EBITDA A$m, EV/EBITDA, P/E fwd, div yield, consensus
 ("BHP Group",        "Iron ore, copper, met coal, potash", 312560, 343660, 50600, None, 17.38, 0.0431, "Hold"),
 ("Rio Tinto",        "Iron ore, aluminium, copper, lithium",220530, 247680, 45500, 7.84, 11.70, 0.0355, "Hold"),
 ("Fortescue",        "Iron ore, green energy",              68680,  70150, 13230, 5.55, 14.72, 0.0700, "Neutral"),
 ("South32",          "Alumina, aluminium, base metals",     17190,  17150,  3790, 8.48, 18.20, 0.0249, "Buy"),
 ("Mineral Resources","Lithium, iron ore, mining services",  10400,  15720,  2600, 7.82, 15.50, None,   "Buy"),
]
r = 6
r = section(tc, r, "The case peer set  (figures as reported around Aug-Sep 2026; vendors disagree - see Sources)", span=8)
for j,h in enumerate(["Company","Commodity exposure","Mkt cap A$m","EV A$m","FY26 EBITDA A$m","EV/EBITDA","P/E fwd","Div yield","Consensus"]):
    c = tc.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
C0R = r
for nm, ex, mc, ev, eb_, evb, pe, dy, con in COMPS_CASE:
    tc.cell(r,2,nm).font = F(9, True)
    tc.cell(r,3,ex).font = F(8, False, GREY)
    for col,val,fmt in [(4,mc,CUR),(5,ev,CUR),(6,eb_,CUR),(7,evb,MULT),(8,pe,MULT),(9,dy,PCT)]:
        c = tc.cell(r,col, val if val is not None else "n/a")
        c.number_format = fmt; c.font = F(9, False, BLUE_IN if val is not None else GREY)
    tc.cell(r,10,con).font = F(9, False, GREY); r += 1
C1R = r-1
tc.cell(r,2,"Peer median").font = F(9, True, NAVY)
for col in (7,8,9):
    c = tc.cell(r,col, f"=MEDIAN({gcl(col)}{C0R}:{gcl(col)}{C1R})")
    c.number_format = MULT if col<9 else PCT; c.font = F(9, True, BLACK_F)
MED_R = r; r += 2

r = section(tc, r, "PLS Group valued against the peer median", span=8)
tc.cell(r,2,"FY27E EBITDA, base case (A$m)").font = F(9)
PE27 = r; tc.cell(r,4, f"='{SEN}'!{yl(F0)}{B['ebitda']}").number_format = CUR; tc.cell(r,4).font = F(9, False, BLACK_F); r += 1
LOWX = r; tc.cell(r,2,"Multiple applied - low").font = F(9)
tc.cell(r,4, 8.0).number_format = MULT; tc.cell(r,4).font = F(9, False, BLUE_IN); r += 1
HIGHX = r; tc.cell(r,2,"Multiple applied - high").font = F(9)
tc.cell(r,4, 11.0).number_format = MULT; tc.cell(r,4).font = F(9, False, BLUE_IN); r += 1
tc.cell(r,2,"Implied value per share - low (A$)").font = F(9, True)
CL = r; tc.cell(r,4, f"=(D{PE27}*D{LOWX}+{REF['netcash']})/{REF['shares']}").number_format = CUR2; tc.cell(r,4).font = F(9, True, BLACK_F); r += 1
tc.cell(r,2,"Implied value per share - high (A$)").font = F(9, True)
CH = r; tc.cell(r,4, f"=(D{PE27}*D{HIGHX}+{REF['netcash']})/{REF['shares']}").number_format = CUR2; tc.cell(r,4).font = F(9, True, BLACK_F); r += 1
tc.cell(r,2,"Midpoint (A$)").font = F(9, True, NAVY)
CM = r; tc.cell(r,4, f"=AVERAGE(D{CL},D{CH})").number_format = CUR2; tc.cell(r,4).font = F(10, True, BLACK_F)
tc.cell(r,4).fill = fill(YELLOW); r += 2
for t in [
 "Why a premium to the diversified peer median is warranted, and why it is capped.",
 "PLS is not a mature cash-return miner. Base-case volumes rise from 1,065kt in FY27 to 2,350kt by FY33, so a",
 "single-year forward multiple understates it - the diversified peers on this page are growing volumes at low",
 "single digits. Against that, PLS carries single-commodity risk and a price series that has moved by a factor of",
 "three inside two years. We therefore apply 8.0x to 11.0x, a premium to the ~7.8x peer median but well below the",
 "26.8x PLS itself traded at on trailing FY26 EBITDA before the earnings recovery came through.",
]:
    tc.cell(r,2,t).font = F(8, False, GREY, True); r += 1
TCN = "Trading Comps"

# ==================================================================
# 14. PRECEDENT TRANSACTIONS
# ==================================================================
pt = newsheet("Precedents", GREY, widths={"B":13,"C":24,"D":24,"E":15,"F":15,"G":62}, freeze=None)
title(pt, "Precedent transactions", "Lithium M&A, 2023-2026")
DEALS = [
 ("Mar-2025","Rio Tinto","Arcadium Lithium","US$6.7bn","All cash",
  "US$5.85/share. Rio becomes the third-largest global lithium producer; adds Rincon, Olaroz, Mt Cattlin, Fenix, James Bay."),
 ("Jan-2025","PLS Group","Latin Resources","A$560m","All scrip",
  "0.07 PLS shares per LRS share. Adds the Colina project in Brazil and preserves PLS's net cash position."),
 ("May-2026","Zhejiang Huayou Cobalt","Atlantic Lithium","US$210m","All cash",
  "US$0.25486/share, a 26.6% premium. Reported explicitly as a price-rebound-driven acquisition of Ewoyaa, Ghana."),
 ("Aug-2025","Sayona Mining","Piedmont Lithium","n/d","Merger of equals",
  "50/50 equity split creating Elevra Lithium. Both were sub-scale standalone through the price trough."),
 ("May-2024","SQM and Hancock","Azure Minerals","A$1.7bn","Scheme, cash",
  "A$3.70/share. Gives SQM its first Australian hard-rock foothold at Andover."),
 ("Oct-2023","Albemarle (withdrawn)","Liontown Resources","A$6.6bn","Cash, lapsed",
  "A$3.00/share, nearly double the pre-bid price. Collapsed after Hancock built a 19.9% blocking stake."),
 ("Jan-2024","Livent","Allkem","US$10.6bn","Merger of equals",
  "Created Arcadium Lithium, the entity Rio Tinto acquired 14 months later."),
 ("Oct-2025","Ganfeng Lithium","Leo Lithium (Goulamina 40%)","US$343m","Staged cash",
  "Consolidates operating control of Goulamina in Mali, plus a 1.5% gross revenue royalty for 20 years."),
]
r = 6
for j,h in enumerate(["Completed","Acquirer","Target","Value","Structure","Rationale and terms"]):
    c = pt.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
for dt,acq,tgt,val,stru,rat in DEALS:
    pt.cell(r,2,dt).font = F(9, False, GREY)
    pt.cell(r,3,acq).font = F(9, True)
    pt.cell(r,4,tgt).font = F(9)
    pt.cell(r,5,val).font = F(9, True, TEAL)
    pt.cell(r,6,stru).font = F(9, False, GREY)
    c = pt.cell(r,7,rat); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    pt.row_dimensions[r].height = 30
    r += 1
r += 1
r = section(pt, r, "Applying a control premium to PLS", span=5)
pt.cell(r,2,"Base-case value per share (A$)").font = F(9)
PB = r; pt.cell(r,5, f"='{SEN}'!$C${B['Value per share (A$)']}").number_format = CUR2; pt.cell(r,5).font = F(9, False, BLACK_F); r += 1
pt.cell(r,2,"Control premium observed in completed lithium deals").font = F(9)
PP = r; pt.cell(r,5, 0.266).number_format = PCT; pt.cell(r,5).font = F(9, False, BLUE_IN)
pt.cell(r,7,"Huayou / Atlantic Lithium, May-2026, the most recent completed cash deal with a disclosed premium").font = F(8, False, GREY, True); r += 1
pt.cell(r,2,"Implied takeout value per share (A$)").font = F(9, True, NAVY)
PTV = r; pt.cell(r,5, f"=E{PB}*(1+E{PP})").number_format = CUR2; pt.cell(r,5).font = F(10, True, BLACK_F)
pt.cell(r,5).fill = fill(YELLOW); r += 2
for t in [
 "A control premium is a reference point, not our target. PLS at ~A$17.6bn is large for this sector: the biggest",
 "completed lithium deal on this page, Rio Tinto and Arcadium, was US$6.7bn. Consolidation in 2026 has run through",
 "sub-scale developers rather than producers of PLS's size. We show the premium to frame downside support, not to",
 "argue PLS is a target.",
 "EV/resource multiples were deliberately left out: the disclosed resource statements for these targets are not on a",
 "consistent basis (JORC vs exploration target, ore tonnes vs LCE), so any multiple built from them would be spurious.",
]:
    pt.cell(r,2,t).font = F(8, False, GREY, True); r += 1
PTN = "Precedents"

# ==================================================================
# 15. FOOTBALL FIELD
# ==================================================================
ff = newsheet("Football Field", LIME, widths={"B":38,"C":14,"D":14,"E":14,"F":12,"G":58}, freeze=None)
title(ff, "Valuation summary", "Range by methodology, and the weighted 12-month target price")
r = 6
for j,h in enumerate(["Methodology","Low (A$)","High (A$)","Midpoint","Weight","Basis"]):
    c = ff.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
M0 = r
METHODS = [
 ("DCF - base case", f"='{SEN}'!$C${SE_RES['base']['Value per share (A$)']}",
  f"='{SEN}'!$C${SE_RES['base']['Value per share (A$)']}", 0.60,
  "WACC 8.88% built from the case's prescribed CAPM inputs. Terminal value is an annuity over the "
  "remaining ore base, not a growing perpetuity - an orebody is finite"),
 ("DCF - probability weighted (25/50/25)", f"='{SSN}'!$F${VPS_R}", f"='{SSN}'!$F${VPS_R}", 0.00,
  "Reference. Shown so the reader can see what the bear case does to the expected value"),
 ("DCF - scenario range", f"='{SEN}'!$C${SE_RES['bear']['Value per share (A$)']}",
  f"='{SEN}'!$C${SE_RES['bull']['Value per share (A$)']}", 0.00,
  "Bear to bull. Shown to frame asymmetry - the point estimate above already sits inside this range"),
 ("Trading comparables", f"='{TCN}'!$D${CL}", f"='{TCN}'!$D${CH}", 0.40,
  "8.0x to 11.0x FY27E EBITDA against a diversified peer median near 7.8x"),
 ("Precedent transactions", f"='{SEN}'!$C${SE_RES['base']['Value per share (A$)']}", f"='{PTN}'!$E${PTV}", 0.00,
  "Reference only. Transaction EV/EBITDA could not be sourced on a consistent basis, and applying a "
  "premium to our own DCF would be circular"),
 ("Broker target range (individual analysts)", 2.50, 6.83, 0.00,
  "Full individual spread across 17-20 analysts, Aug-Sep 2026. Vendor averages cluster A$4.50-5.70; "
  "our A$6.12 sits inside the individual range, below the most bullish. Reference only"),
 ("52-week trading range", P.WK52_LOW, P.WK52_HIGH, 0.00, "Where the market has actually traded - reference only"),
]
for nm, lo, hi, w, basis in METHODS:
    ff.cell(r,2,nm).font = F(9, True)
    c = ff.cell(r,3,lo); c.number_format = CUR2; c.font = F(9, False, BLACK_F if isinstance(lo,str) else BLUE_IN)
    c = ff.cell(r,4,hi); c.number_format = CUR2; c.font = F(9, False, BLACK_F if isinstance(hi,str) else BLUE_IN)
    c = ff.cell(r,5,f"=AVERAGE(C{r}:D{r})"); c.number_format = CUR2; c.font = F(9, True, BLACK_F)
    c = ff.cell(r,6,w); c.number_format = PCT; c.font = F(9, False, BLUE_IN)
    c = ff.cell(r,7,basis); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    ff.row_dimensions[r].height = 26
    r += 1
M1 = r-1
ff.cell(r,2,"Total weight").font = F(9, True)
ff.cell(r,6, f"=SUM(F{M0}:F{M1})").number_format = PCT; ff.cell(r,6).font = F(9, True, BLACK_F)
r += 2
TGT = r
ff.cell(r,2,"12-month target price (A$)").font = F(12, True, NAVY)
ff.cell(r,3, f"=SUMPRODUCT(E{M0}:E{M1},F{M0}:F{M1})/SUM(F{M0}:F{M1})").number_format = CUR2
ff.cell(r,3).font = F(14, True, BLACK_F); ff.cell(r,3).fill = fill(YELLOW); ff.cell(r,3).border = thin(NAVY)
r += 1
ff.cell(r,2,"Last close (A$)").font = F(9)
ff.cell(r,3, f"={REF['price']}").number_format = CUR2; ff.cell(r,3).font = F(9, False, BLACK_F); r += 1
UPR = r
ff.cell(r,2,"Implied upside / (downside)").font = F(11, True, NAVY)
ff.cell(r,3, f"=C{TGT}/C{TGT+1}-1").number_format = PCT; ff.cell(r,3).font = F(13, True, BLACK_F)
ff.cell(r,3).fill = fill(YELLOW); ff.cell(r,3).border = thin(NAVY); r += 1
ff.cell(r,2,"Plus forecast FY27 dividend yield").font = F(9)
ff.cell(r,3, f"='{IS}'!{yl(F0)}{IS_YLD}").number_format = PCT; ff.cell(r,3).font = F(9, False, BLACK_F); r += 1
TSR_R = r
ff.cell(r,2,"Implied 12-month total return").font = F(10, True, NAVY)
ff.cell(r,3, f"=C{UPR}+C{UPR+1}").number_format = PCT; ff.cell(r,3).font = F(11, True, BLACK_F); r += 1
ff.cell(r,2,"S&P/ASX 200 return, FY26 (benchmark)").font = F(9)
ff.cell(r,3, f"={REF['bench']}").number_format = PCT; ff.cell(r,3).font = F(9, False, BLACK_F); r += 1
ff.cell(r,2,"Implied outperformance").font = F(10, True, NAVY)
ff.cell(r,3, f"=C{TSR_R}-C{TSR_R+1}").number_format = PCT; ff.cell(r,3).font = F(11, True, BLACK_F); r += 2
srcnote(ff, r, "The DCF carries 60% because it is the only method that prices the volume growth from P2000 and Colina. Comparables carry 40% as the discipline of what the market pays for a producing miner today. Precedents, consensus and the trading range are shown but not weighted.")
FFN = "Football Field"

# ==================================================================
# 16. RETURNS
# ==================================================================
rt = newsheet("Returns", LIME, widths={"B":42,"C":15,"D":15,"E":15,"F":50}, freeze=None)
title(rt, "Returns", "Against the fund's benchmark and mandate")
r = 6
r = section(rt, r, "Mandate", span=4)
RT_BENCH = r
r = kv(rt, r, "S&P/ASX 200 return, FY26", f"={REF['bench']}", PCT, color=BLACK_F, vcol=3,
       note="Case p.4")
r = kv(rt, r, "Fund return, FY25", P.FUND_RET_FY25, PCT, vcol=3, note="Case p.4 - beat the index by 2.0%")
r = kv(rt, r, "Outperformance the fund must repeat", 0.02, PCT, vcol=3)
r += 1
r = section(rt, r, "This recommendation", span=4)
r = kv(rt, r, "Entry price (A$)", f"={REF['price']}", CUR2, color=BLACK_F, vcol=3)
r = kv(rt, r, "12-month target (A$)", f"='{FFN}'!$C${TGT}", CUR2, color=BLACK_F, vcol=3)
r = kv(rt, r, "Capital return", f"='{FFN}'!$C${UPR}", PCT, color=BLACK_F, vcol=3)
r = kv(rt, r, "Dividend yield, FY27E", f"='{IS}'!{yl(F0)}{IS_YLD}", PCT, color=BLACK_F, vcol=3)
RT_TSR = r
r = kv(rt, r, "Total shareholder return, 12 months", f"='{FFN}'!$C${TSR_R}", PCT, bold=True, color=BLACK_F, vcol=3)
r = kv(rt, r, "Excess return over benchmark", f"=C{RT_TSR}-C{RT_BENCH}", PCT, bold=True, color=BLACK_F, vcol=3)
r += 1
r = section(rt, r, "Multi-year hold", span=4)
r = kv(rt, r, "Bear case value per share (A$)", f"='{SEN}'!$C${SE_RES['bear']['Value per share (A$)']}", CUR2, color=BLACK_F, vcol=3)
BRR = r-1
r = kv(rt, r, "Base case value per share (A$)", f"='{SEN}'!$C${SE_RES['base']['Value per share (A$)']}", CUR2, color=BLACK_F, vcol=3)
r = kv(rt, r, "Bull case value per share (A$)", f"='{SEN}'!$C${SE_RES['bull']['Value per share (A$)']}", CUR2, color=BLACK_F, vcol=3)
BLR = r-1
r = kv(rt, r, "Downside to bear", f"=C{BRR}/{REF['price']}-1", PCT, color=BLACK_F, vcol=3)
r = kv(rt, r, "Upside to bull", f"=C{BLR}/{REF['price']}-1", PCT, color=BLACK_F, vcol=3)
RRR = r
r = kv(rt, r, "Reward-to-risk ratio", f"=IFERROR(ABS(C{r-1}/C{r-2}),0)", '0.00"x"', bold=True, color=BLACK_F, vcol=3,
       note="Upside to bull divided by downside to bear")
r += 1
r = section(rt, r, "Stress test: does the bear case clear the price the market actually printed?", span=4)
r = kv(rt, r, "52-week low, actually traded (A$)", P.WK52_LOW, CUR2, vcol=3,
       note="Reached when spodumene was at its trough")
LOWX2 = r-1
r = kv(rt, r, "Our bear case (A$)", f"=C{BRR}", CUR2, color=BLACK_F, vcol=3)
r = kv(rt, r, "Bear case premium to the traded low", f"=C{r-1}/C{LOWX2}-1", PCT, bold=True, color=BLACK_F, vcol=3)
r += 1
for t in ["At the A$1.91 low the company held A$974m of cash and was loss-making. It now holds A$2,290m and earned",
          "A$526m. Our bear case assumes prices revert to the marginal cost, P2000 is never sanctioned, Colina never",
          "proceeds and volumes stay flat for a decade - all at once. Reaching the old low from here would take",
          "conditions materially worse than the trough the market has already lived through."]:
    rt.cell(r,2,t).font = F(8, False, GREY, True); r += 1
r += 1
srcnote(rt, r, "A long-only fund benchmarked to the ASX 200 needs positions where the asymmetry, not just the point estimate, is favourable.")
RTN = "Returns"

# ==================================================================
# 12b. DOWNSTREAM OPTION  (Porter & Kramer level 1 - reconceiving markets)
# ==================================================================
do = newsheet("Downstream Option", TEAL, widths={"B":34,"C":13,"D":13,"E":13,"F":11,"G":12,"H":54}, freeze=None)
title(do, "The low-carbon downstream option",
      "Sized deliberately OUTSIDE the target price. This is where the shared value actually is.")
r = 6
for t in [
 "Why this sits outside the target. None of the three levers below is earning yet: the mid-stream plant",
 "produces its first lithium phosphate in the September 2026 quarter, the POSCO joint venture is still ramping,",
 "and we found no verified carbon-linked premium in any disclosed PLS contract. We size them here so the reader",
 "can see the prize, and we keep them out of the A$6.12 target so the recommendation does not depend on them.",
]:
    do.cell(r,2,t).font = F(9, False, GREY, True); r += 1
r += 1

for j,h in enumerate(["Lever","Volume","Unit margin","EBITDA A$m","Multiple","NPV A$m","Basis"]):
    c = do.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
D0 = r
# --- 1. mid-stream lithium phosphate
do.cell(r,2,"Mid-stream lithium phosphate").font = F(9, True, TEAL)
do.cell(r,3, 400.0).number_format = NUM_A; do.cell(r,3).font = F(9, False, BLUE_IN)
do.cell(r,4, 480.0).number_format = CUR;   do.cell(r,4).font = F(9, False, BLUE_IN)
do.cell(r,5, f"=C{r}*D{r}/1000").number_format = CUR; do.cell(r,5).font = F(9, False, BLACK_F)
do.cell(r,6, 8.0).number_format = MULT;    do.cell(r,6).font = F(9, False, BLUE_IN)
do.cell(r,7, f"=E{r}*F{r}").number_format = CUR; do.cell(r,7).font = F(9, True, BLACK_F)
do.cell(r,8,"kt of concentrate calcined in-house (20% of a 2Mtpa base), at the conversion margin "
            "retained rather than ceded to a third-party converter").font = F(8, False, GREY)
do.cell(r,8).alignment = Alignment(wrap_text=True, vertical="top"); do.row_dimensions[r].height = 34; r += 1
# --- 2. POSCO JV
do.cell(r,2,"POSCO JV equity earnings").font = F(9, True, TEAL)
do.cell(r,3, 43.0).number_format = NUM_A1; do.cell(r,3).font = F(9, False, BLUE_IN)
do.cell(r,4, 4200.0).number_format = CUR;  do.cell(r,4).font = F(9, False, BLUE_IN)
POSCO_PC = r
do.cell(r,5, f"=C{r}*D{r}/1000*0.18").number_format = CUR; do.cell(r,5).font = F(9, False, BLACK_F)
do.cell(r,6, 8.0).number_format = MULT;    do.cell(r,6).font = F(9, False, BLUE_IN)
do.cell(r,7, f"=E{r}*F{r}").number_format = CUR; do.cell(r,7).font = F(9, True, BLACK_F)
do.cell(r,8,"ktpa lithium hydroxide at Gwangyang, A$/t conversion margin, PLS share 18%. "
            "PLS holds an option to lift that stake to 30%.").font = F(8, False, GREY)
do.cell(r,8).alignment = Alignment(wrap_text=True, vertical="top"); do.row_dimensions[r].height = 34; r += 1
# --- 3. qualification premium
do.cell(r,2,"Low-carbon qualification premium").font = F(9, True, TEAL)
do.cell(r,3, 1000.0).number_format = NUM_A; do.cell(r,3).font = F(9, False, BLUE_IN)
do.cell(r,4, 75.0).number_format = CUR;     do.cell(r,4).font = F(9, False, BLUE_IN)
do.cell(r,5, f"=C{r}*D{r}/1000").number_format = CUR; do.cell(r,5).font = F(9, False, BLACK_F)
do.cell(r,6, 8.0).number_format = MULT;     do.cell(r,6).font = F(9, False, BLUE_IN)
do.cell(r,7, f"=E{r}*F{r}").number_format = CUR; do.cell(r,7).font = F(9, True, BLACK_F)
do.cell(r,8,"kt of qualified volume at an A$/t premium. Illustrative only: no verified carbon-linked "
            "premium exists in PLS's disclosed contracts today.").font = F(8, False, GREY)
do.cell(r,8).alignment = Alignment(wrap_text=True, vertical="top"); do.row_dimensions[r].height = 34; r += 1
D1 = r-1
do.cell(r,2,"Unrisked total").font = F(10, True, NAVY)
do.cell(r,5, f"=SUM(E{D0}:E{D1})").number_format = CUR; do.cell(r,5).font = F(10, True, BLACK_F)
UNRISK = r
do.cell(r,7, f"=SUM(G{D0}:G{D1})").number_format = CUR; do.cell(r,7).font = F(10, True, BLACK_F); r += 2

r = section(do, r, "Risking and per-share value", span=6)
for j,h in enumerate(["Lever","NPV A$m","Probability","Risked A$m","A$/share"]):
    c = do.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
R0 = r
RISKS = [("Mid-stream lithium phosphate", D0,   0.45, "Plant is built and commissioned; first product due Sep-qtr 2026. Scale-up beyond the demonstration unit is not funded."),
         ("POSCO JV equity earnings",     D0+1, 0.70, "Both trains built; Train 2 ramping. Lowest execution risk of the three."),
         ("Low-carbon qualification premium", D0+2, 0.25, "Directionally supported by EU and US policy, but unproven in PLS's contracts. Priced sceptically.")]
for nm, src, pr, basis in RISKS:
    do.cell(r,2,nm).font = F(9, True)
    do.cell(r,3, f"=G{src}").number_format = CUR; do.cell(r,3).font = F(9, False, BLACK_F)
    do.cell(r,4, pr).number_format = PCT; do.cell(r,4).font = F(9, False, BLUE_IN)
    do.cell(r,5, f"=C{r}*D{r}").number_format = CUR; do.cell(r,5).font = F(9, False, BLACK_F)
    do.cell(r,6, f"=E{r}/{REF['shares']}").number_format = CUR2; do.cell(r,6).font = F(9, True, BLACK_F)
    do.cell(r,7, basis).font = F(8, False, GREY)
    do.cell(r,7).alignment = Alignment(wrap_text=True, vertical="top"); do.row_dimensions[r].height = 30
    r += 1
R1 = r-1
DO_TOT = r
do.cell(r,2,"Risked downstream option").font = F(11, True, NAVY)
do.cell(r,5, f"=SUM(E{R0}:E{R1})").number_format = CUR; do.cell(r,5).font = F(11, True, BLACK_F)
DO_PS = r
do.cell(r,6, f"=SUM(F{R0}:F{R1})").number_format = CUR2; do.cell(r,6).font = F(12, True, BLACK_F)
do.cell(r,6).fill = fill(YELLOW); do.cell(r,6).border = thin(NAVY); r += 2

r = section(do, r, "What this does to the recommendation", span=6)
do.cell(r,2,"12-month target price (A$)").font = F(9)
do.cell(r,4, f"='{FFN}'!$C${TGT}").number_format = CUR2; do.cell(r,4).font = F(9, False, BLACK_F); r += 1
do.cell(r,2,"Last close (A$)").font = F(9)
do.cell(r,4, f"={REF['price']}").number_format = CUR2; do.cell(r,4).font = F(9, False, BLACK_F); r += 1
UPS = r
do.cell(r,2,"Upside in the target (A$/share)").font = F(9, True)
do.cell(r,4, f"=D{r-2}-D{r-1}").number_format = CUR2; do.cell(r,4).font = F(9, True, BLACK_F); r += 1
do.cell(r,2,"Shared value already inside the target (A$/share)").font = F(9)
INBRIDGE = r
do.cell(r,4, f"='{EBN}'!$D${ESG_TOT}").number_format = CUR2; do.cell(r,4).font = F(9, False, BLACK_F); r += 1
do.cell(r,2,"Share of the upside attributable to shared value").font = F(10, True, NAVY)
do.cell(r,4, f"=D{INBRIDGE}/D{UPS}").number_format = PCT; do.cell(r,4).font = F(12, True, BLACK_F)
do.cell(r,4).fill = fill(YELLOW); do.cell(r,4).border = thin(NAVY); r += 1
do.cell(r,2,"Plus the downstream option, outside the target (A$/share)").font = F(9)
do.cell(r,4, f"=F{DO_PS}").number_format = CUR2; do.cell(r,4).font = F(9, False, BLACK_F); r += 1
do.cell(r,2,"Target plus the risked option (A$/share)").font = F(10, True, NAVY)
do.cell(r,4, f"=D{UPS-2}+F{DO_PS}").number_format = CUR2; do.cell(r,4).font = F(11, True, BLACK_F); r += 2

for t in [
 "The point of this sheet. Measured against the A$6.12 target, the shared-value bridge looks like a rounding",
 "adjustment. Measured against the UPSIDE - the A$0.64 per share between the last close and the target - it is",
 "most of the investment case. The market is paying for a lithium miner. We are paying for the operator whose",
 "carbon position and downstream reach let it sell tonnes the others cannot. That gap is the recommendation.",
]:
    do.cell(r,2,t).font = F(8, False, GREY, True); r += 1
DON = "Downstream Option"

# ==================================================================
# 17. SOTP NAV
# ==================================================================
sp = newsheet("SOTP NAV", LIME, widths={"B":34,"C":14,"D":13,"E":14,"F":13,"G":56}, freeze=None)
title(sp, "Sum of the parts", "Risked net asset value as a cross-check on the consolidated DCF")
r = 6
for j,h in enumerate(["Asset","Unrisked A$m","Risking","Risked A$m","A$/share","Basis"]):
    c = sp.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
N0 = r
NAV = [
 ("Pilgangoora - Pilgan plant", 9800.0, 1.00,
  "In production, ~920ktpa steady state. Carried at the DCF value of the producing base."),
 ("Ngungaju plant", 1450.0, 0.95,
  "Restarted July 2026, ~195ktpa. Small risking for ramp-up execution."),
 ("P2000 expansion", 2600.0, 0.70,
  "PFS incremental NPV A$2.6bn, 55% IRR. Risked for an FID that has not been taken; DFS due Dec-qtr 2026."),
 ("Colina, Brazil", 900.0, 0.40,
  "77.7Mt at 1.24% Li2O. DFS only due Dec-qtr 2027, no FID, no permits. Heavily risked."),
 ("Mid-stream plant (Calix)", 260.0, 0.50,
  "Demonstration scale, opened Jun-26, first production guided Sep-qtr 2026. Optionality, not yet earnings."),
 ("POSCO JV, 18% of PPLS", 320.0, 0.85,
  "18% of a 43ktpa lithium hydroxide facility at Gwangyang, with an option to move to 30%."),
 ("Exploration and other tenements", 180.0, 0.50,
  "Includes the tenements acquired adjacent to Colina."),
 ("Corporate costs, capitalised", -900.0, 1.00,
  "Present value of unallocated corporate and administration costs."),
]
for nm, val, risk, basis in NAV:
    sp.cell(r,2,nm).font = F(9, True)
    c = sp.cell(r,3,val); c.number_format = CUR; c.font = F(9, False, BLUE_IN)
    c = sp.cell(r,4,risk); c.number_format = PCT; c.font = F(9, False, BLUE_IN)
    c = sp.cell(r,5,f"=C{r}*D{r}"); c.number_format = CUR; c.font = F(9, False, BLACK_F)
    c = sp.cell(r,6,f"=E{r}/{REF['shares']}"); c.number_format = CUR2; c.font = F(9, False, BLACK_F)
    c = sp.cell(r,7,basis); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    sp.row_dimensions[r].height = 26
    r += 1
N1 = r-1
sp.cell(r,2,"Enterprise NAV").font = F(10, True, NAVY)
sp.cell(r,5, f"=SUM(E{N0}:E{N1})").number_format = CUR; sp.cell(r,5).font = F(10, True, BLACK_F)
sp.cell(r,6, f"=E{r}/{REF['shares']}").number_format = CUR2; sp.cell(r,6).font = F(10, True, BLACK_F); r += 1
sp.cell(r,2,"Net cash").font = F(9)
sp.cell(r,5, f"={REF['netcash']}").number_format = CUR; sp.cell(r,5).font = F(9, False, BLACK_F)
sp.cell(r,6, f"=E{r}/{REF['shares']}").number_format = CUR2; sp.cell(r,6).font = F(9, False, BLACK_F); r += 1
SPT = r
sp.cell(r,2,"Equity NAV").font = F(11, True, NAVY)
sp.cell(r,5, f"=E{r-2}+E{r-1}").number_format = CUR; sp.cell(r,5).font = F(11, True, BLACK_F)
sp.cell(r,6, f"=E{r}/{REF['shares']}").number_format = CUR2; sp.cell(r,6).font = F(12, True, BLACK_F)
sp.cell(r,6).fill = fill(YELLOW); sp.cell(r,6).border = thin(NAVY); r += 1
sp.cell(r,2,"Premium / (discount) of last close to NAV").font = F(9, True)
sp.cell(r,6, f"={REF['price']}/F{SPT}-1").number_format = PCT; sp.cell(r,6).font = F(10, True, BLACK_F); r += 2
for t in [
 "The SOTP is a cross-check, not the primary method. Asset NPVs are our own estimates built from the same",
 "price deck and discount rate as the consolidated DCF, except P2000 which uses the company's own PFS figure.",
 "Risk weightings are judgement: P2000 at 70% reflects a study due in the December 2026 quarter and a board",
 "that has already committed A$175m of pre-FID capital; Colina at 40% reflects a study still a year further out.",
]:
    sp.cell(r,2,t).font = F(8, False, GREY, True); r += 1

# ==================================================================
# 18. SOURCES
# ==================================================================
so = newsheet("Sources", GREY, widths={"B":40,"C":16,"D":10,"E":70}, freeze=None)
title(so, "Source register", "Provenance for every input. Tags: A actual, G guidance, M market, D derived, E our estimate, C prescribed by the case")
r = 6
for j,h in enumerate(["Input","Value","Tag","Source"]):
    c = so.cell(r,2+j,h); c.font = F(9, True, WHITE); c.fill = fill(NAVY)
r += 1
SRC = [
 ("Risk-free rate","5.00%","C","FMAA / Shared Value Project, Investing for the Future Case 2026, p.6 - prescribed"),
 ("Market risk premium","6.00%","C","FMAA case p.6 - prescribed"),
 ("Equity beta","0.73","C","FMAA case p.6, sourced there to Yahoo Finance 5Y monthly"),
 ("Benchmark return FY26","5.90%","C","FMAA case p.4, S&P/ASX 200"),
 ("Last close","A$5.48","M","Market Index and Google Finance quote pages, early Sep-2026"),
 ("52-week range","A$1.91 - A$6.81","M","Market Index, ASX:PLS"),
 ("Shares on issue","3,220m","M","stockanalysis.com; consistent with ASX quotation notices (~3,223.6m)"),
 ("FY26 revenue","A$1,934m","A","FY26 results, 24-Aug-2026; +152% YoY"),
 ("FY26 underlying EBITDA","A$1,137m","A","FY26 results; 59% margin"),
 ("FY26 statutory NPAT","A$526m","A","FY26 results"),
 ("FY26 production","879.5kt","A","FY26 results; +17%, beat guidance by ~10kt"),
 ("FY26 sales","891.6kt","A","FY26 results"),
 ("FY26 realised price","US$1,488/t","A","FY26 results; +121% YoY"),
 ("Q4 FY26 realised price","US$2,107/t actual grade; US$2,415/t SC6-equivalent","A","June-2026 quarterly activities report"),
 ("FY26 unit operating cost","A$569/t FOB","A","FY26 results; -9% YoY"),
 ("FY26 capex","A$328m","A","FY26 results; mine development A$146m plus infrastructure and sustaining A$182m"),
 ("FY26 closing cash","A$2,290m","A","FY26 results; total liquidity A$2,790m"),
 ("Borrowings","US$600m senior unsecured notes","A","Inaugural international bond issued April 2026"),
 ("FY26 final dividend","5.0cps fully franked","A","FY26 results; ~22% of adjusted free cash flow, policy 20-30%"),
 ("FY27 production guidance","1,030 - 1,100kt","G","Given with FY26 results, 24-Aug-2026"),
 ("FY27 unit cost guidance","A$575 - 625/t FOB","G","Same; step-up attributed to Ngungaju mix"),
 ("FY27 capex guidance","A$620 - 685m","G","Same; includes A$175m approved P2000 pre-FID"),
 ("FY27 Colina spend","A$45 - 55m","G","Same"),
 ("Mineral Resource","446Mt @ 1.28% Li2O, 5.7Mt contained","A","Resource update, June 2025; +23% contained Li2O"),
 ("Ore Reserve","214Mt @ 1.19% Li2O","A","Ore Reserve statement, August 2023 - predates the 2025 resource upgrade"),
 ("P2000 economics","A$2.6bn incremental NPV, 55% IRR, ~A$1.2bn capex","A","P2000 Pre-Feasibility Study, June 2024"),
 ("P2000 timing","DFS Dec-qtr 2026; first ore mid-2029 if sanctioned","G","Company guidance"),
 ("Ngungaju","~200ktpa; idled Dec-2024; restarted Jul-2026","A","Company announcements"),
 ("P680 ore sorting","World's largest lithium ore sorter, >1,000t/hr, A$103m","A","Commissioned Aug-2024; TOMRA sensor-based sorter; part-funded by NAIF"),
 ("Mid-stream plant","100% owned, Calix electric calcination, >80% calcination emissions cut","A","Opened 5-Jun-2026; first production guided Sep-qtr 2026; ARENA-backed"),
 ("POSCO JV","PLS 18%, option to 30%; 43ktpa lithium hydroxide","A","POSCO Pilbara Lithium Solution, Gwangyang, South Korea"),
 ("Colina","77.7Mt @ 1.24% Li2O; DFS Dec-qtr 2027","A","Acquired with Latin Resources, effective Jan-2025"),
 ("Net zero target","Decade commencing 2040","A","Company climate disclosure - a decade window, not a single year"),
 ("Power emissions intensity target","~48% lower by 2027; up to 80% by 2030 if wind available","A","Company power strategy"),
 ("FY25 emissions","7.1% reduction in absolute Scope 1 and 2","A","FY25 full-year results commentary"),
 ("Spodumene spot","US$2,038/t SC6 FOB Australia (12-Aug-26); Platts SpodIX US$2,200/t CIF China","M","Benchmark Mineral Intelligence; S&P Global Platts"),
 ("Lithium carbonate spot","US$18,310/t (12-Aug-26); CNY 152,000/t (4-Sep-26)","M","Benchmark Mineral Intelligence; Trading Economics"),
 ("2026 spodumene forecast","US$2,236/t average","M","Australian Government Resources and Energy Quarterly, June 2026"),
 ("Cost curve","Greenbushes ~US$220/t FOB cash cost; lepidolite >US$1,100/dmt at ~90th percentile","M","S&P Global Market Intelligence; CRU Group"),
 ("Greenfield incentive price","Sustainably above US$20,000-25,000/t LCE","M","Benchmark Mineral Intelligence"),
 ("CATL Jianxiawo","~150ktpa LCE; suspended Aug-2025, restarted mid-2026, re-suspended Aug-2026","M","Benchmark cut its 2026 site estimate from 62.5kt to 32kt LCE"),
 ("Zimbabwe export ban","All raw mineral and concentrate exports banned from 25-Feb-2026","M","Government of Zimbabwe"),
 ("BESS demand","Installations +51% in 2025; share of lithium demand ~23% to ~31% in 2026e","M","Industry data via Benchmark and Rho Motion"),
 ("Short interest","~20% of shares (Sep-2024, most shorted on ASX) falling to ~6.8% (26-May-2026)","M","ASIC short position reports via shortman.com.au"),
 ("Consensus target","~A$4.50 - 5.70 average; full range A$2.50 - 6.83","M","Vendor consensus reads, Aug-Sep 2026; consensus rating Buy"),
 ("Peer multiples","RIO 7.84x, S32 8.48x, MIN 7.82x, FMG 5.55x EV/EBITDA","M","Data vendors, Aug-2026 - see Trading Comps for the vendor-disagreement caveat"),
 ("Rio Tinto / Arcadium","US$6.7bn, completed 6-Mar-2025","M","Company announcements"),
 ("Huayou / Atlantic Lithium","US$210m at a 26.6% premium, announced May-2026","M","Company announcements"),
]
for nm, val, tag, src in SRC:
    so.cell(r,2,nm).font = F(9, True)
    c = so.cell(r,3,val); c.font = F(9, False, TEAL)
    c = so.cell(r,4,tag); c.font = F(9, True, {"A":TEAL,"G":TEAL,"M":GREY,"D":AMBER,"E":AMBER,"C":NAVY}.get(tag,GREY))
    c.alignment = Alignment(horizontal="center")
    c = so.cell(r,5,src); c.font = F(8, False, GREY); c.alignment = Alignment(wrap_text=True, vertical="top")
    r += 1
r += 1
for t in [
 "Verification note. Company sites and the ASX announcements platform could not be opened directly from the",
 "environment used to build this model, so reported figures were corroborated across two or more independent",
 "secondary reports of the same announcement rather than read off the primary PDF. Headline FY26 figures are",
 "consistent across sources. Figures tagged E are our own estimates and are identified as such wherever they appear.",
 "Known unresolved items: total borrowings at 30-Jun-26 (only the US$600m notes issue is confirmed); FY24",
 "comparatives; the Ore Reserve has not been restated since August 2023; and PLS's Scope 3 emissions are not disclosed.",
]:
    so.cell(r,2,t).font = F(8, False, GREY, True); r += 1

# ------------------------------------------------------------------ order and save
order = ["Cover","Assumptions","Deck","Revenue Build","Income Statement","Balance Sheet","Cash Flow",
         "DCF","Scenario Engine","Scenario Summary","Sensitivity","SOTP NAV","Trading Comps",
         "Precedents","Football Field","ESG Value Bridge","Downstream Option","Returns","Sources"]
wb._sheets = [wb[n] for n in order if n in wb.sheetnames] + [s for s in wb._sheets if s.title not in order]
wb.active = 0
wb.save(OUT)
print("saved:", OUT)
print("sheets:", len(wb.sheetnames))
