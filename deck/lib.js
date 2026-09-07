// Reusable slide components for the PLS submission deck.
const C = require('./brand.js');

const SECTIONS = ["Summary","Company","Industry","Thesis","Shared Value","Valuation","Risks","Recommendation"];

function bg(s, dark) {
  s.background = { color: dark ? C.INK : C.PAPER };
}

// Bottom navigation pills. Functional wayfinding, and the active section is filled.
function nav(s, active) {
  const n = SECTIONS.length, w = 1.46, gap = 0.075;
  const total = n * w + (n - 1) * gap;
  let x = (C.W - total) / 2;
  SECTIONS.forEach((name) => {
    const on = name === active;
    if (on) s.addShape("roundRect", { x, y: 7.00, w, h: 0.30, rectRadius: 0.06,
      fill: { color: C.INK } });
    s.addText(name, {
      x, y: 7.00, w, h: 0.30, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, bold: on,
      color: on ? C.WHITE : C.FAINT, align: "center", valign: "middle",
    });
    x += w + gap;
  });
}

// The action title lives INSIDE a full-width dark band, with the section label beneath it.
// Returns the y at which slide content should begin.
function head(s, title, takeaway, opts = {}) {
  const BAND = 1.06;
  s.addShape("rect", { x: 0, y: 0, w: C.W, h: BAND, fill: { color: C.INK } });
  // the claim carries the slide, so it goes in the band, in white, at size
  const claim = takeaway || title;
  let fs = 17;
  if (claim.length > 150) fs = 14.5; else if (claim.length > 105) fs = 15.5;
  s.addText(claim, {
    x: C.M, y: 0.09, w: 11.15, h: 0.62, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: fs, bold: true, color: C.WHITE,
    valign: "middle", lineSpacingMultiple: 1.02,
  });
  s.addText(opts.label || title, {
    x: C.M, y: 0.72, w: 9.6, h: 0.26, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: 10, color: "9FB4C7", valign: "middle",
  });
  // ticker chip, top right
  s.addShape("roundRect", { x: 11.72, y: 0.30, w: 1.16, h: 0.42, rectRadius: 0.08,
    fill: { color: C.SPOD } });
  s.addText("ASX: PLS", { x: 11.72, y: 0.30, w: 1.16, h: 0.42, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: 9.5, bold: true, color: C.WHITE, align: "center", valign: "middle" });
  return 1.42;
}

function foot(s, source, page) {
  if (source) {
    s.addText(source, {
      x: C.M, y: 6.68, w: 11.3, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 7.2, italic: true, color: C.FAINT, valign: "middle",
    });
  }
  if (page !== undefined && page !== null) {
    s.addText(String(page), {
      x: 12.20, y: 6.68, w: 0.68, h: 0.26, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, bold: true, color: C.MUTE, align: "right", valign: "middle" });
  }
}

// A sub-section heading with a rule under it - the benchmark deck's main structural device.
function subhead(s, x, y, w, text, opts = {}) {
  s.addText(text, { x, y, w, h: 0.28, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: opts.size || 11, bold: true,
    color: opts.color || C.INK, valign: "middle", align: opts.align || "left" });
  s.addShape("rect", { x, y: y + 0.28, w, h: 0.015, fill: { color: opts.rule || C.INK } });
  return y + 0.38;
}

// A large figure with a caption beneath it.
function stat(s, x, y, w, value, label, sub, opts = {}) {
  const col = opts.color || C.INK;
  // a long value ("Sep-qtr 2026") wraps and shoves the KPI off the row baseline; step it down instead
  const want = opts.size || 30;
  let vsz = want;
  while (vsz > 15 && String(value).length * 0.62 * vsz / 72 > w - 0.04) vsz -= 0.5;
  if (vsz < want - 0.05) FIT.warnings.push("stat \"" + value + "\": " + want + "pt -> " + vsz + "pt");
  s.addText(value, {
    x, y, w, h: 0.62, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: vsz, bold: true, color: col, valign: "bottom",
    align: opts.align || "left",
  });
  s.addText(label, {
    x, y: y + 0.60, w, h: 0.26, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: 10, bold: true, color: C.TXT, valign: "top", align: opts.align || "left",
  });
  if (sub) {
    s.addText(sub, {
      x, y: y + 0.84, w, h: opts.subh || 0.5, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, color: C.MUTE, valign: "top", align: opts.align || "left",
    });
  }
}

