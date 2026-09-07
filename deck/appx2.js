// Appendix A5-A11 (assets) and B1-B6 (industry).
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;

module.exports = function (pres, ctx) {
  const A = ctx.A, getA = ctx.getA;
  const fin = (s, n) => foot(s, n, "A" + getA());

  const pg = (tag, title, take, body, src) => {
    const { s, cy } = apage(pres, tag, title, take); A(); body(s, cy); fin(s, src);
  };

  // ---------------- A5 P2000
  pg("A5  Company and assets", "P2000: the largest single value event in the pipeline",
     "A$2.6bn of incremental NPV at pre-feasibility level, a study due in the December 2026 quarter, and A$175m already committed to keep it on schedule.",
   (s, cy) => {
    stat(s, C.M, cy, 2.90, "A$2.6bn", "Incremental NPV", "At pre-feasibility level, June 2024. Not a company target for the final project.", { color: C.SPOD });
    stat(s, C.M + 3.15, cy, 2.90, "55%", "IRR at PFS", "On the same pre-feasibility basis.", { color: C.SPOD });
    stat(s, C.M + 6.30, cy, 2.90, "~A$1.2bn", "Estimated capital", "For a new flotation plant alongside the existing Pilgangoora facilities.", { color: C.INK });
    stat(s, C.M + 9.45, cy, 2.99, "1.9 Mtpa", "Average over 10 years", "At about 5.2% grade, taking total capacity above 2.0Mtpa.", { color: C.INK });
    table(s, C.M, cy + 1.52, [{ t: "Milestone", w: 3.05 }, { t: "Status", w: 2.10, align: "center" }, { t: "Detail", w: 7.29 }], [
      ["Pre-feasibility study", "Complete, Jun 2024", "A$2.6bn incremental NPV, 55% IRR, about A$1.2bn capital, 1.9Mtpa average over the first ten years."],
      ["Pre-FID capital approved", { t: "Approved, Jun 2026", c: C.SPOD, b: true }, "About A$175m for early engineering, long-lead procurement, site preparation and study advancement, explicitly to preserve optionality."],
      ["Definitive feasibility study", { t: "Due Dec-qtr 2026", c: C.OCHRE, b: true }, "Originally flagged for the December 2025 quarter and since moved out a year. Inside our investment horizon."],
      ["Final investment decision", { t: "Not taken", c: C.CRIMSON, b: true }, "Expected late 2026, conditional on study outcomes, funding capacity and market conditions."],
      ["First ore", "Guided mid-2029", "Equivalent to FY30 on PLS's June year end. Our base case assumes 250kt in FY30 ramping to 885kt by FY33."],
      ["Underground option", "Under study", "An underground mining option is being assessed to further improve project economics."],
    ], { rowH: 0.38, size: 8.8, boldFirstCol: true });
    para(s, C.M, cy + 4.24, 12.44, 0.94, "How we treat it, and why we do not simply take the A$2.6bn",
      "The A$2.6bn is a pre-feasibility number from June 2024, struck before the price collapse and recovery. We do not add it to our " +
      "valuation. We model the production profile it implies inside the DCF, so it is exposed to our price deck and our cost " +
      "assumptions rather than the company's. In the risked sum-of-the-parts we carry P2000 at 70%: a study that is due but not " +
      "delivered, and a board that has committed A$175m but not the remaining A$1.0bn.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Sources: PLS P2000 pre-feasibility study announcement, 21 June 2024; PLS pre-FID capital approval, June 2026; FY27 guidance. PFS-level economics carry the usual accuracy range and are superseded by a definitive study.");

  // ---------------- A6 Ngungaju
  pg("A6  Company and assets", "Ngungaju: the swing plant, switched back on",
     "Idled in December 2024 when prices collapsed, restarted in July 2026 when they recovered. It is the clearest evidence that PLS manages capacity to the cycle.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Date", w: 2.05 }, { t: "Event", w: 3.55 }, { t: "What it tells you", w: 6.84 }], [
      ["Dec 2024", "Placed into care and maintenance", "PLS cut production guidance and idled about 200ktpa of capacity rather than sell tonnes below cost into a collapsing market."],
      ["FY25", "Operated Pilgan only", "Production of 755.6kt at A$627/t. The company stayed cash generative at an underlying EBITDA of A$97m through the worst of the cycle."],
      ["2026", "Restart approved", "Cited improved market conditions and ongoing customer demand."],
      ["Jul 2026", { t: "Restarted", c: C.SPOD, b: true }, "Just after the FY26 year end. Steady state targeted within the first four months of FY27."],
      ["FY27", "Guidance 1,030-1,100kt", "A 17-25% volume step-up, with unit costs guided A$575-625/t because Ngungaju tonnes cost more than the Pilgan average."],
    ], { rowH: 0.50, size: 8.8, boldFirstCol: true });
    para(s, C.M, cy + 2.96, 6.10, 2.06, "Why this matters more than the tonnes",
      "Idling capacity is easy to announce and hard to do: it means writing off fixed costs, standing down a workforce and telling " +
      "customers no. PLS did it, held the balance sheet through the trough, bought Latin Resources in scrip at the bottom, and " +
      "restarted when the price justified it.\n\n" +
      "That is the behaviour the cost-curve slide predicts. A producer at the low end of the curve gets to choose when to supply. " +
      "A producer at the high end has the choice made for it.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.2 });
    para(s, C.M + 6.34, cy + 2.96, 6.10, 2.06, "The cost consequence we do not hide",
      "Restarting Ngungaju raises the average unit cost. FY27 guidance of A$575-625/t is above the A$569/t achieved in FY26, and the " +
      "company attributes the step-up to the Ngungaju mix.\n\n" +
      "Our base case uses A$600/t for FY27, the guidance midpoint, falling to A$565/t by the 2030s as P2000 volume dilutes fixed costs. " +
      "In the bear case we assume Ngungaju is throttled back to 120kt from FY30 rather than shut, because a restart-capable plant is " +
      "worth more idle than closed.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.2 });
   }, "Sources: PLS announcements on Ngungaju care and maintenance (December 2024) and restart (2026); FY26 results and FY27 guidance; Australian Mining, 'Ngungaju restart powers PLS towards one-million-tonne FY27'.");

  // ---------------- A7 mid-stream
  pg("A7  Company and assets", "The mid-stream plant: where the level-one thesis becomes a product",
     "100% owned, opened June 2026, first production guided for the September 2026 quarter. It cuts emissions from the most energy-intensive step and moves PLS down the value chain.",
   (s, cy) => {
    stat(s, C.M, cy, 2.90, ">80%", "Cut in calcination emissions", "When the electric kiln is powered by renewables. Calcination is the most energy-intensive step in the chain.", { color: C.SPOD });
    stat(s, C.M + 3.15, cy, 2.90, "5 Jun 2026", "Officially opened", "Attended by the WA Premier and the then-Chair of the Australian Renewable Energy Agency.", { color: C.INK });
    stat(s, C.M + 6.30, cy, 2.90, "Sep-qtr 2026", "First production", "First spodumene calcination and lithium phosphate production. Inside our investment horizon.", { color: C.OCHRE });
    stat(s, C.M + 9.45, cy, 2.99, "A$0.21", "Risked value per share", "Our estimate at a 45% probability, held outside the target price.", { color: C.SPOD });
    card(s, C.M, cy + 1.62, 6.10, 2.32, "What it does", [
      "Calix electric-kiln technology replaces fossil-fired calcination with electric heat that can be renewably powered.",
      "The output is lithium phosphate, a mid-stream product, rather than raw concentrate.",
      "PLS captures conversion margin it currently cedes to third-party converters, most of them Chinese.",
      "Full heat cycles of the electric calciner were completed successfully as at the July 2026 quarterly, demonstrating design-spec power draw and heating range.",
      "Supported by the Australian Renewable Energy Agency; the exact grant amount was not found in our sources.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 8.8 });
    card(s, C.M + 6.34, cy + 1.62, 6.10, 2.32, "Why we still carry it outside the target", [
      "It is a demonstration plant. Nothing at demonstration scale is a revenue line until it produces.",
      "First production is guided for the current quarter, so we are one quarterly report away from knowing.",
      "Scale-up beyond the demonstration unit is not funded and not announced.",
      "We therefore size it at A$1,536m unrisked, apply a 45% probability, and keep the resulting A$0.21 per share out of the A$6.14 target.",
      "If it works, this is the single most important thing PLS does this decade, because it converts an ESG claim into a product specification.",
    ], { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 8.8 });
   }, "Sources: PLS and Calix announcements; ARENA, 'ARENA backs low emissions lithium refining in WA'; PLS June-2026 quarterly activities report. The >80% figure is the reduction in calcination emissions specifically, not in PLS's total footprint.");

  // ---------------- A8 POSCO
  pg("A8  Company and assets", "The POSCO joint venture: a non-China conversion route",
     "18% of a 43,000 tonne per year lithium hydroxide plant in Korea, with an option to lift the stake to 30%. Small in earnings, strategically disproportionate.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "", w: 3.05 }, { t: "", w: 9.39 }], [
      ["Vehicle", "POSCO Pilbara Lithium Solution, Gwangyang, South Korea"],
      ["Ownership", "POSCO Holdings 82%, PLS Group 18%, with a PLS option to increase to 30% at any time up to 18 months after Train 2 reaches 90% of nameplate"],
      ["Capacity", "Two trains, 43,000 tonnes per year of lithium hydroxide monohydrate combined - described as enough for roughly one million electric vehicles a year"],
      ["Status", "Train 1 began ramping in 2024; Train 2 construction complete and ramping over 12-18 months post-commissioning"],
      ["Feedstock", "PLS supplies spodumene concentrate from Pilgangoora under a long-term arrangement"],
      ["Why it matters", "It is a conversion route that is not in China, at the moment US foreign-entity-of-concern rules and EU provenance requirements are making that a purchasing criterion"],
      ["What we could not verify", "Whether any impairment or writedown has been taken on the investment. We searched and found none, but treat that as unconfirmed rather than as evidence of none"],
    ], { rowH: 0.42, size: 8.8, boldFirstCol: true, headH: 0.01,
         rowFill: [null,null,null,null,null,C.SPOD_L,C.OCHRE_L] });
    para(s, C.M, cy + 3.20, 12.44, 1.98, "How we value it, and why the option to 30% matters more than the 18%",
      "We size the joint venture at 43,000 tonnes a year, an assumed A$4,200 per tonne conversion margin and an 18% share, giving about " +
      "A$32.5m of attributable EBITDA, capitalised at 8x for A$260m and risked at 70% - the lowest risking of the three downstream " +
      "levers, because both trains are built. That is A$0.06 per share, which is not why this asset matters.\n\n" +
      "It matters because it is a call option on Korean conversion capacity struck before provenance became a purchasing criterion. " +
      "Lifting the stake from 18% to 30% would raise attributable earnings by two thirds at a price agreed years ago. We have not " +
      "valued that option, which makes our downstream number conservative.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Sources: POSCO Newsroom; PLS announcements; KED Global; chemengonline.com. Conversion margin is the team's assumption; PLS does not disclose joint-venture unit economics.");

  // ---------------- A9 Colina
  pg("A9  Company and assets", "Colina, Brazil: a second jurisdiction, a decade out",
     "Acquired in all-scrip at the bottom of the cycle. Real optionality, but no final investment decision, no permits and no production before the 2030s on our numbers.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "", w: 3.05 }, { t: "", w: 9.39 }], [
      ["How PLS got it", "Takeover of Latin Resources, announced 15 August 2024, legally effective January 2025. All scrip at 0.07 PLS shares per Latin share, about A$560m implied"],
      ["Why all-scrip mattered", "It preserved PLS's net-cash position through the trough. No cash left the balance sheet to buy a second orebody"],
      ["Resource", "77.7Mt at 1.24% Li2O, carried over from Latin Resources. We could not confirm any update since acquisition"],
      ["Location", "Salinas, Minas Gerais, in the Vale do Jequitinhonha - Brazil's so-called Lithium Valley"],
      ["Feasibility study", "Outcomes targeted for the December 2027 quarter"],
      ["Final investment decision", "Not taken. PLS says it will consider one after studies, exploration and permitting, taking market conditions into account"],
      ["FY27 spend", "A$45-55m"],
      ["Since year end", "About A$50m spent acquiring tenements adjacent to Colina from Lithium Ionic"],
      ["Community", "Company messaging cites roughly 300 direct and indirect jobs via the revitalisation of a flour factory - a level-three cluster initiative"],
    ], { rowH: 0.345, size: 8.6, boldFirstCol: true, headH: 0.01 });
    para(s, C.M, cy + 3.35, 6.10, 1.30, "Our treatment",
      "First production assumed FY32, ramping to about 500ktpa by FY35. This is our modelling assumption and not a company target - PLS " +
      "has not adopted Latin Resources' original 2026 first-production plan. In the sum-of-the-parts we risk Colina at 40%, the harshest " +
      "risking we apply to any asset, because the study is more than a year away.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9 });
    para(s, C.M + 6.34, cy + 3.35, 6.10, 1.30, "The shared-value angle we did not overstate",
      "The Jequitinhonha valley is one of Brazil's poorest regions, and a flour-factory revitalisation supporting 300 jobs is a genuine " +
      "cluster investment in Porter and Kramer's third sense. It is also, at this stage, a company claim we could not independently " +
      "verify, and it contributes nothing to the valuation. We report it as evidence of intent, not of impact.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
   }, "Sources: PLS and Latin Resources announcements; mining.com.au; mining.com. The 77.7Mt resource is as reported by Latin Resources pre-acquisition; we found no restatement under PLS ownership.");

  // ---------------- A10 offtake
  pg("A10  Company and assets", "The offtake book: spot-linked, and that cuts both ways",
     "PLS sells at prevailing market prices rather than under fixed-price contracts. It captured the recovery in full, and it would capture a relapse in full too.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Counterparty", w: 2.65 }, { t: "Terms as disclosed", w: 5.20 },
      { t: "Pricing mechanism", w: 4.59 }], [
      ["Ganfeng Lithium", "Original 2017 agreement for 160ktpa. Amended January 2024: 310kt in 2024, a further 100kt in 2025 with an option to 150kt, and 100kt in 2026 with an option to 150kt", "Prevailing market price"],
      ["Chengxin Lithium", "85kt in 2024, 150kt in 2025, 150kt in 2026", "Prevailing market price"],
      ["Sichuan Yahua", "Three-year deal: 20-80kt in 2024, then 100-160kt in each of 2025 and 2026", "Not disclosed in our sources"],
      ["Canmax", "150ktpa with an option to increase, described as a two-year agreement", "Not disclosed in our sources"],
      ["POSCO", "Long-term concentrate feedstock into the Gwangyang joint venture", "Linked to joint-venture requirements"],
      ["Yibin Tianyi", "An additional spodumene offtake was signed; tonnage not disclosed in our sources", "Not disclosed"],
    ], { rowH: 0.52, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 3.50, 6.10, 1.70, "What spot linkage did in FY26",
      "Realised prices moved from US$742/t in the September 2025 quarter to US$2,107/t in the June 2026 quarter, a factor of 2.8 inside " +
      "one financial year. A fixed-price book would have muted both the collapse and the recovery. PLS took the full force of each.\n\n" +
      "Grade normalisation is confirmed in the company's own reporting: it discloses both an actual-grade and an SC6-equivalent realised " +
      "price, so contracts are Li2O-linked to the industry benchmark.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 6.34, cy + 3.55, 6.10, 1.42, "What we could not establish",
      "We could not find the exact contractual formula - whether grade adjustment is linear or stepped, which index is referenced, or " +
      "whether an M+1 pricing lag applies. Several sources describe pricing simply as prevailing market price. We have therefore modelled " +
      "realisation as a single blended price per tonne with a freight and timing adjustment calibrated to reported revenue, rather than " +
      "pretending to a contract-level precision we do not have.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
   }, "Sources: smallcaps.com.au; mining.com; miningweekly.com; capitalbrief.com; fastmarkets.com; mysteel.net; PLS quarterly activities reports. Where a term is marked not disclosed, it was searched for and not found.");

  // ---------------- A11 board and management
  pg("A11  Company and assets", "Board and management",
     "A chair with rare-earths experience, a chief executive who has run the company through a full cycle, and a dedicated Sustainability Committee at board level.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Name", w: 2.55 }, { t: "Role", w: 3.10 }, { t: "Since", w: 1.25, align: "center" },
      { t: "Background", w: 5.54 }], [
      ["Kathleen Conlon", "Non-Executive Chair", "Feb 2024", "Recently retired Chair of Lynas Rare Earths; non-executive director of Aristocrat Leisure and BlueScope Steel."],
      ["Dale Henderson", "Managing Director and CEO", "Jul 2022", "Ran the company through the 2023-25 collapse and the 2026 recovery. Succeeded Ken Brinsden."],
      ["Sally-Anne Layman", "Non-Executive Director", "Apr 2018", "Chairs the Sustainability Committee; sits on Audit and Risk; director of Beach Energy."],
      ["Nicholas Cernotta", "Non-Executive Director", "Feb 2017", "Chairs the People and Culture Committee; member of the Sustainability Committee."],
      ["Stephen Scudamore", "Independent Non-Executive Director", "Not confirmed", "30 years with KPMG; non-executive director of Australis Oil & Gas and Regis Resources."],
    ], { rowH: 0.50, size: 8.8, boldFirstCol: true });
    para(s, C.M, cy + 3.02, 6.10, 1.62, "What the structure tells us",
      "A named board Sustainability Committee, chaired by a long-tenured director who also sits on Audit and Risk, is a better signal " +
      "than a sustainability report. It means ESG matters reach the board through a standing committee with a member who sees the " +
      "financial reporting.\n\n" +
      "The chair's Lynas background is directly relevant: rare earths is the one other Australian critical-minerals sector that has had " +
      "to argue provenance and processing to non-Chinese customers.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    para(s, C.M + 6.34, cy + 3.02, 6.10, 2.16, "What we could not confirm",
      "Multiple sources describe the board as six members - five independent non-executive directors plus the chief executive - but we " +
      "could positively identify only the five people listed. At least one director's identity could not be confirmed from the sources " +
      "available to us, and company websites were not reachable from our research environment.\n\n" +
      "We also could not verify whether ESG or sustainability metrics carry explicit weightings in short or long-term incentive " +
      "scorecards. That is a material gap for a shared-value thesis and is listed in the gaps register.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
   }, "Sources: Capital Brief; Mining Magazine; Mining Weekly; businessnews.com.au. PLS's own board page and 2025 Corporate Governance Statement were identified but could not be opened from our environment.");
};
