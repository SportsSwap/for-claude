// Appendix E9-E15 (valuation) and F1-F7 (risk and reference).
const L = require('./lib.js');
const { C, bg, head, foot, stat, card, para, table, apage } = L;
const F = require('./model_facts.json');
const S = require('./scenarios.json');
const n0 = (v) => (v === null || v === undefined) ? "" : Math.round(v).toLocaleString("en-US");

module.exports = function (pres, ctx) {
  let e = 8, f = 0;
  const pgE = (title, take, body, src) => {
    const n = ++e; const { s, cy } = apage(pres, "E" + n + "  Valuation", title, take); body(s, cy); foot(s, src, "E" + n);
  };
  const pgF = (title, take, body, src) => {
    const n = ++f; const { s, cy } = apage(pres, "F" + n + "  Risk and reference", title, take); body(s, cy); foot(s, src, "F" + n);
  };
  const YRS = S.fcst.map((y) => y.replace(/F$/, ""));
  const series = (s, x, y, label, rows, opts = {}) => {
    const lw = opts.lw || 2.60;
    const cols = [{ t: label, w: lw }].concat(YRS.map((yr) => ({ t: yr, w: (12.44 - lw) / 10, align: "right" })));
    return table(s, x, y, cols, rows, { rowH: opts.rowH || 0.27, size: opts.size || 8.2, headSize: 8, boldFirstCol: true });
  };

  // ---------------- E9 bear / E10 bull
  [["bear", "Bear", C.CRIMSON, C.CRIM_L,
    "Restart supply overwhelms demand, prices revert toward the marginal cost, P2000 is never sanctioned, Colina never proceeds and Ngungaju is throttled back.",
    "A$2.30 is still 20% above the A$1.91 the market printed in the last trough, when PLS held A$974m of cash and was loss-making rather than A$2.29bn and earning A$526m. Note the mine life caps at 25 years, because a smaller operation depletes the orebody more slowly - which is why the bear case is not as punitive on terminal value as the price path alone would suggest."],
   ["bull", "Bull", C.INK2, C.SPOD_L,
    "The 2027-29 deficit called by Fastmarkets, Morgan Stanley and UBS arrives, prices overshoot the incentive level before mean-reverting, and both P2000 and Colina proceed on schedule.",
    "Note the mine life falls to 14.2 years. Mining faster depletes the orebody faster, so the annuity period shortens and part of the volume upside is given back in the terminal value. A growing perpetuity would have hidden that entirely and produced a materially higher bull case."],
  ].forEach((sc) => {
    const k = sc[0], d = S[k];
    pgE(sc[1] + " case", sc[4], (s, cy) => {
      let y = cy;
      y = series(s, C.M, y, "Driver", [
        ["Concentrate sold (kt)", ...d.prod.map(n0)],
        ["Realised price (US$/t)", ...d.price.map(n0)],
        ["Unit cost (A$/t)", ...d.cost.map(n0)],
        ["Capital expenditure (A$m)", ...d.capex.map(n0)],
        [{ t: "EBITDA (A$m)", b: true }, ...d.ebitda.map((v) => ({ t: n0(v), b: true }))],
        [{ t: "FCFF (A$m)", b: true }, ...d.fcff.map((v) => ({ t: n0(v), b: true }))],
      ]) + 0.24;
      const rows = [
        ["PV of explicit FCFF, FY27-FY36", n0(d.pv_exp)],
        ["PV of terminal value", n0(d.pv_tv)],
        ["Memo: growing perpetuity would have given", { t: n0(d.perp), c: C.MUTE }],
        [{ t: "Enterprise value", b: true }, { t: n0(d.ev), b: true }],
        ["Add net cash", n0(F.netcash)],
        [{ t: "Equity value", b: true }, { t: n0(d.eq), b: true }],
        [{ t: "Value per share (A$)", b: true, c: sc[2] }, { t: d.vps.toFixed(2), b: true, c: sc[2] }],
        [{ t: "Upside / (downside)", b: true, c: sc[2] }, { t: (d.ups >= 0 ? "+" : "") + (d.ups * 100).toFixed(1) + "%", b: true, c: sc[2] }],
      ];
      table(s, C.M, y, [{ t: sc[1] + " case bridge", w: 4.60 }, { t: "A$m unless stated", w: 2.10, align: "right" }], rows,
        { rowH: 0.235, size: 8.6, boldFirstCol: true });
      table(s, C.M + 7.00, y, [{ t: "Orebody", w: 3.30 }, { t: "", w: 2.14, align: "right" }], [
        ["Ore consumed to FY36 (Mt)", d.ore_used.toFixed(1)],
        ["Ore remaining after FY36 (Mt)", d.ore_left.toFixed(1)],
        ["Remaining mine life (years)", { t: d.life.toFixed(1), b: true }],
        ["Terminal annuity factor", d.annuity.toFixed(2) + "x"],
      ], { rowH: 0.245, size: 8.6, boldFirstCol: true });
      para(s, C.M + 7.00, y + 1.32, 5.44, 1.72, "What this case is telling you",
        sc[5], { fill: sc[3], line: C.RULE, titleColor: sc[2], size: 8.8 });
    }, "Source: team valuation model, Scenario Engine sheet. Set Assumptions!C7 to " + sc[1] + " to reproduce the full statements on this case.");
  });

  // ---------------- E11 sensitivities
  pgE("Sensitivities",
      "The price coefficient is A$46,304m per 100% change and the cost coefficient A$11,628m. Price matters four times as much as cost.",
   (s, cy) => {
    const pf = [-0.20,-0.10,0,0.10,0.20], cf = [-0.10,-0.05,0,0.05,0.10];
    const gx = C.M + 1.45, cw = 1.05, rh = 0.30;
    s.addText("Base-case value per share against realised price and unit cost (A$)", { x: C.M, y: cy, w: 7.5, h: 0.26,
      isTextBox: true, margin: 0, fontFace: C.B, fontSize: 10, bold: true, color: C.INK, valign: "middle" });
    pf.forEach((p, i) => {
      s.addShape("rect", { x: gx + i * cw, y: cy + 0.32, w: cw, h: rh, fill: { color: C.INK } });
      s.addText((p >= 0 ? "+" : "") + (p * 100).toFixed(0) + "%", { x: gx + i * cw, y: cy + 0.32, w: cw, h: rh,
        isTextBox: true, margin: 0, fontFace: C.B, fontSize: 8.5, bold: true, color: C.WHITE, align: "center", valign: "middle" });
    });
    s.addShape("rect", { x: C.M, y: cy + 0.32, w: 1.43, h: rh, fill: { color: C.INK } });
    s.addText("Unit cost", { x: C.M + 0.08, y: cy + 0.32, w: 1.27, h: rh, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8, bold: true, color: C.WHITE, align: "right", valign: "middle" });
    cf.forEach((c2, ri) => {
      const y = cy + 0.32 + (ri + 1) * rh;
      s.addShape("rect", { x: C.M, y, w: 1.43, h: rh, fill: { color: C.INK } });
      s.addText((c2 >= 0 ? "+" : "") + (c2 * 100).toFixed(0) + "%", { x: C.M, y, w: 1.43, h: rh, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 8.5, bold: true, color: C.WHITE, align: "center", valign: "middle" });
      pf.forEach((p, ci) => {
        const v = F.vps_base + (F.k_price * p - F.k_cost * c2) / 3220;
        const on = ri === 2 && ci === 2;
        s.addShape("rect", { x: gx + ci * cw, y, w: cw, h: rh,
          fill: { color: on ? C.SPOD_L : (v > 5.48 ? C.MIST2 : C.CRIM_L) }, line: { color: C.RULE, width: 0.5 } });
        s.addText(v.toFixed(2), { x: gx + ci * cw, y, w: cw, h: rh, isTextBox: true, margin: 0,
          fontFace: C.B, fontSize: 8.6, bold: on, color: on ? C.SPOD : (v > 5.48 ? C.TXT : C.CRIMSON),
          align: "center", valign: "middle" });
      });
    });
    card(s, C.M + 7.10, cy, 5.34, 2.12, "What the coefficients mean", [
      "A 1% change in realised price across every forecast year moves equity value by about A$463m, or A$0.14 per share.",
      "A 1% change in unit cost moves it by about A$116m, or A$0.04 per share.",
      "So price is roughly four times as powerful as cost. Operational excellence cannot rescue this position from a sustained price relapse - which is why the risk register leads with price.",
      "Shaded cells sit below the current share price of A$5.48.",
    ], { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 8.8 });
    para(s, C.M, cy + 2.36, 12.44, 1.78, "Where the break-even sits",
      "PLS needs realised prices no worse than about 8% below our base case to justify today's share price at unchanged costs. Our base " +
      "case already sits 11% below spot-implied realisation and 19% below the June-2026 quarter exit rate. In other words the pitch does " +
      "not require the price to rise from here - it requires the price not to fall by roughly a fifth from a level we have already " +
      "discounted twice.\n\n" +
      "The workbook also carries a WACC against mine-life grid, which we have not reproduced here because it moves the answer far less: " +
      "the annuity structure makes the model relatively insensitive to the terminal assumption.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Source: team valuation model, Sensitivity sheet. Coefficients are computed in the workbook from the base-case volume profile, after the realisation adjustment, royalties, tax and discounting, and include the effect on terminal value.");

  // ---------------- E12 comps
  pgE("Trading comparables",
      "8.0x to 11.0x FY27 estimated EBITDA against a diversified peer median near 7.8x. A premium for growth, capped for single-commodity risk.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Company", w: 2.35 }, { t: "Market cap A$m", w: 1.85, align: "right" },
      { t: "EV A$m", w: 1.75, align: "right" }, { t: "FY26 EBITDA A$m", w: 1.95, align: "right" },
      { t: "EV/EBITDA", w: 1.35, align: "center" }, { t: "P/E forward", w: 1.35, align: "center" },
      { t: "Consensus", w: 1.84, align: "center" }], [
      ["BHP Group", "312,560", "343,660", "50,600", "n/a", "17.4x", "Hold"],
      ["Rio Tinto", "220,530", "247,680", "45,500", "7.8x", "11.7x", "Hold"],
      ["Fortescue", "68,680", "70,150", "13,230", "5.6x", "14.7x", "Neutral"],
      ["South32", "17,190", "17,150", "3,790", "8.5x", "18.2x", "Buy"],
      ["Mineral Resources", "10,400", "15,720", "2,600", "7.8x", "15.5x", "Buy"],
      [{ t: "Peer median", b: true }, "", "", "", { t: "7.8x", b: true }, { t: "15.5x", b: true }, ""],
      [{ t: "PLS Group", b: true, c: C.SPOD }, { t: "17,646", c: C.SPOD }, { t: "16,184", c: C.SPOD }, { t: "1,137", c: C.SPOD }, { t: "26.8x trailing", c: C.SPOD }, "n/m", { t: "Buy", c: C.SPOD }],
    ], { rowH: 0.30, size: 8.6, boldFirstCol: true, rowFill: [null,null,null,null,null,C.MIST,C.SPOD_L] });
    table(s, C.M, cy + 2.55, [{ t: "PLS valued on the peer set", w: 5.10 }, { t: "", w: 2.05, align: "right" }], [
      ["FY27 estimated EBITDA, base case (A$m)", n0(F.fy27_ebitda)],
      ["Multiple applied - low", "8.0x"],
      ["Multiple applied - high", "11.0x"],
      ["Implied value per share - low (A$)", F.comps_lo.toFixed(2)],
      ["Implied value per share - high (A$)", F.comps_hi.toFixed(2)],
      [{ t: "Midpoint (A$)", b: true, c: C.SPOD }, { t: F.comps_mid.toFixed(2), b: true, c: C.SPOD }],
    ], { rowH: 0.25, size: 8.6, boldFirstCol: true });
    para(s, C.M + 7.30, cy + 2.55, 5.14, 1.62, "Why the 26.8x is not the relevant number",
      "PLS's trailing multiple looks extreme because FY26 EBITDA of A$1,137m captures a year that began with realised prices at US$742/t. " +
      "On our FY27 estimate of A$1,731m the same enterprise value is roughly 9.4x. That is the cyclical trap in this sector: the stock " +
      "looks expensive at the bottom and cheap at the top, and a multiple taken at either point is misleading.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 8.8 });
    para(s, C.M, cy + 4.46, 12.44, 0.72, null,
      "Vendor caveat: providers disagree materially on EV/EBITDA across this peer set, reflecting different snapshot dates through a volatile 2026 and different methodologies. Treat single-point figures as indicative.",
      { fill: C.MIST, line: C.RULE, size: 8.8 });
   }, "Sources: company FY26 results; data-vendor multiples, August 2026. PLS-implied values are computed in the workbook's Trading Comps sheet from the model's own FY27 EBITDA estimate.");

  // ---------------- E13 precedents
  pgE("Precedent transactions",
      "Shown as reference only and given zero weight, because transaction multiples could not be sourced on a consistent basis.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Completed", w: 1.35 }, { t: "Acquirer", w: 2.15 }, { t: "Target", w: 2.35 },
      { t: "Value", w: 1.35, align: "center" }, { t: "Structure", w: 1.60 }, { t: "Note", w: 3.64 }], [
      ["Mar 2025", "Rio Tinto", "Arcadium Lithium", "US$6.7bn", "All cash", "US$5.85/share. The largest completed lithium deal on this page."],
      ["Jan 2025", "PLS Group", "Latin Resources", "A$560m", "All scrip", "0.07 PLS shares per Latin share. Preserved PLS's net cash through the trough."],
      ["May 2026", "Huayou Cobalt", "Atlantic Lithium", "US$210m", "All cash", "US$0.25486/share, a 26.6% premium. Explicitly a price-rebound deal."],
      ["Aug 2025", "Sayona Mining", "Piedmont Lithium", "n/d", "Merger of equals", "50/50 split creating Elevra Lithium; both sub-scale standalone."],
      ["May 2024", "SQM and Hancock", "Azure Minerals", "A$1.7bn", "Scheme, cash", "A$3.70/share. SQM's first Australian hard-rock foothold."],
      ["Lapsed 2023", "Albemarle", "Liontown Resources", "A$6.6bn", "Cash, withdrawn", "A$3.00/share, nearly double the pre-bid price. Blocked by a 19.9% Hancock stake."],
      ["Jan 2024", "Livent", "Allkem", "US$10.6bn", "Merger of equals", "Created Arcadium, which Rio acquired 14 months later."],
      ["Oct 2025", "Ganfeng Lithium", "Leo Lithium (Goulamina 40%)", "US$343m", "Staged cash", "Plus a 1.5% gross revenue royalty for 20 years."],
    ], { rowH: 0.375, size: 8.4, boldFirstCol: true });
    para(s, C.M, cy + 3.46, 6.10, 1.72, "Why we gave this method zero weight",
      "Two reasons, either of which would have made a stated multiple spurious. First, no broker-published EV/EBITDA or EV/resource " +
      "multiple for these deals was retrievable, and the targets' resource statements are on inconsistent bases - JORC against " +
      "exploration target, ore tonnes against lithium carbonate equivalent - so any multiple we built would be meaningless.\n\n" +
      "Second, applying a control premium to our own discounted cash flow and calling the result an independent method is circular. " +
      "It would inflate the football field using our own assumptions twice.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
    para(s, C.M + 6.34, cy + 3.46, 6.10, 1.72, "What the deals do tell us",
      "Lithium dealmaking fell about 89% in 2025 across just four transactions, then accelerated in early 2026 on recovering prices and " +
      "concern about future deficits. The Huayou acquisition of Atlantic Lithium in May 2026 was reported explicitly as price-rebound " +
      "driven.\n\n" +
      "PLS at roughly A$17.6bn is also large for this sector: the biggest completed deal here was US$6.7bn. Consolidation in 2026 has " +
      "run through sub-scale developers, not producers of PLS's size, so we do not present it as a takeover candidate.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9 });
   }, "Sources: company announcements for each transaction; trade press coverage of 2025-26 lithium M&A volumes. Deal values are as announced.");

  // ---------------- E14 SOTP
  pgE("Sum of the parts",
      "A risked asset-by-asset cross-check on the consolidated discounted cash flow, and a reminder of how much of the value is not yet producing.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Asset", w: 3.05 }, { t: "Unrisked A$m", w: 1.65, align: "right" },
      { t: "Risking", w: 1.10, align: "center" }, { t: "Risked A$m", w: 1.55, align: "right" },
      { t: "A$/share", w: 1.20, align: "right" }, { t: "Basis", w: 3.89 }], [
      ["Pilgangoora, Pilgan plant", "9,800", "100%", "9,800", "3.04", "In production at about 920ktpa steady state"],
      ["Ngungaju plant", "1,450", "95%", "1,378", "0.43", "Restarted July 2026; small risking for ramp-up execution"],
      ["P2000 expansion", "2,600", "70%", "1,820", "0.57", "PFS incremental NPV; risked for an FID not yet taken"],
      ["Colina, Brazil", "900", "40%", "360", "0.11", "Study due December-quarter 2027; no FID, no permits"],
      ["Mid-stream plant", "260", "50%", "130", "0.04", "Demonstration scale; first production guided this quarter"],
      ["POSCO joint venture, 18%", "320", "85%", "272", "0.08", "Both trains built; Train 2 ramping"],
      ["Exploration and tenements", "180", "50%", "90", "0.03", "Includes tenements acquired adjacent to Colina"],
      ["Corporate costs capitalised", "(900)", "100%", "(900)", "(0.28)", "Present value of unallocated overhead"],
      [{ t: "Enterprise NAV", b: true }, "", "", { t: "12,950", b: true }, { t: "4.02", b: true }, ""],
      ["Net cash", "", "", "1,437", "0.45", "FY26 cash of A$2,290m less A$853m of borrowings"],
      [{ t: "Equity NAV", b: true, c: C.SPOD }, "", "", { t: "14,412", b: true, c: C.SPOD }, { t: "4.48", b: true, c: C.SPOD }, ""],
    ], { rowH: 0.29, size: 8.5, boldFirstCol: true,
         rowFill: [null,null,null,null,null,null,null,null,C.MIST,null,C.SPOD_L] });
    para(s, C.M, cy + 3.55, 12.44, 1.44, "Why the NAV is below the DCF, and why we did not average the two",
      "Equity NAV of about A$4.48 sits well below both the A$6.53 base-case DCF and the A$5.48 share price. That is not a contradiction, " +
      "it is a different question. The NAV values each asset separately, risk-weighted, at a point in time. The DCF values the " +
      "consolidated cash flow the business actually generates, including the sixteen years of ore that follow the explicit forecast.\n\n" +
      "The gap is roughly the value of continuity: an operating business that keeps converting resource into reserve and reserve into " +
      "cash flow is worth more than the sum of its individually risk-weighted parts. We present the NAV because it is the more " +
      "conservative frame and because it makes visible that about A$0.80 per share of our valuation sits in assets that are not yet " +
      "producing anything.",
      { fill: C.MIST, line: C.RULE, titleColor: C.INK, size: 9.2 });
   }, "Source: team valuation model, SOTP NAV sheet. Asset net present values are the team's estimates built on the same price deck and discount rate as the consolidated DCF, except P2000 which uses the company's own PFS figure. Risk weightings are our judgement.");

  // ---------------- E15 downstream option
  pgE("The downstream option, sized and risked",
      "A$2,396m unrisked, A$1,023m risked, A$0.32 per share - and deliberately excluded from the A$6.14 target.",
   (s, cy) => {
    table(s, C.M, cy, [{ t: "Lever", w: 4.00 }, { t: "Volume", w: 1.25, align: "right" },
      { t: "Unit margin", w: 1.35, align: "right" }, { t: "EBITDA A$m", w: 1.35, align: "right" },
      { t: "Multiple", w: 1.05, align: "center" }, { t: "NPV A$m", w: 1.20, align: "right" },
      { t: "Risk", w: 0.90, align: "center" }, { t: "A$/sh", w: 1.34, align: "right" }], [
      ["Mid-stream lithium phosphate", "400kt", "A$480/t", "192", "8.0x", "1,536", { t: "45%", c: C.OCHRE }, { t: "0.21", b: true }],
      ["POSCO joint venture equity", "43ktpa", "A$4,200/t", "33", "8.0x", "260", { t: "70%", c: C.SPOD }, { t: "0.06", b: true }],
      ["Low-carbon qualification premium", "1,000kt", "A$75/t", "75", "8.0x", "600", { t: "25%", c: C.CRIMSON }, { t: "0.05", b: true }],
      [{ t: "Total", b: true }, "", "", { t: "300", b: true }, "", { t: "2,396", b: true }, "", { t: "0.32", b: true, c: C.SPOD }],
    ], { rowH: 0.42, size: 8.5, boldFirstCol: true, rowFill: [null,null,null,C.SPOD_L] });
    para(s, C.M, cy + 2.05, 6.10, 3.10, "The assumptions, stated so they can be attacked",
      "Mid-stream: 400kt of concentrate calcined in-house, being 20% of a 2Mtpa base, at the conversion margin retained rather than " +
      "ceded to a third-party converter. Neither the volume share nor the margin is disclosed by PLS.\n\n" +
      "POSCO: 43ktpa of hydroxide at an assumed A$4,200/t conversion margin, PLS share 18%. The option to lift that stake to 30% is not " +
      "valued at all.\n\n" +
      "Qualification premium: 1,000kt of qualified volume at an assumed A$75/t. This is the weakest of the three and we risk it hardest, " +
      "at 25%, because no verified carbon-linked premium exists in any PLS contract we could find.",
      { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 9 });
    para(s, C.M + 6.34, cy + 2.05, 6.10, 3.10, "Why it sits outside the target price",
      "Because none of it is earning yet. The mid-stream plant produces its first lithium phosphate in the September 2026 quarter, the " +
      "joint venture is still ramping, and the premium is unproven.\n\n" +
      "Keeping it outside means the recommendation does not depend on it. The A$6.14 target rests on an operating asset with a disclosed " +
      "cost base and company-guided volumes. Everything on this page is upside we have identified, sized and then declined to bank.\n\n" +
      "Target plus the risked option would be A$6.44, or 17.5% above the last close. We do not publish that number. A target " +
      "should rest on what is already producing, and this is not yet.",
      { fill: C.SPOD_L, line: "AFD3CC", titleColor: C.SPOD, size: 9 });
   }, "Source: team valuation model, Downstream Option sheet. Volumes, margins, multiples and probabilities are the team's assumptions and are all visible and editable in the workbook.");
  ctx.pgF = pgF;
};
