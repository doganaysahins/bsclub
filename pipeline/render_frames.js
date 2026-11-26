// Usage: node render_frames.js <page.html> <timeline.json> <outdir> <fps>
// Renders deterministic frames; reuses the previous frame while nothing animates.
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const [page_, tl_, out, fpsS] = process.argv.slice(2);
  const fps = +fpsS || 30;
  const tl = JSON.parse(fs.readFileSync(tl_, 'utf8'));
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.resolve(page_));
  await page.evaluate(() => document.fonts.ready);
  const total = Math.ceil(tl.total * fps);
  const ANIM = 1.4; // seconds of motion after each scene start
  let last = null;
  for (let f = 0; f < total; f++) {
    const t = f / fps;
    const sc = tl.starts.filter(s => s <= t + 1e-6).pop();
    const moving = (t - sc) < ANIM;
    const file = path.join(out, `f${String(f).padStart(5, '0')}.jpg`);
    if (moving || last === null || f === 0) {
      await page.evaluate(tt => window.setT(tt), t);
      await page.screenshot({ path: file, type: 'jpeg', quality: 92 });
      last = file;
    } else {
      fs.copyFileSync(last, file);
    }
  }
  if (tl.cover) {
    await page.evaluate(() => window.showCover());
    await page.screenshot({ path: tl.cover, type: 'jpeg', quality: 92 });
  }
  await browser.close();
})();
