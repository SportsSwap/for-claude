// Slides 12-15: valuation, risks, recommendation.
const { C, bg, nav, head, foot, stat, card, para, table, divider } = require('./lib.js');
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
    s.addNotes("60 seconds. Lead with the bear case, not the base case. It builds credibility.\n\n\"Our bear case is two dollars thirty. That assumes prices revert to marginal cost, P2000 is never sanctioned, Colina never proceeds and volumes stay flat for a decade, all at once. Even then it is 20% above the one ninety-one the market actually printed in the last trough, when PLS had a billion less cash and was loss-making.\"\n\nThen admit the weakness: reward to risk is 1.09x. Say it plainly. \"This is not a lopsided bet and we will not present it as one. What justifies the position is the expected return against the mandate.\"\n\nClose on the grid: we need prices not to FALL by a fifth. We do not need them to rise.");
    const cy = head(s, "The range, and what has to be true",
      "Base A$6.53, bear A$2.30, bull A$8.96. The bear sits 20% above the price the market actually paid at the bottom of the last cycle.");
    // football field
    const fx = C.M, fy = cy + 0.06, fw = 7.40, fh = 2.70;
    s.addShape("rect", { x: fx, y: fy, w: fw, h: fh, fill: { color: C.MIST2 }, line: { color: C.RULE, width: 0.75 } });
    s.addText("Valuation range by method (A$ per share)", { x: fx + 0.18, y: fy + 0.10, w: 5.5, h: 0.28,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 11, bold: true, color: C.INK, valign: "middle" });
    const lo = 1.5, hi = 9.5, plotX = fx + 2.62, plotW = 4.50;
    const sx = (v) => plotX + (v - lo) / (hi - lo) * plotW;
    const bars = [
      ["DCF, base case", 6.50, 6.50, C.SPOD, "60%"],
      ["DCF, bear to bull", 2.26, 8.93, C.INK2, "-"],
      ["Trading comparables", 4.76, 6.37, C.INK2, "40%"],
      ["Broker targets", 2.50, 6.83, C.FAINT, "-"],
      ["52-week traded range", 1.91, 6.81, C.FAINT, "-"],
    ];
    bars.forEach((b, i) => {
      const y = fy + 0.52 + i * 0.40;
      s.addText(b[0], { x: fx + 0.18, y, w: 2.36, h: 0.30, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.6, color: C.TXT, valign: "middle" });
      const pt = b[1] === b[2];
      const w = pt ? 0.09 : sx(b[2]) - sx(b[1]);
      s.addShape("rect", { x: sx(b[1]) - (pt ? 0.045 : 0), y: y + 0.06, w, h: 0.19, fill: { color: b[3] } });
      s.addText(pt ? b[1].toFixed(2) : b[1].toFixed(2) + " - " + b[2].toFixed(2),
        { x: sx(b[2]) + (pt ? 0.16 : 0.06), y, w: 1.30, h: 0.30, isTextBox: true, margin: 0,
          fontFace: C.B, fontSize: 8, color: C.MUTE, valign: "middle" });
      s.addText(b[4], { x: fx + fw - 0.52, y, w: 0.40, h: 0.30, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8, bold: true, color: C.MUTE, align: "right", valign: "middle" });
    });
    // last close and target markers
    [[5.48, "Last close", C.CRIMSON], [6.14, "Target", C.INK]].forEach((m, i) => {
      s.addShape("rect", { x: sx(m[0]) - 0.01, y: fy + 0.48, w: 0.022, h: 2.02, fill: { color: m[2] } });
      s.addText(m[1] + "  " + m[0].toFixed(2), { x: sx(m[0]) - 0.72 + i * 1.44, y: fy + 2.44, w: 1.44, h: 0.22,
        isTextBox: true, margin: 0, fontFace: C.B, fontSize: 8, bold: true, color: m[2], align: "center", valign: "middle" });
    });

    card(s, C.M + 7.62, cy + 0.06, 4.82, 1.52, "What the bear case actually assumes", [
      "Prices revert to marginal cost, P2000 is never sanctioned, Colina never proceeds and volumes stay flat for a decade - all at once.",
      "Even then A$2.30 is 20% above the A$1.91 printed in the last trough, when PLS held A$974m of cash and was loss-making rather than A$2.29bn and earning A$526m.",
    ], { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 8.8 });
    card(s, C.M + 7.62, cy + 1.66, 4.82, 1.10, "And the honest weakness", [
      "Reward to risk is 1.09x: +64% to bull against -58% to bear. Not a lopsided bet, and we will not present it as one.",
      "What justifies the position is the expected return against the mandate, not the shape of the distribution.",
    ], { fill: C.MIST2, line: C.RULE, titleColor: C.INK, size: 8.8 });

    // sensitivity grid
    const gy = cy + 2.92;
    s.addText("Base-case value per share against realised price and unit cost (A$)", { x: C.M, y: gy, w: 7.0, h: 0.26,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 10, bold: true, color: C.INK, valign: "middle" });
    const pcols = ["-20%","-10%","Base","+10%","+20%"];
    const crows = ["-10%","-5%","Base","+5%","+10%"];
    // generated from the model's own price and cost coefficients, so it cannot drift from the workbook
    const pf = [-0.20,-0.10,0,0.10,0.20], cf = [-0.10,-0.05,0,0.05,0.10], SH = 3220;
    const grid = cf.map((c3) => pf.map((p3) => F.vps_base + (F.k_price*p3 - F.k_cost*c3)/SH));
    const gx = C.M + 1.15, cw = 0.92, rh = 0.27;
    pcols.forEach((h,i)=>{ s.addShape("rect",{x:gx+i*cw,y:gy+0.30,w:cw,h:rh,fill:{color:C.INK}});
      s.addText(h,{x:gx+i*cw,y:gy+0.30,w:cw,h:rh,isTextBox:true,margin:0,fontFace:C.B,fontSize:8,bold:true,color:C.WHITE,align:"center",valign:"middle"}); });
    s.addText("Unit cost", { x: C.M, y: gy + 0.30, w: 1.13, h: rh, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 7.5, bold: true, color: C.MUTE, align: "right", valign: "middle" });
    crows.forEach((r,ri)=>{
      const y = gy + 0.30 + (ri+1)*rh;
      s.addShape("rect",{x:C.M,y,w:1.13,h:rh,fill:{color:C.INK}});
      s.addText(r,{x:C.M,y,w:1.13,h:rh,isTextBox:true,margin:0,fontFace:C.B,fontSize:8,bold:true,color:C.WHITE,align:"center",valign:"middle"});
      grid[ri].forEach((v,ci)=>{
        const on = (ri===2&&ci===2);
        s.addShape("rect",{x:gx+ci*cw,y,w:cw,h:rh,fill:{color:on?C.SPOD_L:(v>5.48?C.MIST2:C.CRIM_L)},line:{color:C.RULE,width:0.5}});
        s.addText(v.toFixed(2),{x:gx+ci*cw,y,w:cw,h:rh,isTextBox:true,margin:0,fontFace:C.B,fontSize:8.2,
          bold:on,color:on?C.SPOD:(v>5.48?C.TXT:C.CRIMSON),align:"center",valign:"middle"});
      });
    });
    para(s, C.M + 6.20, gy + 0.30, 6.24, 1.62, "What has to be true",
      "Read across the top for the commodity call and down the side for operational delivery. Shaded cells are below the current price.\n\n" +
      "PLS needs realised prices no worse than about 8% below our base case to justify today's price. Our base case is already 11% below " +
      "spot-implied realisation and 19% below the June-2026 quarter. The pitch does not need the price to rise. It needs the price not to fall by a fifth.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9 });
    foot(s, "Source: team valuation model, Football Field and Sensitivity sheets. Broker target range is the full individual analyst spread across 17-20 analysts; vendor averages cluster A$4.50-5.70. Our A$6.14 sits inside the individual range and below the most bullish.", P());
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
    s.addText(String(ctx.p), { x: 12.35, y: 7.02, w: 0.55, h: 0.30, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, color: "5F7183", align: "right", valign: "middle" });
  }
};
