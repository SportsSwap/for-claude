// Appendix E16: Monte Carlo simulation.
const L = require('./lib.js');
const { C, bg, head, foot, subhead, stat, card, para, table, apage } = L;
const F  = require('./model_facts.json');
const MC = require('./montecarlo.json');
const d2 = (x) => "A$" + x.toFixed(2);
const pc = (x, dp = 1) => (x * 100).toFixed(dp) + "%";

module.exports = function (pres, ctx) {
  const { s, cy } = apage(pres, "E16  Valuation",
    "Monte Carlo: how often is this recommendation right?",
    "20,000 trials. Expected value backs the position at A$" + MC.mean.toFixed(2) + ". The median, at A$" + MC.median.toFixed(2) + ", sits below today's close.");

  // distribution
  const bins = MC.hist_centres.map((c, i) => ({ c, p: MC.hist_pct[i] }));
  s.addChart(pres.ChartType.bar, [{
    name: "Share of trials (%)",
    labels: bins.map((b, i) => (i % 3 === 0 ? b.c.toFixed(1) : " ")),
    values: bins.map((b) => b.p),
  }], {
    x: C.M, y: cy, w: 7.75, h: 2.72, chartColors: [C.S1], barGapWidthPct: 12,
    showTitle: true, title: "Distribution of intrinsic value per share (A$), 20,000 trials",
    titleFontFace: C.B, titleFontSize: 10.5, titleColor: C.INK,
    catAxisLabelFontFace: C.B, catAxisLabelFontSize: 8, catAxisLabelColor: C.MUTE,
    valAxisLabelFontFace: C.B, valAxisLabelFontSize: 7.5, valAxisLabelColor: C.MUTE,
    valAxisTitle: "% of trials", showValAxisTitle: true,
    valAxisTitleFontFace: C.B, valAxisTitleFontSize: 7.5, valAxisTitleColor: C.MUTE,
    valGridLine: { color: C.RULE, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
  });

  table(s, C.M + 7.98, cy, [{ t: "Outcome", w: 2.95 }, { t: "", w: 1.51, align: "right" }], [
    ["Mean", d2(MC.mean)],
    ["Median", d2(MC.median)],
    ["Standard deviation", d2(MC.stdev)],
    ["P10", d2(MC.p10)], ["P25", d2(MC.p25)],
    ["P75", d2(MC.p75)], ["P90", d2(MC.p90)],
    [{ t: "Above last close of A$5.48", b: true }, { t: pc(MC.prob_above_lastclose), b: true, c: C.OCHRE }],
    [{ t: "Above our A$6.14 target", b: true }, { t: pc(MC.prob_above_target), b: true, c: C.OCHRE }],
    ["More than 20% below last close", { t: pc(MC.prob_loss_20pc), c: C.CRIMSON }],
    ["More than doubles", { t: pc(MC.prob_double), c: C.S2 }],
  ], { rowH: 0.222, size: 8.5, boldFirstCol: true });

  let y = cy + 2.82;
  subhead(s, C.M, y, 6.10, "What we randomised, and why each is drawn that way", { size: 10.5 });
  table(s, C.M, y + 0.42, [{ t: "Input", w: 1.90 }, { t: "Distribution", w: 1.50 }, { t: "Reasoning", w: 2.70 }], [
    ["Price level", "Lognormal, 28%", "A commodity forecast is wrong by a multiple, and it persists"],
    ["Annual price noise", "Normal, 10%", "Year-to-year variation around that level"],
    ["Unit cost", "Normal, 7%", "Disclosed and guided within a A$50/t band"],
    ["P2000 proceeds", "Bernoulli, 70%", "Conditioned on the price draw, not independent of it"],
    ["Colina proceeds", "Bernoulli, 40%", "Same treatment, lower rate, only after P2000"],
    ["WACC", "Normal, 60bp", "The CAPM inputs are prescribed; gearing is not"],
    ["Reserve conversion", "Normal, 8pp", "Sets the terminal annuity life"],
  ], { rowH: 0.245, size: 8, headSize: 8 });

  para(s, C.M + 6.40, y + 0.02, 6.04, 2.32, "A 46.6% probability, and what it changes",
    "A 46.6% chance that intrinsic value beats today's price is close to a coin flip, and the median trial at " +
    "A$5.19 sits below the A$5.48 close. The mean at A$5.69 sits above it. Both are true: a long right tail from " +
    "the growth options, a fat left tail from the price.\n\n" +
    "That does not move the target, a base-case point estimate. It changes conviction, and therefore sizing: an " +
    "expected value that clears the hurdle on a median that does not is an overweight to build into over several " +
    "prints rather than take in one. The short-interest rebuild says the same.\n\n" +
    "One specification note. The P2000 and Colina decisions are correlated with the price draw. Drawing them " +
    "independently fails the projects in the states where they are worth most, and that error costs four " +
    "percentage points.",
    { fill: C.OCHRE_L, line: "E8C9A3", titleColor: C.OCHRE, size: 8.8 });

  foot(s, "Source: model/monte_carlo.py, 20,000 trials, seed 20260906, run against the same FCFF mechanics as the Scenario Engine sheet. The script is committed with the model and is reproducible.", "E16");
};
