"""Build tradingview/index.html: every Pine script with a copy button.

    python3 tradingview/make_page.py
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# file, group, grade, chart, one-line rule, tested result (net of costs)
BOTS = [
    ("futures/f07_lower_band_ibs.pine", "Futures", "A", "MNQ1! / NQ1! · 5 or 15 min · extended hours on",
     "Buy the 16:00 close when price is below (20-day high − 3 × average range) and IBS < 0.3; sell a close above yesterday's high.",
     "1 MNQ, 2022–26: +$4,571/yr, profit factor 2.43, 72% winners, all 5 years up. ES: +$1,325/yr per MES."),
    ("futures/f06_ibs_dip_buy.pine", "Futures", "B", "MNQ1! / NQ1! · 5 or 15 min · extended hours on",
     "Buy the 16:00 close when IBS < 0.25; sell a close above yesterday's high or IBS > 0.8.",
     "1 MNQ, 2022–26: +$4,705/yr, profit factor 1.60, 72% winners. ES: +$1,337/yr per MES."),
    ("futures/f12_turnaround_tuesday.pine", "Futures", "B", "MNQ1! / NQ1! · daily",
     "After Monday falls 1.5% or more, buy Monday's close and sell two days later.",
     "1 MNQ, 2022–26: +$2,011/yr, 82% winners, but only 17 trades."),
    ("futures/f05_daily_fvg.pine", "Futures", "C", "MNQ1! / NQ1! · 1 hour",
     "Your PA Lab daily fair value gap: limit at the gap edge, stop beyond the far edge, 4R target, 48-hour limit.",
     "1 MNQ, 2022–26: +$1,637/yr, profit factor 1.57, all 5 years up. Your lab setting (3R, 96h): +$2,776/yr. ES about flat."),
    ("futures/f04_overnight_drift.pine", "Futures", "C", "MNQ1! / NQ1! · 1–15 min · extended hours on",
     "Buy the 16:00 close when above the 200-day average; sell at 09:30.",
     "1 MNQ, 2022–26: +$3,259/yr, profit factor 1.17, 4 of 5 years up. ES: +$356/yr."),
    ("futures/f01_noise_band.pine", "Futures", "C", "MNQ1! / NQ1! · 1, 5, 15 or 30 min",
     "Zarattini noise band: trade breaks of the intraday noise area at set check times, trail with VWAP, flat at 16:00.",
     "1 MNQ, 2022–26: +$1,398/yr, profit factor 1.18, but −$149/yr since Aug 2024. ES about flat."),
    ("futures/f02_opening_range_breakout.pine", "Futures", "C", "MNQ1! / NQ1! · 1 or 5 min",
     "Trade the direction of the first 5-minute candle, stop 10% of ATR, 10R target or 16:00.",
     "1 MNQ: lost 2011–21 (−$459/yr), +$1,131/yr 2022–26. ES lost in both."),
    ("futures/f09_turn_of_month.pine", "Futures", "F", "MNQ1! / NQ1! · daily",
     "Long from 5 trading days before month end to day 4 of the new month.",
     "1 MNQ, 2022–26: +$1,709/yr, but +$74/yr since Aug 2024; failed the overfitting checks."),
    ("futures/f11_vwap_trend.pine", "Futures", "F", "MNQ1! / NQ1! or QQQ · 1 min",
     "Long while price holds above VWAP from 10:00, switch after 15 closes on the other side.",
     "1 MNQ, 2022–26: +$1,045/yr, −$667/yr since Aug 2024; the paper's version lost after costs."),
    ("futures/f10_volatility_breakout.pine", "Futures", "F", "MNQ1! / NQ1! · 1–5 min",
     "Larry Williams: buy stop at open + 1 × yesterday's range, stop at the open, out at 16:00.",
     "1 MNQ, 2022–26: +$292/yr. ES lost."),
    ("futures/f03_intraday_momentum.pine", "Futures", "F", "MNQ1! / NQ1! · 1–30 min",
     "Trade the last half hour in the direction of the prev-close-to-10:00 move.",
     "1 MNQ, 2022–26: −$73/yr. The effect has faded."),
    ("futures/f08_opening_gap.pine", "Futures", "F", "MNQ1! / NQ1! · 1–5 min",
     "Fade or follow opening gaps bigger than k × ATR.",
     "1 MNQ, 2022–26: −$2,026/yr."),
    ("systematic/s14_keller_haa.pine", "Systematic", "A", "Any of SPY IWM EFA EEM VNQ DBC IEF TLT SHY · daily",
     "Keller HAA: TIP canary, top 4 of 8 ETFs by momentum, else IEF or cash. Monthly.",
     "2015–26: 10.0%/yr, Sharpe 0.98, worst fall −13% (SPY −34%)."),
    ("systematic/s07_ibs_mean_reversion.pine", "Systematic", "A", "SPY, QQQ, IWM or DIA · daily",
     "Buy the close when IBS < 0.15; sell a close above yesterday's high or IBS > 0.8.",
     "2013–26, 4 ETFs: 11.8%/yr, Sharpe 0.91, in the market 43% of days. QQQ alone: Sharpe 1.14."),
    ("systematic/s12_lower_band_ibs.pine", "Systematic", "A", "SPY or QQQ · daily",
     "Buy the close below (5-day high − 3 × 25-day range) with IBS < 0.3; sell above yesterday's high.",
     "2013–26: 8.6%/yr, Sharpe 0.88, in the market 11% of days."),
    ("systematic/s02_time_series_momentum.pine", "Systematic", "A", "SPY EFA EEM IEF TLT LQD GLD DBC VNQ · daily",
     "Hold each asset while its 63-day return is positive, sized by volatility. Monthly.",
     "2015–26, 9 ETFs: 3.6%/yr, Sharpe 0.78, worst fall −8%."),
    ("systematic/s08_overnight_after_down_days.pine", "Systematic", "A", "SPY or QQQ · 1–15 min",
     "After 3 down closes above the 200-day average, hold from the close to the next open.",
     "2013–26: 2.4%/yr, Sharpe 0.82, worst fall −7%."),
    ("systematic/s04_crypto_donchian_trend.pine", "Systematic", "B", "BTCUSD (or ETH and other large coins) · daily",
     "Average of Donchian breakout states (5–60 days), sized to 40% volatility.",
     "BTC 2020–26: 19.9%/yr, Sharpe 0.88, worst fall −34% (holding BTC: −77%)."),
    ("systematic/s01_faber_trend.pine", "Systematic", "B", "SPY, EFA, IEF, VNQ or DBC · daily",
     "Hold each asset above its 6-month average, else cash. Monthly.",
     "2015–26, 5 ETFs: 4.1%/yr, Sharpe 0.62, worst fall −11%."),
    ("systematic/s09_turn_of_month.pine", "Systematic", "B", "SPY · daily",
     "Long from 5 trading days before month end to day 3 of the new month.",
     "2013–26: 5.9%/yr, Sharpe 0.66, 63% winning months."),
    ("systematic/s15_volatility_edge.pine", "Systematic", "B", "SVXY · daily",
     "Zarattini Volatility Edge: SVXY sized VIX/100 in contango when VIX is above realised vol.",
     "2017–26: 3.9%/yr, Sharpe 0.67, worst fall −8%."),
    ("systematic/s10_sector_rotation.pine", "Systematic", "C", "Any SPDR sector ETF or IEF · daily",
     "Top 3 sectors by 3-month return; IEF when SPY is below its 200-day average. Monthly.",
     "2013–26: 8.7%/yr, Sharpe 0.69; could be luck."),
    ("systematic/s03_keller_vaa.pine", "Systematic", "C", "Any of SPY EFA EEM AGG LQD IEF SHY · daily",
     "Keller VAA-G4: top 2 offensive ETFs, or the best defensive one if any score is negative.",
     "2015–26: 4.5%/yr, Sharpe 0.51, worst fall −23%."),
    ("systematic/s16_connors_double7.pine", "Systematic", "F", "SPY, QQQ, IWM or DIA · daily",
     "Buy a 5-day closing low, sell a 5-day closing high.",
     "2013–26: 6.5%/yr, worst fall −36%; decayed."),
    ("systematic/s06_connors_rsi2.pine", "Systematic", "F", "SPY, QQQ, IWM or DIA · daily",
     "Buy RSI(2) < 10 above the 200-day average, sell RSI(2) > 70.",
     "2013–26: 3.7%/yr, worst fall −41%; decayed."),
    ("systematic/s05_vix_term_structure.pine", "Systematic", "F", "SVXY · daily",
     "Hold SVXY while VIX / VIX3M < 0.95.",
     "2017–26: 6.5%/yr, worst fall −50%. Do not run it."),
    ("systematic/s11_fx_trend.pine", "Systematic", "F", "EURUSD and other majors · daily",
     "Long above, short below the 100-day average, weekly.",
     "2015–26: −3.0%/yr."),
]

GRADE_TEXT = {"A": "Passed every test", "B": "Passed", "C": "Promising, not proven", "F": "Failed"}


def card(i, f, group, grade, chart, rule, result):
    code = (HERE / f).read_text()
    name = next((l.split("strategy(\"")[1].split("\"")[0] for l in code.splitlines() if l.startswith("strategy(")), f)
    cid = f"code-{i}"
    return f"""
    <article class="bot" data-group="{group}" data-grade="{grade}" data-search="{html.escape((name + ' ' + rule + ' ' + chart).lower())}">
      <div class="bot-head">
        <span class="chip g{grade}" title="{GRADE_TEXT[grade]}">{grade}</span>
        <h3>{html.escape(name)}</h3>
        <button class="copy" type="button" data-target="{cid}" id="btn-{i}">Copy code</button>
      </div>
      <p class="rule">{html.escape(rule)}</p>
      <dl class="facts">
        <div><dt>Chart</dt><dd>{html.escape(chart)}</dd></div>
        <div><dt>Tested result</dt><dd>{html.escape(result)}</dd></div>
      </dl>
      <details>
        <summary>Show code <span class="lines">{len(code.splitlines())} lines · {html.escape(f.split('/')[-1])}</span></summary>
        <pre id="{cid}"><code>{html.escape(code)}</code></pre>
      </details>
    </article>"""


def main():
    cards = "\n".join(card(i, *b) for i, b in enumerate(BOTS))
    n_f = sum(1 for b in BOTS if b[1] == "Futures")
    n_s = len(BOTS) - n_f
    page = f"""<title>Trading Bot Pine Scripts</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a single reading column of script cards under a sticky filter bar; code folds away until needed. */
