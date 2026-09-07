// Slides 12-15: valuation, risks, recommendation.
const { C, bg, nav, head, foot, subhead, stat, card, para, table, divider } = require('./lib.js');
const F = require('./model_facts.json');
const d2 = (x)=>"A$"+x.toFixed(2);
const pc = (x,d=1)=>(x*100).toFixed(d)+"%";
const pcs= (x,d=1)=>(x>=0?"+":"")+(x*100).toFixed(d)+"%";

module.exports = function (pres, ctx) {
  const P = () => ++ctx.p;

  divider(pres, 3, "Valuation, risk and recommendation",
    "What the asset is worth, what has to be true for that to hold, and what would tell us first that it is not.",
    ["12  Discounted cash flow", "13  The range and the sensitivities", "14  Risks and mitigants", "15  Recommendation"]);

  // ---------------------------------------------------------------- 12. DCF
  {
    const s = pres.addSlide(); bg(s); nav(s, "Valuation");
    s.addNotes("60 seconds. This is the slide that separates you from teams that ran a standard DCF.\n\n\"Most DCFs end with a perpetuity growing at two and a half percent forever. A mine runs out. On our production profile Pilgangoora consumes 104 of its 334 million mineable tonnes by FY36 and exits at 14.3 million tonnes a year, so about sixteen years remain. We value the terminal period as a sixteen-year annuity.\"\n\nThe number that lands: \"That single choice is worth nine billion dollars. A perpetuity would have given us 19.0 billion of terminal value on an asset that runs out.\"\n\nIf challenged on whether the life is pre or post-expansion: it is POST. We divide remaining ore by the FY36 rate, which already includes P2000. Doubling throughput halves the life and the model captures that.");
    const cy = head(s, "A finite orebody gets an annuity, not a perpetuity",
      "That single choice is worth A$9.0bn of terminal value. It is the difference between valuing a mine and valuing a company that never runs out of rock.");
    // left column: the cost of capital build
    const cols = [{ t: "Input", w: 2.60 }, { t: "Value", w: 1.05, align: "center" }, { t: "Where it comes from", w: 3.30 },
      { t: "Tag", w: 0.85, align: "center" }];
    const rows = [
      ["Risk-free rate", "5.00%", "Case document, page 6", { t: "Case", c: C.INK, b: true }],
      ["Market risk premium", "6.00%", "Case document, page 6", { t: "Case", c: C.INK, b: true }],
      ["Equity beta", "0.73", "Case document; Yahoo 5-year monthly", { t: "Case", c: C.INK, b: true }],
      ["Cost of equity", "9.38%", "CAPM: 5.00% + 0.73 x 6.00%", { t: "Derived", c: C.MUTE }],
      ["After-tax cost of debt", "4.38%", "6.25% note coupon at the 30% rate", { t: "Estimate", c: C.OCHRE }],
      ["Target gearing", "10%", "Through-cycle; PLS is net cash by A$1.44bn", { t: "Estimate", c: C.OCHRE }],
      [{ t: "WACC", b: true }, { t: "8.88%", b: true, c: C.SPOD }, "90% equity, 10% debt after tax", { t: "Derived", c: C.MUTE }],
    ];
    table(s, C.M, cy, cols, rows, { rowH: 0.28, size: 8.8, boldFirstCol: true,
      rowFill: [null,null,null,null,null,null,C.SPOD_L] });

    const c2 = [{ t: "Base case DCF", w: 3.50 }, { t: "A$m", w: 1.30, align: "right" },
      { t: "Per share", w: 2.05 }, { t: "A$", w: 0.95, align: "right" }];
    table(s, C.M, cy + 2.40, c2, [
      ["PV of explicit forecast, FY27-FY36", "9,661", "Value per share", { t: "6.50", b: true, c: C.SPOD }],
      ["PV of terminal value (annuity)", "9,894", "Last close", "5.48"],
      ["Enterprise value", { t: "19,581", b: true }, "Implied upside", { t: "+19.1%", b: true, c: C.SPOD }],
      ["Net cash", "1,437", "Terminal value as a share of EV", "50.7%"],
    ], { rowH: 0.25, size: 8.8, boldFirstCol: true });

    para(s, C.M, cy + 3.80, 7.80, 1.38, "The orebody runs out. So does the cash flow.",
      "Pilgangoora's mineable base is 334.5Mt: the 446Mt resource at a 75% conversion assumption. Mass pull is 17.5%, from a 1.19% " +
      "reserve grade at 76.5% recovery into a 5.2% concentrate. On the base-case profile the mine consumes 104.0Mt by FY36 and exits " +
      "at 14.3Mt of ore a year, leaving 230.5Mt - about 16.1 years.",
      { titleColor: C.INK, size: 9.2 });

    // right column: what the terminal-value choice costs
    const bx = C.M + 8.02, by = cy;
    s.addShape("rect", { x: bx, y: by, w: 4.42, h: 5.18, fill: { color: C.OCHRE_L }, line: { color: "E8C9A3", width: 0.75 } });
    s.addText("What that choice costs us", { x: bx + 0.20, y: by + 0.16, w: 4.0, h: 0.32, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 12, bold: true, color: C.OCHRE, valign: "middle" });
    s.addText("A$19.0bn", { x: bx + 0.20, y: by + 0.62, w: 4.0, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 30, bold: true, color: C.FAINT, valign: "middle" });
    s.addText("if we grew the final year's cash flow at 2.5% forever", { x: bx + 0.20, y: by + 1.24, w: 4.0, h: 0.44,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 9.2, color: C.MUTE, valign: "top", lineSpacingMultiple: 1.1 });
    s.addText("A$9.9bn", { x: bx + 0.20, y: by + 1.86, w: 4.0, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 30, bold: true, color: C.OCHRE, valign: "middle" });
    s.addText("as a 16-year annuity over the ore that is actually left - what we use", { x: bx + 0.20, y: by + 2.48, w: 4.0, h: 0.50,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 9.2, bold: true, color: C.OCHRE, valign: "top", lineSpacingMultiple: 1.1 });
    s.addShape("rect", { x: bx + 0.20, y: by + 3.08, w: 4.0, h: 0.012, fill: { color: "E0BC94" } });
    s.addText("Why it matters here more than usual", { x: bx + 0.20, y: by + 3.24, w: 4.0, h: 0.30, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 10.5, bold: true, color: C.OCHRE, valign: "middle" });
    s.addText("P2000 roughly doubles the mining rate. Doubling throughput without restating reserves halves the mine life, so an " +
      "expansion that looks purely additive on volume is partly just faster depletion. A growing perpetuity hides that entirely. " +
      "The annuity forces us to pay for it.\n\nTerminal value is 50.7% of enterprise value on our approach. On a perpetuity it would " +
      "have been about 68%, with most of the answer resting on an assumption no orebody can honour.",
      { x: bx + 0.20, y: by + 3.58, w: 4.02, h: 1.48, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, color: C.TXT, valign: "top", lineSpacingMultiple: 1.1 });

    foot(s, "Source: team valuation model, Assumptions and DCF sheets. Discounting uses a mid-year convention. The 75% resource-to-reserve conversion is a key judgement: the 214Mt Ore Reserve alone, last stated in August 2023 and not restated since the June 2025 resource upgrade, would not support the modelled expansion.", P());
  }

  // ---------------------------------------------------------------- 13. RANGE
  {
    const s = pres.addSlide(); bg(s); nav(s, "Valuation");
    const cy = head(s, "The range, and what has to be true",
      "Base A$6.53, bear A$2.30, bull A$8.96. Our own Monte Carlo puts the odds of being right at 47%, so we build the position rather than take it in one.");

    // --- football field, laid out like a research-desk valuation summary
    const fx = C.M, fy = cy + 0.02;
    const LOW = 1.2, HIGH = 12.2;
    const colM = 2.55, colBar = 4.95, colW = 0.72, colP = 0.78, colC = 3.36;
    const bx0 = fx + colM, sx = (v) => bx0 + (v - LOW) / (HIGH - LOW) * colBar;
    let hy = fy;
    [["Methodology", fx, colM, "left"], ["", bx0, colBar, "left"],
     ["Weight", fx + colM + colBar, colW, "center"], ["Value", fx + colM + colBar + colW, colP, "right"],
     ["Basis", fx + colM + colBar + colW + colP + 0.14, colC, "left"]].forEach((h) => {
      s.addText(h[0], { x: h[1], y: hy, w: h[2], h: 0.26, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, bold: true, color: C.INK, align: h[3], valign: "middle" });
    });
    s.addShape("rect", { x: fx, y: hy + 0.26, w: 12.44, h: 0.018, fill: { color: C.INK } });
    hy += 0.36;
    const METH = [
      ["DCF, base case",          F.vps_base, F.vps_base, "60%", C.S2,
       "WACC 8.88% from the case's prescribed inputs; terminal value an annuity over remaining ore"],
      ["DCF, bear to bull",       F.vps_bear, F.vps_bull, "-",   C.S1,
       "Every bad outcome at once against every good one. Shown to frame asymmetry"],
      ["Monte Carlo, P25 to P75", 3.13,       7.65,       "-",   C.S4,
       "20,000 trials randomising price, cost, WACC, reserve conversion and both growth decisions"],
      ["Trading comparables",     F.comps_lo, F.comps_hi, "40%", C.S2,
       "8.0x to 11.0x FY27E EBITDA against a diversified peer median near 7.8x"],
      ["Precedent transactions",  F.vps_base, 8.27,       "-",   C.MUTE,
       "Reference only: we found no consistent transaction multiple"],
      ["Broker targets",          2.50,       6.83,       "-",   C.MUTE,
       "Full individual spread across 17-20 analysts. Our target sits inside it"],
      ["52-week traded range",    1.91,       6.81,       "-",   C.FAINT,
       "Where the market has paid"],
    ];
    const barTop = hy + 0.04, barBot = hy + METH.length * 0.42 - 0.06;
    const MARKS = [[5.48, "Last close 5.48", C.CRIMSON, -1.26], [F.target, "Target " + F.target.toFixed(2), C.INK, 0.05]];
    // drawn before the rows so the value labels paint over them, not the other way round
    MARKS.forEach((mk) => s.addShape("rect", { x: sx(mk[0]) - 0.008, y: barTop, w: 0.016,
      h: barBot - barTop, fill: { color: mk[2] } }));
    METH.forEach((m, i) => {
      const y = hy + i * 0.42;
      if (i % 2 === 1) s.addShape("rect", { x: fx, y: y - 0.02, w: 12.44, h: 0.40, fill: { color: C.MIST2 } });
      s.addText(m[0], { x: fx, y, w: colM - 0.10, h: 0.36, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.8, bold: true, color: C.TXT, valign: "middle" });
      const pt = m[1] === m[2];
      const w  = pt ? 0.10 : Math.max(0.10, sx(m[2]) - sx(m[1]));
      s.addShape("roundRect", { x: sx(m[1]) - (pt ? 0.05 : 0), y: y + 0.09, w, h: 0.18,
        rectRadius: 0.04, fill: { color: m[4] } });
      let lx = sx(m[1]) - 0.60;
      MARKS.forEach((mk) => {                       // keep the value clear of the reference lines
        const mx = sx(mk[0]);
        if (mx > lx - 0.04 && mx < lx + 0.57) lx = mx - 0.62;
      });
      s.addText(m[1].toFixed(2), { x: lx, y, w: 0.53, h: 0.36, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 7.4, color: C.MUTE, align: "right", valign: "middle" });
      if (!pt) s.addText(m[2].toFixed(2), { x: sx(m[2]) + 0.05, y, w: 0.53, h: 0.36, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 7.4, color: C.MUTE, align: "left", valign: "middle" });
      s.addText(m[3], { x: fx + colM + colBar, y, w: colW, h: 0.36, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.6, bold: m[3] !== "-", color: m[3] === "-" ? C.FAINT : C.INK,
        align: "center", valign: "middle" });
      s.addText(pt ? d2(m[1]) : d2((m[1] + m[2]) / 2), { x: fx + colM + colBar + colW, y, w: colP, h: 0.36,
        isTextBox: true, margin: 0, fontFace: C.B, fontSize: 8.8, bold: true, color: C.INK,
        align: "right", valign: "middle" });
      s.addText(m[5], { x: fx + colM + colBar + colW + colP + 0.14, y, w: colC, h: 0.36, isTextBox: true,
        margin: 0, fontFace: C.B, fontSize: 7.3, color: C.MUTE, valign: "middle", lineSpacingMultiple: 1.0 });
    });
    MARKS.forEach((mk) => {
      s.addText(mk[1], { x: sx(mk[0]) + mk[3], y: barBot + 0.01, w: 1.22, h: 0.22, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 7.8, bold: true, color: mk[2], align: mk[3] < 0 ? "right" : "left", valign: "middle" });
    });

    // --- sensitivity grid and the two things a reader should take from it
    const gy = hy + METH.length * 0.42 + 0.22;
    subhead(s, C.M, gy, 6.35, "Base-case value per share against realised price and unit cost (A$)", { size: 10 });
    const pf = [-0.20, -0.10, 0, 0.10, 0.20], cf = [-0.10, -0.05, 0, 0.05, 0.10], SH = 3220;
    const gx = C.M + 1.10, cw = 1.05, rh = 0.205;
    pf.forEach((p3, i) => {
      s.addShape("rect", { x: gx + i * cw, y: gy + 0.44, w: cw, h: rh, fill: { color: C.INK } });
      s.addText((p3 >= 0 ? "+" : "") + (p3 * 100).toFixed(0) + "%", { x: gx + i * cw, y: gy + 0.44, w: cw, h: rh,
        isTextBox: true, margin: 0, fontFace: C.B, fontSize: 7.8, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    });
    s.addText("Unit cost", { x: C.M, y: gy + 0.44, w: 1.08, h: rh, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 7.4, bold: true, color: C.MUTE, align: "right", valign: "middle" });
    cf.forEach((c3, ri) => {
      const y = gy + 0.44 + (ri + 1) * rh;
      s.addShape("rect", { x: C.M, y, w: 1.08, h: rh, fill: { color: C.INK } });
      s.addText((c3 >= 0 ? "+" : "") + (c3 * 100).toFixed(0) + "%", { x: C.M, y, w: 1.08, h: rh, isTextBox: true,
        margin: 0, fontFace: C.B, fontSize: 7.8, bold: true, color: C.WHITE, align: "center", valign: "middle" });
      pf.forEach((p3, ci) => {
        const v = F.vps_base + (F.k_price * p3 - F.k_cost * c3) / SH;
        const on = ri === 2 && ci === 2;
        s.addShape("rect", { x: gx + ci * cw, y, w: cw, h: rh,
          fill: { color: on ? C.SPOD_L : (v > 5.48 ? C.MIST2 : C.CRIM_L) }, line: { color: C.RULE, width: 0.5 } });
        s.addText(v.toFixed(2), { x: gx + ci * cw, y, w: cw, h: rh, isTextBox: true, margin: 0,
          fontFace: C.B, fontSize: 8, bold: on, color: on ? C.SPOD : (v > 5.48 ? C.TXT : C.CRIMSON),
          align: "center", valign: "middle" });
      });
    });
    para(s, C.M + 6.60, gy, 5.84, 1.72, "What has to be true, and where it breaks",
      "Read across for the commodity call and down for operational delivery. Shaded cells sit below today's price. " +
      "PLS needs realised prices no worse than about 8% below our base case to justify A$5.48, and that base case is " +
      "already 11% below spot-implied realisation.\n\n" +
      "Against that: reward to risk is 1.09x, and 20,000 trials put the probability of intrinsic value beating " +
      "today's price at 46.6%. Expected value clears the hurdle on a median that does not, so we build the " +
      "position over several prints rather than take it in one.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 8.8 });
    foot(s, "Source: team valuation model, Football Field and Sensitivity sheets; Monte Carlo per appendix E16. Broker range is the full individual analyst spread; vendor averages cluster A$4.50-5.70.", P());
  }

  // ---------------------------------------------------------------- 14. RISKS
  {
    const s = pres.addSlide(); bg(s); nav(s, "Risks");
    s.addNotes("45 seconds. Do not read twelve rows. Take the top two.\n\n\"The risk that decides this position is a sustained price relapse. If spodumene averages 20% below our base case, the target falls to about three eighty-six and we are wrong. We have not hedged that language.\"\n\nThen the short-interest point, which most teams will miss entirely: \"PLS went from the most shorted stock on the ASX at 20% of shares to about 6.8%. A material part of the tripling was covering, and that buyer cannot come back. Our target rests on FY27 earnings and the growth option, not on another squeeze.\"");
    const cy = head(s, "What would break this, and what would tell us first",
      "Every risk below has a named early-warning indicator, because a risk you cannot observe is not one you can manage.");
    const cols = [{ t: "Risk", w: 2.75 }, { t: "Why it bites", w: 3.85 }, { t: "Mitigant", w: 3.10 },
      { t: "Our early warning", w: 2.74 }];
    const rows = [
      [{ t: "Price relapse", b: true }, "Restart supply from Bald Hill, Finniss and Jianxiawo overwhelms demand and spodumene revisits the 2025 trough. Wood Mackenzie's base case says surplus until the early 2030s.",
       "PLS earns cash where roughly a quarter of world supply does not, and holds A$2.29bn to wait.",
       "Monthly SpodIX prints and Chinese carbonate inventory days."],
      [{ t: "The re-rating is spent", b: true }, "Short interest fell from about 20% of shares - the most shorted stock on the ASX - to about 6.8%. Much of the tripling was covering, and that buyer is now gone.",
       "We do not underwrite another squeeze. The target rests on earnings and the growth option, not on flow.",
       "ASIC short position reports; a re-build above 10% would be a warning."],
      [{ t: "P2000 slips or is shelved", b: true }, "The DFS is due in the December 2026 quarter and no FID has been taken. Our base case assumes first ore in mid-2029.",
       "A$175m of pre-FID capital is already committed and the balance sheet can fund the A$1.2bn build.",
       "The December quarter study outcome, and the FID decision itself."],
      [{ t: "Single asset, single commodity", b: true }, "One orebody in one jurisdiction, and one price series that has moved by a factor of three in two years.",
       "Colina adds a second jurisdiction from the 2030s. It is risked at 40% in our NAV and contributes nothing before FY32.",
       "Any operational interruption at Pilgangoora; Pilbara weather and cyclone season."],
      [{ t: "The carbon premium never arrives", b: true }, "Our level-one thesis assumes carbon intensity becomes a condition of sale. It may stay a preference that nobody pays for.",
       "We have already priced this at zero inside the target and risked it at 25% outside it.",
       "The first PLS contract with a disclosed carbon-linked term, or an EU declaration enforcement date."],
      [{ t: "Reserve conversion disappoints", b: true }, "Our terminal value assumes 75% of the 446Mt resource converts. The Ore Reserve has not been restated since August 2023.",
       "The 2025 resource upgrade lifted contained lithium 23%, which supports rather than undermines conversion.",
       "The next Ore Reserve statement. A conversion below 60% would cut the target by roughly A$0.40."],
    ];
    table(s, C.M, cy, cols, rows, { rowH: 0.61, size: 8.3 });
    para(s, C.M, cy + 3.95, 12.44, 0.74, null,
      "The risk we are most exposed to is the first one, and we have not hedged the language on it. If spodumene averages 20% below our base case across the forecast, the target falls to about A$3.86 and this recommendation is wrong.",
      { fill: C.OCHRE_L, line: "E8C9A3", size: 9.4 });
    foot(s, "Sources: ASIC short position reports via shortman.com.au (latest retrievable data 26 May 2026); Wood Mackenzie Lithium Energy Transition Outlook, 3 March 2026; PLS disclosures; team valuation model.", P());
  }

  // ---------------------------------------------------------------- 15. RECOMMENDATION
  {
    const s = pres.addSlide(); bg(s, true);
    s.addNotes("45 seconds. Close hard and stop talking.\n\n\"Buy. Six dollars twelve, 12.0% upside, 13.6% total return against a 5.90% benchmark. The fund needs two points of outperformance and this gives seven point seven.\"\n\n\"Two thirds of that upside is shared value the market is not paying for. And a further thirty-two cents of low-carbon downstream value sits outside the target entirely, so nothing in this recommendation depends on it.\"\n\nName the nearest catalyst: first lithium phosphate from the mid-stream plant lands THIS QUARTER, and the P2000 study lands in the December quarter. Both are inside the horizon.\n\nThen stop. Let them ask.");
    s.addText("Recommendation", { x: C.M, y: 0.34, w: 8, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 30, bold: true, color: C.WHITE, valign: "middle" });
    s.addShape("rect", { x: C.M, y: 1.10, w: 3.55, h: 2.20, fill: { color: C.SPOD } });
    s.addText("BUY", { x: C.M, y: 1.22, w: 3.55, h: 0.80, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 42, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("A$6.14", { x: C.M, y: 2.02, w: 3.55, h: 0.52, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 26, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("12-month target   |   +12.0%\nTotal return 13.6% vs benchmark 5.90%", { x: C.M, y: 2.56, w: 3.55, h: 0.62,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 10, color: "DDF0EB", align: "center", valign: "top", lineSpacingMultiple: 1.15 });

    const pts = [
      ["The mandate is met", "A 13.6% expected total return against a benchmark that returned 5.90%, for outperformance of 7.7%. The fund needs 2%."],
      ["The case is the shared value", "A$0.43 of the A$0.66 of upside - 66% - comes from ESG-linked operating decisions the market is not paying for."],
      ["The option is free", "A further A$0.32 per share of low-carbon downstream value sits outside the target entirely. Nothing in this recommendation needs it to land."],
    ];
    pts.forEach((p2, i) => {
      const y = 1.10 + i * 0.75;
      s.addText(p2[0], { x: C.M + 3.85, y, w: 3.15, h: 0.30, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 11.5, bold: true, color: C.SPOD, valign: "middle" });
      s.addText(p2[1], { x: C.M + 3.85, y: y + 0.29, w: 8.55, h: 0.44, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, color: "C9D8E6", valign: "top", lineSpacingMultiple: 1.08 });
    });

    s.addText("Catalysts inside the investment horizon", { x: C.M, y: 3.58, w: 8, h: 0.32, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 12, bold: true, color: C.WHITE, valign: "middle" });
    const cat = [
      ["Sep-qtr 2026", "First lithium phosphate from the mid-stream plant", "Turns the level-one thesis from a plan into a product"],
      ["Oct 2026", "September-quarter activities report", "The first full quarter at the post-restart run rate, and the price print after the August fall"],
      ["Dec-qtr 2026", "P2000 definitive feasibility study", "The single largest value event in the pipeline: A$2.6bn of NPV at PFS level"],
      ["Late 2026", "P2000 final investment decision", "A$175m of pre-FID capital is already spent; this converts the option"],
      ["FY27", "Ngungaju at steady state", "Guidance implies 1,030-1,100kt, a 17-25% volume step-up"],
    ];
    cat.forEach((c2, i) => {
      const y = 3.98 + i * 0.44;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 0.40, fill: { color: i % 2 ? "16304C" : "1B3A5A" } });
      s.addText(c2[0], { x: C.M + 0.16, y, w: 1.55, h: 0.40, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, bold: true, color: C.SPOD, valign: "middle" });
      s.addText(c2[1], { x: C.M + 1.80, y, w: 4.45, h: 0.40, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, bold: true, color: C.WHITE, valign: "middle" });
      s.addText(c2[2], { x: C.M + 6.35, y, w: 5.95, h: 0.40, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, color: "AFC3D4", valign: "middle" });
    });
    s.addText("We would revisit this recommendation if spodumene averages more than 20% below our base case, if the P2000 study is deferred beyond the December 2026 quarter, or if short interest rebuilds above 10% of shares on issue.",
      { x: C.M, y: 6.30, w: 12.44, h: 0.52, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, italic: true, color: "8FA8BE", valign: "top", lineSpacingMultiple: 1.1 });
    foot(s, "", P());
  }
};
