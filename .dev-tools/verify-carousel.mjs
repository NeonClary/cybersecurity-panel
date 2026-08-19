/*
 * Verify advisor carousel: full cards only, arrows inside the message pane.
 * Usage: node .dev-tools/verify-carousel.mjs
 */
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const ROOT = process.cwd();
const FRONTEND = 'http://localhost:3000';
const BACKEND = 'http://localhost:8000';
const OUT = path.join('.dev-tools', 'verify-out');
fs.mkdirSync(OUT, { recursive: true });

function loadLayoutModule() {
  const srcPath = path.join(ROOT, 'frontend', 'src', 'utils', 'advisorCarouselLayout.js');
  const src = fs.readFileSync(srcPath, 'utf8')
    .replaceAll('export const', 'const')
    .replace('export function computeLayout', 'function computeLayout');
  const tmp = path.join(OUT, '_advisorCarouselLayout.mjs');
  fs.writeFileSync(tmp, `${src}\nexport { computeLayout, GAP, CONTROLS_W, PREFERRED_SLIDE, MIN_SLIDE, MAX_VISIBLE };\n`);
  return import(pathToFileURL(tmp).href);
}

function extractCarouselCss() {
  const css = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'styles', 'ChatPage.css'), 'utf8');
  const start = css.indexOf('/* Advisor carousel:');
  const end = css.indexOf('.single-response-wide');
  if (start < 0 || end < 0) throw new Error('Could not extract carousel CSS');
  return css.slice(start, end);
}

const { computeLayout, GAP, CONTROLS_W } = await loadLayoutModule();

const jest = spawnSync(
  process.platform === 'win32' ? 'npx.cmd' : 'npx',
  ['react-scripts', 'test', '--watchAll=false', '--testPathPattern=advisorCarouselLayout'],
  {
    cwd: path.join(ROOT, 'frontend'),
    env: { ...process.env, CI: 'true' },
    encoding: 'utf8',
  },
);
if (jest.status !== 0) {
  console.error(jest.stdout || '');
  console.error(jest.stderr || '');
  console.error('FAIL jest advisorCarouselLayout');
  process.exit(1);
}
console.log('PASS jest advisorCarouselLayout');

const cases = [
  { name: 'wide-1600', width: 1600, count: 3 },
  { name: 'pane-940', width: 940, count: 3 },
  { name: 'almost-3', width: 1231, count: 3 },
  { name: 'overlay-3', width: 1242, count: 4 },
  { name: 'min-2', width: 700, count: 3 },
  { name: 'narrow-420', width: 388, count: 3 },
];

const mathResults = cases.map((c) => {
  const L = computeLayout(c.width, c.count);
  const reserved = L.controlsMode === 'side' ? CONTROLS_W : 0;
  const used = L.cardsWidth + reserved;
  const ok = used <= c.width && L.visible >= 1 && L.visible <= 3;
  const wantsArrows = c.count > L.visible;
  const arrowsOk = wantsArrows ? L.controlsMode !== 'none' : L.controlsMode === 'none';
  return { ...c, ...L, used, reserved, ok, arrowsOk, wantsArrows };
});

if (mathResults.some((r) => !r.ok || !r.arrowsOk)) {
  console.error(JSON.stringify(mathResults, null, 2));
  console.error('FAIL layout math');
  process.exit(1);
}

const carouselCss = extractCarouselCss();
const browser = await chromium.launch({ headless: true, channel: 'chrome' }).catch(
  () => chromium.launch({ headless: true }),
);

