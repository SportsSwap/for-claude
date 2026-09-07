// Slides 7-11: the shared value case.
const { C, bg, nav, head, foot, stat, card, para, table, divider } = require('./lib.js');
const F = require('./model_facts.json');
const d2 = (x)=>"A$"+x.toFixed(2);
const pc = (x,d=0)=>(x*100).toFixed(d)+"%";

module.exports = function (pres, ctx) {
  const P = () => ++ctx.p;

  divider(pres, 2, "The shared value case",
    "Porter and Kramer describe three levels of shared value. Most miners only ever reach the second one.",
    ["07  The framework", "08  Level one: market access", "09  Level two: productivity", "10  The critical eye", "11  The value bridge"]);

  // ---------------------------------------------------------------- 7. FRAMEWORK
  {
    const s = pres.addSlide(); bg(s); nav(s, "Shared Value");
    s.addNotes("60 seconds. This is the intellectual spine of the pitch. Do not rush it.\n\n\"Porter and Kramer describe three levels. Almost every mining ESG story lives at level two: cut cost and cut emissions together. That is real, and every competent operator gets there, so it is not an advantage.\"\n\nThen: \"Level one is where advantage is created, and among these six companies PLS is the only one operating there.\"\n\nRead the bottom band aloud. It is the argument the next slide proves.");
    const cy = head(s, "Three levels of shared value, and where mining actually sits",
      "Cutting cost while cutting emissions is real, but it is the middle level and every competent operator gets there. The first level is where advantage is created.");
    const lv = [
      ["Level 3", "Enabling local cluster development", C.MUTE,
       "Build the suppliers, skills and institutions the business depends on.",
       "PLS: Traditional Owner agreements and Pilbara local content; in Brazil, the Salinas development including a flour-factory revitalisation supporting around 300 direct and indirect jobs.",
       "Makes the growth executable"],
      ["Level 2", "Redefining productivity in the value chain", C.INK2,
       "Solve an environmental problem in a way that lowers cost.",
       "PLS: sensor-based ore sorting rejects waste before the energy-intensive stages, so cost per tonne and energy per tonne fall together. Gas and solar displace diesel generation.",
       "Real, and roughly A$48/t"],
      ["Level 1", "Reconceiving products and markets", C.SPOD,
       "Serve an unmet societal need in a way that opens a market that did not exist.",
       "PLS: electric calcination and a Korean conversion joint venture produce a low-carbon, traceable, non-China unit at the moment carbon intensity is becoming a condition of sale.",
       "Where the advantage is"],
    ];
    lv.forEach((l, i) => {
      const y = cy + (2 - i) * 1.30;
      s.addShape("rect", { x: C.M, y, w: 12.44, h: 1.20,
        fill: { color: i === 2 ? C.SPOD_L : C.MIST2 }, line: { color: i === 2 ? "AFD3CC" : C.RULE, width: 0.75 } });
      s.addText(l[0], { x: C.M + 0.20, y: y + 0.14, w: 0.95, h: 0.34, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 11, bold: true, color: l[2], valign: "middle" });
      s.addText(l[1], { x: C.M + 1.18, y: y + 0.12, w: 4.55, h: 0.34, isTextBox: true, margin: 0,
        fontFace: C.H, fontSize: 13, bold: true, color: C.INK, valign: "middle" });
      s.addText(l[3], { x: C.M + 1.18, y: y + 0.46, w: 4.55, h: 0.42, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, italic: true, color: C.MUTE, valign: "top" });
      s.addText(l[4], { x: C.M + 5.88, y: y + 0.14, w: 4.42, h: 0.94, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, color: C.TXT, valign: "top", lineSpacingMultiple: 1.1 });
      s.addText(l[5], { x: C.M + 10.42, y: y + 0.14, w: 1.85, h: 0.94, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, bold: true, color: l[2], valign: "middle", align: "right" });
    });
    foot(s, "Framework: Michael Porter and Mark Kramer, 'Creating Shared Value', Harvard Business Review, 2011. Company evidence per PLS disclosures; see appendix for the full evidence table and our confidence rating on each item.", P());
  }

  // ---------------------------------------------------------------- 8. LEVEL 1
  {
    const s = pres.addSlide(); bg(s); nav(s, "Shared Value");
    s.addNotes("75 seconds. The most important slide in the deck. Walk the four boxes left to right as a chain.\n\nElectric calcination removes the emissions from the most energy-intensive step, which is what makes a low footprint DECLARABLE rather than merely claimed. Declarable matters because the EU Battery Regulation requires a carbon footprint declaration and a battery passport from 2027, and US rules restrict China-linked chains.\n\nLand it: \"A tonne that cannot be declared cannot be sold into the highest-value chains at any price.\"\n\nThen the discipline: we still carry all of this at zero in the target. Say that before they ask.");
    const cy = head(s, "Carbon intensity is becoming a condition of sale",
      "A tonne that cannot be declared cannot be sold into the highest-value chains at any price. PLS is building tonnes that can be.");
    const chain = [
      ["Electric calcination", "Calix technology, 100% PLS owned. Opened 5 June 2026; first lithium phosphate guided for the September 2026 quarter. Cuts calcination emissions by more than 80%.", C.SPOD],
      ["A declarable unit", "Calcination is the most energy-intensive step in the chain. Removing its emissions is what makes a low carbon footprint declarable rather than merely claimed.", C.INK2],
      ["Qualification", "EU Battery Regulation requires a carbon footprint declaration and, from 2027, a battery passport. US foreign-entity-of-concern rules restrict China-linked chains. Korean and Japanese cell makers qualify suppliers on provenance.", C.INK2],
      ["A market others cannot enter", "PLS supplies an 18%-owned Korean hydroxide joint venture at Gwangyang, with an option to lift that stake to 30% - a non-China conversion route into the customers who need one.", C.SPOD],
    ];
    chain.forEach((c2, i) => {
      const x = C.M + i * 3.15;
      s.addShape("rect", { x, y: cy, w: 2.94, h: 1.98, fill: { color: i%3===0 ? C.SPOD_L : C.MIST2 },
        line: { color: i%3===0 ? "AFD3CC" : C.RULE, width: 0.75 } });
      s.addText(String(i+1), { x: x + 0.16, y: cy + 0.12, w: 0.3, h: 0.28, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: c2[2], valign: "middle" });
      s.addText(c2[0], { x: x + 0.16, y: cy + 0.40, w: 2.62, h: 0.50, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 11, bold: true, color: C.INK, valign: "top" });
      s.addText(c2[1], { x: x + 0.16, y: cy + 0.92, w: 2.62, h: 0.98, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.5, color: C.TXT, valign: "top", lineSpacingMultiple: 1.08 });
      if (i < 3) s.addText(">", { x: x + 2.94, y: cy + 0.75, w: 0.21, h: 0.4, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 15, bold: true, color: C.FAINT, align: "center", valign: "middle" });
    });
    para(s, C.M, cy + 2.16, 6.05, 1.86, "Why we still carry this at zero in the target",
      "The mid-stream plant has not produced yet. The joint venture is still ramping. And we searched PLS's disclosed contracts for a " +
      "carbon-linked price premium and could not find one. Sizing a prize is not the same as booking it, so none of this is in the " +
      "A$6.14 target. It is quantified on the next page and held outside.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9.4 });
    para(s, C.M + 6.28, cy + 2.16, 6.16, 1.86, "Why it is still the thesis",
      "Every other lever in this deck lowers a cost that a competitor can also lower. This one changes which customers PLS is allowed to " +
      "serve. That is Porter and Kramer's first level, it is the only lever on offer across these six companies that creates a market " +
      "rather than defends a margin, and it is the reason we are recommending a lithium producer rather than a diversified major.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });
    foot(s, "Sources: PLS and Calix announcements (plant opened 5 June 2026, ARENA-supported); POSCO Pilbara Lithium Solution disclosures; EU Regulation 2023/1542 on batteries and waste batteries; US Inflation Reduction Act foreign-entity-of-concern provisions. The >80% figure is the reduction in calcination emissions specifically, not in PLS's total footprint.", P());
  }

  // ---------------------------------------------------------------- 9. LEVEL 2
  {
    const s = pres.addSlide(); bg(s); nav(s, "Shared Value");
    s.addNotes("45 seconds. This slide is deliberately self-critical and that is the point.\n\n\"These two levers are worth about 48 dollars a tonne. They are also things a good operator would do without an ESG label, so we do not claim them as a differentiator.\"\n\nShow the arithmetic if asked: FY26 costs fell 58 dollars a tonne, volumes rose 17%, so roughly half is fixed-cost dilution and we attribute the other half to ore sorting. That is our estimate, not a disclosure, and it says so on the slide.");
    const cy = head(s, "Productivity: real money, honestly labelled",
      "These two levers are worth about A$48/t. They are also things a good operator would do without an ESG label, so we do not claim them as a differentiator.");
    para(s, C.M, cy, 6.05, 2.30, "Lever 1  |  Sensor-based ore sorting",
      "The A$103m P680 project installed a TOMRA sensor-based sorter, described by the supplier as the largest in lithium at over " +
      "1,000 tonnes per hour, commissioned in August 2024. It rejects barren rock before the crushing and flotation stages, so fewer " +
      "tonnes are milled for the same lithium output.\n\n" +
      "How we get to A$30/t.  FY26 unit costs fell A$58/t, from A$627 to A$569. Volumes rose 17% over the same period, so roughly half " +
      "of that fall is fixed-cost dilution on higher throughput. We attribute the remaining half - about A$29/t, which we round to A$30/t - " +
      "to ore sorting and the associated processing improvements. This is our estimate, not a company disclosure.",
      { titleColor: C.INK, size: 9.2 });
    para(s, C.M + 6.28, cy, 6.16, 2.30, "Lever 2  |  Power",
      "Pilgangoora runs on its own generation rather than the state grid. Eight new gas gensets and LNG storage have displaced diesel, " +
      "with battery storage planned to firm future solar. The company targets roughly 48% lower power emissions intensity by 2027, " +
      "and up to 80% by 2030 if regional wind becomes available.\n\n" +
      "How we get to A$18/t.  Power is typically 15-20% of hard-rock processing cost, so call it about A$95/t of the A$569/t base. " +
      "A diesel-to-gas-and-solar switch of the scale described would cut that by roughly a fifth, or about A$19/t, which we round down " +
      "to A$18/t. Again, our estimate. PLS does not disclose a power cost per tonne.",
      { titleColor: C.INK, size: 9.2 });
    const cols = [{ t: "", w: 4.30 }, { t: "A$/t", w: 1.25, align: "center" },
      { t: "PV at A$20.5m per A$1/t (A$m)", w: 3.05, align: "center" },
      { t: "A$/share", w: 1.30, align: "center" }, { t: "Evidence", w: 2.54, align: "center" }];
    const rows = [
      ["Sensor-based ore sorting", "30", "614", "0.19", { t: "Strong", c: C.SPOD, b: true }],
      ["Power: gas, solar and storage", "18", "368", "0.11", { t: "Moderate", c: C.OCHRE, b: true }],
      [{ t: "Total productivity levers", b: true }, { t: "48", b: true }, { t: "982", b: true }, { t: "0.31", b: true, c: C.SPOD }, ""],
    ];
    table(s, C.M, cy + 2.48, cols, rows, { rowH: 0.30, size: 9, headSize: 8.4,
      rowFill: [null, null, C.SPOD_L] });
    para(s, C.M, cy + 3.70, 12.44, 0.62, null,
      "The coefficient is from the model: one dollar per tonne of sustained unit margin, across the base-case volume profile, after tax and discounting, is worth A$20.5m of equity value.",
      { fill: C.MIST, line: C.RULE, size: 8.8 });
    foot(s, "Sources: TOMRA Mining and Global Mining Review (sorter commissioned August 2024, >1,000 t/h, described as the largest in lithium); PLS FY26 results (unit cost A$627/t to A$569/t); PLS power strategy disclosures. The A$30/t and A$18/t figures are the team's estimates with the arithmetic shown above, not company-disclosed savings.", P());
  }

  // ---------------------------------------------------------------- 10. CRITICAL EYE
  {
    const s = pres.addSlide(); bg(s); nav(s, "Shared Value");
    s.addNotes("60 seconds. Judges reward a critical eye. This is where you earn it.\n\nDo not apologise. Say: \"We went looking for holes in PLS's shared-value story and we found six. The net-zero target is a DECADE, not a year. There is no Scope 3. There is no emissions intensity per tonne, which means nobody can verify the carbon advantage we are underwriting.\"\n\nThen the offsets finding, which is the strongest thing in our ESG work: the Pilbara scheme every miner points to was independently found underfunded. No Pilbara miner can claim biodiversity risk is mitigated by pointing at it.\n\nClose on the three engagement asks. A long-only holder is a participant, not a spectator.");
    const cy = head(s, "What we found when we went looking for the gaps",
      "The case asks for a critical eye. Here is where PLS's shared-value story is thinner than its reporting suggests, and what we would put to management.");
    const cols = [{ t: "What we looked for", w: 2.55 }, { t: "What we found", w: 5.05 },
      { t: "Why it matters to the investment case", w: 3.30 }, { t: "Severity", w: 1.54, align: "center" }];
    const rows = [
      ["A dated net-zero commitment", "The target is a decade, not a year: \"the decade commencing 2040\". No SBTi validation was found.",
       "A ten-year window is not a plan a capital allocator can hold management to.", { t: "High", c: C.CRIMSON, b: true }],
      ["Scope 3 disclosure", "None found. For a company whose product is consumed downstream, this is the emissions that matter most.",
       "Undermines the low-carbon claim precisely where customers will audit it.", { t: "High", c: C.CRIMSON, b: true }],
      ["Emissions intensity per tonne", "Not disclosed as a KPI. Third-party aggregator figures for FY23-24 exist but disagree and are unreliable.",
       "Without it, no buyer can verify the carbon advantage we are underwriting.", { t: "High", c: C.CRIMSON, b: true }],
      ["A credible biodiversity offset", "PLS pays into the Pilbara Environmental Offsets Fund. An independent review found its rate of A$893-3,781 per hectare too low to fund real conservation.",
       "A sector-wide exposure, not a PLS failure - but PLS cannot claim biodiversity risk is mitigated by pointing at it.", { t: "High", c: C.CRIMSON, b: true }],
      ["Fleet decarbonisation", "No electric haul fleet or trolley-assist programme found, while Fortescue runs public programmes.",
       "A lever PLS has not pulled. Upside if taken, a gap in the meantime.", { t: "Medium", c: C.OCHRE, b: true }],
      ["Tailings approach", "Not disclosed. We could not establish whether Pilgangoora uses filtered or conventional wet tailings, nor its GISTM status.",
       "We refuse to assert either way. It is an unpriced risk, and we say so.", { t: "Medium", c: C.OCHRE, b: true }],
    ];
    table(s, C.M, cy, cols, rows, { rowH: 0.545, size: 8.5, boldFirstCol: true });
    para(s, C.M, cy + 3.62, 6.05, 1.30, "The contradiction we had to resolve",
      "We argue that social licence protects the P2000 permitting schedule while also reporting that the offset system underpinning that " +
      "licence is independently judged inadequate. Both are true. The offsets regime is a live risk to every Pilbara miner, which makes " +
      "getting ahead of it an opportunity rather than a footnote.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
    para(s, C.M + 6.28, cy + 3.62, 6.16, 1.30, "Our three engagement asks as a shareholder",
      "1.  Convert the 2040s window into a dated, SBTi-validated target.\n" +
      "2.  Publish emissions intensity per tonne of concentrate and a verified product carbon footprint - the metric the EU regime will require anyway.\n" +
      "3.  Disclose the tailings method and GISTM conformance status.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
    foot(s, "Sources: PLS climate and sustainability disclosures; ABC News, 'Pilbara mining offset scheme leaves threatened species short-changed, review finds', 21 October 2024; team research. Items marked as not found were searched for and could not be verified; we have not assumed absence of disclosure means absence of practice.", P());
  }

  // ---------------------------------------------------------------- 11. VALUE BRIDGE
  {
    const s = pres.addSlide(); bg(s); nav(s, "Shared Value");
    s.addNotes("60 seconds. Expect the double-counting question here. Answer it before it is asked.\n\n\"Nothing on this page is added to the DCF. Ore sorting and the power strategy are already inside the 569 dollar cost base the model discounts. Adding them again would count the same cash flow twice.\"\n\nThen the reframe: \"Against the six dollar twelve target, forty-three cents is 4.6%, a rounding adjustment. Against the sixty-six cents of UPSIDE, it is 66%. The upside is the right denominator, because the upside is the recommendation.\"\n\nThe dashed box on the right is the part we refused to bank.");
    const cy = head(s, "The bridge is an attribution, not an addition",
      "Nothing here is added to the DCF. These levers are already inside the A$569/t cost base the model discounts. The question is how much of the value depends on them.");
    // bridge visual
    const bx = C.M, by = cy + 0.10, bw = 8.02, bh = 2.42;
    s.addShape("rect", { x: bx, y: by, w: bw, h: bh, fill: { color: C.MIST2 }, line: { color: C.RULE, width: 0.75 } });
    const base = 5.48, tgt = F.target, esg = F.esg_ps, opt = F.do_ps;
    const scale = 4.05;   // inches per A$
    const y0 = by + 1.62;
    // last close bar
    s.addShape("rect", { x: bx + 0.35, y: y0 - 0.62, w: 1.35, h: 0.62, fill: { color: C.INK2 } });
    s.addText("A$5.48", { x: bx + 0.35, y: y0 - 0.62, w: 1.35, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 11, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("Last close", { x: bx + 0.35, y: y0 + 0.02, w: 1.35, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, color: C.MUTE, align: "center", valign: "top" });
    // esg contribution
    const w1 = (esg) * scale;
    s.addShape("rect", { x: bx + 1.82, y: y0 - 0.62, w: w1, h: 0.62, fill: { color: C.SPOD } });
    s.addText("+" + esg.toFixed(2), { x: bx + 1.82, y: y0 - 0.62, w: w1, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 10, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("Shared value\n" + pc(F.esg_pct_upside) + " of the upside", { x: bx + 1.60, y: y0 + 0.02, w: w1 + 0.44, h: 0.46,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 8.5, bold: true, color: C.SPOD, align: "center", valign: "top" });
    // rest of upside
    const w2 = (tgt - base - esg) * scale;
    s.addShape("rect", { x: bx + 1.82 + w1 + 0.08, y: y0 - 0.62, w: w2, h: 0.62, fill: { color: C.FAINT } });
    s.addText("+0.21", { x: bx + 1.82 + w1 + 0.08, y: y0 - 0.62, w: w2, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("Everything else", { x: bx + 1.60 + w1, y: y0 + 0.02, w: w2 + 0.5, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, color: C.MUTE, align: "center", valign: "top" });
    // target
    const xt = bx + 1.82 + w1 + w2 + 0.22;
    s.addShape("rect", { x: xt, y: y0 - 0.90, w: 1.45, h: 0.90, fill: { color: C.INK } });
    s.addText("A$" + tgt.toFixed(2), { x: xt, y: y0 - 0.90, w: 1.45, h: 0.90, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 12, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("Target", { x: xt, y: y0 + 0.02, w: 1.45, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, bold: true, color: C.INK, align: "center", valign: "top" });
    // option outside
    s.addShape("rect", { x: xt + 1.62, y: y0 - 0.90, w: 1.45, h: 0.90, fill: { color: C.PAPER }, line: { color: C.SPOD, width: 1.25, dashType: "dash" } });
    s.addText("+" + opt.toFixed(2), { x: xt + 1.62, y: y0 - 0.90, w: 1.45, h: 0.90, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 12, bold: true, color: C.SPOD, align: "center", valign: "middle" });
    s.addText("Downstream option\nnot in the target", { x: xt + 1.42, y: y0 + 0.02, w: 1.85, h: 0.46, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, bold: true, color: C.SPOD, align: "center", valign: "top" });
    s.addText("From last close to target, and what sits beyond it", { x: bx + 0.20, y: by + 0.12, w: bw - 0.4, h: 0.30,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 11, bold: true, color: C.INK, valign: "middle" });

    card(s, C.M + 8.24, cy + 0.10, 4.20, 2.42, "The arithmetic that reframes this pitch", [
      "Measured against the A$6.14 target, A$0.43 of shared value is 4.6%. A rounding adjustment.",
      "Measured against the A$0.66 of upside, it is " + pc(F.esg_pct_upside) + ". Most of the investment case.",
      "The upside is the right denominator, because the upside is what the recommendation is.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9.4 });

    const cols = [{ t: "Tier", w: 2.05 }, { t: "Lever", w: 3.25 }, { t: "A$/share", w: 1.10, align: "center" },
      { t: "Treatment", w: 6.04 }];
    const rows = [
      [{ t: "In the target", c: C.SPOD, b: true }, "Ore sorting", "0.19", "Already inside the A$569/t cost base the DCF discounts. Attributed, not added."],
      [{ t: "In the target", c: C.SPOD, b: true }, "Power: gas, solar, storage", "0.11", "Same. The bridge decomposes the valuation; it does not inflate it."],
      [{ t: "In the target", c: C.SPOD, b: true }, "P2000 schedule protection", "0.13", "Value of avoiding a two-year permitting slip on a A$2.6bn NPV, at our WACC."],
      [{ t: "Outside the target", c: C.OCHRE, b: true }, "Mid-stream lithium phosphate", "0.21", "Risked at 45%. Plant built, first production due in the September 2026 quarter."],
      [{ t: "Outside the target", c: C.OCHRE, b: true }, "POSCO joint venture equity", "0.06", "Risked at 70%. Both trains built, Train 2 ramping. Lowest execution risk."],
      [{ t: "Outside the target", c: C.OCHRE, b: true }, "Low-carbon qualification premium", "0.05", "Risked at 25%. Directionally supported by policy, unproven in PLS's contracts."],
    ];
    table(s, C.M, cy + 2.70, cols, rows, { rowH: 0.295, size: 8.6, headSize: 8.4,
      rowFill: [C.SPOD_L, C.SPOD_L, C.SPOD_L, C.OCHRE_L, C.OCHRE_L, C.OCHRE_L] });
    foot(s, "Source: team valuation model, ESG Value Bridge and Downstream Option sheets. Every figure on this page is reproducible from the submitted workbook. Risk weightings are our judgement and are stated on the sheet.", P());
  }
};
