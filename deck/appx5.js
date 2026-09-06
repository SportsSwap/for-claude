// Appendix C3-C6 (frameworks) and D1-D6 (ESG).
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;

module.exports = function (pres, ctx) {
  let c = 2, d = 0;
  const pgC = (title, take, body, src) => {
    const n = ++c; const { s, cy } = apage(pres, "C" + n + "  Strategic frameworks", title, take);
    body(s, cy); foot(s, src, "C" + n);
  };
  const pgD = (title, take, body, src) => {
    const n = ++d; const { s, cy } = apage(pres, "D" + n + "  ESG and shared value", title, take);
    body(s, cy); foot(s, src, "D" + n);
  };
  ctx.getD = () => d;

  // ---------------- C3 barriers to entry
  pgC("Barriers to entry",
      "Capital and permitting keep new supply out at low prices and let it in at high ones. That is why the cycle is violent and why cost position, not barriers, is the durable defence.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Barrier", w: 2.75 }, { t: "Strength", w: 1.45, align: "center" },
      { t: "Assessment", w: 8.24 }], [
      ["Capital requirements", { t: "High", c: C.SPOD, b: true }, "P2000 alone is about A$1.2bn. Benchmark estimates the industry needs more than US$116bn by 2030. Few developers can fund a build through a price trough."],
      ["Orebody access", { t: "High", c: C.SPOD, b: true }, "A 446Mt resource at 1.28% Li2O is not a decision a competitor can make. Geology is the one input a competitor cannot buy."],
      ["Permitting and heritage", { t: "Medium-High", c: C.SPOD, b: true }, "Post-Juukan Gorge, Western Australian heritage approvals are slower and more scrutinised. This favours incumbents with existing agreements."],
      ["Processing know-how", { t: "Medium", c: C.OCHRE, b: true }, "Flotation and ore sorting are licensable. TOMRA will sell a sorter to anyone. This is not proprietary."],
      ["Offtake relationships", { t: "Low-Medium", c: C.OCHRE, b: true }, "Contracts are priced at prevailing market and re-tendered. Relationships help; they do not lock customers in."],
      ["Time", { t: "High", c: C.SPOD, b: true }, "First ore from P2000 is guided mid-2029 on a project studied since 2024. A greenfield project is a decade. Supply cannot respond to price inside a cycle."],
    ], { rowH: 0.53, size: 8.6, boldFirstCol: true });
    para(s, C.M, cy + 3.55, 12.44, 1.32, "The asymmetry that matters most",
      "Time is the real barrier. Because supply takes five to ten years to respond and demand moves in eighteen-month cycles, this " +
      "industry structurally overshoots in both directions - which is exactly the 2022 peak and the 2025 trough. It is also why a " +
      "perpetuity struck at either extreme is meaningless, and why our three price scenarios converge rather than diverge. The cycle is " +
      "the industry's defining feature, not an interruption to it.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Framework after George Yip, 'Barriers to Entry', 1982. Assessments are the team's, evidenced from company and industry sources cited elsewhere in this appendix.");

  // ---------------- C4 SWOT
  pgC("SWOT",
      "Written to be useful rather than balanced: the weaknesses and threats are longer than the strengths, because that is what the evidence supports.",
   (s, cy) => {
    const q = [
      ["Strengths", C.SPOD, C.SPOD_L, [
        "Bottom-quartile cost position: A$569/t FOB, about US$425/t SC6-equivalent",
        "446Mt at 1.28% Li2O, one of the largest hard-rock resources globally",
        "A$2.29bn of cash and net cash of A$1.46bn after a full downturn",
        "Three expansions delivered through the trough; dividend reinstated",
        "The only non-China downstream route among the six: Calix plus POSCO",
      ]],
      ["Weaknesses", C.CRIMSON, C.CRIM_L, [
        "One orebody, one commodity, one jurisdiction",
        "Net-zero target expressed as a decade, not a year; no SBTi validation found",
        "No Scope 3 disclosure and no emissions intensity KPI",
        "Ore Reserve not restated since August 2023",
        "No electric haul fleet or trolley assist, unlike Fortescue",
      ]],
      ["Opportunities", C.SPOD, C.SPOD_L, [
        "P2000: A$2.6bn incremental NPV at PFS, study due December-quarter 2026",
        "Mid-stream lithium phosphate: first production guided this quarter",
        "Option to lift the POSCO stake from 18% to 30%",
        "EU Battery Regulation and US FEOC rules turning provenance into a purchase criterion",
        "Colina as a second jurisdiction from the 2030s",
      ]],
      ["Threats", C.CRIMSON, C.CRIM_L, [
        "Restart supply: Bald Hill, Finniss and Jianxiawo all returning",
        "Wood Mackenzie's base case of surplus until the early 2030s",
        "Short-covering fuel is spent: 20% of shares to about 6.8%",
        "Sodium-ion substitution in stationary storage late this decade",
        "The Pilbara offsets regime found independently underfunded",
      ]],
    ];
    q.forEach((qq, i) => {
      const x = C.M + (i % 2) * 6.34, y = cy + Math.floor(i / 2) * 2.42;
      card(s, x, y, 6.10, 2.28, qq[0], qq[3], { fill: qq[2], line: C.RULE, titleColor: qq[1], size: 8.6, gap: 3 });
    });
   }, "Sources: as cited throughout this appendix. This SWOT is a summary of evidence presented elsewhere, not a separate assertion.");

  // ---------------- C5 peer positioning
  pgC("Peer positioning: lithium exposure against balance-sheet capacity",
      "The two things that decide who gets to act counter-cyclically. PLS is the only one of the six with both.",
   (s, cy) => {
    const bx = C.M, by = cy, bw = 7.40, bh = 4.10;
    s.addShape("rect", { x: bx, y: by, w: bw, h: bh, fill: { color: C.MIST2 }, line: { color: C.RULE, width: 0.75 } });
    s.addText("Lithium exposure  →", { x: bx + 0.55, y: by + bh - 0.30, w: 6.4, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9, bold: true, color: C.MUTE, align: "center", valign: "middle" });
    s.addText("Balance-sheet capacity  →", { x: bx - 1.55, y: by + bh / 2 - 0.15, w: 3.0, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9, bold: true, color: C.MUTE, align: "center", valign: "middle", rotate: 270 });
    const pts = [
      ["BHP", 0.05, 0.95, C.FAINT], ["Rio Tinto", 0.30, 0.80, C.FAINT],
      ["Fortescue", 0.03, 0.74, C.FAINT], ["South32", 0.20, 0.54, C.FAINT],
      ["Mineral Resources", 0.62, 0.20, C.OCHRE], ["PLS Group", 0.95, 0.78, C.SPOD],
    ];
    pts.forEach((p) => {
      const px = bx + 0.75 + p[1] * (bw - 1.55), py = by + bh - 0.75 - p[2] * (bh - 1.35);
      const isPLS = p[0] === "PLS Group";
      s.addShape("ellipse", { x: px - (isPLS ? 0.16 : 0.10), y: py - (isPLS ? 0.16 : 0.10),
        w: isPLS ? 0.32 : 0.20, h: isPLS ? 0.32 : 0.20, fill: { color: p[3] } });
      s.addText(p[0], { x: px - 1.05, y: py + (isPLS ? 0.18 : 0.12), w: 2.10, h: 0.24, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: isPLS ? 9.5 : 8.5, bold: isPLS, color: isPLS ? C.SPOD : C.MUTE,
        align: "center", valign: "middle" });
    });
    card(s, C.M + 7.62, cy, 4.82, 4.10, "Reading the chart", [
      "Vertical axis is capacity to act: net cash or low gearing, and the ability to fund growth through a trough.",
      "Horizontal axis is how much of the business is actually lithium.",
      "BHP, Rio Tinto, Fortescue and South32 have the balance sheet but not the exposure. A lithium recovery barely moves their earnings.",
      "Mineral Resources has the exposure but carries roughly US$4.3bn of net debt at 1.7x EBITDA, which constrains what it can do at the bottom of a cycle.",
      "PLS has both. That is why it could idle Ngungaju, buy Latin Resources in scrip at the trough, restart when prices recovered, reinstate a dividend and still hold A$2.29bn.",
      "Position on this chart is our assessment, not a computed score.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 8.8, gap: 4 });
   }, "Sources: company FY26 results and balance sheets. Axis positions are the team's qualitative assessment and are illustrative rather than measured.");

  // ---------------- C6 why not the others
  pgC("Why not the other five, in detail",
      "Each of the five is a defensible investment. None of them is a shared-value investment in the sense this case defines.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Company", w: 1.90 }, { t: "The case for it", w: 4.35 },
      { t: "Why we did not pick it for THIS mandate", w: 6.19 }], [
      ["BHP Group", "Scale, diversification, US$32.9bn of underlying EBITDA, a 4.3% yield and the strongest balance sheet in the sector.", "Its ESG programme is Scope 1 and 2 abatement on iron ore and coal. That is a cost of staying in business. Nothing about it creates a new market, which is what the brief asks us to find."],
      ["Rio Tinto", "The most direct lithium exposure among the majors after acquiring Arcadium for US$6.7bn, plus Rincon in Argentina.", "It bought lithium at the top of the cycle with US$14.1bn of net debt. The lithium exposure is real but diluted to a fraction of group earnings, so a lithium thesis expressed through Rio is mostly an iron ore position."],
      ["Fortescue", "A serious decarbonisation ambition in green hydrogen and an attractive yield.", "The green energy business sits beside the iron ore business rather than inside it. That is adjacency, not shared value: solving a societal problem in a separate division does not change the competitive position of the core."],
      ["South32", "Real transition-metal exposure in aluminium and base metals, net cash, and a consensus Buy.", "The closest runner-up. But its ESG work is still fundamentally licence-to-operate spending on existing assets, and its commodity mix does not put carbon intensity on the revenue line."],
      ["Mineral Resources", "The other lithium pure-play route on the list, with a 44% revenue increase and EBITDA up 183% in FY26.", "Lithium is diluted by mining services and iron ore, gearing is roughly US$4.3bn at 1.7x EBITDA, and the group has carried governance controversies. Constrained optionality is the opposite of what a counter-cyclical thesis needs."],
    ], { rowH: 0.78, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 4.24, 12.44, 0.94, null,
      "None of this says the other five are bad investments. It says that for a mandate defined by shared value, five of the six offer ESG as a cost of doing business and one offers it as the reason the business exists.",
      { fill: C.SPOD_L, line: "AFD3CC", size: 9.4 });
   }, "Sources: company FY26 results; data-vendor consensus and multiples, August 2026. Characterisations of each company's ESG posture are the team's assessment from public disclosure.");

  // ---------------- D1 materiality
  pgD("Materiality now, and materiality in 2030",
      "The case asks what is material today against the medium to long term. For lithium those are different lists, and the difference is the investment case.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Issue", w: 3.05 }, { t: "Material today", w: 1.75, align: "center" },
      { t: "Material by 2030", w: 1.75, align: "center" }, { t: "Why the ranking moves", w: 5.89 }], [
      ["Product carbon intensity", { t: "Low", c: C.MUTE }, { t: "Critical", c: C.SPOD, b: true }, "EU carbon footprint declarations and battery passports from 2027; US FEOC rules. Moves from disclosure to a condition of sale."],
      ["Energy cost and source", { t: "High", c: C.SPOD, b: true }, { t: "High", c: C.SPOD, b: true }, "Already in the unit cost line. Stays material as the grid and diesel prices move."],
      ["Traditional Owner relations", { t: "Critical", c: C.SPOD, b: true }, { t: "Critical", c: C.SPOD, b: true }, "Post-Juukan Gorge this is a permitting precondition. It gates P2000."],
      ["Water", { t: "Medium", c: C.OCHRE }, { t: "Medium", c: C.OCHRE }, "Pilgangoora uses saline groundwater, so it does not compete for potable supply. Structurally lower risk than brine."],
      ["Tailings and waste", { t: "Medium", c: C.OCHRE }, { t: "High", c: C.SPOD, b: true }, "Volumes rise with P2000. GISTM expectations tighten. PLS has not disclosed its method."],
      ["Biodiversity", { t: "Medium", c: C.OCHRE }, { t: "High", c: C.SPOD, b: true }, "Nature-related disclosure is following climate disclosure, and the Pilbara offsets regime is already judged inadequate."],
      ["Scope 3 emissions", { t: "Low", c: C.MUTE }, { t: "High", c: C.SPOD, b: true }, "Customers will be required to account for upstream emissions. Not currently disclosed by PLS."],
      ["Workforce and psychosocial safety", { t: "High", c: C.SPOD, b: true }, { t: "High", c: C.SPOD, b: true }, "WA parliamentary scrutiny of the fly-in fly-out sector; labour scarcity constrains growth delivery."],
      ["Governance and capital discipline", { t: "Critical", c: C.SPOD, b: true }, { t: "Critical", c: C.SPOD, b: true }, "In a cyclical commodity, when you spend matters more than what you spend on."],
    ], { rowH: 0.395, size: 8.4, boldFirstCol: true });
    para(s, C.M, cy + 3.95, 12.44, 1.12, "The one that moves the most",
      "Product carbon intensity goes from an item almost nobody prices today to the single most material issue on the list by 2030. That " +
      "movement is the whole thesis. If we are wrong about the timing, we are wrong about the recommendation - which is why we hold the " +
      "downstream option outside the target price rather than inside it, and why our A$6.12 stands on the cost position alone.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
   }, "Assessment is the team's, informed by SASB Metals and Mining standards, the EU Battery Regulation timetable and PLS's own disclosure. Ratings are ours, not the company's.");

  // ---------------- D2 emissions
  pgD("Emissions and targets: what is disclosed, and what is not",
      "PLS reports directionally and improved 7.1% last year. It does not report the two numbers a low-carbon thesis actually needs.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Metric", w: 3.45 }, { t: "What PLS discloses", w: 4.65 },
      { t: "Our assessment", w: 4.34 }], [
      ["Scope 1 and 2, absolute", "A 7.1% reduction year on year reported in the FY25 results. Absolute tonnages were not retrievable from our sources.", { t: "Directional only", c: C.OCHRE, b: true }],
      ["Scope 3", "Not found.", { t: "Material gap", c: C.CRIMSON, b: true }],
      ["Emissions intensity per tonne", "Not disclosed as a KPI. Third-party aggregators carry FY23-24 figures that disagree and that we judged unreliable.", { t: "Material gap", c: C.CRIMSON, b: true }],
      ["Net zero target", "\"The decade commencing 2040\" - a ten-year window rather than a year.", { t: "Weak", c: C.CRIMSON, b: true }],
      ["Interim target", "About 48% lower power emissions intensity by 2027, rising to as much as 80% by 2030 if regional wind becomes available.", { t: "Credible and dated", c: C.SPOD, b: true }],
      ["SBTi validation", "Not found.", { t: "Gap", c: C.OCHRE, b: true }],
      ["Product carbon footprint", "No third-party verified lifecycle assessment found.", { t: "Material gap", c: C.CRIMSON, b: true }],
    ], { rowH: 0.475, size: 8.6, boldFirstCol: true });
    para(s, C.M, cy + 3.72, 6.10, 1.44, "Why we are still positive",
      "The interim power target is the one that is both dated and quantified, and it is the one that flows to the cost line. A 48% " +
      "reduction in power emissions intensity by 2027 is achievable through the gas conversion already installed plus the planned solar " +
      "and storage. That is a plan with equipment attached, which is more than most net-zero commitments in this sector have.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 6.34, cy + 3.72, 6.10, 1.44, "And why the gaps matter here",
      "Our level-one thesis is that PLS can sell a declarable low-carbon tonne. A company that does not publish emissions intensity per " +
      "tonne of concentrate, has no verified product carbon footprint and discloses no Scope 3 cannot presently make that declaration. " +
      "The gap is not cosmetic - it is the difference between the thesis being true and being aspirational, which is precisely why we " +
      "price the downstream option at zero inside the target.",
      { fill: C.CRIM_L, line: "E5C3C3", titleColor: C.CRIMSON, size: 9 });
   }, "Sources: PLS FY25 full-year results commentary; PLS climate disclosures; third-party ESG aggregators (treated as unreliable and not relied upon). Items marked not found were searched for and could not be verified from our environment.");
};
