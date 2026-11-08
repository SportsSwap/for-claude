# Decisions, prompt 5 (dashboard)

P5-1. **Inputs.** The builder reads only `<LAB_ROOT>/results/`. `Provenance.path()` refuses any
path outside it or under `data/`; a test spies on every path the build opens.

P5-2. **Provenance.** Every number on screen is created by `Provenance.json/cell/count`, which
records file, row, column, format, value and the text shown in `provenance.json`. Before
anything is written, `verify()` re-reads every value with a second reader on a different code
path (CSV: `csv.DictReader` vs pandas with string dtype; JSON: `json` with Decimal floats;
parquet: `pyarrow` vs pandas) and refuses on any difference in value or text. Counts are a
recorded operation (`count where verdict = false`), recomputed by the second reader.

P5-3. **Unsourced digits.** Every visible string on every page, and every text node in the final
HTML (scripts and styles excluded), must have its digits covered by a recorded text or one of
these fixed labels: chart names `1m 5m 15m 1h 4h`, test horizons `10/20/50 bars`, `95% interval`,
era names `2022` and `2023-24`. The amber card badges (1, 2, 3...) are ordinals and are skipped
by element class `badge-n`. The page counter `N / M` is drawn by script at run time.

P5-4. **Formats.** Dollars `-$23.70`; rates `32.4%`; differences of rates in percentage points
`+0.1 pp` (not "pts", which reads as index points); behaviour moves `+0.03 ATR`. Minus is a
plain hyphen. No em or en dashes anywhere; the build refuses one.

P5-5. **Verdicts.** `true / split / false` map to the badges `survived / split / didn't survive`.
Verdict values are compared case-insensitively because `verdicts.csv` was seen holding both
`false` and `False`.

P5-6. **Layout.** 1920x1080 stage scaled to the window. Findings: chart at x 96-1276, y 330-990;
stats and conclusion at x 1340-1824, y 330-702, so the facecam corner (x 1400-1920, y 712-1080)
stays empty. `check_layout.js` (headless Chromium via Node Playwright; the Python package is not
installed) checks every page at 1920x1080 and 1280x720 for anything off stage, anything in the
corner, text overflow, a wrapped subtitle and page scrolling, screenshots every page at
1920x1080, and `check_layout.py` confirms screenshot count and titles match `pages.json`.

P5-7. **Pending pages.** Funnel and final pages name the files and columns they expect in
`dashboard/pages.py` (`FUNNEL_PAGES`, `FINAL_PAGES`). Until those exist the page is listed in
`pending.json`, not drawn. If prompts 3 and 4 write different names, edit those specs.

P5-8. **Synthetic label.** When `LAB_ROOT` is `synthetic_lab`, every eyebrow carries
"SYNTHETIC DATA DEMO" and the title slide carries a banner saying real files are not yet ingested.
