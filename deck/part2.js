// Slides 3-6: company and industry.
const { C, bg, nav, head, foot, stat, card, para, table, divider } = require('./lib.js');
const F = require('./model_facts.json');
const pcs = (x,d=1)=>(x>=0?"+":"")+(x*100).toFixed(d)+"%";

module.exports = function (pres, ctx) {
  const P = () => ++ctx.p;

  divider(pres, 1, "Company and industry",
    "What PLS is, what the last financial year proved, and what has actually changed in the lithium market.",
    ["03  Company overview", "04  The cycle has turned, with a saw-tooth", "05  What changed structurally", "06  The cost curve"]);

  // ---------------------------------------------------------------- 3. COMPANY OVERVIEW
  {
    const s = pres.addSlide(); bg(s); nav(s, "Company");
    const cy = head(s, "PLS came out of the downturn stronger than it went in",
      "Record volumes, a 59% margin, A$2.29bn of cash and a reinstated dividend - achieved while the lithium price was still recovering.");
    const st = [
      ["879.5kt", "Spodumene produced, FY26", "Up 17%. Beat guidance by about 10kt.", C.INK],
      ["A$1,934m", "Revenue, FY26", "Up 152% on FY25's A$769m.", C.INK],
      ["A$1,137m", "Underlying EBITDA", "A 59% margin, against A$97m in FY25.", C.SPOD],
      ["A$569/t", "Unit cost, FOB", "Down 9% while volumes rose 17%.", C.SPOD],
    ];
    st.forEach((t,i)=>stat(s, C.M + i*3.15, cy + 0.05, 2.95, t[0], t[1], t[2], { color: t[3], size: 27 }));

    s.addChart(pres.ChartType.bar, [{
      name: "Realised price (US$/t)",
      labels: ["FY24A","FY25A","FY26A","FY27F","FY28F","FY29F","FY30F"],
      values: [1116, 688, 1488, 1700, 1780, 1850, 1800],
    }], {
      x: C.M, y: cy + 1.30, w: 6.05, h: 3.30,
      chartColors: [C.INK2], barGapWidthPct: 45,
      showTitle: true, title: "Realised price per tonne, actual then base case (US$/t)",
      titleFontFace: C.B, titleFontSize: 11, titleColor: C.INK,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 8.5,
      dataLabelFontFace: C.B, dataLabelColor: C.MUTE, dataLabelFormatCode: "#,##0",
      catAxisLabelFontFace: C.B, catAxisLabelFontSize: 8.5, catAxisLabelColor: C.MUTE,
      valAxisLabelFontFace: C.B, valAxisLabelFontSize: 8.5, valAxisLabelColor: C.MUTE,
      valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" },
      showLegend: false, valAxisMaxVal: 2200, valAxisMinVal: 0,
    });

    card(s, C.M + 6.28, cy + 1.30, 6.16, 1.34, "The number that matters most is not the average", [
      "The June-2026 quarter realised US$2,107/t on actual grade, against a full-year average of US$1,488/t.",
      "PLS exited FY26 earning roughly 40% more per tonne than it averaged across it. FY27 annualises that.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.2 });

    const rows = [
      ["Production", "879.5kt", "1,030-1,100kt", "Ngungaju restart"],
      ["Unit cost, FOB", "A$569/t", "A$575-625/t", "Ngungaju mix effect"],
      ["Capital expenditure", "A$328m", "A$620-685m", "Includes A$175m P2000 pre-FID"],
      ["Dividend", "5.0cps franked", "20-30% of free cash flow", "Reinstated Aug 2026"],
    ];
    table(s, C.M + 6.28, cy + 2.82, [
      { t: "", w: 1.62 }, { t: "FY26 actual", w: 1.20, align: "center" },
      { t: "FY27 guidance", w: 1.58, align: "center" }, { t: "Driver", w: 1.76 },
    ], rows, { rowH: 0.42, size: 8.4, headSize: 8.4, boldFirstCol: true });
    para(s, C.M + 6.28, cy + 4.94, 6.16, 0.74, null,
      "A 17-25% volume step-up in FY27 at a unit cost only 1-10% higher. The extra Ngungaju tonnes cost more than " +
      "the Pilgan average and are still well down the global curve.",
      { fill: C.MIST, line: C.RULE, size: 8.8 });

    foot(s, "Source: PLS Group FY26 results, 24 August 2026; June-2026 quarterly activities report. Realised price is on actual product grade (about SC5.2), which sits below the SC6 benchmark. FOB means free on board, i.e. the cost to get product onto the ship, excluding freight.", P());
  }

  // ---------------------------------------------------------------- 4. THE CYCLE
  {
    const s = pres.addSlide(); bg(s); nav(s, "Industry");
    const cy = head(s, "The cycle has turned, but it is a saw-tooth, not a straight line",
      "Prices tripled off the 2025 trough and then fell hard in August as idled mines restarted. Credible forecasters disagree about what happens next, and we say so.");
    para(s, C.M, cy, 6.05, 1.36, "What has happened",
      "Spodumene bottomed near US$600-750/t in 2025 and reached roughly US$2,038-2,200/t by August 2026. PLS's own realised price " +
      "tripled over the same window. Then, in a single week in August, the Platts SpodIX benchmark fell US$270/t as Mineral Resources' " +
      "Bald Hill, Core Lithium's Finniss and CATL's Jianxiawo all moved to restart.", { titleColor: C.INK, size: 9.4 });
    para(s, C.M + 6.28, cy, 6.16, 1.36, "Why we do not forecast a straight line",
      "Our base case assumes PLS realises US$1,700/t in FY27 - about 11% below what current spot implies and 19% below the June-2026 " +
      "quarter exit rate. We would rather be early and conservative on price than build a recommendation that needs the spike to hold.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.4 });

    const cols = [{ t: "Forecaster", w: 2.30 }, { t: "Call on the 2026 balance", w: 2.35, align: "center" },
                  { t: "What they say", w: 7.79 }];
    const rows = [
      ["Fastmarkets", { t: "Deficit", c: C.SPOD, b: true }, "Flips from a 2025 surplus to a 1.5kt LCE deficit; raised its 2027 carbonate forecast from US$22.65/kg to US$31.40/kg."],
      ["Morgan Stanley", { t: "Deficit", c: C.SPOD, b: true }, "Calls an 80kt LCE deficit in 2026."],
      ["UBS", { t: "Deficit", c: C.SPOD, b: true }, "Calls a 22kt LCE deficit in 2026."],
      ["Macquarie", { t: "Narrowing", c: C.MUTE }, "2025 was the peak surplus year at 120kt; narrows to roughly balance (+1kt) by 2028."],
      ["Wood Mackenzie", { t: "Surplus", c: C.CRIMSON, b: true }, "Base case keeps lithium chemicals in surplus through 2026-27, with a deficit not arriving until the early 2030s."],
      ["IEA", { t: "Long-run shortfall", c: C.MUTE }, "Under its STEPS scenario, announced projects fall about 40% short of 2035 demand."],
    ];
    table(s, C.M, cy + 1.56, cols, rows, { rowH: 0.40, size: 8.8, boldFirstCol: true });
    para(s, C.M, cy + 4.36, 12.44, 0.78, null,
      "We have not smoothed this into one house view, because the disagreement is the point. Wood Mackenzie is the credible dissenter and " +
      "we carry its view as our bear case rather than ignoring it. What every forecaster on this page agrees on is that 2025 was the peak surplus year.",
      { fill: C.MIST, line: C.RULE, size: 9.4 });
    foot(s, "Sources: S&P Global Platts SpodIX assessments, August 2026; Benchmark Mineral Intelligence, 12 August 2026; Fastmarkets; Morgan Stanley; UBS; Macquarie; Wood Mackenzie Lithium Energy Transition Outlook, 3 March 2026; IEA Global Critical Minerals Outlook 2026. LCE means lithium carbonate equivalent.", P());
  }

  // ---------------------------------------------------------------- 5. WHAT CHANGED
  {
    const s = pres.addSlide(); bg(s); nav(s, "Industry");
    const cy = head(s, "Two sovereign supply shocks and a second demand pillar",
      "Whatever the next quarterly price print does, the shape of this market changed in 2026 - and none of it depends on electric vehicle subsidies.");
    card(s, C.M, cy, 4.02, 2.30, "China removed its own largest mine, twice", [
      "CATL's Jianxiawo mine, about 150ktpa LCE and the largest lithium operation in China, was suspended in August 2025, restarted in mid-2026 and re-suspended in August 2026.",
      "Benchmark cut its 2026 estimate for the site from 62.5kt to 32kt LCE. The regulatory review may not conclude until 2027.",
      "A further 108ktpa LCE of Jiangxi capacity sits under the same licence scrutiny.",
    ], { num: 1, size: 8.8, titleColor: C.INK });
    card(s, C.M + 4.21, cy, 4.02, 2.30, "Zimbabwe closed the door early", [
      "All raw mineral and concentrate exports were banned from 25 February 2026.",
      "The market had expected concentrate exports to stay legal until January 2027, so this arrived nearly a year early.",
      "Two unrelated, sovereign-driven disruptions inside twelve months is a more robust supply argument than either alone.",
    ], { num: 2, size: 8.8, titleColor: C.INK });
    card(s, C.M + 8.42, cy, 4.02, 2.30, "Storage became a demand pillar of its own", [
      "Battery storage installations grew about 51% in 2025, on top of 26% growth in electric-vehicle battery demand.",
      "Storage went from roughly 23% of lithium demand in 2025 to about 31% in 2026, pulled by datacentre power demand.",
      "This leg is structurally independent of the vehicle-subsidy cycle now working against the market in the United States.",
    ], { num: 3, numFill: C.SPOD, size: 8.8, titleColor: C.SPOD });

    para(s, C.M, cy + 2.48, 6.05, 1.68, "Why the third one matters most",
      "Every team in this competition will note that lithium demand grows with electric vehicles. That argument is exposed to a single " +
      "policy variable, and that variable has turned hostile in the United States. Grid storage is not. It is pulled by electricity " +
      "demand and by datacentre buildout, and it grew fast enough in 2026 to keep global lithium demand rising 17-30% through the " +
      "US policy reversal rather than in spite of it.", { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
    para(s, C.M + 6.28, cy + 2.48, 6.16, 1.68, "And what it takes to supply it",
      "Benchmark Mineral Intelligence puts the greenfield incentive price - the level at which genuinely new supply gets funded - " +
      "sustainably above US$20,000-25,000/t LCE, and estimates that more than 300 new projects are needed by 2035. Our base case " +
      "long-run price of about US$1,750/t realised sits below the level that incentive analysis implies. If Benchmark is right, we are " +
      "being too cautious, not too aggressive.", { size: 9.4, titleColor: C.INK });
    foot(s, "Sources: Benchmark Mineral Intelligence; Government of Zimbabwe export ban, 25 February 2026; Rho Motion and industry installation data; Reuters analyst poll (2026 demand growth of 17-30%).", P());
  }

  // ---------------------------------------------------------------- 6. COST CURVE
  {
    const s = pres.addSlide(); bg(s); nav(s, "Industry");
    const cy = head(s, "Pilgangoora earns cash at prices that shut a quarter of world supply",
      "This is why swing tonnes come off before PLS's do, and why the balance sheet compounds through a downturn instead of surviving it.");
    s.addChart(pres.ChartType.bar, [{
      name: "Cash cost, US$/t SC6",
      labels: ["Greenbushes","PLS Pilgangoora","23% of world\nsupply above","African hard rock\n(indicative)","Chinese lepidolite\n(90th percentile)"],
      values: [220, 425, 787, 900, 1100],
    }], {
      x: C.M, y: cy, w: 7.10, h: 3.42,
      chartColors: [C.INK2, C.SPOD, C.MUTE, C.MUTE, C.CRIMSON],
      varyColors: true, barGapWidthPct: 40,
      showTitle: true, title: "Where the tonnes sit on the cost curve (US$/t of SC6 concentrate)",
      titleFontFace: C.B, titleFontSize: 11, titleColor: C.INK,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9,
      dataLabelFontFace: C.B, dataLabelColor: C.MUTE, dataLabelFormatCode: "#,##0",
      catAxisLabelFontFace: C.B, catAxisLabelFontSize: 8.2, catAxisLabelColor: C.MUTE,
      valAxisLabelFontFace: C.B, valAxisLabelFontSize: 8.5, valAxisLabelColor: C.MUTE,
      valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" },
      showLegend: false, valAxisMaxVal: 1300,
    });
    card(s, C.M + 7.32, cy, 5.12, 1.68, "Read it against our own bear case", [
      "Our bear case assumes a realised price equal to roughly US$1,145/t on an SC6 basis.",
      "At that price the top decile of world supply is under water and PLS still earns about US$720/t of cash margin.",
      "That is the mechanism behind the phrase swing supply: the marginal tonne leaves the market before the low-cost tonne does.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 7.32, cy + 1.86, 5.12, 1.56, "The assumption most teams will get wrong",
      "Brine is no longer automatically the cheap end of this industry. S&P Global puts weighted Argentine brine all-in sustaining cost at " +
      "US$7,223/t LCE in 2026, inflated by Argentine cost pressure, which is at or above much of the hard-rock curve. The old " +
      "\"brine beats rock\" shorthand no longer describes the cost curve.", { size: 9.2, titleColor: C.INK });
    para(s, C.M, cy + 3.58, 12.44, 0.70, null,
      "Basis note. PLS reports A$569/t FOB on its own product grade of about SC5.2. Converted to an SC6 basis and translated at 0.65 AUD/USD, " +
      "that is roughly US$425/t - the figure shown above. We have made the conversion explicit rather than comparing grades that are not alike.",
      { fill: C.MIST, line: C.RULE, size: 8.8 });
    foot(s, "Sources: S&P Global Market Intelligence Mine Cost Outlook, January 2026; CRU Group (lepidolite cost distribution); PLS Group FY26 results. Greenbushes is operated by Talison, a Tianqi, Albemarle and IGO joint venture.", P());
  }
};
