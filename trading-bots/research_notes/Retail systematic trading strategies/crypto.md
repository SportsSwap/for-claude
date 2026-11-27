# Systematic crypto trading strategies: evidence file (as of Nov 2026)

Method note: built from web search snippets. WebFetch failed for quantpedia.com, cxoadvisory.com, cfbenchmarks.com, theblock.co and ar5iv.labs.arxiv.org (hosts not in the session network allowlist), so full papers were NOT read. Where a figure is missing it is listed under Gaps rather than guessed.

## Time-series momentum / trend following / moving-average rules on BTC

### Takeaway
Time-series momentum and MA/trend rules have the strongest academic support of any crypto signal (Liu-Tsyvinski 2021; Detzel et al. 2021; Hudson-Urquhart 2021), and MA filters on BTC historically cut drawdown versus buy-and-hold. Evidence is mostly in-sample or pre-2022. I found no clean published out-of-sample 2022-2026 result for a plain BTC MA rule, so that must be tested by backtest on Yahoo BTC-USD with parameters frozen pre-2022.

### Cited Findings
- Liu & Tsyvinski, "Risks and Returns of Cryptocurrency" (NBER w24877 2018; RFS 34(6) 2021): strong time-series momentum and investor-attention proxies forecast returns; only crypto-specific factors (momentum, attention) consistently explain returns. Example: 1-week horizon top momentum quintile averages 11.22%/week, Sharpe 0.45; bottom quintile 2.60%/week. — [NBER](https://nber.org/papers/w24877), [PDF](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf), [SSRN](https://papers.ssrn.com/abstract=3226806)
- Detzel, Liu, Strauss, Zhou, Zhu, "Learning and predictability via technical analysis: Evidence from bitcoin and stocks with hard-to-value fundamentals", Financial Management 50(1), 2021: ratios of price to 5/10/20/50/100-day moving averages forecast daily BTC returns in- and out-of-sample; equilibrium learning model rationalises it. Exact Sharpe figures not seen. — [EconPapers](https://econpapers.repec.org/RePEc:bla:finmgt:v:50:y:2021:i:1:p:107-137), [WashU profile](https://profiles.wustl.edu/en/publications/learning-and-predictability-via-technical-analysis-evidence-from-/), [CXO summary](https://www.cxoadvisory.com/currency-trading/timing-bitcoin-with-smas/)
- Summary of the above (secondary, from a 2018 academic paper as reported in search results): 50- and 100-day MAs reduced max gross drawdown to -70.3% vs -89.5% for buy-and-hold; gross Sharpe falls from 2.6 (5-day SMA) to 2.2 (100-day SMA). Gross of costs; the source paper is not identified with certainty in my results. — [Grayscale/summary search result](https://research.grayscale.com/reports/the-trend-is-your-friend-managing-bitcoins-volatility-with-momentum-signals)
- Hudson & Urquhart, "Technical trading and cryptocurrencies", Annals of Operations Research 297, 2021: ~15,000 rules across five classes (filters, MA, support/resistance, channel breakout, on-balance volume); significant predictability and profitability in each class; breakeven transaction costs for most rules far above typical crypto costs. Variable-length MA best; buy signals outperform sell signals. Exact rule definitions/cost numbers not seen. — [Springer](https://link.springer.com/article/10.1007/s10479-019-03357-1), [Reading repo](https://centaur.reading.ac.uk/85715)
- Counter-evidence: Svogun & Bazan-Palomino (2022, Int. Review of Financial Analysis; per search result) test 69 MA and breakout rules with/without costs and bubble periods; results mixed by coin; costs reduce profitability for Ripple/Litecoin but "increase" it for BTC/ETH per snippet (odd wording, verify). — [IDEAS](https://ideas.repec.org/a/eee/intfin/v79y2022ics1042443122000816.html)
- Grayscale Research, "The Trend Is Your Friend" (Aug 2023): 50-day MA rule (long when price above 50-day MA, cash below), Jan 2012-Jul 2023, Sharpe 1.9 vs 1.3 buy-and-hold; full-sample, not OOS; Grayscale warns history may not repeat; crossover rules sensitive to lookback. — [Grayscale](https://research.grayscale.com/reports/the-trend-is-your-friend-managing-bitcoins-volatility-with-momentum-signals)
- Rozario, Holt, West, Ng, "A Decade of Evidence of Trend Following Investing in Cryptocurrencies" (arXiv 2009.12155, 2020): SMA/EMA/DEMA rules, parameters optimised for Sharpe; headline 255% walk-forward annualised return on BTC; assumes negligible fees/spread/slippage (so optimistic); for S&P 500 no attractive Sharpe emerges when trained on 1 year and tested next year. — [arXiv](https://arxiv.org/pdf/2009.12155)
- Monash Centre for Financial Studies: shorter lookbacks give higher Sharpe in crypto trend following but transaction costs can erode profit. — [Monash](https://www.monash.edu/business/monash-centre-for-financial-studies/our-research/all-projects/investment-strategy/trend-following-strategies-for-crypto-investors)
- OOS caution: a study splitting Jan 2022-Jun 2023 at Jan 2023 found strategies good in-sample did not always hold out of sample. — [arXiv 2602.10785](https://arxiv.org/html/2602.10785v1)
- Recent single-year / derivative backtests (weak evidence): SMA-50 filtered crypto allocation Jan 2024-Jan 2025 cumulative +231.51%, Sharpe 2.51 (one bull year, multi-asset); QuantConnect BTC-50d-filter holding QQQ, Sharpe 0.838, Jan 2014-Aug 2026. — [Articlegateway](https://articlegateway.com/index.php/JAF/article/download/6453/6095), [QuantConnect](https://www.quantconnect.com/research/21195/bitcoin-regime-signal-for-growth-equities/p0)

### Inferences
- Testable rule set on Yahoo BTC-USD daily: long if close > SMA(n) for n in {20,50,100,200}, else cash; also Donchian breakout. Use next-bar execution, 10-30 bps per side cost assumption (my assumption, not from sources).
- BTC went through a full 2022 bear (-60%+), so any MA rule's 2022 result is the key OOS test; MA filters are expected to cut drawdown more than raise CAGR.

### Gaps
- No exact CAGR/Sharpe/MDD tables for Detzel et al. or Hudson-Urquhart (full text unread).
- No peer-reviewed 2022-2026 OOS test of simple BTC MA rules found.

## Cross-sectional momentum, crash risk, vol scaling

### Takeaway
Cross-sectional crypto momentum is weak, sample-dependent and crash-prone; time-series momentum is stronger. Volatility scaling reduces crashes in several studies, but a 2025-26 literature says payoffs are partly an artefact of untradable or disappearing coins.

### Cited Findings
- Liu, Tsyvinski, Wu, "Common Risk Factors in Cryptocurrency", JF 77(2) 2022 (NBER w25882): market, size, momentum factors capture cross-section; momentum factor explains excess returns of long-short strategies they examine. — [NBER](https://www.nber.org/papers/w25882.pdf), [Cowles PDF](https://cowles.yale.edu/sites/default/files/2022-10/LiuTsyvinskiWu2019%20COMMON%20RISK%20FACTORS.pdf)
- Han, Kang, Ryu: strong evidence for time-series momentum, weak for cross-sectional. — [ACFR](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf)
- A 2026 comparative study: TS momentum beats CS momentum risk-adjusted; CS momentum max drawdown 55%. — [Journals VU](https://www.journals.vu.lt/BATP/lt/article/download/44540/42590/138419)
- Springer (Financial Markets and Portfolio Management, 2025): volatility management reduces crypto momentum crashes but not underlying tail behaviour; crashes come from extreme price moves not reversals; look-ahead-bias debate on vol scaling. — [Springer](https://link.springer.com/article/10.1007/s11408-025-00474-9)
- Vaasa dissertation: plain momentum not significant due to crashes; vol-scaled momentum yields substantial gains. — [Vaasa](https://osuva.uwasa.fi/bitstreams/28ff208a-92f4-4911-9b4b-836ba96835c3/download)
- Grobys, Sandretto, Aijo, "On survivor cryptocurrency momentum": momentum not evident for survivor coins; with top-30 coins yearly it is profitable only after trimming; robustness highly sample-dependent. Also a note (secondary) that Grobys & Shahzad 2024 argue Sharpe is unreliable for crypto momentum (unverified). — [Vaasa](https://osuva.uwasa.fi/bitstreams/2a766d58-9fd3-44b8-b1a3-14a048a0b653/download)

### Inferences
- Yahoo top-coin survivorship bias would inflate any CS momentum backtest on today's large caps; treat results with suspicion.

### Gaps
- Exact vol-scaled momentum Sharpe/CAGR/MDD numbers not retrieved. No 2022-26 CS momentum result found.

## Calendar / time-of-day effects

### Takeaway
Time-of-day patterns exist but vary by regime; since ~2021 BTC increasingly trades on US hours and weekend liquidity has thinned. Evidence of a durable tradable edge is thin and mostly vendor backtests.

### Cited Findings
- Quantpedia (Gemini data 2015-2022): hours 22:00-23:00 UTC strongest, 03:00-04:00 UTC weakest; hour-based strategy reported ~33% annualised (backtest, costs not confirmed). Splitting sessions around NYSE hours: since 2021 most BTC returns realised in overnight (non-US-session) periods, equity-like; weekend effect noted. — [Quantpedia](https://quantpedia.com/how-to-profitably-trade-bitcoins-overnight-sessions/), [Quantpedia seasonal](https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/)
- Baur et al. (2019): time-specific anomalies without persistence; Kinateder & Papavassiliou (2021): lower weekend risk (volatility, not mean return). — [EconPapers](https://econpapers.repec.org/RePEc:eee:finlet:v:31:y:2019:i:c:p:78-92)
- Kaiko: weekend share of BTC volume ~13% record low vs 24% in 2018; wider weekend spreads on Coinbase vs Binance. A Kraken-based study: US-hours share of realised variance 50.6% in 2022-2025 (US hours = 37.5% of day); shift dated Nov 2021, no break at Jan 2024 ETF approval. — [CryptoSlate](https://cryptoslate.com/crypto-never-closes-but-bitcoin-ethereum-xrp-and-solana-now-move-on-wall-street-time/), [The Block](https://www.theblock.co/amp/post/279353/bitcoin-weekend-trading)
- Session returns conflict: Kaiko-cited piece says US session returns exceeded APAC/London Jan 2023-Dec 2025; other analyses favour APAC. — [CryptoSlate](https://cryptoslate.com/only-the-us-market-is-buying-bitcoin-while-the-foreign-smart-money-keeps-taking-profit/)

### Inferences
- Needs hourly data (Yahoo gives only ~730 days hourly), so a long-history test requires another source.

### Gaps
- No evidence found on month-end, options-expiry effects, or rigorous post-2022 day-of-week stats.

## Carry / funding-rate / basis

### Takeaway
Basis and funding yields compressed sharply after spot ETFs and the 2024-25 unwind; the simple trade is no longer a high-Sharpe edge and is hard for retail (needs margin on two venues, exchange risk, liquidation risk). Regime recovery to ~8% annualised funding was reported late 2026.

### Cited Findings
- CF Benchmarks, "Revisiting the Bitcoin Basis": ETF-share long / CME-short basis trade grew with ETF inflows. — [CF Benchmarks](https://www.cfbenchmarks.com/blog/revisiting-the-bitcoin-basis-how-momentum-sentiment-impact-the-structural-drivers-of-basis-activity)
- 10x Labs (via search): at least 25% of BTC ETF capital tied to arbitrage; up to 55%+ of inflows from arbitrage funds; basis falls when speculation fades. — [Advisor Perspectives](https://www.advisorperspectives.com/articles/2026/01/22/wall-street-pulls-back-bitcoin-trade)
- BitMEX Research: funding positive >92% of the time; "glory days" of simple funding trades may be fading. — [BreakingCrypto](https://markets.financialcontent.com/ms.intelvalue/article/breakingcrypto-2025-10-14-bitmex-research-uncovers-persistent-positive-bias-in-crypto-funding-rates-signaling-new-era-of-market-stability)
- Sygnum outlook (Nov 2026): 30-day average BTC funding below zero for 67 consecutive days through May 2026; recovered to ~8% annualised by end-Oct; argues carry may beat T-bills in 2027 (forecast, not fact). — [The Block](https://theblock.co/news/markets/2026-11-19-sygnum-bitcoin-carry-trades-beating-treasury-bills-2027-443547)
- FXStreet (Aug 2026): futures yield "once over 20% now less than Treasury notes". — [FXStreet](https://www.fxstreet.com/cryptocurrencies/news/the-bitcoin-futures-yield-collapse-once-over-20-now-less-than-treasury-notes-202608031149)
- Robot Wealth "Quantifying and Combining Crypto Alphas": carry (24h funding) + momentum (10-day price change) signals on Binance perps since late 2019; results not confirmed. — [Robot Wealth](https://robotwealth.com/quantifying-and-combining-crypto-alphas)
- Independent blogs (low reliability): cross-sectional funding carry modest but real; simple funding-level trade finished; Feb 2026 BTC/ETH funding contrarian decaying. — [Ruby's blog](https://askrubyai.github.io/blog/posts/2026-02-26-funding-regime-filter/index.html)

### Gaps
- No Sharpe/CAGR/MDD for funding carry from a reputable source; not testable with Yahoo OHLC (needs funding data).

## On-chain, sentiment, halving-cycle

### Takeaway
MVRV and cycle-top signals have weakened (smaller peaks each cycle); no rigorous OOS evidence found for Fear & Greed; halving-timing claims rest largely on non-peer-reviewed material.

### Cited Findings
- Galaxy Research: four-year cycle still valid but "halving rule" losing impact; MVRV peaked at only 2.29 this cycle vs 2.93-5.91 previously; Pi Cycle top did not trigger. — [KuCoin summary](https://www.kucoin.com/news/flash/galaxy-research-bitcoin-s-four-year-cycle-remains-valid-halving-rule-losing-impact)
- Molnar preprint (Jun 2026, arXiv 2607.26188; not peer reviewed): price-indicator power decays to zero/inverts across epochs; MVRV peaks 5.88 > 4.72 > 3.96 > 2.74; cycle top 534 days after Apr 2024 halving vs 525 (2017) and 546 (2021). — [arXiv](https://arxiv.org/pdf/2607.26188)
- Vaasa thesis: MVRV Z-score rule beats buy-and-hold (numbers not seen). — [Vaasa](https://osuva.uwasa.fi/bitstreams/6575b90c-6140-44e7-a798-011a1793d134/download)
- Fear & Greed: only trader commentary found. — [TradingView](https://br.tradingview.com/chart/BLX/18ZY1yWJ-A-Journey-Through-Halving-Events-Fear-Greed-Dynamics)

### Inferences
- Only 4 halving cycles: any halving claim has n=4, statistically unsupported.

### Gaps
- No stablecoin-flow evidence; no Glassnode/Kaiko primary research read; Fear & Greed untested; Yahoo can't supply MVRV.
