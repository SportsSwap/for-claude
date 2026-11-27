"""Write RESULTS.md and results/dashboard.json from the saved results."""
import json
import math

from engine.validate import RESULTS
from portfolio import grade

VERDICT = {
    "01": "Works mainly as drawdown control (max DD -11% vs SPY -34%); lags SPY's return in the 2015-26 bull market. PBO high: the 6 vs 10 month choice is noise.",
    "02": "Steady, low volatility, Sharpe 0.78 out of sample. Low return on its own; a good portfolio building block.",
    "03": "Decayed after publication (out-of-sample Sharpe 0.51, deflated Sharpe below 0.9). Superseded by HAA (#14).",
    "04": "19.9%/yr vs 36.2% for holding BTC, but the drawdown is -34% instead of -77% and the Sharpe is a bit higher (0.88 vs 0.82). Setting choice is fragile (PBO 0.67), so expect less.",
    "05": "Simple SVXY contango rule: -50% drawdowns, Sharpe 0.36 out of sample. Don't run it.",
    "06": "Connors RSI(2) has decayed: out-of-sample Sharpe 0.36, -41% drawdown. Matches the published re-tests.",
    "07": "Best single bot. Works on each ETF separately (QQQ Sharpe 1.14, SPY 0.94, ~340 trades each, ~72% winners) and still works when filled at the next open (Sharpe 0.76).",
    "08": "Clean but tiny edge (~2.4%/yr, -7% DD). Only the 3-down-day version works; the 1-day default does not. Useful as a diversifier.",
    "09": "The turn-of-month effect still exists on SPY (63% winning months, profit factor 1.8). Holding 5 days before month end works better than the classic 1.",
    "10": "Decent (8.8%/yr, Sharpe 0.69) but deflated Sharpe 0.84: could be luck. Not proven.",
    "11": "FX trend on majors lost money 2015-26, as the research warned (post-publication Sharpe near zero). Spot only, carry not included.",
    "12": "Strong (Sharpe 0.88, in the market 11% of days) but sensitive to fill timing: Sharpe 0.56 if filled at the next open. Needs market-on-close orders.",
    "13": "Your MACD 12/144/9 rule exactly as specified LOSES (-1.2%/yr out of sample). The optimiser's pick (12/26/9, no filter, 60 days) made 21%/yr but simply holding the same 12 stocks made 36%/yr, and the list is today's winners (survivorship bias). Not recommended.",
    "14": "Strong new find: 10%/yr, Sharpe 0.98, max DD -13% out of sample; the published setting was also the plateau pick (PBO 0.16).",
    "15": "Works only WITHOUT the paper's long-VIX leg (Sharpe 0.67, DD -8%). The paper's exact version: Sharpe 0.54, DD -30%.",
    "16": "Double 7s has decayed: Sharpe 0.47, -36% drawdown, and walk-forward Sharpe 0.28.",
    "17": "Good on paper (12.7%/yr, Sharpe 1.16 vs BTC 0.50, DD -17%) but the coin list is today's survivors, which flatters it. Kept out of the portfolio.",
}


def pct(x):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x*100:.1f}%"


def num(x):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


