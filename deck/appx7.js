// Appendix E: valuation.
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage, statement } = L;
const F = require('./model_facts.json');
const S = require('./scenarios.json');
const n0 = (v) => (v === null || v === undefined) ? "" : Math.round(v).toLocaleString("en-US");

module.exports = function (pres, ctx) {
  let e = 0;
  const pgE = (title, take, body, src) => {
    const n = ++e; const { s, cy } = apage(pres, "E" + n + "  Valuation", title, take);
    body(s, cy); foot(s, src, "E" + n);
  };
  const YRS = S.fcst.map((y) => y.replace(/F$/, ""));

  // series table across the ten forecast years
  const series = (s, x, y, label, rows, opts = {}) => {
    const cols = [{ t: label, w: opts.lw || 3.20 }].concat(YRS.map(() => ({ t: "", w: ((12.44 - (opts.lw || 3.20)) / 10), align: "right" })));
    YRS.forEach((yr, i) => { cols[i + 1].t = yr; });
    return table(s, x, y, cols, rows, { rowH: opts.rowH || 0.28, size: opts.size || 8.2, headSize: 8, boldFirstCol: true, ...opts });
  };

  // ---------------- E1 architecture
  pgE("How the model is built",
      "Nineteen sheets, 1,728 live formulas, zero evaluation errors. One switch repoints the whole thing.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Sheet", w: 2.55 }, { t: "What it does", w: 5.55 }, { t: "Why it is there", w: 4.34 }], [
      ["Assumptions", "Scenario switch, market data, CAPM and WACC build, orebody inputs, operating drivers", "Every driver in the model resolves to a cell here. Nothing downstream is typed"],
      ["Deck", "Production by asset, realised price, unit cost and capex - all three scenarios side by side", "The ACTIVE block uses CHOOSE() against the switch, so one cell repoints the model"],
      ["Revenue Build", "Volume times price by asset, with a freight and timing adjustment calibrated to reported revenue", "FY25A and FY26A tie exactly to reported revenue"],
      ["Income Statement, Balance Sheet, Cash Flow", "FY24A to FY36F, fully articulated and balancing", "The balance check row is nil in every year"],
      ["DCF", "Unlevered FCFF, mid-year discounting, reserve-life annuity terminal value, equity bridge", "The primary valuation"],
      ["Scenario Engine", "A compact FCFF for each of bear, base and bull, computed simultaneously", "So the scenario summary is live rather than a pasted snapshot"],
      ["Sensitivity", "WACC against mine life, and realised price against unit cost, with derived coefficients", "The price and cost coefficients also drive the sensitivity grid in the main deck"],
      ["ESG Value Bridge, Downstream Option", "Shared-value levers converted to A$ per share; the downstream prize sized and risked", "The analytical contribution of this submission"],
      ["SOTP NAV, Trading Comps, Precedents, Football Field", "Cross-checks and the weighted target price", "So the DCF is not marking its own homework"],
      ["Sources", "Every input tagged A, G, M, D, E or C for provenance", "So a reviewer can audit any number back to where it came from"],
    ], { rowH: 0.35, size: 8.4, boldFirstCol: true });
    para(s, C.M, cy + 3.96, 12.44, 1.26, "Colour convention, and how to interrogate it",
      "Blue text is a hardcoded input, black is a formula, green is a link to another sheet, and yellow fill marks the judgements a " +
      "reviewer should challenge first. To stress the model, change Assumptions!C7 to Bear or Bull and every statement, the DCF and the " +
      "target price repoint. To test a single judgement, the yellow cells are the ones that matter: beta, the resource-to-reserve " +
      "conversion, the WACC, and the active price and cost rows.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Source: the submitted workbook, PLS_Valuation_Model_FMAA_2026.xlsx. Formula and error counts are from the LibreOffice recalculation run at build time.");

  // ---------------- E2 price deck
  pgE("The price deck, and why all three cases converge",
      "A trough forces supply out; a spike pulls it in. A perpetuity struck at either extreme is not a forecast, it is an arithmetic error.",
   (s, cy) => {
    s.addChart(pres.ChartType.line, [
      { name: "Bear", labels: YRS, values: S.bear.price },
      { name: "Base", labels: YRS, values: S.base.price },
      { name: "Bull", labels: YRS, values: S.bull.price },
    ], {
      x: C.M, y: cy, w: 7.60, h: 3.05, chartColors: [C.S3, C.S2, C.S1], lineSize: 2.5, lineSmooth: false,
      showTitle: true, title: "Realised price by scenario (US$/t, actual grade)",
      titleFontFace: C.B, titleFontSize: 11, titleColor: C.INK,
      catAxisLabelFontFace: C.B, catAxisLabelFontSize: 8, catAxisLabelColor: C.MUTE,
      valAxisLabelFontFace: C.B, valAxisLabelFontSize: 8.5, valAxisLabelColor: C.MUTE,
      valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" },
      showLegend: true, legendPos: "b", legendFontFace: C.B, legendFontSize: 9,
      valAxisMinVal: 800, valAxisMaxVal: 2800,
    });
    card(s, C.M + 7.84, cy, 4.60, 3.05, "The logic behind each path", [
      "Bear: restart supply overwhelms demand into FY30 and the price reverts toward the 90th-percentile cash cost, where high-cost tonnes leave. Then it grinds back as that supply exits.",
      "Base: prices ease from the June-2026 quarter peak as restart tonnes land, then recover as the surplus narrows, settling near US$1,750/t.",
      "Bull: the 2027-29 deficit called by Fastmarkets, Morgan Stanley and UBS arrives, prices overshoot the incentive level, new supply responds, and the price mean-reverts down to the same anchor.",
      "All three converge because that is what commodity markets do. The scenarios differ on the path and on volumes, not on where the cycle ends.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 8.6 });
    series(s, C.M, cy + 3.22, "US$/t realised", [
      ["Bear", ...S.bear.price], ["Base", ...S.base.price], ["Bull", ...S.bull.price],
    ], { rowH: 0.27 });
    para(s, C.M, cy + 4.47, 12.44, 0.71, null,
      "Anchor points: FY26 actual realised US$1,488/t; June-2026 quarter US$2,107/t; spot SC6 about US$2,038-2,200/t in August 2026; the Australian Government forecast a 2026 average of US$2,236/t. Our base FY27 of US$1,700/t is below all of them.",
      { fill: C.MIST, line: C.RULE, size: 8.8 });
   }, "Source: team valuation model, Deck sheet. Anchors per PLS quarterly reports, Benchmark Mineral Intelligence, S&P Global Platts and the Australian Government Resources and Energy Quarterly, June 2026.");

  // ---------------- E3 production build
  pgE("Production build by asset",
      "FY27 base of 1,065kt is the exact midpoint of company guidance. Everything after that is ours.",
   (s, cy) => {
    let y = cy;
    [["base", "BASE CASE", C.SPOD], ["bear", "BEAR CASE", C.CRIMSON], ["bull", "BULL CASE", C.INK2]].forEach((sc) => {
      s.addText(sc[1], { x: C.M, y, w: 3.0, h: 0.24, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, bold: true, color: sc[2], valign: "top" });
      y += 0.21;
      y = series(s, C.M, y, "kt of concentrate", [
        ["Pilgan plant", ...S[sc[0]].assets.pilgan],
        ["Ngungaju plant", ...S[sc[0]].assets.ngungaju],
        ["P2000 increment", ...S[sc[0]].assets.p2000],
        ["Colina, Brazil", ...S[sc[0]].assets.colina],
        [{ t: "Total", b: true }, ...S[sc[0]].prod.map((v) => ({ t: n0(v), b: true }))],
      ], { rowH: 0.20, headH: 0.24, size: 8 }) + 0.09;
    });
    s.addText([
      { text: "Where these numbers come from.  ", options: { bold: true, color: C.INK } },
      { text: "Pilgan nameplate is about 1.0Mtpa after P1000; it produced 879.5kt in FY26 with Ngungaju idle. Ngungaju is about " +
        "200ktpa and restarted in July 2026. P2000 lifts Pilgangoora capacity above 2.0Mtpa, first ore guided mid-2029, so we show it as " +
        "the increment over the two existing plants. Colina first production in FY32 is our assumption, not a company target - PLS has " +
        "not adopted Latin Resources' original 2026 plan.", options: { color: C.TXT } },
    ], { x: C.M, y: y + 0.04, w: 12.44, h: 0.52, isTextBox: true, margin: 0,
         fontFace: C.B, fontSize: 8.2, valign: "top", lineSpacingMultiple: 1.06 });
   }, "Sources: PLS FY27 guidance of 1,030-1,100kt; P2000 pre-feasibility study; Ngungaju restart announcement; team valuation model, Deck sheet.");

  // ---------------- E4 cost and capex
  pgE("Unit cost and capital expenditure build",
      "FY27 cost and capex both sit at the midpoint of guidance. The bear case does not assume costs run away, because operators cut in a downturn.",
   (s, cy) => {
    let y = cy;
    s.addText("UNIT OPERATING COST, FOB (A$/t)", { x: C.M, y, w: 5.0, h: 0.24, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9.5, bold: true, color: C.INK, valign: "middle" }); y += 0.22;
    y = series(s, C.M, y, "A$/t", [
      ["Bear", ...S.bear.cost], [{ t: "Base", b: true }, ...S.base.cost.map((v) => ({ t: n0(v), b: true }))], ["Bull", ...S.bull.cost],
    ], { rowH: 0.22, headH: 0.26 }) + 0.12;
    s.addText("CAPITAL EXPENDITURE (A$m)", { x: C.M, y, w: 5.0, h: 0.24, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9.5, bold: true, color: C.INK, valign: "middle" }); y += 0.22;
    y = series(s, C.M, y, "A$m", [
      ["Bear", ...S.bear.capex], [{ t: "Base", b: true }, ...S.base.capex.map((v) => ({ t: n0(v), b: true }))], ["Bull", ...S.bull.capex],
    ], { rowH: 0.22, headH: 0.26 }) + 0.12;
    s.addText("EBITDA, MODEL OUTPUT (A$m)", { x: C.M, y, w: 5.0, h: 0.24, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9.5, bold: true, color: C.SPOD, valign: "middle" }); y += 0.22;
    y = series(s, C.M, y, "A$m", [
      ["Bear", ...S.bear.ebitda.map(n0)], [{ t: "Base", b: true }, ...S.base.ebitda.map((v) => ({ t: n0(v), b: true }))], ["Bull", ...S.bull.ebitda.map(n0)],
    ], { rowH: 0.22, headH: 0.26 }) + 0.12;
    para(s, C.M, y, 12.44, 1.36, "Reading the cost rows",
      "FY26 actual was A$569/t against FY27 guidance of A$575-625/t, the step-up attributed to higher-cost Ngungaju tonnes. Base case " +
      "uses the A$600/t midpoint, falling to A$565/t as P2000 volume dilutes fixed costs. Bear costs rise to A$655/t then fall back to " +
      "A$610/t: a miner facing a sustained trough cuts, and letting bear costs drift up forever would have made that case artificially severe.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 8.8 });
   }, "Sources: PLS FY26 results and FY27 guidance (A$575-625/t, capex A$620-685m including A$175m of approved P2000 pre-FID capital); team valuation model.");

  // ---------------- E5-E7 statements
  pgE("Income statement, base case",
      "FY24A to FY36F. FY25A and FY26A tie to reported revenue and reported underlying EBITDA by construction.",
   (s, cy) => {
    statement(s, C.M, cy, [
      ["Revenue", "Revenue", "n", { b: true }],
      ["Operating costs, FOB", "Operating costs (FOB)", "n", { ind: true }],
      ["State royalties", "State royalties", "n", { ind: true }],
      ["Corporate, admin and reconciliation", "Corporate, administration and cost-definition reconciliation", "n", { ind: true }],
      ["EBITDA", "EBITDA", "n", { b: true, hi: true }],
      ["EBITDA margin", "EBITDA margin", "pct", { ind: true }],
      ["Depreciation and amortisation", "Depreciation and amortisation", "n", { ind: true }],
      ["EBIT", "EBIT", "n", { b: true }],
      ["Net interest", "Net interest income / (expense)", "n", { ind: true }],
      ["Profit before tax", "Profit before tax", "n"],
      ["Income tax expense", "Income tax expense", "n", { ind: true }],
      ["NPAT", "NPAT", "n", { b: true, hi: true }],
      ["EPS (A$)", "EPS (A$)", "cur2", { ind: true }],
      ["DPS (A$)", "DPS (A$)", "cur2", { ind: true }],
    ], { src: "is", rowH: 0.245 });
    para(s, C.M, cy + 3.90, 12.44, 1.12, "The historical reconciliation line, explained",
      "Our cost build is deliberately simple: volume times unit cost, plus a royalty, plus corporate overhead. Reported underlying EBITDA " +
      "reflects a more granular cost definition than that. Rather than tune our inputs until the two happened to agree, we let the " +
      "corporate line absorb the difference in FY24A to FY26A, and labelled it as a reconciliation. The result is that the historical " +
      "columns tie exactly to reported figures and the forecast columns are driven purely by the deck, with no hidden plug.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Source: team valuation model, Income Statement sheet, base case. FY24A figures are estimates and are flagged as such in the workbook's source register.");

  pgE("Balance sheet, base case",
      "Opens on the reported FY26 cash position and rolls forward. The balance check is nil in every year.",
   (s, cy) => {
    statement(s, C.M, cy, [
      ["Cash and equivalents", "Cash and cash equivalents", "n"],
      ["Net working capital", "Net working capital", "n"],
      ["Property, plant and equipment", "Property, plant and equipment (net)", "n"],
      ["Total assets", "Total assets", "n", { b: true }],
      ["Borrowings", "Borrowings", "n"],
      ["Shareholders' equity", "Shareholders' equity", "n"],
      ["Total liabilities and equity", "Total liabilities and equity", "n", { b: true }],
      ["Balance check", "Balance check (must be nil)", "n", { b: true, hi: true }],
      ["Net cash / (net debt)", "Net cash / (net debt)", "n"],
      ["Return on equity", "Return on equity", "pct", { ind: true }],
      ["Return on invested capital", "Return on invested capital (after tax)", "pct", { ind: true }],
    ], { src: "bs", rowH: 0.26 });
    para(s, C.M, cy + 3.30, 6.10, 1.62, "What we could not verify",
      "The FY26 opening property, plant and equipment balance of A$3,200m is our estimate. We could not retrieve the reported net book " +
      "value, and the ASX announcements platform was unreachable from our environment.\n\n" +
      "It matters because depreciation is struck as 11.5% of opening PP&E, so the estimate flows into EBIT and into tax. It does not " +
      "affect the DCF, which is built on unlevered free cash flow where depreciation is added back.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
    para(s, C.M + 6.34, cy + 3.30, 6.10, 1.62, "The cash build, and why we raised the payout",
      "On the base case PLS accumulates cash rapidly once the P2000 build is funded. Left at a 30% payout the balance sheet would carry " +
      "an implausible cash pile by the mid-2030s.\n\n" +
      "We therefore step the payout ratio to 50% from FY30. This has no effect on the DCF, which values the firm before financing " +
      "decisions, but it keeps the balance sheet and the earnings-per-share path realistic. The company's stated policy is 20-30% of " +
      "free cash flow with excess available for buybacks or growth.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9 });
   }, "Source: team valuation model, Balance Sheet sheet. FY24A and FY25A balance sheets are not modelled; the DCF runs off the FY26A closing position.");

  pgE("Cash flow, base case",
      "Free cash flow to the firm is the line the valuation actually uses. Everything below it is a financing choice.",
   (s, cy) => {
    statement(s, C.M, cy, [
      ["EBITDA", "EBITDA", "n", { b: true }],
      ["Net interest received / (paid)", "Net interest received / (paid)", "n", { ind: true }],
      ["Tax paid", "Tax paid", "n", { ind: true }],
      ["Movement in working capital", "Movement in net working capital", "n", { ind: true }],
      ["Operating cash flow", "Operating cash flow", "n", { b: true }],
      ["Capital expenditure", "Capital expenditure", "n", { ind: true }],
      ["Free cash flow to the firm", "Free cash flow to the firm (pre-financing)", "n", { b: true, hi: true }],
      ["Dividends paid", "Dividends paid", "n", { ind: true }],
      ["Net movement in cash", "Net movement in cash", "n", { b: true }],
      ["Closing cash", "Closing cash", "n", { b: true }],
    ], { src: "cf", rowH: 0.27 });
    para(s, C.M, cy + 3.20, 12.44, 1.42, "Two simplifications we are declaring rather than burying",
      "First, tax paid is shown equal to the accrued charge. In practice PLS carries franking credits and prior-year tax losses that " +
      "would defer cash tax, so our near-term operating cash flow is conservative.\n\n" +
      "Second, the base case assumes the US$600m senior notes are refinanced at maturity rather than repaid, so no debt repayment appears " +
      "in the financing lines. Neither simplification affects the DCF: free cash flow to the firm is struck before financing, and the " +
      "equity bridge adds the FY26 net cash position rather than a projected one.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Source: team valuation model, Cash Flow sheet, base case.");

  // ---------------- E8 FCFF and DCF
  pgE("Free cash flow and the discounted cash flow",
      "Unlevered FCFF discounted at 8.88% on a mid-year convention, with a terminal value that is an annuity over the ore that is left.",
   (s, cy) => {
    statement(s, C.M, cy, [
      ["EBIT", "EBIT", "n"],
      ["NOPAT", "NOPAT", "n", { b: true }],
      ["Add back D&A", "Add back: D&A", "n", { ind: true }],
      ["Less capital expenditure", "Less: capital expenditure", "n", { ind: true }],
      ["Less increase in working capital", "Less: increase in net working capital", "n", { ind: true }],
      ["Free cash flow to the firm", "Free cash flow to the firm", "n", { b: true, hi: true }],
      ["Discount factor", "Discount factor", "x", { ind: true }],
      ["Present value of FCFF", "PV of FCFF", "n", { b: true }],
    ], { src: "dcf", rowH: 0.275 });
    const rows = [
      ["Sum of PV of explicit forecast FCFF, FY27-FY36", n0(F.ev - F.tv_annuity)],
      ["PV of terminal value (16.1-year annuity)", n0(F.tv_annuity)],
      [{ t: "Enterprise value", b: true }, { t: n0(F.ev), b: true }],
      ["Add net cash", n0(F.netcash)],
      [{ t: "Equity value", b: true }, { t: n0(F.ev + F.netcash), b: true }],
      ["Shares on issue (m)", "3,220"],
      [{ t: "Value per share (A$)", b: true, c: C.SPOD }, { t: F.vps_base.toFixed(2), b: true, c: C.SPOD }],
      ["Last close (A$)", "5.48"],
      [{ t: "Implied upside", b: true, c: C.SPOD }, { t: "+" + (F.ups_base * 100).toFixed(1) + "%", b: true, c: C.SPOD }],
      ["Terminal value as a share of EV", (F.tv_pct * 100).toFixed(1) + "%"],
    ];
    table(s, C.M, cy + 2.58, [{ t: "Base case bridge", w: 4.95 }, { t: "A$m unless stated", w: 2.05, align: "right" }], rows,
      { rowH: 0.222, size: 8.6, boldFirstCol: true });
    para(s, C.M + 7.30, cy + 2.58, 5.14, 2.50, "Why terminal value is only half of enterprise value",
      "On a growing perpetuity, the terminal period would have been A$19.0bn and roughly 68% of enterprise value - meaning most of the " +
      "answer would rest on an assumption about the year 2037 onward.\n\n" +
      "The reserve-life annuity brings it to A$9.9bn and 50.7%. That is still a lot, and it is the right treatment for a long-life mining " +
      "asset: half the value is in the ten years we forecast explicitly, half in the sixteen years of ore that follow.\n\n" +
      "It also means the model is less sensitive to the terminal assumption than a conventional DCF, which is a feature rather than a " +
      "coincidence. The sensitivity table at E11 shows the whole surface.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
   }, "Source: team valuation model, DCF sheet. Discounting uses a mid-year convention; the stub from the 5 September 2026 valuation date to 30 June 2027 is not discounted separately and the effect is immaterial at this WACC.");
};