// A tinted panel with a heading and body lines.
function card(s, x, y, w, h, title, lines, opts = {}) {
  s.addShape("rect", { x, y, w, h, fill: { color: opts.fill || C.MIST2 },
    line: { color: opts.line || C.RULE, width: 0.75 } });
  let ty = y + 0.16;
  if (opts.num !== undefined) {
    s.addShape("ellipse", { x: x + 0.16, y: ty, w: 0.34, h: 0.34,
      fill: { color: opts.numFill || C.INK } });
    s.addText(String(opts.num), { x: x + 0.16, y: ty, w: 0.34, h: 0.34, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 11, bold: true, color: C.WHITE, align: "center", valign: "middle" });
  }
  if (title) {
    const tx = opts.num !== undefined ? x + 0.60 : x + 0.18;
    s.addText(title, {
      x: tx, y: ty - 0.02, w: w - (tx - x) - 0.16, h: opts.titleH || 0.40, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: opts.titleSize || 11.5, bold: true,
      color: opts.titleColor || C.INK, valign: "middle",
    });
    ty += (opts.titleH || 0.40) + 0.06;
  }
  if (lines && lines.length) {
    const gap = opts.gap === undefined ? 5 : opts.gap;
    const ncol = opts.cols || 1;                       // a wide card reads better in columns
    const colGap = 0.24;
    const colW = (w - 0.40 - (ncol - 1) * colGap) / ncol;
    const per = Math.ceil(lines.length / ncol);
    const chunks = [];
    for (let k = 0; k < ncol; k++) chunks.push(lines.slice(k * per, (k + 1) * per));
    const cw2 = colW - 0.34, ch2 = y + h - ty - 0.12;
    const tallest = chunks.reduce((a, b) => (b.length > a.length ? b : a), chunks[0]);
    const csz = fitSize(tallest, cw2, ch2, opts.size || 9.5, 1.0,
                        tallest.length * gap / 72, opts.label || (title || "card"));
    chunks.forEach((chunk, k) => {
      if (!chunk.length) return;
      s.addText(chunk.map((t, i) => ({
        text: t, options: { bullet: { code: "25AA" }, breakLine: i < chunk.length - 1 },
      })), {
        x: x + 0.20 + k * (colW + colGap), y: ty, w: colW, h: ch2, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: csz, color: opts.color || C.TXT,
        valign: "top", paraSpaceAfter: gap, lineSpacingMultiple: 1.0,
      });
    });
  }
}

// Plain paragraph block inside a panel (no bullets).
// ---------------------------------------------------------------- text fitting
// Calibri averages ~0.50em per character across mixed-case prose. Estimating the
// wrapped line count lets a panel shrink its own type rather than spill past its
// border, which is what every hand-placed height was quietly risking.
const FIT = { warnings: [] };
function _lines(text, widthIn, size) {
  // 0.53em per character and a 1.25 line box, both measured against slides that
  // still overflowed at the earlier 0.50/1.20 estimate
  const cpl = Math.max(8, widthIn / (0.53 * size / 72));
  let n = 0;
  String(text).split("\n").forEach((para) => {
    n += para.length === 0 ? 1 : Math.ceil(para.length / cpl);
  });
  return n;
}
// largest size <= want that fits `paras` (array of strings) into widthIn x heightIn
function fitSize(paras, widthIn, heightIn, want, lsm, extraIn, label) {
  const extra = extraIn || 0;
  for (let size = want; size >= 6.8; size -= 0.1) {
    let n = 0;
    paras.forEach((t) => { n += _lines(t, widthIn, size); });
    if (n * (size * 1.25 * lsm / 72) + extra <= heightIn * 0.97) {
      if (size < want - 0.05 && label) {
        FIT.warnings.push(label + ": " + want.toFixed(1) + "pt -> " + size.toFixed(1) + "pt");
      }
      return Math.round(size * 10) / 10;
    }
  }
  if (label) FIT.warnings.push("OVERFLOW " + label + " (at 6.8pt floor)");
  return 6.8;
}

