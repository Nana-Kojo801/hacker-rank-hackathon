// Render one chapter: drive scenes.html frame by frame from a timeline and pipe JPEG frames into ffmpeg.
// usage: node render.js <timeline.json> <audio.wav> <out.mp4>
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const [tlPath, wav, out] = process.argv.slice(2);
  const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'scenes.html'));
  await page.evaluate(() => document.fonts.ready);
  const missing = await page.evaluate((t) => window.__init(t), tl);
  if (missing.length) throw new Error('scenes missing from scenes.html: ' + missing.join(', '));

  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(tl.fps), '-c:v', 'mjpeg',
    '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
    '-r', String(tl.fps), '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => ff.on('close', (c) => (c === 0 ? res() : rej(new Error('ffmpeg ' + c)))));

  const frames = Math.ceil(tl.duration * tl.fps);
  let lastKey = null, buf = null, shots = 0;
  for (let f = 0; f < frames; f++) {
    const key = await page.evaluate((t) => window.__seek(t), f / tl.fps);
    if (key !== lastKey) {
      buf = await page.screenshot({ type: 'jpeg', quality: 92 });
      lastKey = key;
      shots++;
    }
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await done;
  await browser.close();
  console.log(`chapter ${tl.chapter}: ${frames} frames, ${shots} rendered`);
})().catch((e) => { console.error(e); process.exit(1); });
