# Trend following, tactical asset allocation, and quant-firm practices: what a retail daily-bar trader can copy

Research conditions: WebSearch worked; WebFetch failed for every host (arxiv.org, ssrn, yale, alphaarchitect, cxoadvisory, allocatesmartly, cfm.com, cambridgeassociates all returned ENOTFOUND, i.e. not in the session's allowed network domains). All numbers below come from search-result summaries, not from reading primary PDFs. Search summaries are secondary; anything marked "verify" should be checked against the primary paper. Current date context: Nov 2026.

## 1. Trend following / managed futures research and exact rules

### Takeaway
Long-history studies (Hurst-Ooi-Pedersen 1880-2016; Lempérière et al. ~200 years) show a robust, diversified time-series-momentum premium with Sharpe around 0.7-0.8 in-sample, but results are backtests/simulations (AQR is a seller of the product). Post-2008 weakness, a big 2022 recovery, and a poor first half of 2025 are the recent record. I could not retrieve exact signal parameters for most papers.

### Cited Findings
- Hurst, Ooi, Pedersen, "A Century of Evidence on Trend-Following Investing", Journal of Portfolio Management, Fall 2017 (AQR): monthly returns for 67 markets (29 commodities, 11 equity indices, 15 bonds, plus currencies), 1880-2016; reported gross and net of simulated costs; performed well in 8 of the 10 largest 60/40 drawdown crises; authors found no evidence that post-2008 conditions were anomalously poor relative to history. Secondary summary of the paper; strategy up to ~25% drawdowns over extended periods. — [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing), summary at [Alpha Architect](https://alphaarchitect.com/time-series-momentum-aka-trend-following-the-historical-evidence/)
- Sharpe: the 2014 whitepaper version (1880-2013) reports net Sharpe 0.77; one commentary on the 2017 (1880-2016) version reports Sharpe 0.76 after all costs and 2/20 fees. Per-asset average net Sharpe ~0.4 (not the strategy figure). — [TrendFollowing.com whitepaper copy](https://www.TrendFollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf), [Alpha Architect](https://alphaarchitect.com/trend-following-is-everywhere/)
- Signal design in Hurst et al.: combines 1-, 3- and 12-month lookbacks, position set by sign of past return over each lookback (per search summary; the 12-month-only/10% vol target specifics I could not confirm). — [Alpha Architect summary](https://alphaarchitect.com/time-series-momentum-aka-trend-following-the-historical-evidence/)
- Lempérière, Deremble, Seager, Potters, Bouchaud, "Two centuries of trend following", Journal of Investment Strategies (arXiv 1404.3274, 2014): four asset classes (commodities, currencies, stock indices, bonds); trend-following excess return t-stat about 5 for futures since 1960 and about 10 back to 1800 (after removing market drift); effect stable across time and assets; trend predictability saturates for large signal values (so a bounded/capped signal is justified). — [arXiv listing via ar5iv](https://ar5iv.arxiv.org/html/1404.3274), [Risk.net](https://www.risk.net/journal-investment-strategies/2349968/two-centuries-trend-following)
- Baltas & Kosowski, "Momentum Strategies in Futures Markets and Trend-Following Funds": builds futures TSMOM benchmarks to explain CTA returns; found no statistically significant evidence of capacity constraints; post-2008 weakness candidates (capacity, lack of trends, rising cross-asset correlations): only correlation rise supported. Nick Baltas's follow-up work: better vol estimation and trend detection (e.g., linear-trend fit on price path) reduce turnover. — [EDHEC](https://climateinstitute.edhec.edu/publications/momentum-strategies-futures-markets-and-trend-following-funds), [EFMA PDF](https://efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2012-Barcelona/papers/BK_MOMF_Full.pdf)
- Clare, Seaton, Smith, Thomas: (a) "Trend following, risk parity and momentum in commodity futures", Int. Review of Financial Analysis 31 (2014): trend following overlay matters more than momentum or risk-parity adjustments for risk-adjusted return and downside; (b) "The Trend is Our Friend: Risk Parity, Momentum and Trend Following in Global Asset Allocation", J. Behavioral and Experimental Finance 9 (2016): trend following substantially improves risk-adjusted performance versus buy-and-hold and beats risk parity as an allocation method. — [IDEAS (a)](https://ideas.repec.org/a/eee/finana/v31y2014icp1-12.html), [City repository (b)](https://openaccess.city.ac.uk/id/eprint/17841/8/TREND%20IS%20YOUR%20FRIEND%20%20%20SSRN-id2126478.pdf)
- Turtle rules as commonly documented (community/educational sources, not Dennis's originals): System 1 enters on 20-day high breakout, exits at 10-day low; System 2 enters on 55-day high, exits at 20-day low; N = 20-day ATR; initial stop 2N; unit size = about 1% of equity / (N x dollar value per point); sources disagree on exact exits, risk % and pyramiding. — [TrendSpider](https://trendspider.com/learning-center/richard-dennis-turtle-trading-strategy/), [TradingView script](https://www.tradingview.com/script/jbyeMkat/)
- Recent performance (third-party recaps of SG data, provisional): SG CTA Index +20.13% in 2022 (record); SG Trend Index -9.3% through April 2025, SG CTA Index down >8% by late May 2025; SG Trend Index reported +2.39% for full 2025 (TTU) while Barclay CTA Index about +3.16% (different index); 2024 gain reported as 2.6% (index unclear); 2026: SG Trend +7.33% YTD through May, SG CTA about +9.28% YTD through June (conflicts with TTU saying double-digit YTD in April; unresolved). ETFs as of 8 Apr 2026: KMLM +7%, DBMF +8%, CTA +8% YTD. — [Hedgeweek 2022](https://www.hedgeweek.com/flat-december-sees-ctas-complete-record-year-2022/), [Alternatives Watch](https://www.alternativeswatch.com/2025/06/02/trend-following-hedge-funds-endure-more-pain-societe-generale-indices/), [TheFullFX 2025](https://thefullfx.com/ctas-end-2025-on-a-positive-note/), [TTU April 2026](https://www.toptradersunplugged.com/trend-following-performance-report-april-2026/), [Wisdom Trading May 2026](https://wisdomtrading.com/insights/managed-futures-may-2026-trend-recap/), [247WallSt](https://247wallst.com/investing/2026/04/10/the-3-managed-futures-etfs-that-made-money-while-the-sp-500-crashed/)

### Inferences
- A retail bot can replicate the core: sign of 1/3/12-month return per market, vol-scaled, equal-risk across ~20-60 liquid futures/ETF proxies; expected Sharpe is likely well below the 0.7-0.8 backtest once decay, costs and fewer markets apply (inference; the 2010s fund indices were far weaker than the long-run figure, but I did not obtain exact 2010s numbers).
- The 2022 +20% and 2025 H1 -9% swings show trend following is a high-variance, regime-dependent premium; judge it over decades, not years.

### Gaps
- Exact net Sharpe, vol and drawdown for the 2010s and a clean annual SG Trend table 2010-2026: not retrievable (fetch blocked, searches returned fragments). Man AHL and Winton research pages not retrieved. Exact Baltas-Kosowski Sharpe/turnover figures not verified. Donchian/MA crossover published-parameter robustness studies not found.

## 2. Tactical asset allocation with ETFs

### Takeaway
Published rules are simple monthly trend/momentum filters with strong in-sample drawdown reduction (Faber: ~-9.5% vs -36% to -46%). Independent replications exist but I found no Allocate Smartly / Portfolio Visualizer numbers; HAA replication discrepancy and universe/parameter snooping are flagged.

### Cited Findings
- Faber, "A Quantitative Approach to Tactical Asset Allocation" (SSRN 962461; Feb 2013 update): 5 asset classes (US stocks, intl stocks, Treasuries, commodities, REITs); at month-end hold each if price > 10-month SMA, else cash; 1973-2012 gross annualized 10.5% vs buy-and-hold 9.9%, vol 7.0% vs 10.3%; max drawdown about -9.5% (timing) vs -36% (MoneySense table, period not stated) or -46% (Juniata summary, 1973-2011); worst year -0.59%. Critique: 10-month choice may carry data-snooping bias; other MAs performed similarly. — [Scribd copy of SSRN](https://www.scribd.com/document/559580322/SSRN-id962461), [MoneySense](https://www.moneysense.ca/columns/the-failed-promise-of-market-timing), [CXO Advisory](https://www.cxoadvisory.com/?p=1115), [Quantpedia](https://quantpedia.com/strategies/asset-class-trend-following)
- Antonacci GEM (Global Equities Momentum): 12-month lookback for relative and absolute momentum, monthly rebalance; bonds as safe harbor; 1974-2013 CAGR/avg annual 17.43% vs 9.55% for ACWI (some sources say 12.34% for S&P 500), stdev 12.64%, Sharpe 0.87, max DD 22.7%; gross, monthly rebalance; model created 2013 so 1974-2013 is in-sample. Blogger notes commonly circulated GEM rules are not official (absolute momentum applied before relative). Post-2013 out-of-sample numbers not obtained. — [CXO Advisory](https://cxoadvisory.com/momentum-investing/a-few-notes-on-dual-momentum-investing), [Advisor Perspectives craftsman's perspective](https://files.advisorperspectives.com/articles/2019/05/06/global-equity-momentum-a-craftsmans-perspective), [Index Swing Trader](https://indexswingtrader.blogspot.sg/2016/10/prospecting-dual-momentum-with-gem.html)
- Keller & Keuning family: PAA, VAA, DAA, BAA, HAA. VAA summary: 10-16% CAGR vs 7-8% benchmarks, out-of-sample 1993-2016, 12 asset classes, breadth-based crash protection. DAA canary universe VWO/BND; DAA beat VAA in CAGR in 3 of 4 universes but with higher max DD. BAA (SSRN 4166845, v0.981 July 2022): slow relative momentum + fast absolute momentum, switches to defensive universe when any canary asset has negative momentum; spends about 60% of time defensive. Specific BAA CAGR/maxDD figures not obtained. — [CXO VAA/DAA](https://www.cxoadvisory.com/technical-trading/conservative-breadth-rule-for-asset-class-momentum-crash-protection/), [BAA SSRN copy](https://thechartist.com.au/wp-content/uploads/2024/12/5369/SSRN-id4166845.pdf), [CXO canary](https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/)
- A QuantConnect replication of HAA did not match Keller's published results. — [QuantConnect forum](https://www.quantconnect.com/forum/discussion/14842/hybrid-asset-allocation/)
- Quantpedia study of Antonacci-style dual momentum over a 9-ETF universe (weekly rebalance, vs equal weight) warns the universe choice is a hidden parameter that introduces bias. — [Quantpedia](https://quantpedia.com/active-dual-momentum-gtaa-strategy/)
- Alpha Architect "trend following on steroids" (canary-universe experiment on SPY, not BAA): >15% annual return, max monthly DD <15% (in-sample). — [Alpha Architect](https://alphaarchitect.com/trend-following-on-steroids/)

### Inferences
- Many Keller-style models are published after parameter search on the same history (BAA/DAA canary sets, thresholds), so expect live results meaningfully below headline CAGR; Faber's simple SMA is the most robust and least overfit candidate.
- Monthly rebalancing on ETFs fits free daily data and a retail bot well.

### Gaps
- Allocate Smartly, Portfolio Visualizer, Quantpedia independent out-of-sample tables (2013/2016/2022 to 2026) not retrieved. Exact rules and numbers for Accelerating Dual Momentum, PAA, HAA, Golden Butterfly, risk parity not obtained. 

## 3. Volatility targeting and position sizing

### Takeaway
Volatility-managed portfolios look strong in-sample but implementable versions show weak or inconsistent out-of-sample gains; Kelly is used fractionally.

### Cited Findings
- Moreira & Muir, "Volatility-Managed Portfolios", Journal of Finance 2017: scaling exposure inversely to recent variance raised factor Sharpe ratios and produced large alphas/utility gains; lower risk in recessions. — [NBER w22208](https://www.nber.org/papers/w22208)
- Harvey et al. (incl. Man AHL authors), "The Impact of Volatility Targeting", JPM 2018: studies practical vol targeting. — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf)
- Critiques: Liu, Tang & Zhou (2019) say the Moreira-Muir/Harvey strategies suffer look-ahead bias via ex post scaling; Cooper, Wang & Yan find vol-managed portfolios do not systematically outperform; another study finds implementable vol targeting does not consistently improve risk-adjusted performance internationally and can have turnover >200%/yr. — [Lehigh COWY](https://www.lehigh.edu/~xuy219/research/COWY.pdf), [arXiv 2212.07288](https://arxiv.org/pdf/2212.07288) (summaries via search)
- Kelly: practitioners use half or quarter Kelly because overbetting costs more than underbetting; full Kelly implies ~50% chance of a 50% drawdown in the idealized model; Thorp-cited S&P Kelly fraction estimate ~117%; Vince's optimal f maximizes growth on historical trades and shares Kelly's sensitivity to input error; a note argues half-Kelly is equivalent to full Kelly on a Bayesian-shrunk estimate. Several of these sources are blogs/glossaries (verify "75% of growth" style claims). — [Wikipedia Kelly](https://www.wikipedia.org/wiki/Kelly_criterion), [escholarship](https://escholarship.org/content/qt5mr5k8qj/qt5mr5k8qj.pdf), [arXiv 2503.17927](https://www.arxiv.org/pdf/2503.17927)

### Inferences
- For a retail bot: cap leverage, use lagged (known at the time) vol estimates, count costs; fractional Kelly of a shrunk edge estimate is safer than raw optimal f.

### Gaps
- Exact numbers from Harvey et al. (e.g., which assets benefit) not retrieved.

## 4. Hedge fund / prop firm practices and retail transferability

### Takeaway
Publicly documented material is thin and mostly about scale and infrastructure; the transferable parts are slow, diversified signal research and risk control, not latency or market making.

### Cited Findings
- Renaissance Medallion (from Zuckerman, The Man Who Solved the Market, 2019): 1988-2018 about 66% gross and 39% net annualized; fees 5% of assets plus up to 44% of profits; unaudited and employee-only; Cornell (SSRN) calls it the ultimate counterexample to market efficiency, estimates $100 grows to $398.7M (63.3% compound, gross). — [Wikipedia Medallion](https://en.wikipedia.com/wiki/Medallion_Fund), [Institutional Investor](https://www.institutionalinvestor.com/article/2bswymr8cih3jeaslxc00/portfolio/famed-medallion-fund-stretches-explanation-to-the-limit-professor-claims)
- Jane Street 2024: net trading revenue reported $20.5B (Citadel Securities $9.7B, other source ~$10B); >10% of North American equity volume; 24% of US ETF primary and 16% secondary market, 41% of bond ETF creations/redemptions; strategy described generally as exploiting tiny discrepancies, e.g., ETF vs underlying basket; SEBI barred it temporarily in July 2025 over alleged index manipulation (Jane Street denies). — [Global Trading](https://www.globaltrading.net/?p=38181), [Bloomberg](https://www.bloomberg.com/news/articles/2024-12-02/jane-street-reaps-14-2-billion-in-first-nine-months-of-trading)
- Pairs trading: Gatev-Goetzmann-Rouwenhorst (2006) baseline not retrieved directly; Do & Faff (2010, FAJ) show top-20-pair excess return fell from about 0.86%/month (1962-88) to 0.37% (1989-2002) to 0.24% (2003-09); Do & Faff (2012) with costs find about 30bp/month in refined industry groups but largely unprofitable post-2002. — [IDEAS](https://ideas.repec.org/a/taf/ufajxx/v66y2010i4p83-95.html), [Strathprints](https://strathprints.strath.ac.uk/41722/)

### Inferences (my classification, not sourced)
- Realistic for retail with free daily data: time-series momentum / trend following on ETFs or micro futures, monthly TAA, vol targeting, simple multi-signal ensembles, daily-bar cross-sectional momentum with costs modeled.
- Impossible or impractical: market making, ETF creation/redemption arbitrage, latency/HFT stat arb, Medallion-style short-horizon signals (need tick data, financing, capacity, execution); pairs trading on daily bars is largely decayed after costs per Do-Faff.

### Gaps
- Nothing retrieved on D.E. Shaw, Two Sigma, Citadel (hedge fund), AQR other than trend, Man AHL/Winton methods, Millennium, Avellaneda-Lee (2010) results. Interviews/podcasts (Top Traders Unplugged, Flirting with Models) not retrieved.

## 5. Combining strategies / ensembles

### Takeaway
Little retrieved; findings above imply diversification across assets and lookbacks is the main combination lever.

### Cited Findings
- Hurst et al. combine 1-, 3-, 12-month trend signals; Clare et al. find trend following beats risk parity as allocation; Quantpedia/Keller work shows crash-protection overlays (canaries) layered on momentum. See sections 1-2 for sources.

### Inferences
- Combining weakly correlated sleeves (trend on futures/ETFs, monthly TAA, a defensive canary rule) is plausible; correlation estimates between these sleeves were not retrieved.

### Gaps
- No sourced correlation matrix, ensemble/"signal stacking" research, or Allocate Smartly portfolio-of-strategies results.
