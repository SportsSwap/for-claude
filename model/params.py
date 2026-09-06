# -*- coding: utf-8 -*-
"""
PLS Group Limited (ASX:PLS) - Valuation model parameters
FMAA x Shared Value Project "Investing for the Future" Case Competition 2026

EVERY number carries a provenance tag:
    A   = reported actual (company disclosure)
    G   = company guidance
    M   = market data
    D   = derived arithmetically from reported figures
    E   = analyst estimate (ours) - must be justified in the deck
    C   = prescribed by the case document

Update this file as research lands; build_model.py consumes it.
"""

# ---------------------------------------------------------------- meta
COMPANY      = "PLS Group Limited"
TICKER       = "ASX: PLS"
VALN_DATE    = "5 September 2026"
CURRENCY     = "A$"
TEAM         = "FMAA Asset Management - Shared Value Coverage"

# ---------------------------------------------------------------- market data (M)
SHARE_PRICE      = 5.48          # M  A$/sh, last close early Sep-26
SHARES_OUT_M     = 3220.0        # M  million shares on issue
WK52_HIGH        = 6.81          # M
WK52_LOW         = 1.91          # M

# ---------------------------------------------------------------- case-prescribed (C)
RISK_FREE        = 0.0500        # C  FMAA case p.6
MRP              = 0.0600        # C  FMAA case p.6
BETA             = 0.73          # C  FMAA case p.6 (Yahoo 5Y monthly)
TAX_RATE         = 0.30          # Australian corporate rate
BENCH_RET_FY26   = 0.0590        # C  S&P/ASX 200 FY26 return
FUND_RET_FY25    = 0.0790        # C  fund return FY25

# ---------------------------------------------------------------- capital structure
COST_OF_DEBT     = 0.0625        # E  indicative on US$600m senior notes - VERIFY
CASH_FY26        = 2290.0        # A  A$m closing cash FY26 (total liquidity A$2,790m)
DEBT_FY26        = 853.0         # A  reported borrowings at 30-Jun-26, after the US$600m notes issue
                                 #    net of revolving credit facility repayments
TARGET_D_RATIO   = 0.10          # E  target debt / (debt+equity)

# ---------------------------------------------------------------- FX
AUDUSD = {  # M / E
    "FY24A": 0.657, "FY25A": 0.646, "FY26A": 0.650,
    "FY27F": 0.660, "FY28F": 0.670, "FY29F": 0.680, "FY30F": 0.690,
    "FY31F": 0.700, "FY32F": 0.700, "FY33F": 0.700, "FY34F": 0.700,
    "FY35F": 0.700, "FY36F": 0.700,
}

YEARS   = ["FY24A","FY25A","FY26A","FY27F","FY28F","FY29F","FY30F",
           "FY31F","FY32F","FY33F","FY34F","FY35F","FY36F"]
HIST    = ["FY24A","FY25A","FY26A"]
FCST    = ["FY27F","FY28F","FY29F","FY30F","FY31F","FY32F","FY33F","FY34F","FY35F","FY36F"]

# ---------------------------------------------------------------- historicals
# FY26A reported; FY25A and FY24A derived from disclosed growth rates (D) - VERIFY vs annual report
HIST_DATA = {
    "production_kt":   {"FY24A": 725.3, "FY25A": 755.6, "FY26A": 879.5},   # A (FY25/26), E (FY24)
    "sales_kt":        {"FY24A": 707.0, "FY25A": 749.0, "FY26A": 891.6},   # A (FY26), E
    "realised_usd_t":  {"FY24A": 1116.0,"FY25A":  688.0,"FY26A": 1488.0},  # A (FY26), D
    "unit_cost_aud_t": {"FY24A":  655.0,"FY25A":  627.0,"FY26A":  569.0},  # A (FY25/26)
    "revenue_am":      {"FY24A": 1254.0,"FY25A":  769.0,"FY26A": 1934.0},  # A (FY25/26)
    "ebitda_am":       {"FY24A":  538.0,"FY25A":   97.0,"FY26A": 1137.0},  # A underlying (FY25/26)
    "npat_am":         {"FY24A":  257.8,"FY25A": -196.0,"FY26A":  526.0},  # A statutory (FY25/26)
    "capex_am":        {"FY24A":  820.0,"FY25A":  500.0,"FY26A":  328.0},  # A (FY26), E
}