function para(s, x, y, w, h, title, text, opts = {}) {
  s.addShape("rect", { x, y, w, h, fill: { color: opts.fill || C.MIST2 },
    line: { color: opts.line || C.RULE, width: 0.75 } });
  let ty = y + 0.14;
  if (title) {
    s.addText(title, { x: x + 0.18, y: ty, w: w - 0.36, h: 0.32, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: opts.titleSize || 11.5, bold: true, color: opts.titleColor || C.INK, valign: "middle" });
    ty += 0.36;
  }
  const pw = w - 0.36, ph = y + h - ty - 0.10;
  const psz = fitSize([text], pw, ph, opts.size || 9.5, 1.05, 0, opts.label || (title || "para"));
  s.addText(text, { x: x + 0.18, y: ty, w: pw, h: ph, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: psz, color: opts.color || C.TXT, valign: "top", lineSpacingMultiple: 1.05 });
}

// Data table. cols = [{t:"Header", w:2.1, align:"left"}], rows = [[...], ...]
function table(s, x, y, cols, rows, opts = {}) {
  const th = opts.headH || 0.32;
  const rh = opts.rowH || 0.28;
  let cx = x;
  cols.forEach((c) => {
    s.addShape("rect", { x: cx, y, w: c.w, h: th, fill: { color: opts.headFill || C.INK } });
    s.addText(c.t, { x: cx + 0.07, y, w: c.w - 0.14, h: th, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: opts.headSize || 9, bold: true, color: C.WHITE,
      align: c.align || "left", valign: "middle" });
    cx += c.w;
  });
  rows.forEach((row, ri) => {
    const ry = y + th + ri * rh;
    const zebra = ri % 2 === 1;
    let rx = x;
    cols.forEach((c, ci) => {
      s.addShape("rect", { x: rx, y: ry, w: c.w, h: rh,
        fill: { color: (opts.rowFill && opts.rowFill[ri]) || (zebra ? C.MIST2 : C.PAPER) },
        line: { color: C.RULE, width: 0.5 } });
      let v = row[ci];
      let col = opts.color || C.TXT, bold = false;
      if (v && typeof v === "object") { col = v.c || col; bold = !!v.b; v = v.t; }
      if (opts.boldFirstCol && ci === 0) bold = true;
      s.addText(String(v === undefined || v === null ? "" : v), {
        x: rx + 0.07, y: ry, w: c.w - 0.14, h: rh, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: opts.size || 9, color: col, bold,
        align: c.align || "left", valign: "middle" });
      rx += c.w;
    });
  });
  return y + th + rows.length * rh;
}

// Section divider (does not count toward the 15-slide limit).
function divider(pres, num, title, blurb, contents) {
  const s = pres.addSlide();
  bg(s, true);
  s.addText(String(num).padStart(2, "0"), {
    x: C.M, y: 2.05, w: 2.0, h: 1.5, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: 88, bold: true, color: C.SPOD, valign: "middle",
  });
  s.addText(title, {
    x: 2.35, y: 2.30, w: 9.6, h: 0.9, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: title.length > 30 ? 30 : 36, bold: true, color: C.WHITE, valign: "middle",
  });
  if (blurb) {
    s.addText(blurb, {
      x: 2.40, y: 3.25, w: 9.2, h: 0.9, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 13, color: "AFC3D4", valign: "top", lineSpacingMultiple: 1.1,
    });
  }
  if (contents && contents.length) {
    s.addText(contents.join("     "), {
      x: 2.40, y: 4.35, w: 9.6, h: 0.9, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9.5, color: C.SPOD, valign: "top", lineSpacingMultiple: 1.3,
    });
  }
  return s;
}

