# Exact rules - Round 2 (PARTIAL VERIFICATION)

IMPORTANT: In this session WebFetch could not resolve ANY host (arxiv.org, davidhbailey.com, wikipedia, cxoadvisory,
thechartist, blogspot all ENOTFOUND). Only WebSearch snippets were available. Items marked [SEARCH] come from search
snippets with URL; items marked [RECALL] are from the model's memory of the primary papers and MUST be verified
against the PDFs before coding. Network allowlist needs arxiv.org, papers.ssrn.com mirrors, davidhbailey.com, allocatesmartly.com.

## 1. Faber GTAA
- [SEARCH] 10-month SMA trend filter; decisions on last day of month; below SMA -> cash. https://the7circles.uk/?p=35413 ; https://canadiancouchpotato.com/2013/12/30/the-failed-promise-of-market-timing/
- [SEARCH] Faber specified index classes, not ETFs (ETF mapping is the implementer's choice). https://stockcharts.com/articles/muscular-investing/2019/01/which-etfs-will-outperform-4.html
- [RECALL] GTAA-5: US stocks (VTI), foreign stocks (VEU), 10y UST (IEF), commodities (DBC/GSCI), REITs (VNQ); 20% each; price>10m SMA hold else T-bill/cash.
- [RECALL] GTAA-13 adds Russell2000/US small, EM, 20y UST, TIPS, corp bonds, intl bonds, gold, intl REITs. Aggressive AGG3/AGG6: top 3 / top 6 of 13 by avg of 1,3,6,12-month return, equal weight, only if above 10m SMA, else cash. Verify.

## 2. Antonacci GEM
- [RECALL] Monthly. If SPY 12m total return > BIL (T-bill) 12m return: hold the better of SPY vs ACWX/VEU (12m return); else hold AGG (US agg bonds). Newfound found GEM fragile to lookback/implementation (6 vs 12m). [SEARCH] https://quantpedia.com/active-dual-momentum-gtaa-strategy/ (Newfound claim summarized via search).

## 3. Keller family
HAA [SEARCH] https://www.cxoadvisory.com/?p=43931 ; https://indexswingtrader.blogspot.com/2023/02/introducing-hybrid-asset-allocation-haa.html
- Momentum = equal-weight average of 1,3,6,12-month returns (13612U). Canary: TIP (>0 -> offensive, else defensive).
- Offensive: top 4 equal-weight of SPY, IWM, VWO, VEA, VNQ, DBC, IEF, TLT; any with momentum<=0 replaced by best of BIL/IEF.
- Defensive: best of BIL, IEF by momentum. Monthly. (Replications using EFA/EEM/PDBC differ.)
BAA [SEARCH] https://allocatesmartly.com/bold-asset-allocation/ ; https://bestfolio.app/strategies/baa ; https://www.quantconnect.com/forum/discussion/14190/
- Canary: SPY, VWO, VEA, BND, momentum 13612W; B=1 (any one negative -> full defense). Offense: top 6 (of G12: SPY QQQ IWM VGK EWJ VWO VNQ DBC GLD TLT HYG LQD) by SMA12 relative momentum (P/SMA12 where SMA of 13 month-ends); defense: top 3 of TIP DBC BIL IEF TLT LQD BND by relative momentum, replaced by BIL if worse than BIL.
- [SEARCH] Reported backtest 14.6% CAGR, -8.7% MaxDD, 472% turnover, Dec1970-Jun2022 (pre-inception, paper). https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/
- 13612W = (12*r1 + 4*r3 + 2*r6 + 1*r12)/19 [RECALL, consistent with SEARCH weights 12,4,2,1].
VAA/DAA [RECALL]: VAA-G12 offense SPY IWM QQQ VGK EWJ VWO VNQ GSG GLD TLT LQD HYG, defense SHY IEF LQD, 13612W, any offensive <0 -> best defensive (B=1). VAA-G4 offense SPY VEA VWO BND, defense LQD IEF SHY, top 1. DAA: canary VWO+BND, B=2 (cash fraction = b/B, b=#bad canaries), offense G12 top 6, defense top 1 of SHY IEF LQD. Verify top-N for VAA-G12.

## 4. TSMOM / Hurst-Ooi-Pedersen
- [SEARCH] HOP 2017 JPM: 67 markets, 1880-2016, vol-targeted positions, needs 3y history for vol. https://fairmodel.econ.yale.edu/ec439/hurst.pdf
- [RECALL] MOP 2012: signal = sign of past 12m excess return; position = 40%/sigma_t, sigma = EWMA (center of mass 60 days) of daily squared returns, annualized; monthly rebalance; portfolio vol 10% appears in factor/HOP versions. NOT confirmed by search - verify.

## 5. Connors [SEARCH] https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/connorsrsi ; https://www.quantifiedstrategies.com/connors-rsi/
- ConnorsRSI(3,2,100) = (RSI(close,3) + RSI(streak,2) + PercentRank(ROC(1),100))/3 (streak = consecutive up/down days, signed). Oversold <10, overbought >90 (typical exits ~70).
- Double 7s: SPY > SMA200; buy at close of 7-day closing low; sell at close of 7-day closing high.
- Cumulative RSI(2): close > SMA200; sum of RSI(2) over 2 days < 35 -> buy; exit RSI(2) > 65. [RECALL] RSI(2): >SMA200, close<SMA5, RSI(2)<10; exit close>SMA5. TPS [RECALL]: >SMA200, RSI(2)<25 two consecutive days, scale in 4 units on lower closes; exit RSI(2)>70. Verify.

## 6. IBS [SEARCH] https://arxiv.org/abs/2306.12434v1 ; https://www.quantifiedstrategies.com
- IBS=(Close-Low)/(High-Low). Pagonidis (2013): long after IBS<0.2, expect rise; >0.8 tends to fall. Exit commonly IBS>0.8 or next-day close (QS exact rule not confirmed).

## 7. Zarattini-Aziz-Mele "The Volatility Edge" (Jun 2025) [SEARCH] https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5316487 ; https://concretumgroup.com/the-volatility-edge-a-dual-approach-for-vix-etns-trading/ ; https://www.quantconnect.com/research/21143/
- Dual signal: expected VRP (eVRP > 0) and VIX vs VIX3M term structure (contango/backwardation, measured 3:45pm). Instruments: VIX ETNs (short/long), not clearly SVXY. Reported 2008-2025 CAGR 16.3%, Sharpe ~1.0, equity corr ~15%. Exact thresholds NOT found - need PDF https://concretumgroup.com/wp-content/uploads/2026/02/The-Volatility-Edge.pdf

## 8. Clenow Stocks on the Move [SEARCH] https://www.quantconnect.com/forum/discussion/16578 ; https://quant-investing.com/blog/how-to-find-stocks-on-the-move-with-a-better-momentum-indicator-exponential-regression
- Momentum = annualized exp. regression slope (log price, 90d) * R^2; skip stocks with >15% gap in 90d; sell when leaving index; 100d SMA stock filter; index filter 200d; weekly, same weekday; sizing 10bp risk / ATR.
- [RECALL] ATR(20); shares = equity*0.001/ATR; hold top 20% ranks; open new only if S&P>200d SMA; position resize every 2 weeks.

## 9. DSR / PBO [SEARCH confirms structure] https://papers.ssrn.com/abstract=2460551 ; https://gmarti.gitlab.io/qfin/2018/05/30/deflated-sharpe-ratio.html
[RECALL of Bailey & Lopez de Prado 2014, verify vs http://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf]
- SR0 = sqrt(V[{SR_n}]) * ( (1-g) * Z^-1[1-1/N] + g * Z^-1[1-1/(N e)] ), g = 0.5772 (Euler-Mascheroni), N = # independent trials, V = cross-trial variance of the (non-annualized, per-period) Sharpe ratios.
- DSR = Z[ (SR_hat - SR0) * sqrt(T-1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) ], g3 skew, g4 NON-excess kurtosis, SR per-period, T observations. (PSR with benchmark SR0.)
- PBO via CSCV (Bailey, Borwein, LdP, Zhu 2015): matrix T x N; split into S even blocks (S=16); all C(S,S/2) combos: IS = S/2 blocks, OOS = rest; n* = argmax IS Sharpe; omega = rank_OOS(n*)/(N+1); lambda = ln(omega/(1-omega)); PBO = share of combos with lambda<=0.

## 10. Independent OOS results
Nothing dated and reliable retrieved. [SEARCH] anecdotal Reddit AllocateSmartly (2024, unofficial) mid-teens CAGR long backtest, DD low-20s, Sharpe ~1.1 for a dual-momentum model https://r.datuan.dev/r/AllocateSmartly/ ; GEM drawdown ~20.7% Oct 2022 https://portfolioslab.com/portfolio/zevhmpq9ee9ewpc70387qvk5 ; bestfolio claim canary models beat GEM in 2022 https://bestfolio.app/blog/dual-momentum-2022-canary-models (unverified). Needs allowed access to allocatesmartly.com.

# ===== ADDENDUM: VERIFIED via curl on primary/secondary text (supersedes [RECALL] above where conflicting) =====
(curl works for allocatesmartly.com, concretumgroup.com, fairmodel.econ.yale.edu, quantifiedstrategies.com, davidhbailey.com via https://www.)

## BAA (Allocate Smartly, Aug 2022) https://allocatesmartly.com/bold-asset-allocation/
- Monthly, close of last trading day. Canary (both versions): SPY, EEM, EFA, AGG (NOT VWO/VEA/BND). 13612W each = 12*(p0/p1-1)+4*(p0/p3-1)+2*(p0/p6-1)+(p0/p12-1) (divide by 19 optional; sign only matters for canary).
- If ALL canary >0 -> offensive, else defensive (B=1; negative ~60% of months).
- Relative momentum = p0/average(p0..p12) (13 month-end prices).
- Offensive Balanced: top 6 of SPY QQQ IWM VGK EWJ EEM VNQ DBC GLD TLT HYG LQD. Offensive Aggressive: top 1 of QQQ EEM EFA AGG.
- Defensive (both): top 3 of TIP DBC BIL IEF TLT LQD AGG by relative momentum; if asset's relative momentum < BIL's, that slot -> cash. Equal weight, rebalance monthly regardless. AS substitutes cash for BIL.
- AS warns of overfitting/brute-forcing. Paper CAGR 14.6/MaxDD -8.7 (search snippet, cxoadvisory) is pre-inception.

## HAA https://allocatesmartly.com/hybrid-asset-allocation/ (Mar 2023)
- Momentum = unweighted average of 1,3,6,12m % returns. Canary TIP: momentum>0 (positive ~86% of time since 1971) -> offense, else 100% to best of IEF vs cash(BIL) (T-bill momentum proxy).
- Offense: top 4 of SPY IWM EFA EEM VNQ PDBC IEF TLT, 25% each; if that asset's momentum<=0 -> its slot to IEF or cash, whichever has higher momentum. Paper uses VEA/VWO/DBC-type variants. Monthly, last trading day close.

## VAA https://allocatesmartly.com/vigilant-asset-allocation/ (G4, T=1/B=1)
- Offense: SPY EFA EEM AGG; Defense: LQD IEF SHY. 13612W. If all 4 offensive >0 -> 100% highest-score offensive; if any <0 -> 100% highest-score defensive (even if <0). Monthly. (G12 universe per Keller: SPY IWM QQQ VGK EWJ EEM VNQ GSG GLD TLT LQD HYG - recall, unverified.) AS: Sharpe fell 1.10->0.83 without AGG.
- DAA (https://allocatesmartly.com/two-new-strategies-added-defensive-asset-allocation-and-accelerating-dual-momentum/): canary universe (VWO,BND in paper - recall) smaller than VAA; moves to defense less often. Full rules not retrieved.

## Zarattini-Aziz-Mele "The Volatility Edge" (full text read) https://concretumgroup.com/wp-content/uploads/2026/02/The-Volatility-Edge.pdf
- Signals computed daily 3:45pm ET (orders MOC), SPY 10-day std of daily returns (last return = prev close -> 3:45pm level): eRV30 = std10d*sqrt(252)*100; eVRP = VIX(3:45pm) - eRV30. VIX vs VIX3M for contango/backwardation.
- Instruments: VIXSHORT (e.g. SVXY, -0.5x per Table 1 at present; ProShares), VIXLONG (e.g. VIXY 1x). Rebalance band +-2% (e.g. 20% target rebalanced if outside 18-22%), cost 5 bps.
- S1 passive: 20% VIXSHORT. S2: eVRP>0 -> 20% VIXSHORT else cash.
- S3: eVRP>0 & VIX<VIX3M -> 20% short; eVRP<=0 & VIX<VIX3M -> 10% short; eVRP<=0 & VIX>VIX3M -> 20% VIXLONG; else cash (i.e. eVRP>0 & VIX>=VIX3M -> cash).
- S4 sizing: same signals but size = VIX/100 (e.g. VIX 20 -> 20%), 0.5*VIX% for the 10% case; long VIX size = VIX%.
- Results 2008-2025 (net 5bps): Passive CAGR 6.2%/vol14.8/SR0.48/MDD-32.0; eVRP 6.9/13.5/0.56/-23.5; eVRP+BoC 10.5/12.4/0.87/-15.2; S4 16.3/16.4/SR1.00/MDD -31.0, beta 0.12, corr 14.8%. In-sample, author-reported.

## DSR / PBO (Bailey & LdP, davidhbailey.com PDF read; Greek lost in extraction but structure matches)
- Eq.(1): E[max_n SR_n] ~= E[{SR}] + sqrt(V[{SR_n}]) * ( (1-g)*Z^-1[1-1/N] + g*Z^-1[1-1/(N*e)] ), g=0.5772 Euler-Mascheroni, Z = std normal CDF, V = variance ACROSS the N trials' estimated SRs. SR0 = that with E[{SR}]=0 for the deflation benchmark. Trials must be independent; App.3 gives effective-N for dependent trials.
- DSR = PSR(SR0) = Z[ (SR_hat - SR0)*sqrt(T-1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) ], per-period SR, g3 skew, g4 non-excess kurtosis (normal=3).
- PBO via CSCV: as described in [RECALL] section above (S=16 blocks, logit of OOS rank of IS-best, PBO = P[lambda<=0]).

## Hurst-Ooi-Pedersen (read) https://fairmodel.econ.yale.edu/ec439/hurst.pdf
- Monthly rebalance; three TSMOM strategies (lookbacks 1, 3, 12 months); sign of past excess return -> long/short every market; each position vol-scaled equally; aggregated and scaled to 10% annualized ex-ante portfolio vol. 67 markets 1880-2016. (EWMA/60-day center-of-mass and 40% per-asset target are MOP 2012 details; not found in this paper's text - unverified.)

## IBS https://www.quantifiedstrategies.com/internal-bar-strength-ibs-indicator-strategy/
- IBS=(C-L)/(H-L). Buy at close if IBS<0.2; sell at close when IBS>0.8. A "twist" variant on SPY 1993-2026: CAGR 15.3%, 36% in market, 583 trades, avg 5.8 days, win 74%, MDD 22%, PF 2.73, Sharpe 1.7 (QS-reported, rule twist not specified; page dated Feb-Jul 2026).

## Still unverified (not retrieved): Faber GTAA exact page, GEM exact, Connors books, Clenow book (see recall/search sections).
