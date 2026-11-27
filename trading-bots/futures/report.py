"""Write FUTURES_RESULTS.md from results/futures/*.json."""
import json
import math

from portfolio import grade
from engine.validate import RESULTS
from . import engine as E

OUT = RESULTS / "futures"


def money(x):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"${x:,.0f}"


def main():
    S = json.loads((OUT / "summary.json").read_text())
    P = json.loads((OUT / "portfolio.json").read_text())
    order = {"A": 0, "B": 1, "C": 2, "F": 3}
    S.sort(key=lambda o: (order[grade(o)], o["name"]))
    rows = []
    for o in S:
        m = E.MICRO[o["sym"]]
        c = o["contracts"][m]
        is_, new, fin, oos = c["IS 2011-2021"], c["NEW 2022-Jul 2024"], c["FIN Aug 2024-2026"], c["OOS 2022-2026"]
        etf = o["etf_equivalent_oos"]
        lev = list(etf)[1]
        rows.append(f"| {o['name']} | **{grade(o)}** | {o['chosen']} | {money(is_.get('usd_per_year'))} | {money(new.get('usd_per_year'))} | "
                    f"{money(fin.get('usd_per_year'))} | {money(oos.get('usd_per_year'))} | {oos.get('profit_factor', 0):.2f} | "
                    f"{oos.get('win_rate', 0)*100:.0f}% | {oos.get('trades', 0)} | {money(oos.get('max_dd_usd'))} | {oos.get('years_up', '—')} | "
                    f"{money(c['OOS 2022-2026 at 2x costs'].get('usd_per_year'))} | {lev.split()[0]} {etf[lev]['CAGR']*100:.0f}% |")
    md = f"""# Futures bots: NQ / MNQ and ES / MES

Built 27 Nov 2026 on free 1-minute Nasdaq-100 and S&P 500 index data from
HistData.com (Nov 2010 to 13 Nov 2026, New York time). Every number is
**per 1 micro contract, after costs**: $1.24 commission per round trip plus
1 tick (0.25 point) of slippage on every market or stop fill. MNQ = $2 a
point, MES = $5 a point. **One full-size NQ or ES is 10× the dollars and 10× the
drawdowns.**

Research and education, not financial advice. Paper trade first.

## How they were tested

Same rules as the systematic bots, fixed before any result was seen:
settings picked only on **2011–2021**, then run unchanged on **2022–Jul 2024
(NEW)** and **Aug 2024–Nov 2026 (FIN)**, the windows of your PA Lab. Plus
walk-forward, deflated Sharpe, overfitting probability (PBO) and doubled costs.
Grades as before: A passes everything, B a looser bar, C made money but could be
luck, F failed.

Data caveats: these are index quotes, not CME futures (no roll gaps, no basis);
2023 is missing about 60 days; the data has no volume, so "VWAP" in the Python
tests is a time-weighted price (the Pine scripts use real VWAP).

Two bugs were caught and fixed before these numbers: a look-ahead in the
intraday-momentum filter (it had shown a fake Sharpe of 4.7) and a 1-hour peek
in the daily FVG's decision time.

## Results (1 micro contract, dollars per year)

| Bot | Grade | Settings (picked on 2011–21) | 2011–21 | NEW 2022–Jul 24 | FIN Aug 24–26 | 2022–26 | Profit factor | Win | Trades | Worst fall | Years up | 2022–26 at 2× costs | QQQ-style 3× ETF CAGR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

The last column puts the whole account in each trade through a 3× ETF (TQQQ for
NQ, UPRO for ES), compounded, ignoring the ETF's fees: a rough guide to the
"QQQ / TQQQ" version of each bot.

## The futures portfolio (2022–2026, out of sample)

The bots that passed (A/B): {", ".join(P["members"])}, 1 MNQ each.

- **{money(P["usd_per_year"])} a year**, {money(P["net_usd"])} in total, worst fall {money(P["max_dd_usd"])}, Sharpe {P["sharpe"]:.2f}.
- Every year up: {", ".join(f"{k}: {money(v)}" for k, v in P["yearly_usd"].items())}.
- At most {P["max_contracts_open"]} MNQ open at once (average {P["avg_contracts_open"]:.1f}). Check your broker's overnight
  margin per MNQ (it changes with volatility) and keep enough on top to sit through a fall at least twice the worst one above.

All three are "buy the Nasdaq dip" bots, so they depend on the same market.
Adding your style of bots (daily FVG, noise band, overnight drift, all grade C)
gave about $17,400 a year with a worst fall of about $8,900 over the same years
(Sharpe 1.92). Higher, but those three are not proven.

## What this says about your bot types

- **Daily FVG (your PA Lab bot):** better on this data than on Dukascopy's. On NQ it
  made money in 2011–21 (+$284/yr per MNQ) and in all 5 later years
  (+$1,637/yr); your lab setting (3R, 96h) made +$2,776/yr after 2022. On ES it was
  flat. Grade C: real enough to paper trade, not proven.
- **Noise band:** worked in 2022–Jul 2024, flat since Aug 2024, flat on ES. The paper's
  results do not hold up on futures after costs, which matches the independent
  replications the research found.
- **Opening range breakout:** lost money on NQ in 2011–21 and made money after 2022
  (grade C); lost on ES in both. **VWAP trend, gap, volatility breakout, intraday
  momentum:** none survived costs on futures. Independent costed tests online
  found the same.
- **What did work:** buying sharp one-day dips in the Nasdaq at the close (IBS,
  lower band, Turnaround Tuesday) and holding the overnight session.

## Files

- `futures/` — data loader, contract engine, the 12 bots, runner, portfolio, this report.
- `tradingview/futures/` — Pine Script v6 for all 12; `tradingview/index.html` is the copy page.
- `results/futures/` — every number and every trade list.
- `research_notes/Round 3 intraday futures/` — the research behind the rules.
"""
    (RESULTS.parent / "FUTURES_RESULTS.md").write_text(md)
    print("wrote FUTURES_RESULTS.md")


if __name__ == "__main__":
    main()