async function measureFixture(page, width, count, theme) {
  const L = computeLayout(width, count);
  const reserved = L.controlsMode === 'side' ? CONTROLS_W : 0;
  const viewportWidth = L.visible * L.slideW + GAP * (L.visible - 1);
  const showControls = L.controlsMode !== 'none';
  await page.setContent(`<!doctype html>
<html data-theme="${theme}">
<head>
<style>
:root {
  --border-primary: #d6d3cd;
  --card-bg: #ffffff;
  --bg-primary: #ffffff;
  --text-primary: #1f2937;
  --accent-primary: #2563eb;
  --accent-fill: #2563eb;
  --accent-on-accent: #ffffff;
  --shadow-md: 0 4px 10px -2px rgba(40, 30, 10, 0.12);
  --shadow-lg: 0 8px 18px -4px rgba(40, 30, 10, 0.16);
}
[data-theme="dark"] {
  --border-primary: #3f3f46;
  --card-bg: #1f1f23;
  --bg-primary: #18181b;
  --text-primary: #f4f4f5;
  --accent-primary: #60a5fa;
  --accent-fill: #3b82f6;
  --shadow-md: 0 4px 10px -2px rgba(0, 0, 0, 0.4);
}
* { box-sizing: border-box; }
body { margin: 0; background: ${theme === 'dark' ? '#18181b' : '#f7f4ee'}; }
.messages-scroll {
  width: ${width + 40}px;
  padding: 20px;
  overflow-x: hidden;
  overflow-y: auto;
  height: 420px;
}
.card-mock {
  height: 220px;
  border-radius: 12px;
  border: 1px solid var(--border-primary);
  background: ${theme === 'dark' ? '#2a2430' : '#fde8e8'};
}
${carouselCss}
</style>
</head>
<body>
  <div class="messages-scroll" id="pane">
    <div class="advisor-carousel carousel-mode controls-${showControls ? L.controlsMode : 'none'}"
         style="width:100%" id="shell">
      <div class="carousel-stage" id="stage">
        <div class="carousel-viewport" id="viewport" style="width:${viewportWidth}px">
          <div class="carousel-track" style="gap:${GAP}px">
            ${Array.from({ length: count }, (_, i) => `
              <div class="carousel-slide" style="width:${L.slideW}px;flex:0 0 ${L.slideW}px">
                <div class="card-mock">card ${i + 1}</div>
              </div>`).join('')}
          </div>
        </div>
        ${showControls ? `
        <div class="carousel-controls" id="controls">
          <div class="carousel-controls-inner">
            <button class="carousel-arrow" type="button" aria-label="Previous advisor">‹</button>
            <button class="carousel-arrow" type="button" aria-label="Next advisor">›</button>
          </div>
        </div>` : ''}
      </div>
    </div>
  </div>
</body>
</html>`);

  return page.evaluate(() => {
    const pane = document.getElementById('pane');
    const shell = document.getElementById('shell');
    const viewport = document.getElementById('viewport');
    const slides = [...document.querySelectorAll('.carousel-slide')];
    const arrows = [...document.querySelectorAll('.carousel-arrow')];
    const paneR = pane.getBoundingClientRect();
    const shellR = shell.getBoundingClientRect();
    const vpR = viewport.getBoundingClientRect();
    const visibleSlides = slides.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.left < vpR.right - 2 && r.right > vpR.left + 2;
    });
    const partial = visibleSlides.filter((el) => {
      const r = el.getBoundingClientRect();
      const vis = Math.min(r.right, vpR.right) - Math.max(r.left, vpR.left);
      return vis < r.width - 2;
    });
    const arrowsClipped = arrows.filter((el) => {
      const r = el.getBoundingClientRect();
      return r.right > paneR.right + 1 || r.left < paneR.left - 1
        || r.right > shellR.right + 1 || r.width < 8;
    });
    return {
      paneW: Math.round(paneR.width),
      shellW: Math.round(shellR.width),
      vpW: Math.round(vpR.width),
      slideCount: slides.length,
      visibleSlideCount: visibleSlides.length,
      partialCount: partial.length,
      arrowCount: arrows.length,
      arrowsClipped: arrowsClipped.length,
      arrowRights: arrows.map((el) => Math.round(el.getBoundingClientRect().right)),
      paneRight: Math.round(paneR.right),
    };
  });
}

const page = await browser.newPage();
const fixture = [];
for (const c of cases) {
  for (const theme of ['light', 'dark']) {
    const m = await measureFixture(page, c.width, c.count, theme);
    const L = computeLayout(c.width, c.count);
    const failPartial = m.partialCount > 0;
    const failArrows = (c.count > L.visible) && (m.arrowCount < 2 || m.arrowsClipped > 0);
    const failVisible = m.visibleSlideCount !== L.visible;
    fixture.push({
      name: `${c.name}-${theme}`,
      layout: L,
      metrics: m,
      pass: !failPartial && !failArrows && !failVisible,
    });
    await page.screenshot({
      path: path.join(OUT, `carousel-${c.name}-${theme}.png`),
    });
  }
}

const fixtureFails = fixture.filter((f) => !f.pass);
if (fixtureFails.length) {
  console.error(JSON.stringify(fixtureFails, null, 2));
  await browser.close();
  console.error('FAIL carousel fixture overflow');
  process.exit(1);
}
console.log('PASS carousel fixtures');

