// Layout check of deck.html in headless Chromium at 1920x1080 and 1280x720.
// node dashboard/check_layout.js <deck.html> <out_dir>
// Writes <out_dir>/layout_report.json and screenshots <out_dir>/screens/page_NN.png (1920x1080).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [deck, outDir] = process.argv.slice(2);
const SIZES = [[1920, 1080], [1280, 720]];
const CAM = { x: 1920 - 520, y: 1080 - 368, w: 520, h: 368 };

(async () => {
  const browser = await chromium.launch();
  const report = { sizes: {}, pages: [] };
  fs.mkdirSync(path.join(outDir, 'screens'), { recursive: true });
  for (const [w, h] of SIZES) {
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    await page.goto('file://' + path.resolve(deck) + '#1');
    await page.evaluate(() => window.deck.finish());
    const n = await page.evaluate(() => window.deck.count());
    const problems = [];
    for (let i = 0; i < n; i++) {
      await page.evaluate(i => window.deck.go(i), i);
      await page.waitForTimeout(30);
      const res = await page.evaluate((CAM) => {
        const stage = document.getElementById('stage').getBoundingClientRect();
        const s = stage.width / 1920;
        const act = document.querySelector('.page.active');
        const out = [];
        const sel = '.eyebrow,.title,.subtitle,.stitle,.tagline,.banner,.card,.card *,.stat,.stat *,.conclusion,.conclusion *,' +
                    '.chartbox,.chart text,.chart rect,.chart circle,.chart line';
        const els = [...act.querySelectorAll(sel)];
        els.push(document.getElementById('pageno'));
        for (const el of els) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 && r.height === 0) continue;
          const x = (r.left - stage.left) / s, y = (r.top - stage.top) / s, ww = r.width / s, hh = r.height / s;
          const name = (el.className && el.className.baseVal !== undefined ? el.tagName : el.className) + ' ' +
                       (el.textContent || '').trim().slice(0, 40);
          if (x < -1 || y < -1 || x + ww > 1921 || y + hh > 1081) out.push('off stage: ' + name);
          const ix = Math.min(x + ww, CAM.x + CAM.w) - Math.max(x, CAM.x);
          const iy = Math.min(y + hh, CAM.y + CAM.h) - Math.max(y, CAM.y);
          if (ix > 0.5 && iy > 0.5) out.push('in facecam corner: ' + name);
        }
        for (const el of act.querySelectorAll('.title,.subtitle,.stitle,.tagline,.eyebrow,.big,.clabel,.cnote,.sval,.slabel')) {
          if (el.scrollWidth > el.clientWidth + 1) out.push('text overflows: ' + el.textContent.trim().slice(0, 60));
        }
        const sub = act.querySelector('.subtitle,.tagline');
        if (sub && sub.textContent.trim()) {
          const lh = parseFloat(getComputedStyle(sub).lineHeight) || parseFloat(getComputedStyle(sub).fontSize) * 1.25;
          if (sub.getClientRects().length && sub.scrollHeight > lh * 1.5) out.push('subtitle wraps: ' + sub.textContent.trim());
        }
        const se = document.scrollingElement;
        if (se.scrollWidth > innerWidth || se.scrollHeight > innerHeight) out.push('page scrolls');
        const t = act.querySelector('.title,.stitle');
        return { problems: out, title: t ? t.textContent.trim() : '', key: act.dataset.key };
      }, CAM);
      res.problems.forEach(p => problems.push(`page ${i + 1} (${res.key}): ${p}`));
      if (w === 1920) {
        const file = `page_${String(i + 1).padStart(2, '0')}.png`;
        await page.screenshot({ path: path.join(outDir, 'screens', file) });
        report.pages.push({ n: i + 1, key: res.key, title: res.title, screenshot: 'screens/' + file });
      }
    }
    report.sizes[`${w}x${h}`] = { pages: n, problems };
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(outDir, 'layout_report.json'), JSON.stringify(report, null, 1));
  const bad = Object.values(report.sizes).reduce((a, s) => a + s.problems.length, 0);
  console.log(JSON.stringify(Object.fromEntries(Object.entries(report.sizes).map(([k, v]) => [k, v.problems.length]))));
  process.exit(bad ? 1 : 0);
})();