# ---------------------------------------------------------------- FY27 guidance (G)
FY27_PROD_LOW,  FY27_PROD_HIGH  = 1030.0, 1100.0     # G  kt
FY27_COST_LOW,  FY27_COST_HIGH  =  575.0,  625.0     # G  A$/t FOB
FY27_CAPEX_LOW, FY27_CAPEX_HIGH =  620.0,  685.0     # G  A$m
FY27_CAPEX_MINEDEV   = (250.0, 280.0)                # G
FY27_CAPEX_SUSTAIN   = ( 85.0, 100.0)                # G
FY27_CAPEX_INFRA     = (110.0, 130.0)                # G
FY27_CAPEX_P2000     = 175.0                         # G  approved pre-FID
FY27_COLINA_SPEND    = ( 45.0,  55.0)                # G

# ---------------------------------------------------------------- resource / reserve (A)
RESOURCE_MT      = 446.0     # A  Mt @ 2025 update
RESOURCE_GRADE   = 0.0128    # A  1.28% Li2O
RESOURCE_LI2O_MT = 5.7       # A  Mt contained Li2O
RESERVE_MT       = 214.2     # A  Mt
RESERVE_GRADE    = 0.0119    # A  1.19% Li2O

# ---------------------------------------------------------------- production profile by asset (E)
# kt of spodumene concentrate. Pilgangoora core = existing Pilgan plant; Ngungaju restarting FY27;
# P2000 first production assumed FY30 post-FID; Colina (Brazil) assumed FY32 first production.
PRODUCTION = {
    # Pilgan plant ~1.0Mtpa nameplate post-P1000 (FY26A delivered 879.5kt with Ngungaju idle).
    # Ngungaju ~200ktpa nameplate, restarted Jul-26, steady state within 4 months of FY27.
    # P2000 lifts total Pilgangoora capacity above 2.0Mtpa; PFS 1.9Mtpa avg over first 10 years,
    # first ore guided mid-2029 (= FY30). Shown here as the increment over Pilgan + Ngungaju.
    # Colina (Brazil) DFS due Dec-qtr 2027, no FID; Latin Resources PEA implied ~500ktpa SC5.2-equiv.
    "base": {
        "pilgan":  {"FY27F": 900, "FY28F": 920, "FY29F": 920, "FY30F": 920, "FY31F": 920,
                    "FY32F": 920, "FY33F": 920, "FY34F": 920, "FY35F": 920, "FY36F": 920},
        "ngungaju":{"FY27F": 165, "FY28F": 195, "FY29F": 195, "FY30F": 195, "FY31F": 195,
                    "FY32F": 195, "FY33F": 195, "FY34F": 195, "FY35F": 195, "FY36F": 195},
        "p2000":   {"FY27F":   0, "FY28F":   0, "FY29F":   0, "FY30F": 250, "FY31F": 550,
                    "FY32F": 800, "FY33F": 885, "FY34F": 885, "FY35F": 885, "FY36F": 885},
        "colina":  {"FY27F":   0, "FY28F":   0, "FY29F":   0, "FY30F":   0, "FY31F":   0,
                    "FY32F": 150, "FY33F": 350, "FY34F": 460, "FY35F": 500, "FY36F": 500},
    },
    # Bear: no P2000 FID, no Colina, Ngungaju re-idled from FY30 as prices fall back.
    "bear": {
        "pilgan":  {"FY27F": 880, "FY28F": 880, "FY29F": 870, "FY30F": 870, "FY31F": 860,
                    "FY32F": 860, "FY33F": 850, "FY34F": 850, "FY35F": 850, "FY36F": 850},
        "ngungaju":{"FY27F": 150, "FY28F": 170, "FY29F": 160, "FY30F": 120, "FY31F": 120,
                    "FY32F": 140, "FY33F": 150, "FY34F": 160, "FY35F": 170, "FY36F": 170},
        "p2000":   {"FY27F":   0, "FY28F":   0, "FY29F":   0, "FY30F":   0, "FY31F":   0,
                    "FY32F":   0, "FY33F":   0, "FY34F":   0, "FY35F":   0, "FY36F":   0},
        "colina":  {"FY27F":   0, "FY28F":   0, "FY29F":   0, "FY30F":   0, "FY31F":   0,
                    "FY32F":   0, "FY33F":   0, "FY34F":   0, "FY35F":   0, "FY36F":   0},
    },
    # Bull: P2000 FID late-2026 on schedule, faster ramp; Colina FID follows the Dec-27 DFS.
    "bull": {
        "pilgan":  {"FY27F": 920, "FY28F": 960, "FY29F": 970, "FY30F": 970, "FY31F": 970,
                    "FY32F": 970, "FY33F": 970, "FY34F": 970, "FY35F": 970, "FY36F": 970},
        "ngungaju":{"FY27F": 180, "FY28F": 205, "FY29F": 205, "FY30F": 205, "FY31F": 205,
                    "FY32F": 205, "FY33F": 205, "FY34F": 205, "FY35F": 205, "FY36F": 205},
        "p2000":   {"FY27F":   0, "FY28F":   0, "FY29F": 120, "FY30F": 450, "FY31F": 780,
                    "FY32F": 925, "FY33F": 950, "FY34F": 950, "FY35F": 950, "FY36F": 950},
        "colina":  {"FY27F":   0, "FY28F":   0, "FY29F":   0, "FY30F":   0, "FY31F": 180,
                    "FY32F": 380, "FY33F": 500, "FY34F": 560, "FY35F": 560, "FY36F": 560},
    },
}

