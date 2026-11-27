# Hidden gems research - PARTIAL / UNVERIFIED

STATUS: WebFetch was blocked in this session (DNS failure for quantitativo.substack.com, concretumgroup.com,
cxoadvisory.com, abarbon.com, arxiv.org, ayratmurtazin.beehiiv.com). Only WebSearch worked, and it returns
synthesized snippets, not page text. Nothing below was read from the original page. Re-run once these hosts are allowed.
Target of 15-25 candidates NOT reached; 6 leads below.

## Leads (second-hand figures, verify against primary)

1. Zarattini/Pagani/Barbon "Catching Crypto Trends" (SFI WP 25-80, Oct 2025)
   - Donchian-channel ensemble, lookbacks ~5-360d plus midpoints, equal-weighted, daily rebalance, rotational top-20 liquid coins.
   - Reported: Sharpe >1.5, alpha 10.8%/yr vs BTC net of fees; one summary Sharpe 1.58, CAGR 30% (unconfirmed which config).
   - Data Jan 2010-Mar 2025, 21,616 coins, survivorship-free; tested costs 0.10/0.25/0.50%.
   - URLs: https://ideas.repec.org/p/chf/rpseri/rp2580.html ; https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/ ; https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/
   - Caveat: top-20 coin rotation needs spot access to many alts; BTC/ETH-only subset not quantified here. Independent retest: none found.

2. Zarattini/Aziz/Barbon "Beat the Market" intraday momentum SPY (SFI WP 24-97)
   - Noise-area breakout: boundary from avg intraday move over previous 14 days; trade when price exits the area.
   - Reported (CXO summary): 19.6% net annualized, Sharpe 1.33, maxDD -25%, May 2007-Apr 2024, with assumed frictions.
   - URLs: https://www.cxoadvisory.com/momentum-investing/complex-intraday-time-series-momentum-strategy-applied-to-spy/ ; https://www.sfi.ch/fr/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy
   - Needs intraday (minute) bars; exact rules not verified. Same authors as #1, so not independent.

3. Quantitativo SPY mean reversion "2.11 Sharpe" (lower band + IBS filter)
   - Repost claims Sharpe 2.11, ~13% annualized, 25-yr backtest; original ran only to 2020; QQQ retest and PSQ bear-switch variant exist.
   - URLs: https://ayratmurtazin.beehiiv.com/p/a-mean-reversion-strategy-with-2-11-sharpe ; https://red.127.pp.ua/r/algotrading/comments/1cwsco8/a_mean_reversion_strategy_with_211_sharpe
   - Exact rules/costs NOT verified. Risk: tuned on in-sample, ends 2020.

4. Keller Bold Asset Allocation BAA-G12 (SSRN 4166845)
   - CXO: 14.6% CAGR, -8.7% maxDD, Dec 1970-Jun 2022 (pre-inception modeled), monthly, 0.1% one-way costs; last-10y CAGR 7.8%.
   - URLs: https://www.cxoadvisory.com/momentum-investing/complex-offensive-defensive-asset-class-momentum ; https://thechartist.com.au/wp-content/uploads/2024/12/5369/SSRN-id4166845.pdf ; https://turingtrader-com.web.app/portfolios/keller-bold-asset-allocation
   - Exact universe not retrieved. Note the weak 10y CAGR (7.8%): decay flag.

5. SPY overnight after 3 down closes, above 200d MA (Quantified Strategies)
   - Buy close on 3rd consecutive down close, sell next open; 200d filter "important".
   - URL: https://quantifiedstrategies.substack.com/p/3-days-down-overnight-trading-strategy-1db
   - Costs/stats not verified. Alpha Architect: plain overnight anomaly weak net of costs / low robustness (https://alphaarchitect.com/trading-costs-wipe-out-the-overnight-return-anomaly/). Unconfirmed pulse.bot figure: 0.06% cost, 5.8% CAGR.

6. Connors Double 7 (7-day low entry, 200d filter), StrategyQuant test on SPY + 8 markets - zero costs assumed (flag).
   - URL: https://strategyquant.com/blog/larry-connors-double-7-strategy-tested-on-spy-and-8-other-markets/

Also seen (not read): IBS on SPY avg gain 0.8%/trade, 78% win; QQQ 1.33%, 75% (Quantified Strategies, gross, unverified).

## Not researched (blocked/time): sector/country rotations, TOM, TLT month-end, VIX dip buying, BTC weekend, gold trend, accelerating dual momentum, Alvarez, Robot Wealth, Newfound, etc.
