# Crypto + FX systematic research notes (Round 2)

STATUS / CAVEAT: WebFetch was blocked for every host tried (concretumgroup.com, abarbon.com, quantpedia.com, snb.ch, cxoadvisory.com, ideas.repec.org: DNS not allowed in session). Everything below comes from WebSearch result summaries only. NO primary PDF was read. Treat all numbers as secondary/unverified; re-run after allowing those hosts (SSRN PDF mirror: https://papers.ssrn.com/sol3/Delivery.cfm/5209907.pdf?abstractid=5209907&mirid=1).

## Crypto

### Zarattini-Pagani-Barbon "Catching Crypto Trends" (SFI Research Paper 25-80)
- Sources: https://ideas.repec.org/p/chf/rpseri/rp2580.html ; https://concretumgroup.substack.com/p/catching-crypto-trends ; https://github.com/zebadee2kk/DeFi-TraderStack-Agent/issues/137
- Ensemble of Donchian-channel trend models; long when price hits upper channel; vol-based sizing.
- Lookbacks (secondary): 9 horizons 5,10,20,30,60,90,150,250,360 days. Vol target 25% annualised, 90-day realised vol, leverage cap 2x. (GitHub issue #137 summary; one other PR says 8 lookbacks - discrepancy.)
- Altcoin version: rotational portfolio, top 20 most liquid coins; Sharpe >1.5, alpha ~10.8%/yr vs BTC (secondary). BTC alone from Jan 2015: net CAGR ~30%, Sharpe ~1.56 (secondary; https://www.quantifiedstrategies.com/crypto-trend-trading-strategy-for-bitcoin/).
- Paper claims: long trends robust, short trends weakened recently, signal saturation for very strong trends.
- Independent replication BTC 2018-2026: ~16.4% / Sharpe 1.10 / MaxDD -19.9% (ambiguous columns) - https://github.com/shuazs/kitchenSinkTrading/pull/7 region of search results; weaker than paper.
- Exact stop/exit rule and cost assumption NOT verified.

### Detzel, Liu, Strauss, Zhou, Zhu (Financial Management 2021)
- https://ideas.repec.org/a/bla/finmgt/v50y2021i1p107-137.html ; CXO summary https://www.cxoadvisory.com/currency-trading/timing-bitcoin-with-smas/
- Price / moving-average ratios forecast daily BTC returns in and out of sample; alpha and Sharpe gain vs buy-and-hold. Earlier WP tested 5-100 day SMAs, Jul 2010-Dec 2017, results GROSS of costs. Exact MA lengths used and OOS numbers not verified. Later study of 12 cryptos: only short-term log-MA ratio and Hashrate index genuinely profitable.

### Liu & Tsyvinski (RFS 2021)
- https://nber.org/papers/w24877 ; https://www.nber.org/system/files/working_papers/w24877/w24877.pdf
- Significant TSMOM for BTC/XRP/ETH at daily and weekly horizons. Per-horizon BTC numbers not retrieved. Cross-sectional weekly momentum (Liu-Tsyvinski-Wu, https://cowles.yale.edu/sites/default/files/2022-10/LiuTsyvinskiWu2019%20COMMON%20RISK%20FACTORS.pdf): ~2.7% (1w), 3.3% (2w), 4.1% (3w), 2.5% (4w) weekly excess, gross, early sample, not codeable as-is.

### Time-of-day / day-of-week
- Quantpedia (Gemini hourly, 2015-2022, UTC): 22:00 and 23:00 UTC strongest, 03:00-04:00 weakest, none statistically negative; buy 21:00 / sell 23:00 UTC had drawdown in 2022-23. https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/
- UWA, 7 exchanges, 15M obs: effects time-varying, no persistent pattern. https://research-repository.uwa.edu.au/en/publications/bitcoin-time-of-day-day-of-week-and-month-of-year-effects-in-retu/
- arXiv 2109.12142: periodicity in volatility/liquidity (not returns). https://arxiv.org/pdf/2109.12142v2.pdf
- Weekend post-ETF: Kaiko weekend volume share ~13% early 2024 vs 24% in 2018 (https://theblock.co/post/302705/bitcoin-sees-all-time-low-weekend-trading-levels-following-etf-approvals-kaiko); Volmex WP: weekend vol lower, extra -9.07 vol pts post-ETF (https://volmex.finance/The Impact of Spot Bitcoin ETFs.pdf). CXO day-of-week (Sep 2014-Jul 2025): Monday strongest, small vs SD, inconsistent (https://www.cxoadvisory.com/calendar-effects/bitcoin-day-of-the-week-effects). No rigorous post-ETF weekend RETURN study found.

### Robot Wealth / carry
- Longmore trades crypto trend with low conviction, expects fade. Posts on carry: https://robotwealth.com/rw-pro-weekly-update-a-broader-crypto-carry-trade-and-lots-more (body not captured).
- Christin-Routledge-Soska carry (Binance, 8h funding): in-sample Sharpe 7-10 (https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf). Low-provenance page says simple funding carry decayed to ~0.6% by 2026, MaxDD -35%; cross-sectional funding factor modest edge (https://bryanvine.github.io/alpha-research/paper2.html).
- Monash: short-lookback crypto trend gives high Sharpe but costs bite (https://www.monash.edu/business/mcfs/our-research/all-projects/investment-strategy/trend-following-strategies-for-crypto-investors).

## Forex
- Breedon & Ranaldo, JMCB 2013 45(5) 953-965: currencies depreciate during own local trading hours; participants net buyers of the currency in own hours; EURUSD simple profitable strategy (https://www.snb.ch/en/publications/research/working-papers/2011/working_paper_2011_04). EXACT GMT hours NOT retrieved. Rule of thumb: short EUR in European hours, long EUR in US hours.
- Jiang (2015) long EUR in US hours/short EUR in EU hours: net Sharpe ~0.79 (reported as "79%"), cost ~2 bps per trade/day (https://www.cicfconf.org/sites/default/files/paper_67.pdf).
- SNB WP 2007-03: EURUSD time-of-day profitable after costs, breakeven ~4 pips (https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2007/working_paper_2007_03/publications0_en/working_paper_2007_03.n.pdf). Old sample.
- Krohn London-fix strategy: Sharpe 0.65 after conservative costs, negative at full costs (https://sites.insead.edu/facultyresearch/research/file.cfm?fid=66802).
- Menkhoff et al JFE 2012: cross-sectional momentum spread up to ~10%/yr, costs materially cut it (https://www.bis.org/publ/work366.pdf). Sharpe not retrieved.
- FX technical rules G11: avg Sharpe 0.62 in-sample, 0.06 OOS, sample to Apr 2020 (https://repository.adu.ac.ae/bitstreams/30d15095-739e-4967-a33f-7233bf0644df/download). G10 trend/carry weak post mid-2000s, zero-rate era worst, some recovery to 2023 (https://www.ai-cio.com/?p=88107; https://nber.org/system/files/working_papers/w32900/w32900.pdf).
- IBKR IDEALPRO: commission 0.2 bp of trade value (tiers down to ~0.08 bp at volume), min USD 2/order (older sheet: 2.50), no spread markup; min order 25k USD; odd lots can fill 1-2 bp worse (https://www.interactivebrokers.com/en/index.php?f=49654 ; https://ibkb.interactivebrokers.com/node/1459). Third-party review EURUSD avg spread 0.226 pip (https://www.forexbrokers.com/reviews/interactive-brokers). Retail round-trip EURUSD ~0.3-0.6 pip all-in; GBPUSD/USDJPY not verified.
