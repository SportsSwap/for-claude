// Appendix B7-B12 (industry) and C1-C6 (frameworks).
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;

module.exports = function (pres, ctx) {
  const B = ctx.B;
  const pgB = (title, take, body, src) => {
    const n = B(); const { s, cy } = apage(pres, "B" + n + "  Industry", title, take);
    body(s, cy); foot(s, src, "B" + n);
  };
  let c = 0;
  const pgC = (title, take, body, src) => {
    const n = ++c; const { s, cy } = apage(pres, "C" + n + "  Strategic frameworks", title, take);
    body(s, cy); foot(s, src, "C" + n);
  };

  // ---------------------------------------------------------------- B7 cost curve detail
  pgB("Cost curve detail",
      "Australian hard rock sits at the bottom, Chinese lepidolite at the top, and Argentine brine has moved from the cheap end to the middle.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Benchmark", w: 4.35 }, { t: "Level", w: 2.45, align: "center" },
      { t: "Basis", w: 2.35 }, { t: "Source", w: 3.29 }], [
      ["Greenbushes cash cost", "~US$220/t SC6 FOB", "Cash cost", "Lowest-cost operation globally; Talison joint venture"],
      ["PLS Pilgangoora", { t: "~US$425/t SC6-equivalent", c: C.SPOD, b: true }, "A$569/t FOB at SC5.2, converted", "PLS FY26 results; conversion shown in the main deck"],
      ["Threshold above which 23% of concentrate production sits", "US$787/t SC6 FOB", "All-in sustaining", "S&P Global Mine Cost Outlook, January 2026"],
      ["Some lepidolite operations", { t: ">US$1,100/dmt", c: C.CRIMSON, b: true }, "Concentrate cost, about the 90th percentile", "CRU Group"],
      ["Argentine brine, weighted", "US$7,223/t LCE", "All-in sustaining, 2026", "S&P Global - elevated by Argentine cost inflation"],
      ["Industry average", "US$5,887/t LCE", "All-in sustaining, 2026, +0.8% year on year", "S&P Global Market Intelligence"],
      ["Greenfield incentive price", "Sustainably above US$20,000-25,000/t LCE", "What new supply needs to get funded", "Benchmark Mineral Intelligence"],
      ["Long-run incentive price", "~US$29,000/t LCE in real 2024 terms", "Long-run", "Benchmark Mineral Intelligence"],
    ], { rowH: 0.40, size: 8.5, boldFirstCol: true, rowFill: [null,C.SPOD_L,null,C.CRIM_L,null,null,null,null] });
    para(s, C.M, cy + 3.62, 6.10, 1.36, "The comparison most decks get wrong",
      "Concentrate costs are quoted per tonne of concentrate; brine and integrated costs per tonne of lithium carbonate equivalent. " +
      "They are not comparable without converting at roughly 7.5 tonnes of SC6 per tonne of LCE. We have kept the two units separate " +
      "on this page rather than presenting a single misleading ladder.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9 });
    para(s, C.M + 6.34, cy + 3.62, 6.10, 1.36, "What it implies for our price deck",
      "Our long-run base case of about US$1,750/t realised, roughly US$2,000/t on an SC6 basis, converts to well under the US$20,000-25,000/t " +
      "LCE that Benchmark says greenfield supply requires. Either our long-run price is too low, or the 300-plus projects Benchmark says " +
      "2035 demand needs will not be funded. Both cannot be true, and we have chosen the conservative side.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
   }, "Sources: S&P Global Market Intelligence, Mine Cost Outlook, January 2026; CRU Group; Benchmark Mineral Intelligence. PLS's SC6-equivalent cost is our conversion from the disclosed A$569/t FOB at SC5.2 grade and 0.65 AUD/USD.");

  // ---------------------------------------------------------------- B8 EV demand
  pgB("Electric-vehicle demand: still the largest leg, and the most politically exposed",
      "It remains most of lithium demand, and it is the part of the thesis a single government can damage. That is why we do not rest the case on it.",
   (s, cy) => {
    card(s, C.M, cy, 4.02, 2.10, "What is growing", [
      "Electric-vehicle battery demand grew about 26% in 2025.",
      "Reuters-polled analysts expect total lithium demand to grow 17-30% in 2026.",
      "China remains the dominant single market for both production and sales.",
    ], { num: 1, size: 9, titleColor: C.INK });
    card(s, C.M + 4.21, cy, 4.02, 2.10, "What is working against it", [
      "United States policy has turned: the Inflation Reduction Act consumer incentives and tariff settings under the current administration have removed support from US electric-vehicle demand.",
      "Global demand nonetheless kept rising through that reversal, which is the point.",
    ], { num: 2, numFill: C.OCHRE, size: 9, titleColor: C.OCHRE });
    card(s, C.M + 8.42, cy, 4.02, 2.10, "Why chemistry matters here", [
      "The shift toward lithium iron phosphate cathodes favours lithium carbonate over hydroxide.",
      "Spodumene feeds both, so PLS is chemistry-agnostic at the concentrate level.",
      "The POSCO joint venture produces hydroxide, which is the nickel-rich end of the market - a partial exposure to the chemistry mix.",
    ], { num: 3, size: 9, titleColor: C.INK });
    para(s, C.M, cy + 2.28, 12.44, 1.86, "The argument we are deliberately not making",
      "The standard lithium pitch is: electric vehicles grow, therefore lithium goes up, therefore buy a lithium miner. We think that " +
      "argument is weaker in 2026 than it has been at any point in the last five years, because its central assumption - that policy " +
      "support for electric-vehicle adoption is a one-way ratchet - has just been falsified in the world's second-largest car market.\n\n" +
      "Our case does not need electric-vehicle demand to accelerate. It needs the cost curve to keep sorting winners from losers, and it " +
      "needs carbon accounting to keep spreading through supply chains. Both of those continue regardless of what happens to US " +
      "purchase incentives. The storage demand leg on the next page is what makes total demand robust to this particular risk.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: Rho Motion and industry battery-demand data; Reuters analyst poll on 2026 lithium demand; IEA Global EV Outlook. US policy characterisation reflects reporting through 2026.");

  // ---------------------------------------------------------------- B9 storage demand
  pgB("Storage demand: the leg nobody was modelling three years ago",
      "Installations grew about 51% in 2025 and storage went from roughly 23% to about 31% of lithium demand in a single year, pulled partly by datacentre power.",
   (s, cy) => {
    s.addChart(pres.ChartType.bar, [{
      name: "Share of lithium demand (%)",
      labels: ["Battery storage 2025", "Battery storage 2026e"],
      values: [23, 31],
    }], {
      x: C.M, y: cy, w: 5.30, h: 2.60, chartColors: [C.INK2, C.SPOD], varyColors: true, barGapWidthPct: 60,
      showTitle: true, title: "Storage share of total lithium demand (%)",
      titleFontFace: C.B, titleFontSize: 11, titleColor: C.INK,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelFontFace: C.B,
      dataLabelColor: C.MUTE, dataLabelFormatCode: '0"%"',
      catAxisLabelFontFace: C.B, catAxisLabelFontSize: 9, catAxisLabelColor: C.MUTE,
      valAxisLabelFontFace: C.B, valAxisLabelFontSize: 8.5, valAxisLabelColor: C.MUTE,
      valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" },
      showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 40,
    });
    card(s, C.M + 5.54, cy, 6.90, 2.60, "Why this is structurally different from vehicle demand", [
      "Grid storage is bought by utilities and datacentre operators on a levelised-cost basis, not by households responding to a purchase subsidy.",
      "Its driver is electricity demand growth and grid firming, which is currently being pulled hard by artificial-intelligence datacentre buildout.",
      "China's power and energy-storage battery production reached 191.7 GWh in May 2026 alone, up 55.2% year on year.",
      "Storage overwhelmingly uses lithium iron phosphate chemistry, which consumes lithium carbonate - the product spodumene feeds most directly.",
      "It is therefore a demand leg that is uncorrelated with the single largest political risk to the electric-vehicle leg.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M, cy + 2.78, 12.44, 1.36, "The honest limit of this argument",
      "Storage is growing from a smaller base and is more price-elastic than vehicle demand: a storage project that does not pencil at " +
      "US$25,000/t lithium carbonate simply waits. So this leg supports demand at moderate prices and caps it at high ones. That is " +
      "consistent with our price deck, which has all three scenarios converging on a long-run level rather than running away, and it is " +
      "part of why we think a spike would be self-correcting rather than sustained.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: industry installation data via Benchmark Mineral Intelligence and Rho Motion; China Automotive Battery Innovation Alliance production data reported for May 2026.");

  // ---------------------------------------------------------------- B10 market balance
  pgB("Market balance: the forecasters do not agree",
      "Presented as found rather than smoothed into a house view, because the disagreement is itself the most useful thing on this page.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Year", w: 1.15, align: "center" }, { t: "Forecaster", w: 2.85 },
      { t: "Balance, kt LCE", w: 2.35, align: "center" }, { t: "Note", w: 6.09 }], [
      ["2023", "S&P Global", { t: "+120", c: C.CRIMSON }, "Surplus"],
      ["2024", "S&P Global", { t: "+84", c: C.CRIMSON }, "Surplus narrowing"],
      ["2025", "S&P Global", { t: "+33", c: C.CRIMSON }, "Also cited elsewhere at +141; two report vintages we could not reconcile"],
      ["2025", "Macquarie", { t: "+120", c: C.CRIMSON }, "Described as the peak surplus year"],
      ["2025", "Fastmarkets", { t: "+10", c: C.CRIMSON }, "Small surplus"],
      ["2026", "Fastmarkets", { t: "-1.5", c: C.SPOD, b: true }, "Flips to deficit"],
      ["2026", "Morgan Stanley", { t: "-80", c: C.SPOD, b: true }, "Deficit"],
      ["2026", "UBS", { t: "-22", c: C.SPOD, b: true }, "Deficit"],
      ["2026-27", "Wood Mackenzie", { t: "Surplus", c: C.CRIMSON, b: true }, "Base case: oversupply peaks in 2027; deficit not until the early 2030s"],
      ["2028", "Macquarie", { t: "+1", c: C.MUTE }, "Roughly balanced"],
      ["2028", "Wood Mackenzie", { t: "Deficit", c: C.SPOD }, "Net Zero scenario only"],
      ["2035", "IEA", { t: "-40%", c: C.SPOD, b: true }, "Announced projects fall about 40% short of demand under the STEPS scenario"],
    ], { rowH: 0.285, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 3.85, 12.44, 1.18, "What we take from it",
      "The one point of convergence is that 2025 was the peak surplus year. Beyond that, credible houses disagree by a full turn of the " +
      "cycle. We have not resolved the disagreement by picking a favourite: Wood Mackenzie's surplus-until-the-2030s view is effectively " +
      "our bear case, and the Fastmarkets, Morgan Stanley and UBS deficit calls are effectively our bull case. Our base case sits between " +
      "them, which is the honest place for it to sit.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: S&P Global Commodity Insights; Macquarie; Fastmarkets; Morgan Stanley; UBS; Wood Mackenzie Lithium Energy Transition Outlook, 3 March 2026; IEA Global Critical Minerals Outlook 2026. Figures are as reported by each house at different dates and are not on a common definition.");

  // ---------------------------------------------------------------- B11 substitution
  pgB("Substitution and recycling: the two ways this thesis dies slowly",
      "Neither is material inside our forecast window, but both are real, and a lithium bull who ignores them is not being serious.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Threat", w: 2.55 }, { t: "What it is", w: 4.35 },
      { t: "Realistic timeline", w: 2.15, align: "center" }, { t: "Our view", w: 3.39 }], [
      ["Sodium-ion batteries", "Sodium replaces lithium entirely. Lower energy density, cheaper inputs, better cold performance.", { t: "Late 2020s at scale", c: C.OCHRE }, "Most credible in stationary storage and low-range vehicles - which is where our storage demand leg sits. This is the sharpest threat to the bull case."],
      ["Solid-state batteries", "Solid electrolyte replacing liquid. Often uses MORE lithium, sometimes lithium metal anodes.", { t: "2030s", c: C.MUTE }, "Usually mischaracterised as a lithium threat. It is more likely lithium-positive on a per-kWh basis."],
      ["Recycling", "Black-mass recovery returning lithium to the chain without new mining.", { t: "Material in the 2030s", c: C.MUTE }, "Constrained by the stock of end-of-life batteries. Today's fleet has not aged enough to supply it at scale."],
      ["Lithium iron phosphate shift", "Cheaper cathode chemistry using less nickel and cobalt but similar lithium.", { t: "Already happening", c: C.SPOD }, "Neutral to positive for spodumene: it shifts demand toward carbonate, which spodumene feeds."],
      ["Thrifting and design", "Less lithium per kWh through cell and pack engineering.", { t: "Continuous", c: C.MUTE }, "Real but incremental, and historically outrun by volume growth."],
    ], { rowH: 0.62, size: 8.5, boldFirstCol: true, rowFill: [C.OCHRE_L, null, null, C.SPOD_L, null] });
    para(s, C.M, cy + 3.42, 12.44, 1.46, "Where this bites our numbers",
      "Sodium-ion is the one we would watch. If it takes a meaningful share of stationary storage before 2030, the demand leg we described " +
      "as structurally independent of vehicle policy becomes partly substitutable, and our long-run price of about US$1,750/t realised is " +
      "too high. Our terminal value is an annuity over sixteen years, so roughly half our enterprise value sits in a period where this risk " +
      "is live.\n\n" +
      "That is a vulnerability and we would rather state it than have a judge find it. The mitigant is that it is a slow risk with " +
      "visible tells - sodium-ion cell cost per kWh and announced storage orders - rather than a sudden one.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.4 });
   }, "Sources: Benchmark Mineral Intelligence; BloombergNEF; IEA. Timelines are the team's read of published roadmaps and are inherently uncertain.");

  // ---------------------------------------------------------------- C1 five forces
  pgC("Porter's five forces applied to hard-rock lithium",
      "Rivalry is brutal and undifferentiated on price. The only defensible position is a cost and provenance position, which is what we are buying.",
   (s, cy) => {
    const forces = [
      ["Rivalry among producers", "HIGH", C.CRIMSON, "A commodity with no product differentiation at the concentrate level. Price is set by the marginal tonne, and the 2023-25 collapse showed how fast it clears."],
      ["Threat of new entrants", "MEDIUM", C.OCHRE, "Capital intensity and permitting are real barriers, but Benchmark says 300-plus new projects are needed by 2035, so entry is expected and funded when prices allow."],
      ["Supplier power", "LOW", C.SPOD, "Mining inputs - fuel, reagents, labour, contractors - are competitive markets. Labour tightness in the Pilbara is the main exception."],
      ["Buyer power", "HIGH", C.CRIMSON, "Concentrated Chinese converters buy most of the world's spodumene at prevailing market prices. This is the force PLS's downstream strategy is designed to reduce."],
      ["Threat of substitutes", "LOW to MEDIUM", C.OCHRE, "Sodium-ion in stationary storage is the credible one, and it is late-decade. Solid-state is more likely lithium-positive."],
    ];
    forces.forEach((f, i) => {
      const y = cy + i * 0.80;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 0.72, fill: { color: i % 2 ? C.MIST2 : C.PAPER }, line: { color: C.RULE, width: 0.6 } });
      s.addText(f[0], { x: C.M + 0.18, y, w: 3.05, h: 0.72, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10.5, bold: true, color: C.INK, valign: "middle" });
      s.addText(f[1], { x: C.M + 3.30, y, w: 1.55, h: 0.72, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: f[2], align: "center", valign: "middle" });
      s.addText(f[3], { x: C.M + 5.00, y: y + 0.05, w: 7.25, h: 0.62, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.8, color: C.TXT, valign: "middle", lineSpacingMultiple: 1.06 });
    });
    para(s, C.M, cy + 4.12, 12.44, 1.06, "The conclusion that follows",
      "Four of the five forces are unattractive or neutral, and the industry structure offers no product differentiation. In an industry " +
      "like that, only two positions survive a full cycle: the lowest-cost quartile, or a position that changes what the buyer is buying. " +
      "PLS is attempting both simultaneously, which is why we own it rather than a diversified major with a lithium division.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Framework: Michael Porter, 'How Competitive Forces Shape Strategy', Harvard Business Review, 1979. Ratings are the team's assessment.");

  // ---------------------------------------------------------------- C2 seven powers
  pgC("Hamilton Helmer's seven powers: PLS satisfies two, partially",
      "We ran the test honestly. A commodity producer does not have many durable powers, and pretending otherwise would be the easiest thing on this deck to puncture.",
   (s, cy) => {
    const powers = [
      ["Scale economies", "PARTIAL", C.OCHRE, "446Mt at 1.28% Li2O and 17.5% mass pull give real fixed-cost dilution. But scale in mining is replicable by anyone with a comparable orebody."],
      ["Network economies", "NO", C.CRIMSON, "Spodumene has no network effect. A tonne is worth the same to the tenth customer as the first."],
      ["Counter-positioning", "PARTIAL", C.OCHRE, "Electric calcination is a business model Chinese converters cannot easily copy without stranding fossil-fired kilns. That is the closest thing here to counter-positioning."],
      ["Switching costs", "NO", C.CRIMSON, "Offtakes are priced at prevailing market. Customers can and do switch suppliers between cargoes."],
      ["Branding", "NO", C.CRIMSON, "There is no brand premium on concentrate. Provenance is a specification, not a brand."],
      ["Cornered resource", "PARTIAL", C.SPOD, "The orebody itself is cornered: 446Mt at that grade in a stable jurisdiction cannot be replicated by a competitor's decision."],
      ["Process power", "NO", C.CRIMSON, "Ore sorting and flotation are available to any operator with the capital. We say this on the ore-sorting slide too."],
    ];
    powers.forEach((p, i) => {
      const y = cy + i * 0.58;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 0.52, fill: { color: i % 2 ? C.MIST2 : C.PAPER }, line: { color: C.RULE, width: 0.6 } });
      s.addText(p[0], { x: C.M + 0.18, y, w: 2.65, h: 0.52, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: C.INK, valign: "middle" });
      s.addText(p[1], { x: C.M + 2.90, y, w: 1.25, h: 0.52, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, bold: true, color: p[2], align: "center", valign: "middle" });
      s.addText(p[3], { x: C.M + 4.30, y: y + 0.03, w: 7.95, h: 0.46, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.6, color: C.TXT, valign: "middle", lineSpacingMultiple: 1.04 });
    });
    para(s, C.M, cy + 4.20, 12.44, 1.02, "Why we still recommend it after failing four of seven",
      "Because we are not claiming a moat. We are claiming a cost position, an orebody that cannot be replicated, and a five-year window " +
      "in which carbon accounting reorders who is allowed to sell into the best markets. That is a temporal advantage, not a permanent " +
      "one, and it is priced accordingly: our target implies 11.7% upside, not a re-rating to a premium multiple.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Framework: Hamilton Helmer, '7 Powers: The Foundations of Business Strategy', 2016. Assessments are the team's.");
};
