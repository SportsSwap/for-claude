// Appendix D3-D11: ESG deep dive.
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;

module.exports = function (pres, ctx) {
  let d = 2;
  const pgD = (title, take, body, src) => {
    const n = ++d; const { s, cy } = apage(pres, "D" + n + "  ESG and shared value", title, take);
    body(s, cy); foot(s, src, "D" + n);
  };

  pgD("Power strategy: the lever that shows up in the cost line",
      "Diesel to gas is done. Solar and storage are planned. Wind is aspirational. We have valued the first, part-valued the second and ignored the third.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Element", w: 2.85 }, { t: "Status", w: 2.05, align: "center" },
      { t: "Detail", w: 4.15 }, { t: "How we treat it", w: 3.39 }], [
      ["Gas gensets and LNG storage", { t: "Installed", c: C.SPOD, b: true }, "Eight new gas gensets plus LNG storage, displacing diesel generation at Pilgangoora.", "Inside the A$569/t FY26 cost base. Attributed within our A$18/t estimate."],
      ["Battery energy storage", { t: "Planned", c: C.OCHRE, b: true }, "A lithium-ion system to support future solar generation - PLS storing its own product on its own site.", "Partly reflected in the FY27-onward cost path. Not separately valued."],
      ["Solar generation", { t: "Planned", c: C.OCHRE, b: true }, "Named in the power strategy as the route to the 2027 intensity target.", "Same."],
      ["Wind", { t: "Conditional", c: C.CRIMSON, b: true }, "PLS says up to 80% intensity reduction by 2030 IS POSSIBLE if regional wind becomes available. It is not a committed project.", "Excluded entirely. We do not model conditional infrastructure."],
      ["Camp microgrid", { t: "Operating", c: C.SPOD, b: true }, "A GenOffGrid microgrid cutting emissions by more than 36%, about 529 tonnes CO2e a year, displacing roughly 200,000 litres of diesel.", "Noted but immaterial: 529 tonnes against site emissions in the hundreds of thousands."],
      ["Electric haul fleet", { t: "Not found", c: C.CRIMSON, b: true }, "No electric haul truck or trolley-assist programme was found, while Fortescue runs public programmes.", "Treated as a gap and an upside lever PLS has not pulled."],
    ], { rowH: 0.57, size: 8.4, boldFirstCol: true });
    para(s, C.M, cy + 3.80, 12.44, 1.24, "The discipline we applied to this page",
      "It would have been easy to add the 80% by 2030 figure to the bridge and claim a larger shared-value number. We did not, because " +
      "that target is explicitly conditional on wind that does not yet exist in the region. Equally, we could have presented the camp " +
      "microgrid's 529 tonnes as evidence of decarbonisation; it is roughly 0.3% of site emissions on the best aggregator estimate we " +
      "found, and presenting it as more would be exactly the greenwashing this case asks us to detect.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: PLS power strategy disclosures; pilbaraminerals.com.au news releases; GenOffGrid; mining.com.au. The Alinta Energy hybrid project that appears in searches relates to Fortescue's Newman operations, not PLS, and we have not attributed it here.");

  pgD("Ore sorting as a shared-value case study",
      "Worked through properly, because this is the one lever where the environmental and financial mechanisms are provably the same mechanism.",
   (s, cy) => {
    const steps = [
      ["The problem", "Milling and flotation are the energy-intensive steps. Every tonne of barren rock that enters them consumes power, water and reagents for no lithium."],
      ["The intervention", "A TOMRA sensor-based sorter, over 1,000 tonnes per hour, installed in the A$103m P680 project and commissioned in August 2024. Rock is scanned and waste ejected before it reaches the plant."],
      ["The environmental outcome", "Less ore milled per tonne of contained lithium means less energy per tonne of product, and waste that never enters the plant never enters the tailings stream."],
      ["The financial outcome", "FY26 unit costs fell A$58/t, from A$627 to A$569, while volumes rose 17%. We attribute roughly half the fall to volume scale and half - about A$29/t - to sorting and associated processing gains."],
      ["The shared-value test", "Would PLS have done it without an ESG rationale? Almost certainly yes. That does not disqualify it under Porter and Kramer's second level - which is precisely about solving environmental problems in ways that lower cost - but it does mean it is not a differentiator. Any competitor can buy a sorter."],
      ["The valuation treatment", "A$30/t multiplied by the model's coefficient of A$20.5m of equity value per A$1/t gives A$614m, or A$0.19 per share. It is attributed from the existing valuation, not added to it."],
    ];
    steps.forEach((st, i) => {
      const y = cy + i * 0.66;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 0.60,
        fill: { color: i === 4 ? C.OCHRE_L : (i % 2 ? C.MIST2 : C.PAPER) }, line: { color: C.RULE, width: 0.6 } });
      s.addText(st[0], { x: C.M + 0.18, y, w: 2.55, h: 0.60, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.8, bold: true, color: i === 4 ? C.OCHRE : C.INK, valign: "middle" });
      s.addText(st[1], { x: C.M + 2.85, y: y + 0.04, w: 9.40, h: 0.52, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.7, color: C.TXT, valign: "middle", lineSpacingMultiple: 1.05 });
    });
    para(s, C.M, cy + 4.14, 12.44, 1.00, "Why we included the fifth row",
      "A judge will ask whether ore sorting is really shared value or just good engineering. The honest answer is that it is both, and " +
      "that the label does not change the cash flow. What it does change is how much weight the lever can carry: an advantage any " +
      "competitor can buy is worth having and not worth paying a premium for. That is why our level-one argument rests on the mid-stream " +
      "plant and the Korean joint venture rather than on this.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
   }, "Sources: TOMRA Mining; Global Mining Review; PLS FY26 results; team valuation model, ESG Value Bridge sheet.");

  pgD("Water",
      "Structurally the strongest environmental position PLS holds, and largely an accident of geology rather than a strategic choice. We say so.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "", w: 3.05 }, { t: "", w: 9.39 }], [
      ["Source", "Groundwater from the Pilbara fractured-rock aquifer, drawn via dewatering bores including the Southern Borefield and piped to the process plant"],
      ["Salinity", "Naturally saline. A reverse-osmosis plant on site produces potable water for camp and process needs"],
      ["Recycling", "More than 60% of processing water is recycled, per one source we rate as low-to-medium confidence and could not corroborate against a primary disclosure"],
      ["Water intensity per tonne", "Not found"],
      ["Formal water stewardship target", "Not found"],
      ["Comparison with brine", "South American brine operations consume large volumes in evaporation ponds in water-stressed basins, and have generated sustained community conflict. Hard rock does not carry that exposure"],
    ], { rowH: 0.44, size: 8.8, boldFirstCol: true, headH: 0.01,
         rowFill: [null,null,C.OCHRE_L,C.CRIM_L,C.CRIM_L,C.SPOD_L] });
    para(s, C.M, cy + 2.78, 6.10, 1.72, "The honest framing",
      "Using saline, non-potable groundwater rather than competing for community fresh water is an avoided-conflict advantage " +
      "for a Pilbara hard-rock miner. But it is largely a geological given, not a distinctive strategic decision by PLS.\n\n" +
      "We therefore describe it as a risk PLS does not have rather than an advantage PLS created. Framing a favourable accident of " +
      "geology as a shared-value achievement is exactly the move this case asks entrants to be sceptical about, and we would rather " +
      "apply that scepticism to our own pick.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.2 });
    para(s, C.M + 6.34, cy + 2.78, 6.10, 1.72, "What we would ask management",
      "Publish water intensity in kilolitres per tonne of concentrate, and a stewardship target. Both are standard under SASB's Metals " +
      "and Mining standard and neither was retrievable.\n\n" +
      "This matters more as P2000 doubles throughput: a plant twice the size draws roughly twice the water from the same aquifer, and " +
      "the absence of a disclosed intensity metric means neither we nor the regulator can see whether efficiency is improving or simply " +
      "being outrun by volume.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.2 });
   }, "Sources: mining-technology.com Pilgangoora project profile; farmonaut.com (recycling figure, low-to-medium confidence); general Pilbara hydrogeology literature. Items marked not found were searched for and could not be verified.");

  pgD("Tailings and biodiversity: the two we refuse to give PLS credit for",
      "One is undisclosed and we will not guess. The other relies on a scheme an independent review found underfunded.",
   (s, cy) => {
    para(s, C.M, cy, 6.10, 2.30, "Tailings: not disclosed",
      "We could not establish whether Pilgangoora uses filtered or dry-stack tailings or a conventional wet storage facility, nor its " +
      "conformance status with the Global Industry Standard on Tailings Management.\n\n" +
      "Filtered tailings would be a differentiator and several competing lithium operations promote it. PLS may well use it. " +
      "But an undisclosed practice cannot be underwritten, and we would rather record an unpriced risk than assert a strength we cannot " +
      "evidence.\n\n" +
      "This matters because P2000 roughly doubles throughput, and therefore roughly doubles tailings volumes, on an asset whose tailings " +
      "method we cannot see.",
      { fill: C.CRIM_L, line: "E5C3C3", titleColor: C.CRIMSON, size: 9.2 });
    para(s, C.M + 6.34, cy, 6.10, 2.30, "Biodiversity: the offset scheme is the problem",
      "PLS operates in the area covered by the Pilbara Environmental Offsets Fund, a pooled per-hectare payment scheme established in " +
      "2018 to fund landscape-level conservation for six threatened species including the northern quoll, the greater bilby and the " +
      "night parrot.\n\n" +
      "An independent review reported by ABC News in October 2024 found the fund's rate - A$893 to A$3,781 per hectare cleared - too low " +
      "to fund adequate conservation, compounded by almost no private land in the Pilbara bioregion available for like-for-like offsets.\n\n" +
      "A Northern Quoll Management Plan prepared for PLS exists, which is a point in its favour.",
      { fill: C.CRIM_L, line: "E5C3C3", titleColor: C.CRIMSON, size: 9.2 });
    para(s, C.M, cy + 2.48, 12.44, 1.68, "Why this is the most useful finding in our ESG work",
      "This is a sector-wide structural failure, not a PLS-specific one. Every Pilbara miner pays into the same scheme, and every one of " +
      "them can point to participation as evidence that biodiversity risk is managed. The independent review says it is not.\n\n" +
      "For an investor that has two consequences. First, no Pilbara miner - PLS included - can claim biodiversity risk is mitigated by " +
      "pointing at the fund, and any deck that does so has not looked. Second, it is a live regulatory risk: a scheme found inadequate " +
      "tends to be repriced, and the operator with the most hectares to clear has the most exposure. P2000 clears more hectares. " +
      "We have listed it as an engagement ask rather than a valuation adjustment, because we cannot date it or size it.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: ABC News, 'Pilbara mining offset scheme leaves threatened species short-changed, review finds', 21 October 2024; Western Australian Department of Biodiversity, Conservation and Attractions; a Northern Quoll Management Plan prepared for Pilbara Minerals by Animal Plant Mineral Pty Ltd.");

  pgD("Traditional Owners and heritage",
      "Post-Juukan Gorge this is the single hardest constraint on Western Australian mine development, and it is the precondition for P2000.",
   (s, cy) => {
    para(s, C.M, cy, 6.10, 2.05, "Why it gates the growth option",
      "Rio Tinto's destruction of the Juukan Gorge rock shelters in 2020 ended the era in which Western Australian heritage approvals " +
      "were a formality. It cost that company its chief executive, triggered a federal parliamentary inquiry, and reset how every " +
      "Pilbara operator is expected to engage.\n\n" +
      "The practical consequence for an investor is that heritage is now a schedule risk with a real distribution. Our P2000 base case " +
      "assumes first ore in mid-2029 on a study due in the December 2026 quarter. A heritage dispute would not stop the project; it " +
      "would move it, and a two-year move on a A$2.6bn net present value costs about A$407m at our discount rate, or A$0.13 per share.",
      { titleColor: C.INK, size: 9.2 });
    para(s, C.M + 6.34, cy, 6.10, 2.05, "What we could and could not verify",
      "We were not able to confirm from our sources which Traditional Owner groups hold native title over the Pilgangoora tenements, " +
      "the agreement type or its date, nor PLS's Indigenous employment percentage, Indigenous procurement spend or Reconciliation " +
      "Action Plan level.\n\n" +
      "That is a significant gap in a shared-value assessment, and it is the reason we have valued schedule protection as an avoided " +
      "delay rather than as a positive claim about relationship quality. We are pricing the absence of a disclosed problem, not the " +
      "presence of a verified strength.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.2 });
    para(s, C.M, cy + 2.22, 12.44, 1.86, "The circularity we had to confront, stated plainly",
      "There is a tension in our own argument, and we would rather set it out than have it found. We claim social licence protects the " +
      "P2000 schedule. We also report that the offsets regime behind environmental approvals in the region has been independently " +
      "judged inadequate, and that we could not verify PLS's Indigenous engagement metrics.\n\n" +
      "The resolution is that these are different approvals with different failure modes. Heritage approval turns on relationships with " +
      "Traditional Owners and on process; environmental offsets turn on a state scheme's pricing. PLS can be strong on the first and " +
      "exposed on the second simultaneously, and on the evidence available it probably is. What we cannot do is claim the first without " +
      "evidence, which is why A$0.13 per share is the smallest item in our bridge and why we have flagged the verification gap rather " +
      "than filling it with an assumption.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: team research; Australian Parliament Joint Standing Committee on Northern Australia inquiry into the destruction of Indigenous heritage sites at Juukan Gorge (2020-21). PLS-specific native title agreement details could not be verified from our environment and are recorded in the gaps register.");

  pgD("Workforce, safety and diversity",
      "The area where our research came back thinnest. We report what we found and flag the rest rather than filling the gaps with sector averages.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Metric", w: 3.65 }, { t: "What we found", w: 4.95 },
      { t: "Status", w: 3.84, align: "center" }], [
      ["Total recordable injury frequency rate", "Not retrievable for FY22-FY26", { t: "Not found", c: C.CRIMSON, b: true }],
      ["Lost time injury frequency rate", "Not retrievable", { t: "Not found", c: C.CRIMSON, b: true }],
      ["Fatalities", "None reported in the sources we reviewed", { t: "No reports found", c: C.OCHRE, b: true }],
      ["Total workforce", "Not retrievable as a headcount split between employees and contractors", { t: "Not found", c: C.CRIMSON, b: true }],
      ["Female participation", "Not retrievable at overall, operational or leadership level", { t: "Not found", c: C.CRIMSON, b: true }],
      ["Board gender composition", "One of the five directors we identified is the Chair, Kathleen Conlon; a second, Sally-Anne Layman, chairs the Sustainability Committee", { t: "Partial", c: C.OCHRE, b: true }],
      ["Psychosocial safety", "No PLS-specific response to the WA parliamentary inquiry into sexual harassment in the FIFO mining sector was retrievable", { t: "Not found", c: C.CRIMSON, b: true }],
      ["Community investment", "Not retrievable as a dollar figure", { t: "Not found", c: C.CRIMSON, b: true }],
    ], { rowH: 0.42, size: 8.6, boldFirstCol: true });
    para(s, C.M, cy + 3.75, 12.44, 1.32, "Why we are showing a table of gaps rather than omitting the topic",
      "Our research environment could not reach company websites or the ASX announcements platform, so the FY26 Sustainability Report " +
      "was not readable. Every figure above sits in that document. We could have substituted sector averages and produced a page that " +
      "looked complete; a page that looks complete and is not is worse than a page that admits what it does not know.\n\n" +
      "For the live rounds, these are the first numbers we would retrieve, and the safety record in particular would materially change " +
      "our view of execution risk on a doubling of throughput.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.4 });
   }, "Sources: team research. Every item marked not found was searched for and could not be verified from the environment available to us. See the gaps register at F5.");

  pgD("Governance",
      "The structure is better than the disclosure. A standing board Sustainability Committee is a real signal; the absence of visible ESG-linked pay is a real gap.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Element", w: 3.25 }, { t: "What we found", w: 5.35 },
      { t: "Assessment", w: 3.84 }], [
      ["Board Sustainability Committee", "Exists as a standing committee, chaired by Sally-Anne Layman, who also sits on Audit and Risk", { t: "Genuine strength", c: C.SPOD, b: true }],
      ["Board independence", "Described across sources as five independent non-executive directors plus the chief executive; we identified five people in total", { t: "Partly verified", c: C.OCHRE, b: true }],
      ["Chair experience", "Kathleen Conlon, formerly Chair of Lynas Rare Earths - directly relevant critical-minerals experience", { t: "Strength", c: C.SPOD, b: true }],
      ["ESG metrics in incentive pay", "We could not verify whether sustainability measures carry weightings in short or long-term incentive scorecards", { t: "Material gap", c: C.CRIMSON, b: true }],
      ["Remuneration report strikes", "None found", { t: "No issues found", c: C.OCHRE, b: true }],
      ["Capital allocation framework", "Stated policy: 20-30% of free cash flow to dividends, leverage below 1.5x through the cycle, excess to debt reduction, buybacks or growth", { t: "Clear and tested", c: C.SPOD, b: true }],
      ["Capital allocated FY23-FY26", "A$4.8bn: A$2.4bn to capital investment (50%), A$1.7bn to the balance sheet (35%), A$0.8bn to shareholders (16%)", { t: "Disciplined", c: C.SPOD, b: true }],
    ], { rowH: 0.475, size: 8.6, boldFirstCol: true });
    para(s, C.M, cy + 3.72, 12.44, 1.30, "The one that matters for a shared-value thesis",
      "If ESG outcomes are not in the incentive scorecard, then a shared-value strategy depends on management goodwill rather than on " +
      "management incentives - and goodwill does not survive a change of chief executive. We could not verify either way. It is our " +
      "second engagement ask after dated emissions targets, and it is the question we would put first at an investor meeting: not " +
      "\"what is your net-zero ambition\" but \"what percentage of the chief executive's long-term incentive depends on reaching it\".",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.4 });
   }, "Sources: PLS FY26 results and capital allocation commentary; discoveryalert.com.au; Capital Brief; Mining Magazine. The 2025 Corporate Governance Statement was identified but could not be opened from our environment.");

  pgD("External ratings, and why we did not lead with them",
      "The case asks entrants to go beneath the ESG rank. We could not retrieve reliable ratings, and on reflection that did not weaken the analysis.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Provider", w: 3.05 }, { t: "PLS score", w: 2.65, align: "center" },
      { t: "Note", w: 6.74 }], [
      ["MSCI ESG Rating", { t: "Not retrieved", c: C.MUTE }, "Not accessible from our environment"],
      ["Sustainalytics ESG Risk", { t: "Not retrieved", c: C.MUTE }, "Not accessible from our environment"],
      ["S&P Global CSA", { t: "Not retrieved", c: C.MUTE }, "Not accessible from our environment"],
      ["CDP", { t: "Not retrieved", c: C.MUTE }, "Not accessible from our environment"],
      ["Controversies and fines", { t: "None found", c: C.OCHRE }, "No environmental prosecutions, EPA breaches or material ESG litigation surfaced in our searches"],
    ], { rowH: 0.40, size: 8.8, boldFirstCol: true });
    para(s, C.M, cy + 2.30, 6.10, 2.10, "Why this is less damaging than it looks",
      "The case explicitly asks entrants to go beneath a company's ESG rank and reporting. A rating is a third party's weighted average " +
      "of disclosure quality; it is not evidence about whether ESG is wired into strategy.\n\n" +
      "Everything material in our assessment came from operating facts: a sorter that reduces milled tonnes, a kiln that removes " +
      "calcination emissions, a target expressed as a decade, an offsets scheme found underfunded. None of those needed a rating, and a " +
      "rating would not have revealed any of them.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.2 });
    para(s, C.M + 6.34, cy + 2.30, 6.10, 2.10, "But we are not pretending it is costless",
      "Two things we lost. First, we cannot benchmark PLS against BHP, Rio Tinto, Fortescue, South32 and Mineral Resources on a common " +
      "external scale, so our comparative judgement rests on our own reading of each company's disclosure rather than on a third party's.\n\n" +
      "Second, ratings do move flows. Index inclusion and ESG-mandated funds respond to them, so a rating change is a real, if crude, " +
      "catalyst that we cannot forecast. We have not claimed one in either direction.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.2 });
   }, "Sources: team research. Rating providers were not reachable from our environment; the absence of a retrieved score is not evidence about the score itself.");

  pgD("Our engagement plan as a shareholder",
      "A long-only fund holding a position for years has one instrument beyond buying and selling. Here is how we would use it.",
   (s, cy) => {
    const asks = [
      ["1", "Convert the net-zero window into a dated, validated target", C.CRIMSON,
       "\"The decade commencing 2040\" is not a commitment a capital allocator can hold anyone to. We would ask for a single year and Science Based Targets initiative validation.",
       "Removes the largest single credibility gap in the low-carbon thesis"],
      ["2", "Publish emissions intensity per tonne and a verified product carbon footprint", C.CRIMSON,
       "This is the number EU customers will require under the Battery Regulation regardless. Publishing early converts a compliance cost into a commercial credential.",
       "Directly enables the level-one market-access argument"],
      ["3", "Disclose the tailings method and GISTM conformance", C.OCHRE,
       "Tailings volumes roughly double with P2000. An undisclosed method on a doubling asset is an unpriced risk for every holder.",
       "Removes an unpriced risk we currently carry at nil"],
      ["4", "Put sustainability measures into incentive pay, with disclosed weightings", C.OCHRE,
       "A strategy that depends on management goodwill does not survive a change of management. Weighted scorecard metrics do.",
       "Makes the shared-value strategy durable beyond the current team"],
      ["5", "Get ahead of the Pilbara offsets problem", C.OCHRE,
       "The regional scheme has been independently found underfunded. The operator that funds real landscape conservation before the scheme is repriced buys both goodwill and regulatory optionality.",
       "Converts a sector-wide liability into a differentiator"],
    ];
    asks.forEach((a, i) => {
      const y = cy + i * 0.78;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 0.72, fill: { color: i % 2 ? C.MIST2 : C.PAPER }, line: { color: C.RULE, width: 0.6 } });
      s.addShape("ellipse", { x: C.M + 0.16, y: y + 0.19, w: 0.34, h: 0.34, fill: { color: a[2] } });
      s.addText(a[0], { x: C.M + 0.16, y: y + 0.19, w: 0.34, h: 0.34, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: C.WHITE, align: "center", valign: "middle" });
      s.addText(a[1], { x: C.M + 0.62, y: y + 0.05, w: 4.30, h: 0.62, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.3, bold: true, color: C.INK, valign: "middle" });
      s.addText(a[3], { x: C.M + 5.05, y: y + 0.05, w: 4.60, h: 0.62, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.2, color: C.TXT, valign: "middle", lineSpacingMultiple: 1.04 });
      s.addText(a[4], { x: C.M + 9.78, y: y + 0.05, w: 2.50, h: 0.62, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.2, bold: true, color: a[2], valign: "middle", lineSpacingMultiple: 1.04 });
    });
    para(s, C.M, cy + 4.06, 12.44, 1.08, "Why this belongs in an investment recommendation",
      "Shared value is not something an investor observes from outside. Porter and Kramer's argument is that the returns come from " +
      "changing how a business is run, which means a holder with a multi-year horizon is a participant rather than a spectator. Each of " +
      "the five asks above would, if met, move a lever we have currently valued at zero.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
   }, "Engagement priorities are the team's, derived from the gaps identified across section D.");
};
