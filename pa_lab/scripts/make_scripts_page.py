"""Build tradingview/scripts_page.html: every Pine script with a copy button."""
import html
import pathlib

T = pathlib.Path(__file__).resolve().parent.parent / "tradingview"

CARDS = [
    ("breakout", "15-minute level breakout", "15-minute chart · NQ1! or MNQ1!", "Tested",
     "Trades the first 15-minute close through a level made of three swing points, long or short, between 8am and 4pm New York time. Stop beyond the last swing, target equal to the risk, out after 96 bars.",
     "Lab, Aug 2024 to Nov 2026: NQ 941 trades, Sharpe 0.72 · ES 993 trades, Sharpe 0.59", "palab_breakout_15m.pine"),
    ("fvg", "Daily fair value gap", "1-hour chart · NQ1! or MNQ1!", "Tested",
     "After each daily close, a three-day gap gets a limit order at its near edge, with the stop beyond the far edge and a target of three times the risk. The order lives, and any trade closes, after 96 hourly bars. Gaps formed on CPI, jobs-report or Fed days are skipped.",
     "Lab, Aug 2024 to Nov 2026: NQ 50 trades, Sharpe 1.01 · ES 49 trades, Sharpe 0.84", "palab_daily_fvg_1h.pine"),
    ("fvgetf", "Daily fair value gap on TQQQ / SQQQ", "1-hour chart · TQQQ, SQQQ or QQQ", "Not tested by the lab",
     "The same daily gap signals, read from NQ futures in the background, traded in the ETF on your chart. On TQQQ it takes the long signals, on SQQQ the short signals (as a buy of SQQQ). Prices are converted with the ETF's 3x leverage; each trade is $10,000 of the ETF. Gaps seen after NQ's 5pm close are acted on the next morning, when the ETF opens.",
     "Paper trade first: this adaptation has only TradingView's own backtest behind it.", "palab_daily_fvg_etf_1h.pine"),
]


def card(idn, title, chart, status, desc, stats, fname):
    code = (T / fname).read_text()
    cls = "ok" if status == "Tested" else "warn"
    return f'''
<section class="script" aria-labelledby="{idn}-h">
  <header class="script-head">
    <div class="titles">
      <h2 id="{idn}-h">{title}</h2>
      <p class="setup"><span class="chip">{chart}</span> <span class="badge {cls}">{status}</span></p>
    </div>
    <button class="copy" type="button" id="{idn}-btn" data-target="{idn}-code">Copy code</button>
  </header>
  <p class="desc">{desc}</p>
  <p class="stats">{stats}</p>
  <div class="codewrap"><pre><code id="{idn}-code">{html.escape(code)}</code></pre></div>
</section>'''


STYLE = """<style>
/* layout: one narrow column of script cards, code scrolls inside its own box */
:root {
  --bg: #f4f6f8; --surface: #ffffff; --fg: #17202a; --muted: #5a6776; --line: #d9e0e7;
  --accent: #0f7b6c; --accent-fg: #ffffff; --warn: #9a5b00; --code-bg: #0f1720; --code-fg: #d7e2ec;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0d1218; --surface: #141b23; --fg: #e3e9ef; --muted: #93a1b0; --line: #243040;
  --accent: #3cc2ad; --accent-fg: #06221d; --warn: #e7a94a; --code-bg: #0a0f14; --code-fg: #d7e2ec; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0d1218; --surface: #141b23; --fg: #e3e9ef; --muted: #93a1b0; --line: #243040;
  --accent: #3cc2ad; --accent-fg: #06221d; --warn: #e7a94a; --code-bg: #0a0f14; --code-fg: #d7e2ec; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--sans); font-size: 16px; line-height: 1.55;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 32px 48px; }
main { max-width: 860px; margin: 0 auto; display: grid; gap: 28px; }
h1 { font-size: 1.75rem; margin: 0; text-wrap: balance; }
.lede { color: var(--muted); margin: 6px 0 0; max-width: 65ch; }
.howto { margin: 0; padding-left: 1.2em; color: var(--muted); display: grid; gap: 4px; }
.script { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 20px; display: grid; gap: 10px; min-width: 0; }
.script-head { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-start; justify-content: space-between; }
.titles { min-width: 0; }
h2 { font-size: 1.2rem; margin: 0; }
.setup { margin: 6px 0 0; display: flex; flex-wrap: wrap; gap: 8px; }
.chip, .badge { font-family: var(--mono); font-size: 0.8rem; letter-spacing: 0.02em; border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px; color: var(--muted); }
.badge.ok { color: var(--accent); border-color: var(--accent); }
.badge.warn { color: var(--warn); border-color: var(--warn); }
.desc { margin: 0; max-width: 65ch; }
.stats { margin: 0; color: var(--muted); font-size: 0.9rem; font-variant-numeric: tabular-nums; }
.copy { font: 600 0.95rem var(--sans); background: var(--accent); color: var(--accent-fg); border: 0; border-radius: 8px; padding: 10px 18px; cursor: pointer; min-width: 140px; }
.copy:focus-visible { outline: 3px solid var(--fg); outline-offset: 2px; }
.codewrap { overflow: auto; max-height: 420px; background: var(--code-bg); border-radius: 8px; min-width: 0; }
pre { margin: 0; padding: 14px 16px; }
code { font-family: var(--mono); font-size: 0.8rem; color: var(--code-fg); white-space: pre; }
.note { color: var(--muted); font-size: 0.9rem; margin: 0; max-width: 65ch; }
</style>"""

SCRIPT = """<script>
document.querySelectorAll(".copy").forEach(btn => {
  btn.addEventListener("click", () => {
    const el = document.getElementById(btn.dataset.target);
    const done = () => { btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy code"), 1800); };
    const fallback = () => {
      const r = document.createRange(); r.selectNodeContents(el);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      btn.textContent = "Selected: press Ctrl+C";
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(el.textContent).then(done).catch(fallback);
    } else { fallback(); }
  });
});
</script>"""


def main():
    page = ('<title>PA Lab Pine Scripts</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">\n'
            + STYLE + '\n<main>\n  <header>\n    <h1>PA Lab Pine Scripts</h1>\n'
            '    <p class="lede">The strategies from the lab, ready for TradingView. Press Copy, then paste into the Pine Editor and click Add to chart.</p>\n'
            '  </header>\n  <ol class="howto">\n    <li>Open the symbol shown on the card.</li>\n'
            '    <li>Set the chart timeframe shown on the card.</li>\n'
            '    <li>Pine Editor, paste, Add to chart. Results show in the Strategy Tester tab.</li>\n  </ol>\n'
            + "".join(card(*c) for c in CARDS)
            + '\n  <p class="note">Paper trade before using real money. On MNQ, set commission to about $0.50 per order in the strategy\'s Properties. News dates are built in through December 2027.</p>\n</main>\n'
            + SCRIPT + "\n")
    (T / "scripts_page.html").write_text(page)
    print("wrote", T / "scripts_page.html", len(page))


if __name__ == "__main__":
    main()
