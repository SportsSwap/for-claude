# Equity and ETF return anomalies tradable with free daily data

Method note: research was done with web search snippets only. WebFetch was blocked for econpapers.repec.org, libertystreeteconomics.newyorkfed.org and alphaarchitect.com (not in the session's allowed network domains), so primary PDFs were not read. Figures below come from search-result summaries. Items marked "unverified" should be checked against the paper before use. Many requested numbers (Sharpe ratios, drawdowns, exact trading rules, 2010-2026 ETF-specific results) were not found and are listed under Gaps.

## Calendar and intraday-structure effects on index ETFs (overnight/intraday, turn-of-month, pre-FOMC, Halloween, day-of-week)

### Takeaway
The overnight-return concentration in the S&P 500 is well documented historically and still visible in SPY in long samples, but a realistic after-cost edge for a retail trader is disputed. Pre-FOMC drift was strong through 2011 and replicated in the Fed authors' own 2018 update, but an independent replication found it fading after 2016. Turn-of-month and Halloween are well documented historically, and post-publication evidence is mixed or unresolved.

### Cited Findings
- Overnight vs intraday (Lou, Polk, Skouras, "A Tug of War: Overnight Versus Intraday Expected Returns", JFE 2019): past smoothed overnight returns and past smoothed intraday returns push future returns in opposite directions. Past intraday returns positively forecast subsequent overnight returns ("night extends the day") and overnight returns revert intraday ("day destroys the night"). — [LSE paper](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf); search summary of the 2026 SPY-based working paper at [LSE 2026 draft](https://personal.lse.ac.uk/POLK/research/LPS_ClientelePerspectiveOnEquityPremium_20260603.pdf)
- A 2026 working paper from the same group uses SPY as the market proxy and finds smoothed overnight SPY return forecasts future SPY returns; it attributes the 2008 crisis mainly to intraday returns and COVID-era variation to overnight returns. Not verified against full text. — [LSE 2026 draft](https://personal.lse.ac.uk/POLK/research/LPS_ClientelePerspectiveOnEquityPremium_20260603.pdf)
- CXO Advisory summary of the Tug of War paper: intermediate-term momentum profits arise overnight (0.89% vs -0.18% monthly, per snippet), while value and size effects arise intraday (sample 1993-2013, per snippet; details truncated). — [CXO Advisory](https://www.cxoadvisory.com/calendar-effects/momentum-happens-at-night/)
- SPY buy-at-close/sell-at-open, 1993 to January 2020: cumulative price returns of 717% overnight, 627% buy-and-hold, and 12% intraday. The same Alpha Architect piece argues trading costs wipe out the overnight anomaly. — [Alpha Architect, "Trading Costs Wipe Out the Overnight Return Anomaly" (2020)](https://alphaarchitect.com/trading-costs-wipe-out-the-overnight-return-anomaly/)
- Quantpedia says its SPY backtests show the overnight effect "alive", with only a small drop if the exit is at 9:31 instead of the open; it also warns that OHLC data can mislead (GDX example). — [Quantpedia](https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/?a=6080)
- QuantConnect implementations of the Quantpedia overnight strategy gave widely varying results (Sharpe 0.219 in one 5-year run; Sharpe -0.11 and -28.9% net profit in a 2000-2018 run; fees about 25% of starting capital in a 20-year run). These are different universes and settings, not a clean SPY test. — [QuantConnect overnight anomaly](https://www.quantconnect.com/research/15296/overnight-anomaly/p1)
- Pre-FOMC drift (Lucca and Moench, "The Pre-FOMC Announcement Drift", NY Fed Staff Report 512; later published in the Journal of Finance): large equity returns in the 24 hours before scheduled FOMC announcements, 1980s to March 2011, with no subsequent reversal. — [NY Fed SR512](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.html)
- Lucca-Moench update (Liberty Street Economics, Nov 2018): after 2011 the drift persisted at about 40 bp measured from the prior-day open, tied to meetings with a Chair press conference, with returns starting earlier (the morning before the announcement). Similar drifts appear in other developed-country equity markets; none in Treasuries. — [Liberty Street 2018](https://libertystreeteconomics.newyorkfed.org/2018/11/the-pre-fomc-announcement-drift-more-recent-evidence.html)
- Independent replication by Kurov, Wolfe and Gilbert (sample to December 2019): drift disappeared for announcements without press conferences, and since January 2016 weakened substantially even with press conferences. — [Kurov, Wolfe, Gilbert](https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf); contradicts the 2018 NY Fed update above
- Turn-of-month (McConnell and Xu, "Equity Returns at the Turn of the Month", Financial Analysts Journal 2008): effect found in 31 of 35 countries (another summary says 34 of 38; counts differ by source), 1926-2005; held in the two most recent decades of the sample. — [FAJ via CFA Institute](https://rpc.cfainstitute.org/en/research/financial-analysts-journal/2008/equity-returns-at-the-turn-of-the-month)
- Turn-of-month post-publication in the US: a 2001-2011 SPY study found the effect still present but occurring earlier; other work reports it vanishing after 1990 in S&P 500 spot and futures, or in the S&P 100 after controlling for macro announcements; a 2025 Finance Research Letters paper is titled "The disappearing turn-of-month effect" (findings not checked). — [search results incl. Purdue working paper](https://docs.lib.purdue.edu/ciberwp/43)
- Halloween / Sell in May (Bouman and Jacobsen, American Economic Review 2002): 37 countries, 1970-1998; effect present in 36 and significant in 20; the authors also report UK evidence back to 1694. — [Bouman-Jacobsen SSRN](https://www.tias.edu/docs/default-source/Kennisartikelen/ssrn-id76248.pdf?sfvrsn=2)
- Halloween out-of-sample: one follow-up covering November 1998 to April 2012 found the indicator had not disappeared; Maberly and Pierce (2004) argued the US result is outlier-driven (snippet garbled, unverified). — [CFA Institute Enterprising Investor 2016](https://blogs.cfainstitute.org/investor/2016/04/12/dumb-alpha-sell-in-may-and-go-away)

### Inferences
- Overnight/intraday tests on SPY should use open and close prices from free daily OHLC data but need execution at the auction (market-on-open/market-on-close orders). Daily turnover of about 250 round trips a year makes spreads and fees the dominant risk; the sources suggest costs consume most of the gross edge.
- Pre-FOMC drift has only about 8 observations a year, so it is a low-capacity add-on, and its post-2016 weakening makes it a weak standalone strategy.
- Day-of-week effects were not found in my searches and should be treated as unsupported here.

### Gaps
- No verified post-2010 Sharpe, annual return or drawdown numbers for overnight SPY/QQQ/IWM, turn-of-month, Halloween or pre-FOMC after costs.
- Kelly-Clark and Cooper-Cliff-Gulen papers were not retrieved.
- Day-of-week and pre-holiday effects were not searched successfully.
- Exact trading rules (days of the turn-of-month window, etc.) were not confirmed; the only figure seen is a "four-day" window in an unattributed snippet.
- Content of the 2025 "disappearing turn-of-month" paper not checked.

## Momentum (cross-sectional, time-series, industry, crashes, volatility-managed)

### Takeaway
Momentum crash risk is real and scaling by realized volatility is reported to improve it, but the improvement has look-ahead and cost caveats. Time-series momentum is contested as a predictability result even though the trend strategy earns money.

### Cited Findings
- Barroso and Santa-Clara ("Momentum has its moments", JFE 2015): scaling momentum by its own realized volatility roughly doubles the Sharpe ratio and largely eliminates crashes. — [Alpha Architect summary](https://alphaarchitect.com/avoiding-momentum-crashes/); [JFE record](https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120)
- Daniel and Moskowitz ("Momentum crashes", JFE 2016): dynamic scaling cuts the worst monthly crashes from as much as 77% to about 28% (constant-volatility) and 25% (dynamic), per one secondary study. — [secondary summary](https://link.springer.com/content/pdf/10.1057/s41260-021-00229-x.pdf)
- A follow-up reports that after correcting a look-ahead bias, the performance of such dynamic momentum strategies worsened substantially (Liu et al. 2019, as cited). — [Bianchi et al., "Taming momentum crashes"](https://strathprints.strath.ac.uk/90217/1/Bianchi-etal-SSRN-2022-Taming-momentum-crashes.pdf)
- Huang, Li, Wang and Zhou ("Time series momentum: Is it there?", JFE 2020): asset-by-asset regressions show little evidence of TSMOM in or out of sample; the pooled t-statistic is not reliable; the TSMOM strategy performs about the same as one based on the historical sample mean. — [JFE record](https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:3:p:774-794); [Alpha Architect](https://alphaarchitect.com/2020/03/an-empirical-challenge-for-trend-following/)
- Moreira and Muir ("Volatility-Managed Portfolios", NBER 22208, later JF 2017): market volatility-managed strategy alpha of 4.9%, appraisal ratio 0.33, 25% higher Sharpe than buy-and-hold. — [NBER](https://www.nber.org/papers/w22208.pdf)
- Cederburg et al. (JFE 2020): across 103 equity strategies, real-time volatility-managed versions generally do not beat unmanaged versions in certainty-equivalent return or Sharpe; spanning-regression alphas are not implementable. — [Arizona record](https://experts.arizona.edu/en/publications/on-the-performance-of-volatility-managed-portfolios/); contradicts the Moreira-Muir headline
- A separate paper identifies look-ahead bias in the Moreira-Muir weight calibration (full-sample unconditional volatility). Barroso and Detzel report that these strategies do not survive transaction costs (as summarized in DeMiguel et al.). DeMiguel, Martin-Utrera and Uppal (JF 2024) argue a conditional multifactor version works out of sample and net of costs. — [DeMiguel et al. JF 2024](https://lbsresearch.london.edu/id/eprint/3716/1/The%20Journal%20of%20Finance%20-%202024%20-%20DeMIGUEL%20-%20A%20Multifactor%20Perspective%20on%20Volatility%E2%80%90Managed%20Portfolios.pdf)

### Inferences
- A simple ETF momentum rule scaled by trailing realized volatility is implementable from daily closes, but the evidence suggests expecting less than the published Sharpe gains.

### Gaps
- No search result confirmed the Sharpe values I was asked about (0.97/0.53 for momentum); not found.
- Jegadeesh-Titman, Moskowitz-Ooi-Pedersen, Asness-Moskowitz-Pedersen and Moskowitz-Grinblatt figures were not retrieved; ETF/country/sector momentum numbers (post-2010) not found.

## Reversal, low-volatility, betting-against-beta, 52-week high, seasonality

### Takeaway
Only same-calendar-month seasonality was covered; the rest were not retrieved. Heston-Sadka is documented internationally but partly attributed to sorting artifacts.

### Cited Findings
- Heston and Sadka seasonality: stocks with strong same-calendar-month past returns keep outperforming in that month; a long-short strategy earned about 13% a year 1963-2011 in one source and up to 12% a year in another; survives controls for size, industry and Fama-French factors; also found in Canada, Japan, 12 European countries (JFQA 2010). — [NBER w20815](https://www.nber.org/papers/w20815.pdf); [JFQA 2010](https://econpapers.repec.org/RePEc:cup:jfinqa:v:45:y:2010:i:05:p:1133-1160_00)
- Critique: a sort on past returns picks up seasonalities regardless of origin; Keloharju, Linnainmaa and Nyberg describe offsetting seasonal reversals. — [AQR/Keloharju et al. link](https://www.aqr.com/-/media/AQR/Documents/AQR-Insight-Award/2015/AllSeasons20141219pdf.pdf)

### Inferences
- This is a stock-level long-short anomaly and not directly applicable to index ETFs without shorting.

### Gaps
- Short-term reversal, low-vol/BAB (Frazzini-Pedersen), George-Hwang 52-week high: no sourced figures found. Not assessed.

## Post-publication decay and replication

### Takeaway
Most published stock anomalies replicate in raw data, but fewer survive value-weighting, microcap exclusion and multiple-testing hurdles; post-publication returns shrink materially.

### Cited Findings
- McLean and Pontiff (JF 2016, 97 variables): the commonly cited figures are returns 26% lower out of sample and 58% lower post-publication; a search summary gave about 35% decay for the 2013 working-paper version (82 characteristics) and about 32% for another draft, so numbers vary by version. The 26% and 58% were confirmed only by a secondary search summary. — [Econpapers record](https://econpapers.repec.org/RePEc:bla:jfinan:v:71:y:2016:i:1:p:5-32); [paper PDF](https://Www.Gwern.net/doc/economics/2016-mclean.pdf)
- Hou, Xue and Zhang (RFS 2020, 452 anomalies): with microcaps mitigated (NYSE breakpoints, value-weighting), 65% fail |t| >= 1.96 and 82% fail a multiple-testing hurdle of 2.78; replicated anomalies are smaller than originally reported. — [NBER w23394](https://www.nber.org/papers/23394)
- Jensen, Kelly and Pedersen (JF 2023, 153 factors, 93 countries): Bayesian replication rate 82.4%, versus 35% in Hou-Xue-Zhang; most factors replicate and hold out of sample, though a non-trivial minority fail. — [NBER w28432](https://nber.org/system/files/working_papers/w28432/w28432.pdf)
- Chen and Zimmermann (Critical Finance Review 2022): of 180 clearly significant predictors, 98% reproduce with t > 1.96; regression of reproduced on original t-stats has slope 0.90, R-squared 83%. — [SSRN](https://papers.ssrn.com/abstract=3604626)

### Inferences
- The disagreement between Hou-Xue-Zhang (35% replicate) and the others (82-98%) is mostly methodological (value-weighting and microcap treatment, test hurdle), so a retail trader limited to liquid stocks and ETFs should lean toward the lower numbers.

### Gaps
- Which anomalies survive best post-publication: not found.

## Lesser-known effects (leveraged-ETF rebalancing, options hedging flows, expiration week, window dressing)

### Takeaway
End-of-day flow effects from leveraged ETFs and options hedging are documented and need intraday data; expiration-week and window-dressing effects were not found.

### Cited Findings
- A 1% index move triggers about $1.04 billion of leveraged-ETF rebalancing in stock (Tuzun, Fed FEDS 2013-48); Cheng and Madhavan (2009) argue rebalancing demand pressures end-of-day S&P 500 returns. — [Fed FEDS 2013-48](https://www.federalreserve.gov/pubs/feds/2013/201348/201348pap.pdf)
- Barbon, Beckmeyer, Buraschi and Moerke: large negative (positive) aggregate gamma imbalance gives end-of-day momentum (reversal), dissipating within the next trading day. — [SSRN 3925725](https://papers.ssrn.com/abstract=3925725)

### Inferences
- These effects need the last-hour return and aggregate flow estimates, so they are not implementable with daily OHLC alone.

### Gaps
- Option-expiration week, quarter-end window dressing and index reconstitution: no sources found.
