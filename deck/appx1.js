// Appendix contents + Section A: company and assets.
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, divider, apage } = L;
const F = require('./model_facts.json');

module.exports = function (pres, ctx) {
  let a = 0; const A = () => ++a; ctx.A = () => ++a; ctx.getA = () => a;
  const fin = (s, n) => foot(s, n, "A" + a);

  // ------------------------------------------------ appendix cover + contents
  {
    const s = pres.addSlide(); bg(s, true);
    s.addText("APPENDIX", { x: C.M, y: 0.55, w: 8, h: 0.72, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 40, bold: true, color: C.WHITE, valign: "middle" });
    s.addText("Everything behind the fifteen slides: the asset, the market, the frameworks, the ESG evidence, the model, and what we could not verify.",
      { x: C.M, y: 1.30, w: 11.0, h: 0.42, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 12, color: "AFC3D4", valign: "top" });
    const secs = [
      ["A", "Company and assets", "A1-A11", ["Pilgangoora overview","Resource, reserve and mine life","P680 and ore sorting","P1000","P2000 expansion economics","Ngungaju restart","Mid-stream plant","POSCO joint venture","Colina, Brazil","Offtake portfolio","Board and management"]],
      ["B", "Industry", "B1-B12", ["The lithium value chain","Price history","Supply by country and source","The Jianxiawo timeline","Resource nationalism","Restart supply tracker","Cost curve detail","Electric-vehicle demand","Storage demand","Chemistry mix","Market balance by forecaster","Substitution and recycling risk"]],
      ["C", "Strategic frameworks", "C1-C6", ["Porter's five forces","Helmer's seven powers","Barriers to entry","SWOT","Peer positioning","Why not the other five"]],
      ["D", "ESG and shared value", "D1-D11", ["Materiality now and in 2030","Emissions and targets","Power strategy","Ore sorting case study","Water","Tailings and biodiversity","Traditional Owners","Workforce and safety","Governance","ESG in remuneration","Ratings and what we could not verify"]],
      ["E", "Valuation", "E1-E15", ["Model architecture","WACC","Price deck and convergence","Production build","Cost and capex build","Income statement","Balance sheet","Cash flow","FCFF and DCF","Bear case","Bull case","Mine life and terminal value","Sensitivities","Comparables and precedents","Downstream option"]],
      ["F", "Risk and reference", "F1-F7", ["Full risk register","Short interest","Share price catalysts","Broker views and register","Gaps register","Glossary","Bibliography"]],
    ];
    secs.forEach((sec, i) => {
      const x = C.M + (i % 3) * 4.16, y = 2.00 + Math.floor(i / 3) * 2.42;
      s.addShape("rect", { x, y, w: 3.98, h: 2.22, fill: { color: "16304C" } });
      s.addText(sec[0], { x: x + 0.18, y: y + 0.12, w: 0.5, h: 0.34, isTextBox: true, margin: 0,
        fontFace: C.H, fontSize: 18, bold: true, color: C.SPOD, valign: "middle" });
      s.addText(sec[1], { x: x + 0.72, y: y + 0.12, w: 2.4, h: 0.34, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 12, bold: true, color: C.WHITE, valign: "middle" });
      s.addText(sec[2], { x: x + 3.10, y: y + 0.12, w: 0.75, h: 0.34, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, color: "8FA8BE", align: "right", valign: "middle" });
      s.addText(sec[3].map((t) => "▪  " + t).join("\n"), { x: x + 0.20, y: y + 0.52, w: 3.62, h: 1.60,
        isTextBox: true, margin: 0, fontFace: C.B, fontSize: 7.6, color: "C9D8E6", valign: "top", lineSpacingMultiple: 1.06 });
    });
  }

  // ------------------------------------------------ A1 Pilgangoora
  {
    const { s, cy } = apage(pres, "A1  Company and assets", "Pilgangoora: one orebody doing all the work",
      "A single 100%-owned operation in the Pilbara with two processing plants, supplying customers in China and a joint venture in Korea.");
    A();
    const rows = [
      ["Location", "Pilbara region, Western Australia, about 120km from Port Hedland"],
      ["Ownership", "100% PLS Group"],
      ["Mineral Resource", "446Mt at 1.28% Li2O, containing 5.7Mt Li2O (June 2025 update, +23% contained lithium)"],
      ["Measured and Indicated", "376Mt at 1.29% Li2O"],
      ["Ore Reserve", "214Mt at 1.19% Li2O - stated August 2023 and not restated since the 2025 resource upgrade"],
      ["Processing plants", "Pilgan plant (about 1.0Mtpa after P1000) and Ngungaju plant (about 200ktpa, restarted July 2026)"],
      ["Product", "Spodumene concentrate at roughly 5.2% Li2O, shipped FOB Port Hedland"],
      ["Lithia recovery", "About 76.5% in FY26"],
      ["FY26 production", "879,500 dry metric tonnes, up 17%, ahead of guidance of 820,000-870,000t"],
      ["Power", "Site generation: gas gensets with LNG storage, displacing diesel; battery storage planned to firm future solar"],
      ["Water", "Saline groundwater from the Pilbara fractured-rock aquifer, with reverse osmosis on site for potable supply"],
    ];
    table(s, C.M, cy, [{ t: "", w: 2.75 }, { t: "", w: 9.69 }], rows,
      { rowH: 0.335, size: 9, boldFirstCol: true, headH: 0.01 });
    para(s, C.M, cy + 3.90, 6.10, 1.28, "Why a single asset is the central risk",
      "Everything in this recommendation rests on one orebody in one jurisdiction. There is no second mine to carry a bad quarter. " +
      "Colina adds a second jurisdiction only from the 2030s, and we risk it at 40%. A cyclone season, a plant outage or a permitting " +
      "dispute at Pilgangoora is not diversifiable inside this position.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
    para(s, C.M + 6.34, cy + 3.90, 6.10, 1.28, "And why the orebody is nonetheless the reason to own it",
      "446Mt at 1.28% Li2O is one of the largest hard-rock lithium resources in the world, at a grade that keeps mass pull at 17.5% " +
      "and unit costs near the bottom of the global curve. Scale and grade are not strategy - but they are what makes the strategy " +
      "affordable, and they cannot be replicated by a competitor's decision.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    fin(s, "Sources: PLS Group resource update, June 2025; Ore Reserve statement, August 2023; FY26 results, 24 August 2026; mining-technology.com project profile.");
  }

  // ------------------------------------------------ A2 Resource, reserve, mine life
  {
    const { s, cy } = apage(pres, "A2  Company and assets", "Resource, reserve and the mine-life arithmetic",
      "The reserve alone does not support the expansion we model. We say so, show the conversion assumption, and sensitise it.");
    A();
    table(s, C.M, cy, [{ t: "Step", w: 4.20 }, { t: "Value", w: 1.75, align: "center" },
      { t: "Working", w: 6.49 }], [
      ["Mineral Resource", "446.0 Mt", "At 1.28% Li2O, containing 5.7Mt Li2O. June 2025 update."],
      ["Resource-to-reserve conversion", "75%", "Our assumption. The single most important judgement on this page."],
      ["Mineable ore base", "334.5 Mt", "446.0 x 75%"],
      ["Reserve grade", "1.19% Li2O", "Per the August 2023 Ore Reserve statement"],
      ["Lithia recovery", "76.5%", "FY26 reported"],
      ["Concentrate grade", "5.2% Li2O", "PLS ships roughly SC5.2, below the SC6 benchmark"],
      ["Mass pull", "17.5%", "1.19% x 76.5% / 5.2% - tonnes of concentrate per tonne of ore"],
      ["Concentrate FY27-FY36, base case", "18.2 Mt", "Sum of the modelled production profile"],
      ["Ore consumed to FY36", "104.0 Mt", "18.2 / 17.5%"],
      ["Ore remaining after FY36", "230.5 Mt", "334.5 - 104.0"],
      ["Exit mining rate", "14.3 Mt p.a.", "FY36 concentrate of 2,500kt / 17.5%"],
      ["Remaining mine life", "16.1 years", "230.5 / 14.3 - the annuity period in our terminal value"],
    ], { rowH: 0.30, size: 8.8, boldFirstCol: true,
      rowFill: [null,C.OCHRE_L,null,null,null,null,C.MIST,null,null,null,null,C.SPOD_L] });
    para(s, C.M, cy + 4.06, 12.44, 1.02, "What happens if conversion disappoints",
      "At 60% conversion the mineable base falls to 267.6Mt, remaining life drops to about 11.4 years, and our target falls by roughly " +
      "A$0.40 per share. At 90% it rises to 401.4Mt and about 20.8 years, adding roughly A$0.30. The Ore Reserve has not been restated " +
      "since August 2023, so the next reserve statement is a genuine catalyst in both directions. We have flagged it in the risk register " +
      "rather than assuming the 2025 resource upgrade converts automatically.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
    fin(s, "Sources: PLS resource and reserve statements; FY26 results; team valuation model, Assumptions sheet. Mass pull and mine life are computed live in the workbook, not typed.");
  }

  // ------------------------------------------------ A3 P680 / ore sorting
  {
    const { s, cy } = apage(pres, "A3  Company and assets", "P680 and the ore sorter",
      "The clearest example in this business of an environmental improvement and a cost improvement being the same decision.");
    A();
    stat(s, C.M, cy, 2.90, "A$103m", "P680 capital cost", "Part-funded by a Northern Australia Infrastructure Facility debt facility of up to A$125m.", { color: C.INK });
    stat(s, C.M + 3.15, cy, 2.90, ">1,000 t/h", "Sorting capacity", "A TOMRA sensor-based sorter, described by the supplier as the largest in lithium.", { color: C.SPOD });
    stat(s, C.M + 6.30, cy, 2.90, "Aug 2024", "Commissioned", "Followed by the P1000 ramp, which lifted combined capacity to about 1.0Mtpa.", { color: C.INK });
    stat(s, C.M + 9.45, cy, 2.99, "A$30/t", "Our attribution", "Roughly half of the A$58/t fall in FY26 unit costs, with the remainder from volume scale.", { color: C.SPOD });
    card(s, C.M, cy + 1.62, 6.10, 2.30, "How sensor-based sorting works, and why it cuts two things at once", [
      "Ore is scanned and barren rock is ejected before it reaches crushing and flotation.",
      "Fewer tonnes are milled for the same contained lithium, so energy per tonne of product falls.",
      "The same mechanism lowers unit cost, because milling and flotation are the expensive steps.",
      "Waste that never enters the plant also never enters the tailings stream.",
      "This is Porter and Kramer's second level: an environmental problem solved in a way that lowers cost, rather than an offset purchased after the fact.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 8.8 });
    card(s, C.M + 6.34, cy + 1.62, 6.10, 2.30, "The honest limits of this claim", [
      "PLS does not disclose an energy saving per tonne attributable to the sorter, so our A$30/t is an attribution, not a disclosure.",
      "Trade press reported a 10% quarter-on-quarter unit cost reduction during the P1000 ramp; we could not verify the exact quarters, so we did not build on it.",
      "Ore sorting is available to any operator with the capital. It is a cost advantage today, not a durable moat.",
      "We would put a request for disclosed energy intensity per tonne to management, and have listed it as an engagement ask.",
    ], { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 8.8 });
    fin(s, "Sources: TOMRA Mining; Global Mining Review; Northern Australia Infrastructure Facility project page; PLS FY26 results. The A$30/t figure is the team's attribution, derived on slide 9 of the main deck.");
  }

  // ------------------------------------------------ A4 P1000 and capacity history
  {
    const { s, cy } = apage(pres, "A4  Company and assets", "How Pilgangoora got to a million tonnes",
      "Three completed expansions in four years took nameplate from about 500ktpa to roughly 1.2Mtpa including Ngungaju.");
    A();
    const rows = [
      ["P680", "Complete", "A$103m", "Aug 2024", "Crushing and ore sorting. Lifted the Pilgan plant to about 640-680ktpa."],
      ["P1000", "Complete", "A$375m", "2025", "Lifted combined Pilgangoora concentrate capacity to about 1.0Mtpa."],
      ["Ngungaju restart", "Complete", "Restart cost not disclosed", "Jul 2026", "About 200ktpa returned to service after being idled in December 2024."],
      ["Mid-stream demonstration", "Commissioning", "Milestone payments to Calix of at least A$11.4m identified", "Opened Jun 2026", "Electric calcination to lithium phosphate. First production guided for the September 2026 quarter."],
      ["P2000", "Pre-FID", "About A$1.2bn at PFS level; A$175m pre-FID approved", "DFS Dec-qtr 2026", "A new flotation plant taking total capacity above 2.0Mtpa. First ore guided mid-2029 if sanctioned."],
      ["Colina, Brazil", "Study", "A$45-55m of FY27 spend", "DFS Dec-qtr 2027", "77.7Mt at 1.24% Li2O. No final investment decision taken."],
    ];
    table(s, C.M, cy, [{ t: "Project", w: 2.30 }, { t: "Status", w: 1.55, align: "center" },
      { t: "Capital", w: 2.95 }, { t: "Timing", w: 1.55, align: "center" }, { t: "Scope", w: 4.09 }], rows,
      { rowH: 0.47, size: 8.6, boldFirstCol: true,
        rowFill: [C.SPOD_L, C.SPOD_L, C.SPOD_L, C.MIST, C.OCHRE_L, C.OCHRE_L] });
    para(s, C.M, cy + 3.20, 6.10, 1.42, "What the completed column tells you",
      "The three shaded green rows are done and inside the FY26 cost base. That is the record we underwrite: PLS has delivered three " +
      "expansions through the worst lithium downturn in a decade, on an asset that kept producing while peers idled. Execution risk on " +
      "P2000 should be judged against that record, not against a blank sheet.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 6.34, cy + 3.20, 6.10, 1.42, "And what the amber column costs",
      "The two amber rows are options, not plans. Neither has an FID. Our base case sanctions P2000 in late 2026 and Colina after the " +
      "December 2027 study; our bear case sanctions neither, and that single difference is most of the gap between A$6.50 and A$2.26. " +
      "The growth pipeline is where the value is and where the risk is, and it is the same pipeline.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
    fin(s, "Sources: PLS and Calix announcements; mining-technology.com; NAIF; PLS FY26 results and FY27 guidance. Capital figures are as disclosed at the time of each announcement.");
  }
};