let live = { skipped: true };
try {
  const health = await fetch(FRONTEND, { signal: AbortSignal.timeout(2500) });
  if (health.ok) {
    const guestRes = await fetch(`${BACKEND}/auth/guest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ choice: 'personal', free_text: null }),
    });
    if (guestRes.ok) {
      const guest = await guestRes.json();
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      await ctx.addInitScript(([token, user]) => {
        localStorage.setItem('authToken', token);
        localStorage.setItem('user', JSON.stringify(user));
        localStorage.setItem('theme', 'light');
      }, [guest.access_token, guest.user]);
      const livePage = await ctx.newPage();
      await livePage.goto(FRONTEND, { waitUntil: 'domcontentloaded' });
      await livePage.waitForSelector('.welcome-state, .floating-input-area', { timeout: 30000 });
      await livePage.waitForTimeout(800);
      const skip = livePage.locator('button:has-text("Skip tour"), button:has-text("Skip"), button:has-text("Maybe later")').first();
      if (await skip.isVisible({ timeout: 800 }).catch(() => false)) {
        await skip.click({ force: true }).catch(() => {});
      }
      const newChat = livePage.locator('button:has-text("New Chat"), button:has-text("New chat")').first();
      if (await newChat.isVisible({ timeout: 1200 }).catch(() => false)) {
        await newChat.click();
        await livePage.waitForTimeout(400);
      }
      const ta = livePage.locator('textarea, [contenteditable="true"]').first();
      await ta.click({ force: true });
      await ta.fill('What should a household do first to stay safer online?');
      await livePage.keyboard.press('Enter');
      const carousel = livePage.locator('.advisor-carousel');
      await carousel.waitFor({ timeout: 120000 });
      await livePage.waitForTimeout(1200);
      await livePage.screenshot({ path: path.join(OUT, 'carousel-live-1280.png') });

      const checkLive = async (label, vw) => {
        await livePage.setViewportSize({ width: vw, height: 800 });
        await livePage.waitForTimeout(500);
        const m = await livePage.evaluate(() => {
          const shell = document.querySelector('.advisor-carousel');
          const pane = document.querySelector('.messages-scroll');
          const vp = document.querySelector('.carousel-viewport');
          const slides = [...document.querySelectorAll('.advisor-carousel .carousel-slide')];
          const arrows = [...document.querySelectorAll('.carousel-arrow')];
          if (!shell || !vp || !pane) return { missing: true };
          const shellR = shell.getBoundingClientRect();
          const paneR = pane.getBoundingClientRect();
          const vpR = vp.getBoundingClientRect();
          const visible = slides.filter((el) => {
            const r = el.getBoundingClientRect();
            return r.left < vpR.right - 2 && r.right > vpR.left + 2 && r.width > 40;
          });
          const partial = visible.filter((el) => {
            const r = el.getBoundingClientRect();
            const vis = Math.min(r.right, vpR.right) - Math.max(r.left, vpR.left);
            return vis < r.width - 2;
          });
          const clippedArrows = arrows.filter((el) => {
            const r = el.getBoundingClientRect();
            return r.right > paneR.right + 1 || r.left < paneR.left - 1 || r.width < 8;
          });
          return {
            visible: Number(shell.dataset.visible || visible.length),
            controls: shell.dataset.controls,
            slideCount: slides.length,
            visibleSlideCount: visible.length,
            partialCount: partial.length,
            arrowCount: arrows.length,
            arrowsClipped: clippedArrows.length,
            shellW: Math.round(shellR.width),
            vpW: Math.round(vpR.width),
          };
        });
        await livePage.screenshot({ path: path.join(OUT, `carousel-live-${label}.png`) });
        return m;
      };

      live = {
        skipped: false,
        w1280: await checkLive('1280', 1280),
        w1600: await checkLive('1600', 1600),
        w900: await checkLive('900', 900),
      };
      await ctx.close();
    }
  }
} catch (err) {
  live = { skipped: true, error: String(err).slice(0, 200) };
}

await browser.close();

const liveFails = [];
if (!live.skipped) {
  for (const [label, m] of [['1280', live.w1280], ['1600', live.w1600], ['900', live.w900]]) {
    if (!m || m.missing) liveFails.push(`${label} missing carousel`);
    else {
      if (m.partialCount > 0) liveFails.push(`${label} partial cards`);
      if (m.slideCount > m.visibleSlideCount && (m.arrowCount < 2 || m.arrowsClipped > 0)) {
        liveFails.push(`${label} arrows missing/clipped`);
      }
    }
  }
}

const summary = { mathResults, fixture, live, liveFails };
fs.writeFileSync(path.join(OUT, 'carousel-summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify({ math: mathResults.map((r) => ({ name: r.name, visible: r.visible, mode: r.controlsMode, used: r.used })), live, liveFails }, null, 2));

if (liveFails.length) {
  console.error('FAIL live carousel layout');
  process.exit(1);
}
console.log('Carousel verify finished');