// Appendix slide shell: consistent header without the main-deck nav.
function appx(pres, tag, title, takeaway, page) {
  const s = pres.addSlide();
  bg(s, false);
  s.addText("APPENDIX  |  " + tag, {
    x: C.M, y: 0.18, w: 12.4, h: 0.24, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: 8.5, bold: true, color: C.SPOD, charSpacing: 1.2, valign: "middle",
  });
  head(s, title, takeaway, { navless: false, size: 21 });
  s.__page = page;
  return s;
}

module.exports = { FIT, fitSize, C, SECTIONS, bg, nav, head, foot, subhead, stat, card, para, table, divider, appx };

// ---- appendix helpers -------------------------------------------------
const T = require('./model_tables.json');

// Render a financial statement straight from the model export.
// rows: [[label, key, fmt, opts]] where fmt is 'n' | 'n1' | 'pct' | 'x' | 'cur2'
function statement(s, x, y, rows, opts = {}) {
  const yrs = T.years, n = yrs.length;
  const lw = opts.labelW || 3.05;
  const cw = opts.colW || ((12.44 - lw) / n);
  const rh = opts.rowH || 0.245;
  // header
  s.addShape("rect", { x, y, w: lw, h: 0.28, fill: { color: C.INK } });
  s.addText(opts.title || "A$m", { x: x + 0.07, y, w: lw - 0.14, h: 0.28, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: 8.2, bold: true, color: C.WHITE, valign: "middle" });
  yrs.forEach((yr, i) => {
    s.addShape("rect", { x: x + lw + i * cw, y, w: cw, h: 0.28, fill: { color: C.INK } });
    s.addText(yr, { x: x + lw + i * cw, y, w: cw, h: 0.28, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 7.6, bold: true, color: yr.endsWith("A") ? "9FD8CE" : C.WHITE,
      align: "center", valign: "middle" });
  });
  rows.forEach((r, ri) => {
    const [label, key, fmt, o = {}] = r;
    const ry = y + 0.28 + ri * rh;
    const src = T[o.src || opts.src];
    const vals = (src && src[key]) || [];
    const fillc = o.hi ? C.SPOD_L : (ri % 2 ? C.MIST2 : C.PAPER);
    s.addShape("rect", { x, y: ry, w: lw, h: rh, fill: { color: fillc }, line: { color: C.RULE, width: 0.4 } });
    s.addText((o.ind ? "    " : "") + label, { x: x + 0.07, y: ry, w: lw - 0.14, h: rh, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 7.8, bold: !!o.b, color: o.b ? C.INK : C.TXT, valign: "middle" });
    yrs.forEach((yr, i) => {
      const v = vals[i];
      let t = "";
      if (typeof v === "number") {
        if (fmt === "pct") t = (v * 100).toFixed(1) + "%";
        else if (fmt === "cur2") t = v.toFixed(2);
        else if (fmt === "n1") t = v.toFixed(1);
        else if (fmt === "x") t = v.toFixed(3);
        else t = Math.round(v).toLocaleString("en-US");
        if (typeof v === "number" && v < 0 && fmt !== "pct")
          t = "(" + t.replace("-", "") + ")";
      }
      s.addShape("rect", { x: x + lw + i * cw, y: ry, w: cw, h: rh, fill: { color: fillc }, line: { color: C.RULE, width: 0.4 } });
      s.addText(t, { x: x + lw + i * cw, y: ry, w: cw - 0.05, h: rh, isTextBox: true, margin: 0,
        fontFace: C.B, fontSize: 7.6, bold: !!o.b,
        color: (typeof v === "number" && v < 0) ? C.CRIMSON : (o.b ? C.INK : C.TXT),
        align: "right", valign: "middle" });
    });
  });
  return y + 0.28 + rows.length * rh;
}

// Appendix page furniture: tag, title, takeaway, footer, page number.
function apage(pres, tag, title, takeaway) {
  const s = pres.addSlide();
  bg(s, false);
  const cy = head(s, title, takeaway, { label: "APPENDIX  |  " + tag });
  return { s, cy };
}

module.exports.statement = statement;
module.exports.apage = apage;
module.exports.T = T;
