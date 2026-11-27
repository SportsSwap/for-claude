# Backtesting, optimisation and ML methodology for ~10 retail trading bots (as of Nov 2026)

Research caveat: in this session WebFetch was blocked for most hosts (davidhbailey.com, nber.org, duke.edu, arxiv.org, wikipedia, carmamaths.org all failed DNS/allowlist). All findings below come from WebSearch result summaries only; primary PDFs were NOT read. Formulas marked [from memory] are the standard published forms recalled from the original papers, and must be checked against the papers before being hard-coded.

## Overfitting and multiple testing (DSR, PBO, Harvey-Liu-Zhu, haircut Sharpe, Reality Check, data-snooping)

### Takeaway
Any bot picked as the best of many tried variants has an inflated Sharpe; correct for the number of trials (Deflated Sharpe, haircut Sharpe, PBO) and demand a much higher bar than t=2 (Harvey-Liu-Zhu: t>3.0). Sullivan-Timmermann-White showed that apparent technical-rule profits can vanish once the whole search universe is accounted for.

### Cited Findings
- Deflated Sharpe Ratio (DSR) is the Probabilistic Sharpe Ratio (PSR) evaluated against the expected maximum Sharpe of N skill-less trials. PSR(SR*) = Phi( (SR_hat - SR*) * sqrt(T-1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) ), g3 = skewness, g4 = (non-excess) kurtosis, T = number of return observations. — [arXiv 2608.27734](https://arxiv.org/pdf/2608.27734) (as relayed by search summary)
- Variance of Sharpe estimates under no skill: V = (1 + SR^2/2)/(T-1) (Lo 2002), used to scale the expected-max benchmark. — [arXiv 2611.03985](https://arxiv.org/pdf/2611.03985)
- Expected max Sharpe of N trials: SR0 = sqrt(V[SR_n]) * [ (1-gamma)*Phi^-1(1-1/N) + gamma*Phi^-1(1-1/(N*e)) ], gamma = Euler-Mascheroni constant (~0.5772), e = Euler's number; DSR = PSR(SR0). Formula bracket recalled from memory and consistent with the description at [gmarti blog](https://gmarti.gitlab.io/qfin/2018/05/30/deflated-sharpe-ratio.html) (which reports it matches simulation for 100 trials). Original: Bailey & Lopez de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", Journal of Portfolio Management 2014, SSRN. Implementations: [fynance docs](https://fynance.readthedocs.io/en/v2.10.1/generated/fynance.research.deflated_sharpe_ratio.html).
- Implementation warning: use per-period (not annualised) Sharpe in DSR or it saturates near 1. — [fynance docs](https://fynance.readthedocs.io/en/v2.10.1/generated/fynance.research.deflated_sharpe_ratio.html)
- Probability of Backtest Overfitting: Bailey, Borwein, Lopez de Prado, Zhu, "The Probability of Backtest Overfitting", Journal of Computational Finance 2017 (DOI 10.21314/jcf.2016.322); SSRN [2326253](https://papers.ssrn.com/abstract=2326253). Uses Combinatorially Symmetric Cross-Validation (CSCV), a model-free nonparametric estimator; authors argue hold-out is unreliable for backtests. — [Risk.net](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting)
- CSCV procedure [from memory, not verified from the PDF]: (1) build matrix M of T rows (time) x N columns (strategy variants/trials); (2) split rows into S even blocks (e.g. S=16); (3) for each of C(S,S/2) combinations, use S/2 blocks as in-sample (IS) and the complement as OOS; (4) pick best IS strategy n*; (5) compute its OOS relative rank omega = rank_OOS(n*)/(N+1); (6) logit lambda = ln(omega/(1-omega)); PBO = fraction of combinations with lambda <= 0 (i.e. IS-best falls at or below OOS median). Also yields performance degradation and stochastic-dominance diagnostics. Also a "Minimum Backtest Length" result (MinBTL) in the same line of work (referenced in [this student treatment](https://sites.math.washington.edu/~morrow/336_18/papers17/akshay.pdf)). Check formula against the paper.
- Harvey, Liu, Zhu, "... and the Cross-Section of Expected Returns", Review of Financial Studies 29(1), 5-68 (2016); NBER WP 20592 (2014). Concludes a new factor needs t-ratio > 3.0 given the many factors tested; most claimed findings in financial economics are likely false; Fama-MacBeth's 2.57 passed the old 2.0 cutoff. — [NBER](https://www.nber.org/papers/w20592), [RePEc](https://econpapers.repec.org/RePEc:oup:rfinst:v:29:y:2016:i:1:p:5-68.). Number of factors tested ("316") could not be verified from search results.
- Harvey & Liu, "Backtesting", Journal of Portfolio Management (2015): proposes haircut to the reported Sharpe and a profit hurdle; haircut is nonlinear (highest Sharpes penalised moderately, marginal Sharpes heavily), rejecting the flat 50% rule of thumb. Uses Bonferroni and Holm (family-wise error) and BHY (false discovery rate); the number of prior tests must be assumed (example: at least 315 factors). Haircut = (SR_reported - SR_adjusted)/SR_reported, where SR_adjusted comes from converting the Sharpe to a t-stat and p-value, adjusting the p-value for N tests, and converting back [from memory]. — [Harvey-Liu PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF); R implementation [quantstrat haircutSharpe](https://www.rdocumentation.org/packages/quantstrat/versions/0.15.6/topics/haircutSharpe)
- Bonferroni: p_adj = min(1, N*p). Holm: sequential, less stringent. BHY: FDR control, most lenient. — [search summary of Harvey-Liu](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)
- Sullivan, Timmermann, White, "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", Journal of Finance 54(5), 1647-1691 (1999): applies White's Reality Check bootstrap to technical rules (building on Brock-Lakonishok-LeBaron 1992's 26 rules) on 100 years of daily DJIA. — [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/119144), [EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:54:y:1999:i:5:p:1647-1691)
- The 7,846-rule figure is attributed to Bajgrowicz & Scaillet, who re-examined "the 7,846 trading rules of STW" on DJIA; I could not verify the count in the original STW text. — [Bajgrowicz & Scaillet](https://bashtage.github.io/kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf) (host of STW PDF; Bajgrowicz-Scaillet at sibling path)
- White's Reality Check (Econometrica 2000) and Hansen's SPA (2005): bootstrap test of whether the best of K rules beats a benchmark, accounting for the search; SPA is less sensitive to poor/irrelevant alternatives. [from memory; not retrieved this session]
- STW's headline conclusion (from memory, not confirmed in this session's search results): the best rules looked significant in-sample, but after Reality Check adjustment, no excess performance in the later out-of-sample decade.

### Inferences
- For ~10 bots each with a parameter grid, N in DSR should count every variant tried across all bots and all research iterations (including discarded ideas), not just the final 10.
- Practical bar: DSR > 0.95, PBO < ~0.2-0.5 (threshold choice is practitioner convention, not from a retrieved source), and a t-stat of strategy mean return > 3 when many variants were searched.

### Gaps
- Primary PDFs of DSR, PBO, Harvey-Liu not read (hosts blocked); exact CSCV and haircut formulas need confirmation.
- Original STW numbers and Hansen SPA paper details not retrieved.

## Validation (walk-forward, CPCV, Monte Carlo, parameter plateau, noise tests, minimum trades)

### Takeaway
Use out-of-sample methods that never reuse tuning data: walk-forward (Pardo) with efficiency >= ~50%, CPCV for a distribution of OOS paths, Monte Carlo on trade sequences, then live/paper incubation. Practitioner thresholds are mostly vendor/blog level, not peer-reviewed.

### Cited Findings
- Walk-forward analysis credited to Robert Pardo (1992 book; 2nd ed. "The Evaluation and Optimization of Trading Strategies", Wiley 2008). — [Walk-forward optimization](https://Www.wikipedia.org/wiki/Walk_forward_optimization)
- Walk-Forward Efficiency (annualised OOS return / annualised IS return): <30% overfit, 30-50% warning, 50-70% acceptable (validate with Monte Carlo), 70-100% good; 50% attributed to Pardo (vendor blog, treat cautiously). — [Backtrex](https://backtrex.com/en/blog/walk-forward-efficiency-ratio-thresholds)
- TradeStation default pass: overall profitable AND WFE >= 50%; also at least half of walk-forward windows profitable; invalid if any single win/period contributes > 50% of net profit. — [TradeStation help](https://help.tradestation.com/10_00/eng/tswfo/topics/walkforward_test_results.htm)
- CPCV (Lopez de Prado, Advances in Financial Machine Learning, 2018; purging ch.7, CPCV ch.12): split into N groups, K as test; C(N,K) splits and phi = C(N-1,K-1) backtest paths (N=6, K=2 gives 15 splits, 5 paths). Purging removes training observations whose labels overlap test labels; embargo buffer after the test set. Gives a distribution of performance, pairs with PSR/DSR. — [Purged cross-validation (Wikipedia)](https://en.wikipedia.org/wiki/Purged_cross-validation), [skfolio CombinatorialPurgedCV](https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html)
- Kevin Davey process: walk-forward (one-shot IS/OOS, no revisiting), then Monte Carlo resampling of trades, then 6-12 months of incubation (paper); failing any gate means reject with no edits; roughly 1 in 20 ideas survives. — [Algo Advantage ep. 036](https://algoadvantage.substack.com/p/036-kevin-davey-part-i-its-all-about), [IBKR Quant summary](https://www.interactivebrokers.com/campus/ibkr-quant-news/algo-advantage-036-kevin-davey-part-i-its-all-about-process-in-algo-trading/)
- Davey sizes so that worst-case Monte Carlo drawdown stays within personal limit. — same sources.
- Secondary blog thresholds (low confidence, NOT Davey's own): at least 100 independent trades in test+OOS; kill rule PF<1.05 over 200 live trades or drawdown >1.5x tested; WFE>=50%; Monte Carlo 1000+ resamples requiring acceptable 5th-percentile equity path. — [forex.in.rs](https://www.forex.in.rs/algo-roots-consistency), [validate guide](https://tradingwyckoff.com/en/algorithmic-trading/validate-trading-strategy-guide/)
- Pre-committed pass/fail gates across IS, WF and OOS stages are described in [arXiv 2603.09219](https://arxiv.org/pdf/2603.09219).

### Inferences
- Parameter plateau check (neighbouring parameter values give similar results; prefer a broad plateau over a sharp peak) and noise-added/synthetic price tests are standard but I found no retrieved source quantifying them; implement as: +/-20-30% parameter perturbation must keep Sharpe >= ~50-70% of base (convention, my suggestion).
- With daily bars, trade-count minima matter: with fewer than ~100 trades, Sharpe/PF are too noisy; the t-stat of mean trade return (mean/(sd/sqrt(n))) is the direct check.

### Gaps
- No primary source for Davey's numeric criteria, minimum trade counts, or plateau/noise-test thresholds.
- No head-to-head WF vs CPCV evidence retrieved.

## Realistic costs and execution assumptions

### Takeaway
US ETFs via Alpaca/IBKR have near-zero commission but non-zero spread, slippage and sell-side regulatory fees; crypto taker fees (0.1% to 0.6% at retail tiers) and FX spreads (0.1 to 1+ pips) are material for high-turnover bots. Execute at next-bar open, not signal-bar close.

### Cited Findings
- Alpaca: no commission on US stocks/ETFs for retail; SEC fee (sells only, on principal) and FINRA TAF (sells only; min $0.000166/share, max $8.30) pass through; CAT fee being added; SEC fee rate has changed over time so check current rate. Elite per-share tiers $0.0025-0.0040/share. — [Alpaca fees](https://alpaca.markets/learn/trading-fees/), [Alpaca regulatory fees](https://alpaca.markets/support/regulatory-fees), [Alpaca Elite](https://alpaca.markets/elite)
- IBKR: Lite commission-free for eligible US residents; Pro tiered $0.0005-$0.0035/share, Pro fixed $0.005/share, min $1.00/order, cap 1% of trade value; plus exchange/regulatory/clearing fees. — [IBKR commissions](https://www.interactivebrokers.com/commissions)
- Binance.com base spot tier 0.10% maker / 0.10% taker, down to 0.02%/0.04% at top tier; 25% discount paying with BNB (secondary comparison site, unverified against Binance). Binance.US: 0% maker, 0.02% taker on most spot pairs (different schedule). — [Spark comparison](https://www.spark.money/tools/crypto-exchange-fee-comparison), [Binance.US](https://blog.binance.us/zero-fee-trading/)
- Coinbase Advanced low-volume tier commonly cited 0.4% maker / 0.6% taker; one source claims a fee rebuild on 16 Sep 2026 that may make this outdated (unconfirmed). — [Coinbase fees help](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees), [DailyCoin 2026](https://dailycoin.com/fees-trading-crypto/)
- EURUSD retail: broker test of 60 brokers averaged 0.59 pips (range 0.0-3.0); standard accounts ~1.11 pips avg; raw/ECN ~0.06-0.10 pips plus commission. — [BrokerChooser](https://brokerchooser.com/broker-costs/spread-comparison-in-germany), [compareforexbrokers](https://www.compareforexbrokers.com/best-forex-broker/lowest-spreads)

### Inferences
- Suggested conservative backtest costs (my judgement, not sourced): liquid US ETFs 1-3 bps per side spread+slippage; crypto 10 bps fee plus 5-10 bps slippage per side (use 60 bps if on Coinbase retail tier); FX majors 1 pip round-trip equivalent plus swap.
- Signal on bar close, fill at next bar open; use adjusted (total-return) prices for dividends, point-in-time universes to avoid survivorship; do not use same-bar highs/lows for stop and entry without worst-case ordering. (Standard practice; no source retrieved.)

### Gaps
- Binance.com and Coinbase official fee tables not verified; current SEC fee rate not retrieved; no sourced ETF slippage study; look-ahead/survivorship pitfalls not sourced.

## Machine learning evidence

### Takeaway
ML on cross-sectional equities shows real out-of-sample predictability (trees, nets, mostly momentum/liquidity/volatility signals), but profits concentrate in small, illiquid stocks, high turnover, and decayed after ~2010 for daily-bar stat-arb. Net of costs for retail it is weak; credible retail-viable use is low-turnover, regularised models with strict purged validation.

### Cited Findings
- Gu, Kelly, Xiu, "Empirical Asset Pricing via Machine Learning", Review of Financial Studies 33(5), 2223-2273 (2020), NBER w25398: trees and neural nets best, gains from nonlinear interactions; dominant signals are momentum, liquidity, volatility; ML roughly doubles performance of a leading regression-based strategy; preliminary version cited annualised Sharpe above 2.0 for ML forecasts (unconfirmed in final). — [NBER](https://nber.org/papers/w25398), [SSRN](https://papers.ssrn.com/abstract=3159577), [RePEc](https://econpapers.repec.org/RePEc:oup:rfinst:v:33:y:2020:i:5:p:2223-2273.)
- Kelly, Malamud, Zhou, "The Virtue of Complexity in Return Prediction", Journal of Finance 79(1), 459-503 (2024), NBER w30217: theory that over-parameterised models (parameters > observations) can predict better; R2 and Sharpe rise with complexity even with minimal regularisation; OOS gains partly from predicting recessions; market-timing focus. — [Yale PDF](https://economics.yale.edu/sites/default/files/2024-01/The%20Journal%20of%20Finance%20-%202023%20-%20KELLY%20-%20The%20Virtue%20of%20Complexity%20in%20Return%20Prediction%20%281%29.pdf), [RePEc](https://econpapers.repec.org/RePEc:bla:jfinan:v:79:y:2024:i:1:p:459-503)
- Krauss, Do, Huck, "Deep neural networks, gradient-boosted trees, random forests: Statistical arbitrage on the S&P 500", EJOR 259(2), 689-702 (2017): daily signals 1992-2015; ensemble >0.45% per day for k=10 before costs; profits declining in recent years, at times negative. — [FAU working paper](https://www.iwf.rw.fau.de/files/2016/03/03-2016.pdf), [EconPapers](https://econpapers.repec.org/RePEc:eee:ejores:v:259:y:2017:i:2:p:689-702)
- Fischer & Krauss, "Deep learning with LSTM networks for financial market predictions", EJOR 270(2), 654-669 (2018): S&P 500 constituents 1992-2015; 0.46% daily return and Sharpe 5.8 before costs; outperformed RF, DNN, logistic regression; but from 2010 excess returns appear arbitraged away, profitability around zero after costs. — [EconPapers](https://econpapers.repec.org/RePEc:eee:ejores:v:270:y:2018:i:2:p:654-669), [FAU WP](https://iwf.rw.fau.de/files/2015/12/11-2017.pdf)
- Avramov, Cheng, Metzker, "Machine Learning vs. Economic Restrictions", Management Science 69(5), 2587-2619 (2023): ML profits come mainly from hard-to-arbitrage stocks and low limits-to-arbitrage states; value-weighting and excluding microcaps/distressed stocks sharply attenuate them; high turnover and extreme positions erode returns after reasonable costs; deep-learning long positions remain viable in recent years. — [SSRN](https://papers.ssrn.com/abstract=3450322), [EconPapers](https://econpapers.repec.org/RePEc:inm:ormnsc:v:69:y:2023:i:5:p:2587-2619)

### Inferences
- Failure modes to guard against: label leakage/overlapping labels (use purging/embargo), tuning on test, microcap/illiquid-driven results, gross-of-cost Sharpe, regime decay post-publication, too many model/feature variants (apply DSR).
- For daily-bar retail: regularised linear (ridge/lasso/elastic net) and gradient-boosted trees on a small, economically motivated feature set, low turnover, liquid ETFs/large caps, are the most defensible; deep nets/LSTM evidence is gross-of-cost and decayed. (My synthesis.)

### Gaps
- No retrieved evidence specific to retail ML on ETFs/crypto/FX daily bars; Nagel or other critiques of Kelly-Malamud-Zhou (e.g. Cartea et al., Buncic) not retrieved; GKX R2 and decile Sharpe numbers not retrieved; no random-forest-on-technical-features OOS study found.

## Metrics to report and acceptance thresholds

### Takeaway
Report CAGR, vol, Sharpe, Sortino, Calmar/MAR, max drawdown and duration, exposure, profit factor, trade count, win rate/payoff, t-stat, plus DSR/PBO and WFE. Thresholds below are practitioner conventions; sourced ones are few.

### Cited Findings
- t-stat > 3.0 hurdle for claimed discoveries — [Harvey, Liu, Zhu](https://www.nber.org/papers/w20592)
- WFE >= 50%, >= half of WF windows profitable, no single period > 50% of net profit — [TradeStation](https://help.tradestation.com/10_00/eng/tswfo/topics/walkforward_test_results.htm)
- Monte Carlo trade resampling to size for worst-case drawdown; 6-12 months incubation — [Algo Advantage](https://algoadvantage.substack.com/p/036-kevin-davey-part-i-its-all-about)
- Blog-level kill rules (PF<1.05 over 200 trades; DD>1.5x tested) and >=100 trades — [forex.in.rs](https://www.forex.in.rs/algo-roots-consistency)

### Inferences (my suggested standard, unsourced conventions)
- Definitions: Sharpe = mean excess/sd * sqrt(252) (daily); Sortino uses downside deviation; Calmar = CAGR/|MaxDD| (3-yr in the original); t-stat of Sharpe ~ SR*sqrt(years); profit factor = gross win/gross loss.
- Accept if: net-of-cost OOS Sharpe >= ~0.7-1.0, Calmar >= ~0.5-1, PF >= ~1.3, >= 100 trades (more is better), DSR >= 0.95, PBO < ~0.3, WFE >= 50%, parameter plateau present, Monte Carlo 95th-percentile drawdown tolerable, results survive 2x cost stress.

### Gaps
- No peer-reviewed source for numeric Sharpe/Calmar/PF acceptance cut-offs; these are convention.
