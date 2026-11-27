# Practitioner mean-reversion and retail systematic strategies (as of Nov 2026)

NOTE ON METHOD: WebFetch was blocked for every host tried (quantifiedstrategies, substack, mql5, backtrex, arxiv not fetched), so all findings below come from WebSearch result summaries, not full-page reads. Figures are therefore partial; numbers marked as quoted come from the search summaries and should be re-verified on the pages. Many QuantifiedStrategies pages are paywalled for exact rules.

## Connors / Alvarez strategies (RSI(2), cumulative RSI, Double 7s, Multiple Days Down) and post-publication performance

### Takeaway
Book-era (1993-2008 in-sample) results are strong (Double 7s: 80% win rate), but I found no clean, independent SPY 2015-2026 retest with costs. The post-2010 and post-2016 evidence found is mixed: modest CAGR (about 7-9%) with low market exposure, and one test showing the rule far behind buy-and-hold in a persistent bull market.

### Cited Findings
- Double 7s rules: buy on a 7-day closing low, sell on a 7-day closing high. Book SPY test from 1/29/93: 153 trades, 0.85% average gain per trade, 80.4% winners, in the market under 25% of the time. No trading costs in the book. — [STTSTW ch.10 PDF](https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf)
- Cumulative RSI rules (book summary): SPY above its 200-day SMA, sum of last two days' RSI(2) below 45, buy on close, exit when RSI(2) closes above 65. No return table found. — [STTSTW](https://thechartist.com.au/wp-content/uploads/2024/12/504/ShortTermTradingStrategiesThatWork.pdf)
- StrategyQuant retest of Double 7 on SPY and 8 other markets assumed zero commission, spread and slippage (results not extracted). — [StrategyQuant](https://strategyquant.com/blog/larry-connors-double-7-strategy-tested-on-spy-and-8-other-markets/)
- Quantified Strategies says Double 7 still works but other Connors strategies work better. — [QS Substack](https://quantifiedstrategies.substack.com/p/larry-connors-double-seven-trading-aa3)
- RSI(2) on SPY, Quantified Strategies: about 9% CAGR, invested about 28% of the time, max drawdown near 34%, nearly 30 years of data (as summarized by search). — [QS](https://www.quantifiedstrategies.com/rsi2-on-spy/)
- QuantConnect RSI backtest, 2010-2022: CAGR 7.568%, win rate 62%, 852 trades (exact rules not confirmed). — [QuantConnect forum](https://quantconnect.com/forum/discussion/15754/an-overview-of-a-simple-rsi-based-trading-strategy)
- Backtrex Connors RSI(2) on an S&P 500 CFD, Oct 2016 to Oct 2026, long-only: about +18.1% total, CAGR about +1.7%, versus about +255% buy-and-hold. The site notes the S&P spent most of the decade above its 200-day average. — [Backtrex](https://backtrex.com/en/backtests/connors-rsi-2-sp-500)
- Alpha Algo Trading Research claims the Connors/Alvarez 2009 "Multiple Days Down" model has over half its track record out of sample, and that RSI(2) has survived 17+ years out of sample (promotional newsletter). — [Alpha Algo](https://algotr.substack.com/p/this-2009-trading-strategy-still)
- StockCharts (Arthur Hill) 2018 said the dip-buying approach kept working since 2016. — [StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2018-01-systemtrader---the-dip-is-your-friend/)
- I found no post on Alvarez's own blog (alvarezquanttrading.com) in search results reporting RSI(2) post-publication results.

### Inferences
- Low exposure (25-28%) with 7-9% CAGR means the edge is risk-adjusted rather than absolute; in a 2016-2026 bull market long-only RSI(2) lagged buy-and-hold on CAGR (Backtrex).
- The Backtrex 1.7% CAGR figure conflicts with the 7.6-9% figures; differences likely come from rules, instrument (CFD), and exit choice. Not resolved.

### Gaps
- No Robot Wealth or Quantitativo retest located; no exact 2015-2026 SPY/QQQ stats for RSI(2), ConnorsRSI, TPS, 3-day high/low; Cesar Alvarez blog pages not reached.

## IBS, Turnaround Tuesday, N-day lows, Williams, Crabel, Raschke

### Takeaway
IBS (Close-Low)/(High-Low) below about 0.2-0.3 has several published SPY/ETF rule sets, but results are paywalled or in-sample; I found only one academic out-of-sample style test. Williams and Crabel patterns show low trade counts and cost fragility.

### Cited Findings
- Quantified Strategies SPY mean reversion: enter at close when IBS < 0.25 and RSI(21) < 45; exit when close exceeds prior day's close. Full stats members-only. — [QS](https://quantifiedstrategies.substack.com/p/the-classical-mean-reversion-strategy)
- TradingView IBS script: IBS <= 0.25, hold max 3 bars or until profitable, long-only, one trade at a time (no verified results). — [TradingView](https://in.tradingview.com/script/2KH3h0AC-S4-IBS-Mean-Rev-3candleExit)
- Pagonidis (original, not reached) reported ETFs with IBS < 0.2 tend to rise next day, > 0.8 fall; data to 5/12/2013. Pandey and Joshi tested 16 country ETFs, 2009-2019, Yahoo data, and report IBS outperforming buy-and-hold for all (Sharpe-based; full figures not extracted). — [arXiv 2306.12434](https://arxiv.org/abs/2306.12434v1)
- R-bloggers IBS SPY example is labelled by its author as optimized (overfit), fit on data to 2000, no slippage or commissions. — [R-bloggers](https://r-bloggers.com/?p=64600)
- A TradingView/TASC 2026-10 script on a "Low-Risk ETF Trading Strategy" exists (likely IBS-related; not read). — [TradingView](https://www.tradingview.com/script/2S4BqQzQ-TASC-2026-10-A-Low-Risk-ETF-Trading-Strategy/)
- NR7 (Quantified Strategies, SPY since 1993): buy at close when range is the smallest of last 6 sessions (as summarized), exit when close exceeds prior day's high; stats not extracted. — [QS](https://quantifiedstrategies.substack.com/p/we-improved-the-nr7-trading-strategy)
- Oxford Strat, 42 US futures 1980-2016: NR pattern better with NR length >= 6; after trading costs the pattern is "not currently tradeable". — [Oxford Strat](https://oxfordstrat.com/trading-strategies/narrow-range/)
- Williams Smash Day, one blog, 15 assets 2014-2024: S&P 500 longs 80% win rate, profit factor 6.94 (unverified methodology; a commenter doubts significance). — [RogueQuant](https://roguequant.substack.com/p/i-backtested-larry-williams-trading)
- Oops pattern on S&P futures: fewer than 200 trades since 1987 (about 7 per year); a DAX test reported the pattern decaying after the session extension. — [Unger Academy](https://ungeracademy.com/?p=7737)

### Inferences
- Low trade frequency of Oops/NR7 on a single index makes statistics weak; portfolio-wide testing is needed.

### Gaps
- Not found: Turnaround Tuesday stats, lower Bollinger band, Williams %R, Raschke Holy Grail / 80-20, Kevin Davey methods, Crabel ORB results, and exact IBS CAGR/PF/drawdown.

## YouTube/TradingView indicator strategies

### Takeaway
Where long-sample tests exist they are negative or underperform buy-and-hold; positive claims rest on short samples, no costs, or are unverified.

### Cited Findings
- Retest of viral "MACD cross below zero + 200 EMA" on gold M30 over 16+ years: 31.4% win rate (claimed 86%), loses after costs, only 2 of 16 years positive. — [MQL5 blog](https://www.mql5.com/en/blogs/post/780027)
- 27-year @ES backtest review: win rate about 32% versus advertised 86%, losses in the last five years. — [TradingView](https://www.tradingview.com/chart/BTCUSD/FbqjaZja-QUIT-RELYING-ON-AUTOMATED-BACK-TESTING/?amp)
- S&P daily MACD+200EMA poster: 500 trades, PF 1.2, +95% without costs versus +151% buy-and-hold. — [MQL5 blog](https://www.mql5.com/en/blogs/post/780027) (as summarized)
- MACD+200 EMA on USD/JPY 4h, 10 years: -22.1% total, CAGR -2.5% versus buy-and-hold +55.5%. — [Backtrex](https://backtrex.com/en/backtests/macd-200-ema-usd-jpy)
- Supertrend: QS weekly S&P 500 test back to 1960 says it can add value as a trend filter; Hackernoon re-ran TradingView's Supertrend on 6.7 years of data (results not extracted). — [QS](https://quantifiedstrategies.substack.com/p/the-supertrend-indicator-backtested); [Hackernoon](https://hackernoon.com/the-truth-about-tradingviews-supertrend-strategy-after-67-years-of-backtesting)

### Gaps
- No credible large-sample tests found for UT Bot, Hull Suite, Ichimoku, Squeeze Momentum; channel-level tests (Trading Rush, TradingLab, The Moving Average) not located.

## Forum/community and momentum systems (Radge, Clenow)

### Takeaway
Only Clenow's rules were found; no Radge Weekly Rotation numbers.

### Cited Findings
- Clenow Stocks on the Move: S&P 500 universe, weekly rebalance (Wednesday), volatility-adjusted momentum ranking, risk-parity sizing, exclude stocks below 100-day MA, hold 10-30 names; book backtest 1994-2015. — [QuantConnect forum](https://www.quantconnect.com/forum/discussion/16578)
- Arthur Hill (StockCharts) posted in-sample/out-of-sample momentum system results. — [StockCharts](https://www.stockcharts.com/articles/arthurhill/2018/02/in-sample-and-out-of-sample-results-for-two-momentum-systems---measuring-performance-and-drawdowns.html)

### Gaps
- Radge rules/results, Elite Trader, r/algotrading, Amibroker threads: not reached.

## Regime filters

### Cited Findings
- Cumulative RSI and RSI(2) use SPY above 200-day SMA as filter (book rules). — [STTSTW](https://thechartist.com.au/wp-content/uploads/2024/12/504/ShortTermTradingStrategiesThatWork.pdf)
- Clenow uses a 100-day MA per-stock filter. — [QuantConnect forum](https://www.quantconnect.com/forum/discussion/16578)

### Gaps
- No VIX-filter evidence found.