# ---------------------------------------------------------------- realised price deck (E)
# US$/dmt of concentrate actually realised by PLS (below SC6 benchmark: grade + FOB basis).
# Anchored on FY26A realised US$1,488/t vs SC6 CIF China benchmark ~US$2,200/t (Platts SpodIX, Aug-26).
# PLS ships ~SC5.2% actual grade; Q4 FY26 realised US$2,107/t actual grade vs US$2,415/t SC6-equivalent,
# a ratio of 0.873. Spot SC6 was ~US$2,038-2,200/t CIF China in Aug-26, implying a spot-equivalent
# realisation near US$1,900/t. Base assumes prices fall BELOW spot as restart supply lands, then recover
# toward a long-run level still beneath Benchmark's stated greenfield incentive price.
# All three paths converge toward a common long-run level near US$1,700-1,750/t realised
# (~US$1,950-2,000/t SC6), which sits below Benchmark's stated greenfield incentive price.
# Convergence is deliberate: in a commodity, a trough forces supply out and a spike pulls it in,
# so a perpetuity struck at either extreme is not a forecast, it is an error. The scenarios
# therefore differ on the PATH and on volumes, not on where the cycle ends up.
PRICE_DECK = {
    "base": {"FY27F":1700,"FY28F":1780,"FY29F":1850,"FY30F":1800,"FY31F":1750,
             "FY32F":1750,"FY33F":1750,"FY34F":1750,"FY35F":1750,"FY36F":1750},
    # Bear: restart supply overwhelms demand into FY30, price reverts toward the 90th-percentile
    # cash cost (lepidolite >US$1,100/dmt, CRU), high-cost tonnes exit, then it grinds back.
    "bear": {"FY27F":1350,"FY28F":1150,"FY29F":1050,"FY30F":1050,"FY31F":1150,
             "FY32F":1250,"FY33F":1350,"FY34F":1450,"FY35F":1500,"FY36F":1550},
    # Bull: the 2027-29 deficit arrives, prices overshoot the incentive level, new supply responds
    # and the price mean-reverts down toward the same long-run anchor.
    "bull": {"FY27F":2050,"FY28F":2400,"FY29F":2600,"FY30F":2450,"FY31F":2300,
             "FY32F":2150,"FY33F":2050,"FY34F":1975,"FY35F":1925,"FY36F":1900},
}

# ---------------------------------------------------------------- unit costs A$/t FOB (E, anchored on G)
COST_DECK = {
    "base": {"FY27F":600,"FY28F":590,"FY29F":585,"FY30F":580,"FY31F":570,
             "FY32F":565,"FY33F":565,"FY34F":565,"FY35F":565,"FY36F":565},
    # Bear: costs rise initially on lower volumes and grade, then the operation is re-based.
    "bear": {"FY27F":625,"FY28F":645,"FY29F":655,"FY30F":640,"FY31F":625,
             "FY32F":615,"FY33F":610,"FY34F":610,"FY35F":610,"FY36F":610},
    "bull": {"FY27F":585,"FY28F":565,"FY29F":550,"FY30F":540,"FY31F":530,
             "FY32F":525,"FY33F":520,"FY34F":520,"FY35F":520,"FY36F":520},
}

