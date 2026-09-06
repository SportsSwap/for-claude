// Main deck: 15 content slides (title and dividers are excluded from the limit).
const { C, bg, nav, head, foot, stat, card, para, table, divider } = require('./lib.js');
const F = require('./model_facts.json');
const pc  = (x, dp=1) => (x*100).toFixed(dp) + "%";
const pcs = (x, dp=1) => (x>=0?"+":"") + (x*100).toFixed(dp) + "%";
const d2  = (x) => "A$" + x.toFixed(2);

module.exports = function build(pres, ctx) {
  const P = () => ++ctx.p;

  // ---------------------------------------------------------------- TITLE
  {
    const s = pres.addSlide(); bg(s, true);
    s.addText("PLS GROUP LIMITED", { x: C.M, y: 2.10, w: 11.5, h: 0.85, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 46, bold: true, color: C.WHITE, valign: "middle" });
    s.addText("ASX: PLS   |   Spodumene concentrate   |   Pilgangoora, Western Australia",
      { x: C.M, y: 2.98, w: 11.5, h: 0.4, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 14, color: C.SPOD, valign: "middle" });
    s.addText("The market is paying for a lithium miner.\nWe are paying for the only one of the six that can sell a tonne the others cannot.",
      { x: C.M, y: 3.62, w: 8.30, h: 1.15, isTextBox: true, margin: 0,
        fontFace: C.H, fontSize: 17, italic: true, color: "C9D8E6", valign: "top", lineSpacingMultiple: 1.15 });
    // recommendation block
    s.addShape("rect", { x: 9.05, y: 3.62, w: 3.83, h: 1.62, fill: { color: C.SPOD } });
    s.addText("BUY", { x: 9.05, y: 3.72, w: 3.83, h: 0.62, isTextBox: true, margin: 0,
      fontFace: C.H, fontSize: 34, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("12-month target  " + d2(F.target), { x: 9.05, y: 4.32, w: 3.83, h: 0.32, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 13, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    s.addText("Last close A$5.48   |   " + pcs(F.upside) + "\nTotal return " + pc(F.tsr) + " vs benchmark 5.90%",
      { x: 9.05, y: 4.62, w: 3.83, h: 0.58, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, color: "DDF0EB", align: "center", valign: "top", lineSpacingMultiple: 1.1 });
    s.addText("FMAA Asset Management  |  Shared Value Coverage Team", { x: C.M, y: 6.20, w: 8, h: 0.3,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 11, bold: true, color: C.WHITE, valign: "middle" });
    s.addText("Shared Value Project x FMAA  |  Investing for the Future Case Competition 2026\nValuation date 5 September 2026",
      { x: C.M, y: 6.50, w: 8, h: 0.6, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.5, color: "8FA8BE", valign: "top", lineSpacingMultiple: 1.15 });
  }

  // ---------------------------------------------------------------- 1. EXEC SUMMARY
  {
    const s = pres.addSlide(); bg(s); nav(s, "Summary");
    s.addNotes("OPEN HERE. 45 seconds, no more.\n\n\"We are recommending PLS Group, a buy, twelve-month target six dollars fourteen against a last close of five forty-eight. That is 12.0% of price plus a 1.7% yield, so a 13.6% total return against a benchmark that returned 5.90%.\"\n\nThen the line that matters: \"Of the sixty-six cents of upside we see, forty-three cents comes from ESG-linked operating decisions the market is not paying for. That is two thirds. This is not a lithium price bet with an ESG slide attached.\"\n\nDo NOT walk the six boxes. They are there for the reader, not the listener. Move to slide 2.");
    const cy = head(s, "Executive summary",
      "Two thirds of the upside we see is the shared-value position the market has not priced. That is the entire recommendation.");
    const bx = [
      ["01", "The asset", "A$569/t", "FY26 unit cost, FOB",
       "Pilgangoora produced 879.5kt in FY26, up 17%, at a 59% EBITDA margin. Costs fell 9% while volumes rose."],
      ["02", "The balance sheet", "A$2.29bn", "Cash at 30 June 2026",
       "Net cash of A$1.44bn, an inaugural US$600m bond, and a dividend reinstated at 5cps fully franked."],
      ["03", "The growth", ">2 Mtpa", "P2000 doubles Pilgangoora",
       "PFS puts the increment at A$2.6bn NPV and a 55% IRR. A$175m of pre-FID capital is already approved."],
      ["04", "The shared value", d2(F.esg_ps), "per share, inside the target",
       "Equal to " + pc(F.esg_pct_upside,0) + " of the A$0.66 of upside. A further " + d2(F.do_ps) + " sits outside it, unpriced."],
      ["05", "The valuation", d2(F.target), "12-month target",
       "60% base-case DCF at an 8.88% WACC, 40% trading comparables. Bear " + d2(F.vps_bear) + ", bull " + d2(F.vps_bull) + "."],
      ["06", "The mandate", pc(F.tsr), "expected total return",
       pcs(F.upside) + " price and a 1.7% yield, against a benchmark that returned 5.90%. Outperformance of " + pc(F.outperf) + "."],
    ];
    bx.forEach((b, i) => {
      const x = C.M + (i % 3) * 4.16, y = cy + Math.floor(i / 3) * 2.22;
      s.addShape("rect", { x, y, w: 3.98, h: 2.02, fill: { color: C.MIST2 }, line: { color: C.RULE, width: 0.75 } });
      s.addText(b[0], { x: x + 0.18, y: y + 0.12, w: 0.5, h: 0.28, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10, bold: true, color: C.SPOD, valign: "middle" });
      s.addText(b[1], { x: x + 0.68, y: y + 0.12, w: 3.1, h: 0.28, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 10.5, bold: true, color: C.MUTE, valign: "middle" });
      s.addText(b[2], { x: x + 0.18, y: y + 0.42, w: 3.6, h: 0.56, isTextBox: true, margin: 0,
        fontFace: C.H, fontSize: 26, bold: true, color: C.INK, valign: "middle" });
      s.addText(b[3], { x: x + 0.18, y: y + 0.98, w: 3.6, h: 0.24, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9, bold: true, color: C.SPOD, valign: "middle" });
      s.addText(b[4], { x: x + 0.18, y: y + 1.24, w: 3.62, h: 0.92, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 9.2, color: C.TXT, valign: "top", lineSpacingMultiple: 1.12 });
    });
    foot(s, "Source: PLS Group FY26 results (24 August 2026); P2000 Pre-Feasibility Study (June 2024); team valuation model. Spodumene concentrate is the lithium-bearing rock concentrate PLS ships; SC6 denotes a 6% Li2O grade.", P());
  }

  // ---------------------------------------------------------------- 2. WHY PLS NOT THE OTHER FIVE
  {
    const s = pres.addSlide(); bg(s); nav(s, "Summary");
    s.addNotes("60 seconds. This slide pre-empts the first question every judge has: why not BHP.\n\nThe argument: four of the six use ESG to defend cash flows they already have. That is competent risk management and it is not shared value. Only PLS sits in a market where the environmental outcome is why the customer exists.\n\nSay the caveat out loud before they raise it: PLS is also the riskiest of the six. One commodity, one asset, a price that moved by a factor of three in two years. Naming it first takes the weapon away.");
    const cy = head(s, "Why PLS, and not the other five",
      "For four of the six, ESG spend defends an existing cash flow. For PLS the societal need is the demand, and carbon intensity decides market access.");
    const cols = [
      { t: "Company", w: 1.85 }, { t: "Primary exposure", w: 2.35 },
      { t: "How ESG works in the business", w: 4.55 },
      { t: "Effect on value", w: 1.75, align: "center" },
      { t: "EV/EBITDA", w: 1.10, align: "center" }, { t: "Net debt", w: 0.84, align: "center" },
    ];
    const rows = [
      ["BHP Group", "Iron ore, copper, coal", "Scope 1 and 2 abatement on long-life bulk assets. Spend protects a licence to operate.", { t: "Defensive", c: C.MUTE }, "n/a", "US$8.7bn"],
      ["Rio Tinto", "Iron ore, aluminium, lithium", "Same, plus a lithium arm bought at the top of the cycle for US$6.7bn.", { t: "Defensive", c: C.MUTE }, "7.8x", "US$14.1bn"],
      ["Fortescue", "Iron ore, green energy", "Green hydrogen ambition sits beside the iron ore business rather than inside it.", { t: "Adjacent", c: C.MUTE }, "5.6x", "US$0.9bn"],
      ["South32", "Alumina, base metals", "Real transition-metal exposure, but ESG is still a cost of operating.", { t: "Defensive", c: C.MUTE }, "8.5x", "net cash"],
      ["Mineral Resources", "Lithium, iron ore, services", "Lithium exposure diluted by services and iron ore, and constrained by gearing.", { t: "Diluted", c: C.OCHRE }, "7.8x", "US$4.3bn"],
      [{ t: "PLS Group", b: true, c: C.SPOD }, { t: "Lithium, pure play", c: C.SPOD }, { t: "The product IS the transition, and the carbon intensity of the tonne decides which market will take it.", c: C.INK }, { t: "Offensive", c: C.SPOD, b: true }, { t: "26.8x", c: C.INK }, { t: "net cash", c: C.SPOD }],
    ];
    table(s, C.M, cy, cols, rows, { rowH: 0.52, size: 8.8, boldFirstCol: true,
      rowFill: [null, null, null, null, null, C.SPOD_L] });
    para(s, C.M, 5.18, 6.10, 1.60, "The screen this case actually asks for",
      "Porter and Kramer's test is whether solving a societal problem creates a new pool of value. Four of these six use ESG " +
      "to protect cash flows they already have. That is competent risk management, and it is not shared value. Only PLS sits " +
      "in a market where the environmental outcome is the reason the customer exists.", { titleColor: C.INK });
    para(s, C.M + 6.30, 5.18, 6.14, 1.60, "The honest caveat",
      "PLS is also the riskiest of the six: one commodity, one principal asset, and a price that has moved by a factor of three " +
      "in two years. A shared-value mandate does not suspend that. It is why our bear case is severe and why we size the " +
      "downstream prize outside the target rather than inside it.", { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE });
    foot(s, "Sources: company FY26 results; data-vendor multiples, August 2026 (providers disagree materially on EV/EBITDA across this peer set - see appendix). PLS's 26.8x is trailing FY26 and falls to roughly 9x on FY27 estimates as the earnings recovery annualises.", P());
  }

};
