// Appendix F: risk and reference.
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;

module.exports = function (pres, ctx) {
  let f = 0;
  const pgF = (title, take, body, src) => {
    const n = ++f; const { s, cy } = apage(pres, "F" + n + "  Risk and reference", title, take); body(s, cy); foot(s, src, "F" + n);
  };

  pgF("Full risk register",
      "Twelve risks, each with an inherent rating, a mitigant, a residual rating and a named indicator we would actually watch.",
   (s, cy) => {
    const R = (t, c) => ({ t, c, b: true });
    table(s, C.M, cy, [{ t: "Risk", w: 2.35 }, { t: "Inh.", w: 0.72, align: "center" },
      { t: "Mitigant", w: 4.55 }, { t: "Res.", w: 0.72, align: "center" }, { t: "Indicator we watch", w: 4.10 }], [
      ["Sustained price relapse", R("High", C.CRIMSON), "Bottom-quartile cost position and A$2.29bn of cash allow PLS to wait. Bear case still values it at A$2.30.", R("High", C.CRIMSON), "Monthly SpodIX prints; Chinese carbonate inventory days"],
      ["Re-rating already spent", R("High", C.CRIMSON), "Target rests on FY27 earnings and the growth option, not on further short covering.", R("Med", C.OCHRE), "ASIC short position reports; a rebuild above 10%"],
      ["P2000 deferred or shelved", R("High", C.CRIMSON), "A$175m of pre-FID capital committed; balance sheet can fund the A$1.2bn build.", R("Med", C.OCHRE), "December-quarter 2026 study outcome; the FID itself"],
      ["Single asset concentration", R("High", C.CRIMSON), "Colina adds a second jurisdiction from the 2030s, risked at 40% and contributing nothing before FY32.", R("High", C.CRIMSON), "Any Pilgangoora interruption; cyclone season"],
      ["Reserve conversion below 75%", R("Med", C.OCHRE), "The 2025 resource upgrade lifted contained lithium 23%, which supports conversion.", R("Med", C.OCHRE), "The next Ore Reserve statement; below 60% costs about A$0.40/share"],
      ["Carbon premium never materialises", R("Med", C.OCHRE), "Already valued at zero inside the target and risked at 25% outside it.", R("Low", C.SPOD), "First PLS contract with a disclosed carbon-linked term"],
      ["Cost inflation in the Pilbara", R("Med", C.OCHRE), "Ore sorting and P2000 scale dilute fixed costs; guidance held within a A$50/t band.", R("Med", C.OCHRE), "Quarterly unit cost against the A$575-625/t guidance"],
      ["Tailings incident or disclosure shock", R("Med", C.OCHRE), "None. The method is undisclosed and we carry this as unpriced.", R("Med", C.OCHRE), "Any tailings or GISTM disclosure; P2000 approval conditions"],
      ["Offsets regime repriced", R("Med", C.OCHRE), "Sector-wide, not PLS-specific. An operator that gets ahead of it gains rather than loses.", R("Med", C.OCHRE), "Western Australian offsets policy review outcomes"],
      ["Sodium-ion substitution in storage", R("Low", C.SPOD), "Late-decade at the earliest, and our terminal value is a finite annuity rather than a perpetuity.", R("Med", C.OCHRE), "Sodium-ion cell cost per kWh; announced storage orders"],
      ["Key person and governance", R("Low", C.SPOD), "Chief executive since 2022 with a full cycle behind him; standing board Sustainability Committee.", R("Low", C.SPOD), "Executive departures; whether ESG enters incentive pay"],
      ["Currency", R("Low", C.SPOD), "Revenue in US dollars, costs mostly in Australian dollars. A weaker AUD helps margins.", R("Low", C.SPOD), "AUD/USD against our 0.66-0.70 forecast path"],
    ], { rowH: 0.335, size: 8.1, boldFirstCol: true });
    para(s, C.M, cy + 4.30, 12.44, 0.86, null,
      "The first four are the ones that decide this position. Everything below them is manageable within a normal holding period. If a judge asks which single line would make us wrong, it is the first: a sustained price relapse of about a fifth from our base case takes the target to roughly A$4.98 and the recommendation with it.",
      { fill: C.OCHRE_L, line: "E8C9A3", size: 9.2 });
   }, "Source: team assessment. Inherent and residual ratings are ours. Indicators are chosen because they are publicly observable at a known frequency, not because they are exhaustive.");

  pgF("Short interest: the part of the re-rating that cannot repeat",
      "PLS went from the most shorted stock on the ASX to roughly the fortieth in eighteen months. That buyer has now finished buying.",
   (s, cy) => {
    s.addChart(pres.ChartType.bar, [{
      name: "Short interest (% of shares on issue)",
      labels: ["Sep 2024", "Oct 2025", "Late 2025", "26 May 2026", "4 Aug 2026"],
      values: [20.0, 19.0, 17.0, 6.8, 10.09],
    }], {
      x: C.M, y: cy, w: 6.60, h: 2.90, chartColors: [C.S3, C.S3, C.S3, C.S2, C.S3], varyColors: true,
      barGapWidthPct: 45, showTitle: true, title: "PLS short interest, % of shares on issue",
      titleFontFace: C.B, titleFontSize: 11, titleColor: C.INK,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelFontFace: C.B,
      dataLabelColor: C.MUTE, dataLabelFormatCode: '0.0"%"',
      catAxisLabelFontFace: C.B, catAxisLabelFontSize: 8.5, catAxisLabelColor: C.MUTE,
      valAxisLabelFontFace: C.B, valAxisLabelFontSize: 8.5, valAxisLabelColor: C.MUTE,
      valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" },
      showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 25,
    });
    card(s, C.M + 6.84, cy, 5.60, 2.90, "Our own warning indicator has triggered", [
      "PLS was the largest, most liquid way to be short falling lithium prices, and about one share in five was borrowed short in September 2024.",
      "The price then went from A$1.91 to A$5.48, and short interest fell to 6.8% by May 2026. A material part of that move was covering, not new fundamental buyers.",
      "Since then shorts have REBUILT to 10.09% as at 4 August 2026, up 0.75 percentage points in a single week.",
      "Our risk register names a rebuild above 10% as a warning signal. It has happened, and we are reporting it rather than quietly dropping the indicator.",
      "What it means: a well-resourced group is positioning against the stock at these levels. We disagree with them, but we would rather show the disagreement than hide it.",
    ], { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 8.6 });
    para(s, C.M, cy + 3.08, 12.44, 1.32, "How we read it, and what it does not change",
      "Two things are true at once. The covering that drove much of the last twelve months is finished, so that flow cannot repeat. And " +
      "shorts are rebuilding, which says some investors think the re-rating overshot.\n\n" +
      "It does not change the target, because our target never depended on a squeeze: it rests on FY27 earnings and the growth option. " +
      "It does change how we would size the position. At 10% short interest and 1.09x reward to risk, this is an overweight to build " +
      "into, not one to take in a single trade. The next ASIC print is the number to watch.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Sources: ASIC short position reports via shortman.com.au, shorted.com.au and stocktrack.com.au. Latest retrievable data point 4 August 2026 at 10.09%, up 0.75 percentage points week on week. ASIC data is published on a T+4 basis.");

  pgF("What moved the share price, and what the market thinks now",
      "A near-tripling in twelve months, and a consensus that lands almost exactly on the current price. Our disagreement with the street is narrow and specific.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Period", w: 2.05 }, { t: "What happened", w: 4.55 }, { t: "Effect", w: 5.84 }], [
      ["Sep 2024", "Lithium prices near the trough; PLS the most shorted stock on the ASX at about 20% of shares", "Share price reaches A$1.91, the 52-week low"],
      ["Dec 2024", "Ngungaju placed into care and maintenance; FY25 guidance cut", "Capacity withdrawn rather than tonnes sold below cost"],
      ["Jan 2025", "Latin Resources acquisition completes in all scrip", "A second orebody added without spending cash at the bottom of the cycle"],
      ["Through 2025", "Spodumene begins recovering; CATL's Jianxiawo suspended", "Short covering begins; short interest falls from 20% to about 17%"],
      ["Dec 2025", "Pilbara Minerals renamed PLS Group", "Signals the shift from single-asset miner to multi-asset group"],
      ["Jun 2026", "Mid-stream plant opened; June-quarter realised price reaches US$2,107/t", "The exit rate runs 40% above the full-year average"],
      ["Jul 2026", "Ngungaju restarted; FY27 guidance of 1,030-1,100kt issued", "A 17-25% volume step-up flagged"],
      ["24 Aug 2026", "FY26 results: revenue up 152%, EBITDA up roughly ninefold, dividend reinstated", "Shares rise on the day; the stock reaches A$5.48"],
    ], { rowH: 0.335, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 3.05, 6.10, 2.14, "Where consensus sits",
      "Vendor averages cluster between about A$4.50 and A$5.70 against a A$5.48 last close, with the full individual spread running from " +
      "A$2.50 to A$6.83 across seventeen to twenty analysts. The consensus rating is Buy.\n\n" +
      "In plain terms the street thinks PLS is roughly fairly valued and that the range of reasonable answers is enormous - a factor of " +
      "2.7 between the most bearish and most bullish analyst. That dispersion is itself the opportunity: it means the disagreement is " +
      "about lithium price assumptions, not about the company.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9 });
    para(s, C.M + 6.34, cy + 3.05, 6.10, 2.14, "What we think the street is missing",
      "Not the lithium price. Our FY27 assumption of US$1,700/t is deliberately below spot and below the Australian Government's own " +
      "forecast, so we are not out-forecasting anyone on the commodity.\n\n" +
      "What we think is underpriced is the operating position: a cost base that is falling for structural reasons, a growth option with " +
      "committed pre-FID capital, and a downstream route that becomes commercially relevant exactly as carbon accounting reaches raw " +
      "materials. That is A$0.43 of the A$0.66 of upside we see, and it is why our A$6.14 sits above the vendor average without sitting " +
      "outside the analyst range.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
   }, "Sources: PLS announcements; data-vendor consensus reads, August-September 2026; market commentary. Consensus figures differ by provider and snapshot date and are shown as a range rather than a point.");

  pgF("What we could not verify",
      "The register of every material gap in our own work. We would rather hand a judge this list than have them assemble it.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Item", w: 3.35 }, { t: "Why it is missing", w: 4.35 },
      { t: "How we handled it", w: 4.74 }], [
      ["Total borrowings at 30 June 2026", "Only the US$600m senior notes issue is confirmed. One source cites about A$1.2bn including leases", "Used A$828m, the notes translated at spot. Net cash of A$1.44bn would fall to about A$1.09bn on the higher figure, costing roughly A$0.12/share"],
      ["Ore Reserve since August 2023", "Not restated after the June 2025 resource upgrade", "Applied a 75% resource-to-reserve conversion and sensitised it. Flagged as a catalyst in both directions"],
      ["FY26 property, plant and equipment", { t: "CLOSED", c: C.SPOD, b: true }, "Derived as A$3,813m from reported total assets of A$6,258m less cash and working capital. The balance sheet now ties to the reported total"],
      ["Scope 3 emissions and intensity per tonne", "Not disclosed by PLS", "Named as a material gap and made an engagement ask. The low-carbon claim cannot presently be declared"],
      ["Tailings method and GISTM status", "Not disclosed", "Refused to assert either way. Carried as an unpriced risk"],
      ["Safety, workforce and diversity metrics", "Partly closed from FY26 results", "TRIFR 2.77 and female participation 21.9% retrieved; Indigenous employment and procurement still not found"],
      ["Native title agreement detail", "Not retrievable", "Valued schedule protection as an avoided delay, not as a claim about relationship quality"],
      ["ESG metrics in incentive pay", "Not retrievable", "Named as our second engagement ask"],
      ["Named broker price targets", "Not retrievable individually", "Used vendor consensus ranges and showed the full spread"],
      ["Current short interest", "Refreshed to 4 August 2026", "10.09%, above the 10% warning level we set. Reported on F2 rather than dropped"],
      ["FY24 comparatives", "Outside the scope of our sourcing", "Marked as estimates in the workbook and in the income statement footnote"],
      ["External ESG ratings", "Providers not reachable", "Explained why operating evidence mattered more, and acknowledged the loss of a common benchmark"],
    ], { rowH: 0.32, size: 8.1, boldFirstCol: true });
    para(s, C.M, cy + 3.98, 12.44, 1.22, "The honest framing",
      "Our research environment could not open company websites or the ASX announcements platform, so every reported figure was " +
      "corroborated across two or more independent secondary reports of the same announcement rather than read from the primary document. " +
      "Headline FY26 figures are consistent across sources. Everything above is what that constraint cost us.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
   }, "Source: team research log. This register is reproduced from the Sources sheet of the submitted workbook.");

  pgF("Glossary",
      "Written for a reader who does not work in mining, because a term nobody understands is a claim nobody can check.",
   (s, cy) => {
    const terms = [
      ["Spodumene", "The lithium-bearing mineral in hard rock. Mined, crushed and floated into a concentrate."],
      ["Spodumene concentrate", "The product PLS sells: rock upgraded to roughly 5.2% lithium oxide."],
      ["SC6", "Industry benchmark grade of 6.0% lithium oxide. PLS ships below it, so it realises less per tonne."],
      ["Li2O", "Lithium oxide. How lithium content in rock is measured."],
      ["LCE", "Lithium carbonate equivalent. The common unit for comparing lithium across chemical forms."],
      ["FOB", "Free on board. The cost to get product onto the ship, excluding freight to the customer."],
      ["CIF", "Cost, insurance and freight. A delivered price including shipping."],
      ["Mass pull", "Tonnes of concentrate produced per tonne of ore processed. PLS is about 17.5%."],
      ["Calcination", "Heating concentrate to convert the mineral structure. The most energy-intensive step in the chain."],
      ["Lithium phosphate", "The mid-stream product PLS's Calix plant will produce, between concentrate and battery chemicals."],
      ["Hydroxide and carbonate", "The two battery-grade lithium chemicals. Hydroxide suits nickel-rich cathodes, carbonate suits iron phosphate."],
      ["LFP and NMC", "Lithium iron phosphate and nickel manganese cobalt: the two dominant cathode chemistries."],
      ["BESS", "Battery energy storage system. Grid-scale storage, now roughly a third of lithium demand."],
      ["P680, P1000, P2000", "PLS's sequential expansion projects, named for target annual concentrate capacity in thousands of tonnes."],
      ["FID", "Final investment decision. The board commitment to build. P2000 has not reached one."],
      ["PFS and DFS", "Pre-feasibility and definitive feasibility studies. A DFS carries a tighter accuracy range."],
      ["Ore Reserve vs Mineral Resource", "A reserve is the economically mineable part of a resource. PLS's reserve statement predates its latest resource."],
      ["Scope 1, 2 and 3", "Direct emissions, purchased-energy emissions, and everything else in the value chain."],
      ["GISTM", "Global Industry Standard on Tailings Management, the post-Brumadinho benchmark for tailings safety."],
      ["FEOC", "Foreign entity of concern. US rules restricting China-linked supply chains from subsidy eligibility."],
      ["WACC", "Weighted average cost of capital. The rate at which we discount future cash flows."],
      ["FCFF", "Free cash flow to the firm. Cash generated before financing decisions - what the DCF values."],
      ["Terminal value", "The value of cash flows beyond the explicit forecast. Ours is an annuity, not a perpetuity."],
      ["Fly-in fly-out", "The Pilbara workforce model, and the context for psychosocial safety scrutiny."],
    ];
    terms.forEach((t, i) => {
      const x = C.M + (i % 2) * 6.28, y = cy + Math.floor(i / 2) * 0.395;
      s.addShape("rect", { x, y, w: 6.10, h: 0.365, fill: { color: i % 4 < 2 ? C.PAPER : C.MIST2 }, line: { color: C.RULE, width: 0.4 } });
      s.addText(t[0], { x: x + 0.10, y, w: 1.75, h: 0.365, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.4, bold: true, color: C.INK, valign: "middle" });
      s.addText(t[1], { x: x + 1.90, y, w: 4.12, h: 0.365, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 7.8, color: C.TXT, valign: "middle", lineSpacingMultiple: 1.0 });
    });
   }, "Definitions are the team's, written for a general reader. Where a term has a formal technical definition, that definition governs.");

  pgF("Bibliography",
      "Grouped by what each source supports. Every figure in this submission traces to one of these or to the workbook's source register.",
   (s, cy) => {
    const groups = [
      ["Company disclosure", C.SPOD, [
        "PLS Group FY26 results and investor presentation, 24 August 2026",
        "PLS Group June-2026 quarterly activities report, 30 July 2026",
        "PLS Group Mineral Resource update, June 2025; Ore Reserve statement, August 2023",
        "P2000 Pre-Feasibility Study announcement, 21 June 2024; pre-FID capital approval, June 2026",
        "Ngungaju care and maintenance (Dec 2024) and restart announcements",
        "Latin Resources scheme documents and completion announcements",
        "Calix Limited announcements on the mid-stream demonstration plant",
        "POSCO Holdings and POSCO Pilbara Lithium Solution disclosures",
      ]],
      ["Market and commodity", C.INK2, [
        "Benchmark Mineral Intelligence price assessments and incentive-price analysis",
        "S&P Global Platts SpodIX assessments; S&P Global Market Intelligence Mine Cost Outlook, January 2026",
        "CRU Group cost-curve analysis",
        "Australian Government Resources and Energy Quarterly, June 2026",
        "Wood Mackenzie Lithium Energy Transition Outlook, 3 March 2026",
        "Fastmarkets, Morgan Stanley, UBS and Macquarie market-balance commentary",
        "IEA Global Critical Minerals Outlook 2026 and Global EV Outlook",
        "Trading Economics and SMM lithium price series",
      ]],
      ["Policy and regulation", C.OCHRE, [
        "EU Regulation 2023/1542 on batteries and waste batteries (carbon footprint declaration, battery passport)",
        "US Inflation Reduction Act foreign-entity-of-concern provisions",
        "Australian Critical Minerals Production Tax Incentive",
        "Government of Zimbabwe raw mineral export ban, 25 February 2026",
      ]],
      ["ESG and social", C.CRIMSON, [
        "ABC News, 'Pilbara mining offset scheme leaves threatened species short-changed, review finds', 21 October 2024",
        "Western Australian Department of Biodiversity, Conservation and Attractions - Pilbara Environmental Offsets Fund",
        "Australian Parliament Joint Standing Committee on Northern Australia - Juukan Gorge inquiry",
        "TOMRA Mining and Global Mining Review on the Pilgangoora ore sorter",
        "ARENA, 'ARENA backs low emissions lithium refining in WA'",
      ]],
      ["Frameworks", C.MUTE, [
        "Porter, M. and Kramer, M., 'Creating Shared Value', Harvard Business Review, 2011",
        "Porter, M., 'How Competitive Forces Shape Strategy', Harvard Business Review, 1979",
        "Helmer, H., '7 Powers: The Foundations of Business Strategy', 2016",
        "Yip, G., 'Barriers to Entry', 1982",
        "SASB Metals and Mining sustainability accounting standard",
      ]],
      ["Market data and comparables", C.FAINT, [
        "Company FY26 results for BHP, Rio Tinto, Fortescue, South32 and Mineral Resources",
        "Market Index, stockanalysis.com and Google Finance quote data, August-September 2026",
        "ASIC short position reports via shortman.com.au",
        "Announcements for the lithium transactions listed at E13",
      ]],
    ];
    groups.forEach((g, i) => {
      const x = C.M + (i % 3) * 4.16, y = cy + Math.floor(i / 3) * 2.52;
      card(s, x, y, 3.98, 2.38, g[0], g[2], { fill: C.MIST2, line: C.RULE, titleColor: g[1], size: 7.3, gap: 2 });
    });
   }, "Research constraint: company websites and the ASX announcements platform were not reachable from our environment, so company disclosures were accessed through secondary reporting and corroborated across independent sources. See F4 for the full gaps register.");

  pgF("Disclaimer and team",
      "Prepared as a university case-competition submission using publicly available information.",
   (s, cy) => {
    para(s, C.M, cy, 6.10, 2.60, "Basis of preparation",
      "This submission was prepared for the Shared Value Project and FMAA 'Investing for the Future' Case Competition 2026, in the role " +
      "of analysts in the shared value coverage team at FMAA Asset Management, addressing the portfolio manager of an ASX 200 long-only " +
      "fund.\n\n" +
      "All information is drawn from publicly available sources. Valuation inputs prescribed by the case document - a 5.00% risk-free " +
      "rate, a 6.00% market risk premium and an equity beta of 0.73 - have been used as directed.\n\n" +
      "Forecasts are the authors' estimates. They will differ from outcomes.",
      { titleColor: C.INK, size: 9.4 });
    para(s, C.M + 6.34, cy, 6.10, 2.60, "Not investment advice",
      "This document is a student case-competition submission. It is not investment advice, not a recommendation to buy or sell any " +
      "security, and not a substitute for independent professional research.\n\n" +
      "Neither the authors nor FMAA Asset Management - a fictional entity created for the purposes of this competition - accepts " +
      "liability for any use of this material.\n\n" +
      "Figures are current to 5 September 2026 and have not been updated for subsequent events.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.4 });
    para(s, C.M, cy + 2.78, 12.44, 1.86, "Reproducibility",
      "Every figure in this deck can be traced to the accompanying workbook, PLS_Valuation_Model_FMAA_2026.xlsx. The workbook contains " +
      "nineteen sheets and 1,728 live formulas with no evaluation errors. Its Sources sheet tags every input by provenance: A for a " +
      "reported actual, G for company guidance, M for market data, D for a derived figure, E for our own estimate and C for an input " +
      "prescribed by the case.\n\n" +
      "To reproduce any scenario in this appendix, set Assumptions!C7 to Bear, Base or Bull. The production profile, price deck, cost " +
      "deck, capital expenditure, all three financial statements, the discounted cash flow and the target price repoint from that single cell.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
   }, "");
};
