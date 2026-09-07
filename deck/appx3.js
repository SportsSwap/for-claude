// Appendix B: industry.
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;

module.exports = function (pres, ctx) {
  let b = 0; const B = () => ++b; ctx.B = B; ctx.getB = () => b;
  const pg = (n, title, take, body, src) => {
    const { s, cy } = apage(pres, "B" + B() + "  Industry", title, take);
    body(s, cy); foot(s, src, "B" + b);
  };

  pg(1, "How a tonne of rock becomes a battery",
     "Five steps, and PLS is trying to move from the first one into the second. That move is the entire level-one thesis.",
   (s, cy) => {
    const steps = [
      ["Mine and concentrate", "Hard-rock pegmatite is mined, crushed, sorted and floated into spodumene concentrate at about 5.2-6.0% Li2O.", "PLS today", C.SPOD],
      ["Calcine and convert", "Concentrate is calcined at high temperature, then leached into lithium carbonate or hydroxide. Most of this happens in China.", "PLS is entering", C.OCHRE],
      ["Cathode active material", "Carbonate or hydroxide becomes cathode powder - LFP, NMC or others.", "Not PLS", C.FAINT],
      ["Cell and pack", "Cathode, anode, electrolyte and separator become a cell, then a module and a pack.", "Not PLS", C.FAINT],
      ["Vehicle or grid storage", "The pack goes into an electric vehicle or a grid-scale storage system.", "The demand driver", C.INK2],
    ];
    steps.forEach((st, i) => {
      const x = C.M + i * 2.50;
      s.addShape("rect", { x, y: cy, w: 2.34, h: 2.30, fill: { color: i < 2 ? C.SPOD_L : C.MIST2 },
        line: { color: i < 2 ? "AFD3CC" : C.RULE, width: 0.75 } });
      s.addText(String(i + 1), { x: x + 0.14, y: cy + 0.10, w: 0.3, h: 0.26, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: st[3], valign: "middle" });
      s.addText(st[0], { x: x + 0.14, y: cy + 0.36, w: 2.06, h: 0.50, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10.5, bold: true, color: C.INK, valign: "top" });
      s.addText(st[1], { x: x + 0.14, y: cy + 0.90, w: 2.06, h: 1.02, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.2, color: C.TXT, valign: "top", lineSpacingMultiple: 1.06 });
      s.addText(st[2], { x: x + 0.14, y: cy + 1.96, w: 2.06, h: 0.26, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.5, bold: true, color: st[3], valign: "middle" });
    });
    para(s, C.M, cy + 2.48, 12.44, 1.70, "Where the value sits, and why step two is the one that matters",
      "A tonne of spodumene concentrate at US$1,750 contains roughly 0.13 tonnes of lithium carbonate equivalent. At US$18,000 per tonne " +
      "of carbonate, that same lithium is worth about US$2,340 once converted - and conversion costs perhaps US$2,000-3,000 per tonne of " +
      "carbonate. The spread is real but not enormous, and it is captured almost entirely outside Australia.\n\n" +
      "The reason step two matters is not the margin. It is that calcination is where most of the embedded carbon in a battery's lithium " +
      "enters the chain. Whoever controls calcination controls the carbon footprint that gets declared under the EU Battery Regulation. " +
      "PLS is not entering conversion to capture a spread; it is entering to control a number that is about to become a condition of sale.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: industry conversion ratios (roughly 7.5 tonnes of SC6 per tonne of LCE); Benchmark Mineral Intelligence price assessments; EU Regulation 2023/1542. Conversion cost is an indicative industry range, not a PLS disclosure.");

  pg(2, "Price history: the round trip that made this case interesting",
     "Spodumene went from about US$8,000/t at the 2022 peak to roughly US$600-750/t in 2025, and back to about US$2,038-2,200/t by August 2026.",
   (s, cy) => {
    s.addChart(pres.ChartType.line, [{
      name: "PLS realised price (US$/t, actual grade)",
      labels: ["FY24A","FY25A","Q1 FY26","Q2 FY26","FY26 avg","Q4 FY26","FY27F","FY28F","FY29F","FY30F"],
      values: [1116, 688, 742, 1161, 1488, 2107, 1700, 1780, 1850, 1800],
    }], {
      x: C.M, y: cy, w: 7.55, h: 3.62, chartColors: [C.S2], lineSize: 2.25, lineSmooth: false,
      showTitle: true, title: "PLS realised price: reported, then our base case (US$/t)",
      titleFontFace: C.B, titleFontSize: 11, titleColor: C.INK,
      showValue: true, dataLabelPosition: "t", dataLabelFontSize: 7.5, dataLabelFontFace: C.B,
      dataLabelColor: C.MUTE, dataLabelFormatCode: "#,##0",
      catAxisLabelFontFace: C.B, catAxisLabelFontSize: 8, catAxisLabelColor: C.MUTE,
      valAxisLabelFontFace: C.B, valAxisLabelFontSize: 8.5, valAxisLabelColor: C.MUTE,
      valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" },
      showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 2400,
    });
    table(s, C.M + 7.78, cy, [{ t: "Benchmark", w: 2.55 }, { t: "Level", w: 2.11, align: "right" }], [
      ["Spodumene SC6, 2022 peak", "~US$8,000/t"],
      ["Spodumene SC6, 2025 trough", "US$600-750/t"],
      ["Spodumene SC6 FOB Australia, 12-Aug-26", "US$2,038/t"],
      ["Platts SpodIX CIF China, Aug-26", "US$2,200/t"],
      ["Weekly move in that August print", "-US$270/t"],
      ["Lithium carbonate, 12-Aug-26", "US$18,310/t"],
      ["Lithium carbonate, China, 4-Sep-26", "CNY 152,000/t"],
      ["Australian Government REQ 2026 forecast", "US$2,236/t"],
    ], { rowH: 0.40, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 3.78, 12.44, 1.40, "Two things this chart is designed to make obvious",
      "First, the June-2026 quarter print of US$2,107/t is above every year in our forecast. Our base case does not assume the recovery " +
      "continues; it assumes prices settle roughly a fifth below the exit rate and stay there. Second, the Australian Government's own " +
      "Resources and Energy Quarterly forecast a 2026 spodumene average of US$2,236/t - materially above the US$1,700/t we use for FY27. " +
      "We are not the bullish end of this debate. We are below the official forecaster and below spot.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
   }, "Sources: PLS quarterly activities reports (realised prices, actual grade, CIF China); Benchmark Mineral Intelligence, 12 August 2026; S&P Global Platts; Trading Economics; Australian Government Resources and Energy Quarterly, June 2026. FY27-FY30 are the team's base case.");

  pg(3, "Where the world's lithium actually comes from",
     "Three countries supply most of it, from three geologically different sources with very different cost and carbon profiles.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Source", w: 2.35 }, { t: "Where", w: 2.30 }, { t: "Cost position", w: 2.55 },
      { t: "Carbon and water profile", w: 2.75 }, { t: "What it means for PLS", w: 2.49 }], [
      ["Hard rock (spodumene)", "Australia, then Zimbabwe, Brazil, Canada, Mali", "Greenbushes about US$220/t; PLS about US$425/t SC6-equivalent", "Energy-intensive at calcination; low water use; dry-stack tailings feasible", "PLS's own category. Scale and grade decide the ranking within it"],
      ["Continental brine", "Chile, Argentina", "Argentine weighted AISC US$7,223/t LCE in 2026 - no longer the cheap end", "Low energy, high water use and long evaporation cycles; local water conflict risk", "Brine's historic cost advantage has eroded, which helps hard rock"],
      ["Lepidolite", "China, mainly Jiangxi", "Some operations above US$1,100/dmt, around the 90th percentile", "20-30 tonnes of ore per tonne of LCE; very high waste and energy intensity", "The marginal tonne. It leaves the market first when prices fall"],
      ["Clay and other", "United States (McDermitt), various", "Pre-production; no established cost curve", "Unproven at scale", "A 2030s question, not a 2026 one"],
    ], { rowH: 0.72, size: 8.4, boldFirstCol: true,
         rowFill: [C.SPOD_L, null, C.CRIM_L, null] });
    para(s, C.M, cy + 3.30, 6.10, 1.42, "The structural point",
      "These are not interchangeable tonnes. A tonne of lithium from Jiangxi lepidolite carries roughly an order of magnitude more waste " +
      "rock and considerably more embedded energy than a tonne from Pilgangoora. As carbon accounting reaches raw materials, the cost " +
      "curve and the carbon curve start to converge - and they converge in the same direction for PLS.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 6.34, cy + 3.30, 6.10, 1.42, "The honest counterpoint",
      "Carbon intensity is not the only thing customers buy on, and today it is rarely the deciding factor. Price and security of supply " +
      "still dominate. Our thesis is that the ordering changes over the next five years under EU and US rules, not that it has already " +
      "changed. If it does not, the level-one argument fails and the stock is worth roughly what the comparables say - about A$5.56.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
   }, "Sources: S&P Global Market Intelligence Mine Cost Outlook, January 2026; CRU Group; USGS Mineral Commodity Summaries; Goldman Sachs lepidolite cost work. Ore-to-LCE intensity for lepidolite is an industry range.");

  pg(4, "The Jianxiawo timeline: how one Chinese mine moved the world price",
     "About 150,000 tonnes a year of lithium carbonate equivalent, suspended, restarted and re-suspended inside thirteen months.",
   (s, cy) => {
    const ev = [
      ["Aug 2025", "First suspension", "CATL's Jianxiawo mine in Jiangxi - the largest lithium operation in China - is suspended over mining-licence issues. Prices rally.", C.SPOD],
      ["Mid-2026", "Restart", "The mine restarts, adding supply back into a recovering market.", C.OCHRE],
      ["Aug 2026", "Re-suspension", "Suspended again. Benchmark Mineral Intelligence cuts its 2026 output estimate for the site from 62,500t to 32,000t LCE.", C.SPOD],
      ["Ongoing", "Review may run into 2027", "The regulatory review may not conclude until 2027, and about 108,000tpa LCE of further Jiangxi capacity sits under the same scrutiny.", C.INK2],
    ];
    ev.forEach((e, i) => {
      const y = cy + i * 0.86;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 0.78, fill: { color: i % 2 ? C.MIST2 : C.PAPER },
        line: { color: C.RULE, width: 0.6 } });
      s.addText(e[0], { x: C.M + 0.18, y, w: 1.35, h: 0.78, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: e[3], valign: "middle" });
      s.addText(e[1], { x: C.M + 1.62, y, w: 2.60, h: 0.78, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10.5, bold: true, color: C.INK, valign: "middle" });
      s.addText(e[2], { x: C.M + 4.32, y: y + 0.06, w: 7.90, h: 0.66, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, color: C.TXT, valign: "middle", lineSpacingMultiple: 1.06 });
    });
    para(s, C.M, cy + 3.62, 12.44, 1.42, "Why this belongs in an investment case rather than a news summary",
      "A single asset representing roughly 150ktpa LCE is about 10% of a market that ran a surplus of perhaps 33-120kt in 2025. Its " +
      "on-off status is therefore not noise; it is the swing factor that decides whether 2026 prints a surplus or a deficit, which is " +
      "exactly why credible forecasters disagree.\n\n" +
      "It also demonstrates something structural: the highest-cost, highest-waste tonnes in this industry sit in a jurisdiction that has " +
      "shown it will suspend them for regulatory reasons unrelated to price. That is a supply curve with a political discontinuity in it, " +
      "and it favours low-cost producers in stable jurisdictions - which is the position we are underwriting.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: Benchmark Mineral Intelligence; S&P Global; Reuters coverage of the Jianxiawo suspensions. Market balance figures per the forecaster comparison in B11.");

  pg(5, "Resource nationalism is now a supply variable",
     "Zimbabwe banned concentrate exports a year earlier than expected. Two sovereign-driven disruptions in twelve months is a pattern, not a coincidence.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Jurisdiction", w: 2.05 }, { t: "Action", w: 4.25 }, { t: "Timing", w: 1.85, align: "center" },
      { t: "Effect on the market", w: 4.29 }], [
      ["Zimbabwe", "Ban on all raw mineral and concentrate exports, forcing domestic processing", { t: "25 Feb 2026", c: C.SPOD, b: true }, "Arrived nearly a year earlier than the market expected; concentrate exports had been assumed legal until January 2027"],
      ["China", "Mining-licence enforcement in Jiangxi; Jianxiawo suspended twice", "2025-2026", "Removes the highest-cost, highest-waste tonnes; review may run into 2027"],
      ["Indonesia, historically", "Nickel ore export ban forcing downstream investment", "2014, 2020", "The template. Resource nationalism in battery materials is an established playbook, not a novelty"],
      ["Chile", "State participation in lithium via a national strategy", "2023 onward", "Raises the bar for new brine supply from the lowest-cost basin"],
      ["Australia", "Critical Minerals Production Tax Incentive: a 10% refundable offset on eligible processing costs", "Legislated", "Pushes in the opposite direction - it subsidises domestic downstream processing rather than restricting exports"],
    ], { rowH: 0.60, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 3.42, 6.10, 1.46, "What it means for the supply forecast",
      "Every forecaster's 2027-2030 supply curve assumes projects come on when economics allow. Two of the last twelve months' largest " +
      "supply events had nothing to do with economics. That asymmetry matters: political supply interruptions are almost always " +
      "restrictive, rarely expansive. It biases the distribution of supply outcomes toward tighter, not looser.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 6.34, cy + 3.42, 6.10, 1.46, "And what it means for PLS specifically",
      "Australia is the counter-example on this page: rather than restricting exports, it is subsidising domestic processing through a " +
      "10% refundable production tax offset. We have not put a number on PLS's eligibility because we could not verify whether the " +
      "mid-stream plant qualifies. If it does, it improves the economics of exactly the asset our level-one thesis depends on. " +
      "We carry that at zero.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
   }, "Sources: Government of Zimbabwe export ban, 25 February 2026; Australian Government Critical Minerals Production Tax Incentive; Reuters and S&P Global coverage. We did not verify PLS's CMPTI eligibility and carry it at nil.");

  pg(6, "The restart tracker: what came back, and what it did to the price",
     "Three idled operations moved to restart in the same window, and the Platts benchmark fell US$270 a tonne in a single week.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Operation", w: 2.55 }, { t: "Owner", w: 2.20 }, { t: "Status", w: 2.75 },
      { t: "Why it matters", w: 4.94 }], [
      ["Bald Hill", "Mineral Resources", "Restarted after being idled since November 2024; first shipment targeted in the first quarter of FY27", "Direct Australian competitor tonnes returning to a recovering market"],
      ["Finniss", "Core Lithium", "Moving to restart", "A previously uneconomic Northern Territory operation made viable again by price"],
      ["Jianxiawo", "CATL", "Restarted mid-2026, re-suspended August 2026", "The largest single swing factor in the market"],
      ["Ngungaju", { t: "PLS Group", c: C.SPOD, b: true }, "Restarted July 2026, steady state targeted within four months", "PLS is part of this supply response. We are not pretending otherwise"],
    ], { rowH: 0.58, size: 8.6, boldFirstCol: true, rowFill: [null, null, null, C.SPOD_L] });
    para(s, C.M, cy + 2.90, 12.44, 1.86, "The uncomfortable point we put on the slide rather than in a footnote",
      "PLS is not a bystander to the restart wave. It restarted Ngungaju in the same window as Bald Hill and Finniss, and it is guiding " +
      "to a 17-25% volume increase in FY27. Every producer restarting at once is precisely what caps a price recovery, and our own " +
      "recommendation contributes to it.\n\n" +
      "That is why our base case assumes realised prices fall roughly a fifth below the June-2026 exit rate rather than holding it. It is " +
      "also why the cost curve matters more than the price forecast: in a market where everyone restarts, the question is not who supplies " +
      "the next tonne but who is still profitable when they all do. On our numbers PLS earns roughly US$720/t of cash margin at a price " +
      "that puts the top decile of world supply under water.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: S&P Global Platts, 'Asian lithium may ease in Q3 amid expectations of higher supply'; company announcements from Mineral Resources, Core Lithium, CATL and PLS.");
};