# ---------------------------------------------------------------- capex A$m (E, anchored on G)
# FY27 = midpoint of guidance A$620-685m. P2000 PFS capex ~A$1.2bn spent over FY28-FY30 in base/bull.
CAPEX_DECK = {
    "base": {"FY27F":652,"FY28F":880,"FY29F":1020,"FY30F":760,"FY31F":560,
             "FY32F":520,"FY33F":430,"FY34F":390,"FY35F":370,"FY36F":370},
    "bear": {"FY27F":620,"FY28F":400,"FY29F":340,"FY30F":320,"FY31F":300,
             "FY32F":295,"FY33F":290,"FY34F":290,"FY35F":290,"FY36F":290},
    "bull": {"FY27F":685,"FY28F":1020,"FY29F":1130,"FY30F":900,"FY31F":720,
             "FY32F":600,"FY33F":480,"FY34F":430,"FY35F":410,"FY36F":410},
}

# ---------------------------------------------------------------- other model drivers (E)
CORP_COST_AM        = 95.0     # E  corporate/admin A$m p.a., grown with inflation
INFLATION           = 0.025    # E
DA_PCT_OF_CAPEX     = 0.85     # E  steady-state D&A as % of capex
NWC_PCT_REVENUE     = 0.08     # E
ROYALTY_RATE        = 0.05     # WA State royalty on spodumene concentrate - VERIFY rate/basis
TGR_BASE            = 0.025    # E  terminal growth
TGR_BEAR            = 0.015
TGR_BULL            = 0.030

# ---------------------------------------------------------------- shared value / ESG levers (E)
# The differentiator: each lever converted to A$m of annual EBITDA or one-off NPV.
# Values are OUR estimates built from disclosed operating data - each must be footnoted in the deck.
ESG_LEVERS = [
    # (name, mechanism, value, unit, evidence strength, source anchor)
    ("Sensor-based ore sorting (P680)",
     "TOMRA sorter rejects waste before energy-intensive downstream processing: fewer tonnes milled "
     "per tonne of Li2O, so both unit cost and energy per tonne of product fall together",
     30.0, "A$/t", "Strong",
     "World's largest lithium ore sorter, >1,000t/hr, commissioned Aug-24 in the A$103m P680 project"),
    ("Power strategy: gas conversion, solar and BESS",
     "Displaces diesel generation at Pilgangoora; company targets ~48% lower power emissions "
     "intensity by 2027 and up to 80% by 2030 if regional wind becomes available",
     18.0, "A$/t", "Moderate",
     "8 new gas gensets plus LNG storage installed; BESS planned to firm future solar"),
    ("Mid-stream lithium phosphate (Calix)",
     "Electric calcination cuts calcination emissions by more than 80% and moves PLS one step "
     "down the value chain, capturing conversion margin rather than selling raw concentrate",
     0.0, "Option", "Moderate",
     "100%-owned demonstration plant opened 5-Jun-26; first production guided Sep-qtr 2026; ARENA-backed"),
    ("Social licence protecting the growth option",
     "Heritage and community standing keep P2000 and Colina permittable on schedule; the PFS values "
     "the P2000 increment at A$2.6bn NPV, so schedule protection is worth real money",
     0.0, "Option", "Moderate",
     "P2000 PFS: A$2.6bn incremental NPV, 55% IRR, first ore guided mid-2029"),
    ("Low-carbon, non-China supply access",
     "EU Battery Regulation carbon declarations and US FEOC rules favour traceable, low-carbon, "
     "non-China units; PLS supplies a Korean JV rather than only Chinese converters",
     0.0, "Unproven", "Weak",
     "No verified carbon-linked price premium in PLS's disclosed contracts - flagged as unproven"),
]

# ---------------------------------------------------------------- peer set (M) - the case's own six
CASE_PEERS = [
    # ticker, name, primary commodity exposure
    ("BHP.AX",  "BHP Group Limited",         "Iron ore, copper, met coal, potash"),
    ("RIO.AX",  "Rio Tinto Group",           "Iron ore, aluminium, copper, lithium"),
    ("FMG.AX",  "Fortescue Ltd",             "Iron ore, green energy"),
    ("S32.AX",  "South32 Limited",           "Alumina, aluminium, base metals, met coal"),
    ("PLS.AX",  "PLS Group Limited",         "Lithium (spodumene)"),
    ("MIN.AX",  "Mineral Resources Limited", "Lithium, iron ore, mining services"),
]
