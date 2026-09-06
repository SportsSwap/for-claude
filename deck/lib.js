// Reusable slide components for the PLS submission deck.
const C = require('./brand.js');

const SECTIONS = ["Summary","Company","Industry","Thesis","Shared Value","Valuation","Risks","Recommendation"];

function bg(s, dark) {
  s.background = { color: dark ? C.INK : C.PAPER };
}

// Top navigation breadcrumb: functional wayfinding, rendered as text only.
function nav(s, active) {
  let x = C.M;
  SECTIONS.forEach((name) => {
    const on = name === active;
    s.addText(name, {
      x, y: 0.16, w: 1.62, h: 0.24, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 9, bold: on,
      color: on ? C.INK : C.FAINT, align: "left", valign: "middle",
    });
    x += 1.58;
  });
}

// Slide title plus the one-line analytical takeaway ("action title").
function head(s, title, takeaway, opts = {}) {
  s.addText(title, {
    x: C.M, y: opts.navless ? 0.30 : 0.50, w: 12.4, h: 0.52, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: opts.size || 25, bold: true, color: C.INK, valign: "middle",
  });
  if (takeaway) {
    s.addShape("rect", {
      x: C.M, y: (opts.navless ? 0.30 : 0.50) + 0.56, w: 12.44, h: 0.46, fill: { color: C.MIST },
    });
    s.addText(takeaway, {
      x: C.M + 0.16, y: (opts.navless ? 0.30 : 0.50) + 0.56, w: 12.12, h: 0.46, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 12.5, bold: true, color: C.INK2, valign: "middle",
    });
  }
}

function foot(s, source, page) {
  if (source) {
    s.addText(source, {
      x: C.M, y: 7.02, w: 11.3, h: 0.30, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 7.5, italic: true, color: C.FAINT, valign: "middle",
    });
  }
  if (page !== undefined && page !== null) {
    s.addText(String(page), {
      x: 12.35, y: 7.02, w: 0.55, h: 0.30, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: 8.5, color: C.FAINT, align: "right", valign: "middle",
    });
  }
}

// A large figure with a caption beneath it.
function stat(s, x, y, w, value, label, sub, opts = {}) {
  const col = opts.color || C.INK;
  s.addText(value, {
    x, y, w, h: 0.62, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: opts.size || 30, bold: true, color: col, valign: "bottom",
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
    s.addText(lines.map((t, i) => ({
      text: t, options: { bullet: { code: "25AA" }, breakLine: i < lines.length - 1 },
    })), {
      x: x + 0.20, y: ty, w: w - 0.40, h: y + h - ty - 0.12, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: opts.size || 9.5, color: opts.color || C.TXT,
      valign: "top", paraSpaceAfter: opts.gap === undefined ? 5 : opts.gap, lineSpacingMultiple: 1.0,
    });
  }
}

// Plain paragraph block inside a panel (no bullets).
function para(s, x, y, w, h, title, text, opts = {}) {
  s.addShape("rect", { x, y, w, h, fill: { color: opts.fill || C.MIST2 },
    line: { color: opts.line || C.RULE, width: 0.75 } });
  let ty = y + 0.14;
  if (title) {
    s.addText(title, { x: x + 0.18, y: ty, w: w - 0.36, h: 0.32, isTextBox: true, margin: 0,
      fontFace: C.B, fontSize: opts.titleSize || 11.5, bold: true, color: opts.titleColor || C.INK, valign: "middle" });
    ty += 0.36;
  }
  s.addText(text, { x: x + 0.18, y: ty, w: w - 0.36, h: y + h - ty - 0.10, isTextBox: true, margin: 0,
    fontFace: C.B, fontSize: opts.size || 9.5, color: opts.color || C.TXT, valign: "top", lineSpacingMultiple: 1.05 });
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
    x: 2.35, y: 2.30, w: 9.2, h: 0.9, isTextBox: true, margin: 0,
    fontFace: C.H, fontSize: 36, bold: true, color: C.WHITE, valign: "middle",
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

module.exports = { C, SECTIONS, bg, nav, head, foot, stat, card, para, table, divider, appx };
