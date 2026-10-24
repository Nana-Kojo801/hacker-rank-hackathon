// Render still frames for checking a layout without encoding video.
// usage: node preview.js <timeline.json> <out_dir> [scene_id ...]   (default: every scene, at its end)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [tlPath, outDir, ...only] = process.argv.slice(2);
  const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8'));
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('file://' + path.join(__dirname, 'scenes.html'));
  await page.evaluate(() => document.fonts.ready);
  const missing = await page.evaluate((t) => window.__init(t), tl);
  if (missing.length) console.log('MISSING', missing);
  const shots = [['title', tl.scenes[0].start - 0.3]].concat(tl.scenes.map((s) => [s.id, s.end - 0.3]));
  for (const [id, t] of shots) {
    if (only.length && !only.includes(id)) continue;
    await page.evaluate((x) => window.__seek(x), t);
    await page.screenshot({ path: path.join(outDir, `${String(tl.chapter).padStart(2, '0')}_${id}.png`) });
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