:root {{
  --bg: #f5f6f4; --panel: #ffffff; --ink: #1d2321; --muted: #5d6763; --line: #dde2de;
  --accent: #0f6e5c; --accent-ink: #ffffff; --code-bg: #f0f3f1;
  --ok: #157347; --info: #2f5d8a; --warn: #9a6400; --bad: #b3362d;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #121615; --panel: #1a201e; --ink: #e6ebe8; --muted: #9aa5a0; --line: #2c3431;
  --accent: #3fb59b; --accent-ink: #0d1412; --code-bg: #0e1211;
  --ok: #4cc38a; --info: #7aa7d6; --warn: #e0a53f; --bad: #ef7a6f; color-scheme: dark }} }}
:root[data-theme="dark"] {{
  --bg: #121615; --panel: #1a201e; --ink: #e6ebe8; --muted: #9aa5a0; --line: #2c3431;
  --accent: #3fb59b; --accent-ink: #0d1412; --code-bg: #0e1211;
  --ok: #4cc38a; --info: #7aa7d6; --warn: #e0a53f; --bad: #ef7a6f; color-scheme: dark }}
body {{ background: var(--bg); color: var(--ink); font-family: var(--sans); font-size: 15px; line-height: 1.5; }}
.wrap {{ max-width: 920px; margin: 0 auto; padding-block: 28px 56px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
h1 {{ font-size: 1.9rem; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.01em; text-wrap: balance; }}
.lede {{ margin: 0 0 14px; color: var(--muted); max-width: 66ch; }}
.steps {{ margin: 0 0 18px; padding-left: 1.2em; max-width: 70ch; }}
.steps li {{ margin: 2px 0; }}
kbd {{ font-family: var(--mono); font-size: 0.85em; background: var(--code-bg); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }}
.bar {{ position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--bg); padding-block: 10px; margin-bottom: 12px;
  border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
body::before {{ content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--bg); }}
.seg {{ display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
.seg button {{ font: inherit; font-size: 0.9rem; background: var(--panel); color: var(--ink); border: 0; padding: 6px 12px; cursor: pointer; }}
.seg button + button {{ border-left: 1px solid var(--line); }}
.seg button[aria-pressed="true"] {{ background: var(--accent); color: var(--accent-ink); }}
.search {{ flex: 1 1 180px; min-width: 0; font: inherit; font-size: 0.9rem; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--ink); }}
.toggle {{ display: inline-flex; gap: 6px; align-items: center; font-size: 0.9rem; color: var(--muted); }}
.count {{ font-size: 0.85rem; color: var(--muted); font-variant-numeric: tabular-nums; }}
.list {{ display: flex; flex-direction: column; gap: 12px; }}
.bot {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; min-width: 0; }}
.bot-head {{ display: flex; align-items: center; gap: 10px; }}
.bot h3 {{ margin: 0; font-size: 1.05rem; font-weight: 600; flex: 1; min-width: 0; }}
.chip {{ font-family: var(--mono); font-weight: 500; font-size: 0.85rem; min-width: 1.9em; text-align: center; padding: 1px 6px; border-radius: 6px; border: 1.5px solid currentColor; }}
.gA {{ color: var(--ok); }} .gB {{ color: var(--info); }} .gC {{ color: var(--warn); }} .gF {{ color: var(--bad); }}
.copy {{ font: inherit; font-size: 0.88rem; font-weight: 500; background: var(--accent); color: var(--accent-ink); border: 0; border-radius: 7px; padding: 6px 12px; cursor: pointer; white-space: nowrap; }}
.copy.done {{ background: var(--ok); }}
button:focus-visible, .search:focus-visible, summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.rule {{ margin: 8px 0 6px; }}
.facts {{ display: grid; grid-template-columns: 1fr; gap: 4px; margin: 0 0 8px; font-size: 0.9rem; }}
.facts div {{ display: grid; grid-template-columns: 7.5em 1fr; gap: 8px; }}
.facts dt {{ color: var(--muted); }} .facts dd {{ margin: 0; min-width: 0; }}
details summary {{ cursor: pointer; font-size: 0.9rem; color: var(--accent); }}
.lines {{ color: var(--muted); font-family: var(--mono); font-size: 0.8rem; margin-left: 6px; }}
pre {{ margin: 8px 0 0; background: var(--code-bg); border: 1px solid var(--line); border-radius: 8px; padding: 12px; overflow: auto; max-height: 460px; font-family: var(--mono); font-size: 12.5px; line-height: 1.45; }}
.foot {{ margin-top: 28px; color: var(--muted); font-size: 0.88rem; max-width: 72ch; }}
.foot p {{ margin: 6px 0; }}
@media (max-width: 520px) {{ .bot-head {{ flex-wrap: wrap; }} .facts div {{ grid-template-columns: 1fr; gap: 0; }} }}
</style>

<div class="wrap">
  <h1>Trading Bot Pine Scripts</h1>
  <p class="lede">{len(BOTS)} TradingView strategies: {n_f} futures bots for Nasdaq-100 and S&amp;P 500 contracts, and {n_s} systematic bots for ETFs, crypto and forex. Each one was backtested in Python first; the result line is what that test found, after costs, on years it never saw.</p>
  <ol class="steps">
    <li>Press <b>Copy code</b> on a bot.</li>
    <li>In TradingView open the chart it names, then <kbd>Pine Editor</kbd> → select all → paste → <kbd>Add to chart</kbd>.</li>
    <li>Read the <kbd>Strategy Tester</kbd> tab, then paper trade before any real money.</li>
  </ol>
  <div class="bar" role="toolbar" aria-label="Filter scripts">
    <div class="seg" id="group-filter">
      <button type="button" id="g-all" data-group="all" aria-pressed="true">All</button>
      <button type="button" id="g-fut" data-group="Futures" aria-pressed="false">Futures</button>
      <button type="button" id="g-sys" data-group="Systematic" aria-pressed="false">Systematic</button>
    </div>
    <label class="toggle"><input type="checkbox" id="passed-only"> Passed only (A, B)</label>
    <input class="search" id="search" type="search" placeholder="Search: IBS, FVG, QQQ…" aria-label="Search scripts">
    <span class="count" id="count"></span>
  </div>
  <div class="list" id="list">
{cards}
  </div>
  <div class="foot">
    <p><b>Grades.</b> A: passed every out-of-sample test. B: passed a looser version. C: made money out of sample but could be luck. F: failed. The failed ones are here so you can check them yourself.</p>
    <p><b>Futures numbers</b> are for 1 micro contract (MNQ = $2 a point, MES = $5). One full-size NQ or ES is 10 times the dollars and the drawdowns. Costs used: $0.62 per contract per side plus 1 tick of slippage. The tests used index quotes, not CME futures, so TradingView's numbers will differ somewhat.</p>
    <p>These scripts were written without a Pine compiler. If TradingView shows an error, send me the line and message and I will fix it. Research and education, not financial advice.</p>
  </div>
</div>

<script>
(function () {{
  var group = "all";
  var bots = Array.prototype.slice.call(document.querySelectorAll(".bot"));
  var search = document.getElementById("search");
  var passed = document.getElementById("passed-only");
  var count = document.getElementById("count");
  function apply() {{
    var q = (search.value || "").trim().toLowerCase();
    var shown = 0;
    bots.forEach(function (b) {{
      var ok = (group === "all" || b.dataset.group === group) &&
               (!passed.checked || b.dataset.grade === "A" || b.dataset.grade === "B") &&
               (!q || b.dataset.search.indexOf(q) !== -1);
      b.hidden = !ok;
      if (ok) shown++;
    }});
    count.textContent = shown + " of " + bots.length;
  }}
  document.querySelectorAll("#group-filter button").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      group = btn.dataset.group;
      document.querySelectorAll("#group-filter button").forEach(function (o) {{ o.setAttribute("aria-pressed", String(o === btn)); }});
      apply();
    }});
  }});
  search.addEventListener("input", apply);
  passed.addEventListener("change", apply);
  document.querySelectorAll(".copy").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      var pre = document.getElementById(btn.dataset.target);
      var text = pre.textContent;
      function done(label) {{ btn.textContent = label; btn.classList.add("done");
        setTimeout(function () {{ btn.textContent = "Copy code"; btn.classList.remove("done"); }}, 1800); }}
      function fallback() {{
        var d = pre.closest("details"); if (d) d.open = true;
        var r = document.createRange(); r.selectNodeContents(pre);
        var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
        done("Selected: press Ctrl+C");
      }}
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(text).then(function () {{ done("Copied"); }}, fallback);
      }} else {{ fallback(); }}
    }});
  }});
  apply();
}})();
</script>
"""
    (HERE / "index.html").write_text(page)
    print("wrote", HERE / "index.html", len(page))


if __name__ == "__main__":
    main()