def main():
    S = json.loads((RESULTS / "summary.json").read_text())
    P = json.loads((RESULTS / "portfolio.json").read_text())
    rows, dash = [], []
    for o in S:
        g = grade(o)
        if o["name"].startswith(("13", "17")) and g in ("A", "B"):
            g = g + "*"
        oos, b, wf = o["out_of_sample"], o.get("benchmark_out_of_sample", {}), o["walk_forward"]
        rows.append(f"| {o['name']} | **{g}** | {oos['start'][:4]}–{oos['end'][:4]} | {pct(oos.get('CAGR'))} | {num(oos.get('Sharpe'))} | "
                    f"{pct(oos.get('maxDD'))} | {pct(oos.get('exposure'))} | {num(wf.get('Sharpe'))} | {num(oos.get('DSR'))} | "
                    f"{num(o['pbo'].get('PBO'))} | {pct(o['costs_x2_out_of_sample'].get('CAGR'))} | {pct(b.get('CAGR'))} / {num(b.get('Sharpe'))} |")
        dash.append({"name": o["name"], "grade": g, "notes": o["notes"], "verdict": VERDICT.get(o["name"][:2], ""),
                     "chosen": o["chosen"], "default": o["default"], "oos": oos, "wf": wf, "bench": b,
                     "default_oos": o["default_out_of_sample"], "pbo": o["pbo"].get("PBO"),
                     "cost2": o["costs_x2_out_of_sample"], "in_sample": o["in_sample"]})
    verdicts = "\n".join(f"- **{o['name']}** — {VERDICT.get(o['name'][:2], '')}" for o in S)
    port_rows = []
    for k, v in P.items():
        if k == "correlation":
            continue
        s, b = v["portfolio"], v["SPY"]
        port_rows.append(f"| {k.replace(' | ', ' — ')} | {pct(s['CAGR'])} | {num(s['Sharpe'])} | {pct(s['maxDD'])} | {pct(s['worst_year'])} | "
                         f"{v['avg_gross_exposure']:.2f}x | {pct(b['CAGR'])} / {num(b['Sharpe'])} / {pct(b['maxDD'])} |")
    members = next(v["members"] for k, v in P.items() if k.startswith("2020"))
    md = f"""# Trading bots: research, backtests and results

Built 27 Nov 2026. 17 strategies, 13 of them tested on 1993–2026 data
(crypto 2014–2026). Every number below is **net of trading costs** and comes
from free daily Yahoo Finance prices (dividend-adjusted).

**This is research, not financial advice. Past results, even out of sample,
do not promise future returns.** Paper-trade anything before real money.

## How every bot was tested (fixed before any result was seen)

1. A small grid of settings around the published rule, tested only on the
   **in-sample** years (ETFs: to 2012 or 2014; VIX: to 2016; crypto: to 2019/2020).
2. The setting picked is the best **plateau** (it and its neighbours all do
   well), not the single best spike.
3. That setting is then run on the **out-of-sample** years it never saw. That
   is the column that matters.
4. **Walk-forward:** re-pick every January using only past data, trade the year.
5. **Deflated Sharpe** (Bailey & López de Prado): the chance the Sharpe is real
   after allowing for how many settings were tried. ≥ 0.95 is good.
6. **PBO** (probability of backtest overfitting, CSCV with 16 blocks): the chance
   the in-sample winner is below median out of sample. Lower is better; 0.5 = coin flip.
7. **Costs doubled**: must still make money.

Costs per side: SPY/QQQ/IWM/DIA 2 bps, other ETFs 4 bps, SVXY/VIXY 8 bps,
crypto 20 bps, FX 1 bp. Signals use data up to the bar's close only; "at the
close" bots need market-on-close orders, others trade at the next open.

**Grades.** A: out-of-sample Sharpe ≥ 0.7, walk-forward Sharpe ≥ 0.6,
deflated Sharpe ≥ 0.95, PBO ≤ 0.5, profitable at 2× costs. B: Sharpe ≥ 0.5,
walk-forward ≥ 0.5, deflated Sharpe ≥ 0.9, profitable at 2× costs.
C: Sharpe ≥ 0.5 only. F: fails. \\* = biased stock/coin list (survivorship), not trusted.

## Results (out of sample)

| Bot | Grade | OOS years | CAGR | Sharpe | Max DD | Time in market | Walk-fwd Sharpe | Deflated Sharpe | PBO | CAGR at 2× costs | Buy & hold CAGR / Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

"Time in market" counts bond/T-bill holdings as invested for the allocation bots.

## What each result means

{verdicts}

## The multi-strategy portfolio

Single bots mostly don't beat simply holding SPY on return. Combined, they do
much better on risk, because they rarely lose at the same time (most pairwise
correlations are 0.0–0.4). This is how multi-strategy funds work.

Members (grade A/B, unbiased lists): {", ".join(members)}.
Each is weighted by the inverse of its trailing 1-year volatility, monthly.
"Stacked" scales the mix to 10% volatility with up to 2× gross exposure (a
margin account). Borrowing is charged at T-bill + 1.5%; idle cash earns
T-bill − 0.5% (IBKR pays nothing on the first US$10k, so small accounts earn less).

| Portfolio | CAGR | Sharpe | Max DD | Worst year | Avg gross exposure | SPY CAGR / Sharpe / Max DD |
|---|---|---|---|---|---|---|
{chr(10).join(port_rows)}

In 2022, when SPY fell about 18%, the stacked portfolio lost 3.8% (2020–26 mix).

## High-octane option (read the warning)

The IBS signal (bot 07) on SPY traded through 2× and 3× ETFs, 2013–2026:
SSO 18.2%/yr (max DD −35%), UPRO 27.1%/yr (max DD −48%, worst year −39%).
On QQQ via TQQQ it made 40.5%/yr with a −36% max DD, but QQQ was picked
*because* it did best out of sample, so that number is cherry-picked. Leveraged
ETFs can lose most of their value in a crash; size them small.

## Files

- `bots/strategies.py` — all 17 bots, with sources in the comments.
- `engine/` — data cache, backtester, metrics (deflated Sharpe, PBO), validation.
- `run_all.py` — reruns every test. `portfolio.py` — the combined portfolio.
- `signals.py` — today's target positions for the passing bots (never places orders).
- `tradingview/` — Pine Script v6 versions of bots 07 and 12 (not compiled here; check in the Pine Editor).
- `reports/Retail systematic trading strategies.md` — the research report.
- `research_notes/` — the raw research notes with sources.
- `results/` — every number, equity curve and trade list.

## Limits

- Research agents could read search summaries and some primary pages, not every
  paper (the network blocked many sites), so published figures are second-hand.
  The backtests here are first-hand.
- Yahoo data only. No survivorship-free stock universe, so stock-picking bots
  (like Clenow's) were not built.
- Out-of-sample periods are 6–14 years; 2015–2026 was a strong bull market,
  which flatters buy-and-hold and hurts defensive bots.
"""
    (RESULTS.parent / "RESULTS.md").write_text(md)
    (RESULTS / "dashboard.json").write_text(json.dumps(dash, indent=1, default=str))
    print("wrote RESULTS.md")


if __name__ == "__main__":
    main()
