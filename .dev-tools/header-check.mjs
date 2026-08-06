/*
 * Live header verification: opens the dev frontend as a guest, walks
 * Chat / Journey / Workspace / Documents at several viewport widths,
 * screenshots the header, and measures real element overlaps.
 *
 * Usage: node header-check.mjs <outDir> [label]
 */
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:3000';
const BACKEND = 'http://localhost:8000';
const WIDTHS = [1280, 1024, 900, 768, 500, 375];
const PAGES = ['chat', 'journey', 'workspace', 'deliverables'];
const OUT = process.argv[2] || 'shots';
const LABEL = process.argv[3] || '';

fs.mkdirSync(OUT, { recursive: true });

async function makeGuest() {
  const r = await fetch(`${BACKEND}/auth/guest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choice: 'business', free_text: null }),
  });
  if (!r.ok) throw new Error(`guest auth failed: ${r.status} ${await r.text()}`);
  return r.json();
}

async function dismissOverlays(page) {
  // Tours / onboarding / modals that may cover the header.
  const texts = ['Skip tour', 'Skip', 'Maybe later', 'Got it', 'Close', 'Dismiss', 'No thanks', 'Later'];
  for (let round = 0; round < 4; round++) {
    let clicked = false;
    for (const t of texts) {
      const btn = page.locator(`button:has-text("${t}")`).first();
      try {
        if (await btn.isVisible({ timeout: 200 })) {
          await btn.click({ timeout: 1000 });
          clicked = true;
          await page.waitForTimeout(300);
          break;
        }
      } catch { /* keep going */ }
    }
    if (!clicked) {
      const x = page.locator('button[aria-label="Close"], button[aria-label="Close tour"], button[aria-label="Dismiss"]').first();
      try {
        if (await x.isVisible({ timeout: 200 })) {
          await x.click({ timeout: 1000 });
          await page.waitForTimeout(300);
          continue;
        }
      } catch { /* fine */ }
      break;
    }
  }
}

async function gotoView(page, view) {
  // Wide viewport first so the pill tabs are visible for navigation.
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(250);
  await dismissOverlays(page);
  const tabName = { chat: 'Chat', journey: 'Journey', workspace: 'Workspace', deliverables: 'Documents' }[view];
  const tab = page.locator(`.chat-view-tabs button:has-text("${tabName}")`).first();
  await tab.click({ timeout: 5000 });
  await page.waitForTimeout(1200);
  await dismissOverlays(page);
}

/** Measure overlaps between visible header elements. Runs in the page. */
function analyzeHeader() {
  const header = document.querySelector('.floating-header');
  if (!header) return { error: 'no .floating-header found' };
  const hr = header.getBoundingClientRect();

  const els = [];
  const walk = (node, pathStr) => {
    for (const child of node.children) {
      const cs = getComputedStyle(child);
      if (cs.display === 'none' || cs.visibility === 'hidden') continue;
      const r = child.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      const id =
        child.tagName.toLowerCase() +
        (child.className && typeof child.className === 'string'
          ? '.' + child.className.trim().split(/\s+/).slice(0, 2).join('.')
          : '');
      const label = (child.textContent || '').trim().slice(0, 25);
      els.push({ id: `${pathStr}>${id}`, label, r: { x: r.x, y: r.y, w: r.width, h: r.height }, el: child });
      walk(child, `${pathStr}>${id}`);
    }
  };
  walk(header, 'header');

  const overlaps = [];
  for (let i = 0; i < els.length; i++) {
    for (let j = i + 1; j < els.length; j++) {
      const a = els[i], b = els[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const ix = Math.min(a.r.x + a.r.w, b.r.x + b.r.w) - Math.max(a.r.x, b.r.x);
      const iy = Math.min(a.r.y + a.r.h, b.r.y + b.r.h) - Math.max(a.r.y, b.r.y);
      if (ix > 3 && iy > 3) {
        overlaps.push({
          a: `${a.id} "${a.label}"`,
          b: `${b.id} "${b.label}"`,
          ix: Math.round(ix),
          iy: Math.round(iy),
        });
      }
    }
  }
  // De-dup: keep only overlaps between elements in *different* top-level slots,
  // since nested descendants duplicate their parents' overlap.
  const slot = (id) => (id.split('>')[1] || '').split('.').slice(1).join('.');
  const topLevel = overlaps.filter((o) => {
    const sa = o.a.split('>')[1] || '', sb = o.b.split('>')[1] || '';
    return sa !== sb;
  });

  const pageOverflowX = document.documentElement.scrollWidth - window.innerWidth;
  const headerChildrenBeyondRight = els
    .filter((e) => e.r.x + e.r.w > hr.right + 2)
    .map((e) => `${e.id} "${e.label}" right=${Math.round(e.r.x + e.r.w)} headerRight=${Math.round(hr.right)}`);

  return {
    headerRect: { x: Math.round(hr.x), y: Math.round(hr.y), w: Math.round(hr.width), h: Math.round(hr.height) },
    overlapCount: topLevel.length,
    overlaps: topLevel.slice(0, 30),
    pageOverflowX,
    headerChildrenBeyondRight,
  };
}

const results = [];
const guest = await makeGuest();
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await ctx.addInitScript(
  ([token, user]) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('user', JSON.stringify(user));
    // Pre-mark tours as seen where the app uses flags.
    for (const k of ['canvas-tour-seen-v1', 'onboarding-tour-seen', 'tour-seen', 'canvas-welcome-tour-v1']) {
      try { localStorage.setItem(k, '1'); } catch {}
    }
  },
  [guest.access_token, guest.user],
);
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') console.log('[console.error]', m.text().slice(0, 200)); });

await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.floating-header', { timeout: 30000 });
await page.waitForTimeout(1500);
await dismissOverlays(page);

// --- Issue 1 check: Journey tracks render for a guest ---
await gotoView(page, 'journey');
await page.waitForTimeout(1500);
const journeyText = await page.evaluate(() => document.body.innerText.slice(0, 4000));
const journeyFailed = /failed to load tracks/i.test(journeyText);
const trackNames = ['Certification Path', 'CIS', 'Custom', 'ITIL', 'NIST', 'Personal Digital Security'];
const seenTracks = trackNames.filter((t) => journeyText.toLowerCase().includes(t.toLowerCase()));
console.log(`JOURNEY: failedBanner=${journeyFailed} tracksVisible=${JSON.stringify(seenTracks)}`);
await page.screenshot({ path: path.join(OUT, `journey-full-1280${LABEL}.png`) });

// --- Issue 2: header at all widths on all pages ---
for (const view of PAGES) {
  await gotoView(page, view);
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.waitForTimeout(450);
    await dismissOverlays(page);
    const analysis = await page.evaluate(analyzeHeader);
    const hh = analysis.headerRect ? analysis.headerRect.h + analysis.headerRect.y : 120;
    const clipH = Math.min(Math.max(hh + 24, 90), 300);
    const file = path.join(OUT, `${view}-${w}${LABEL}.png`);
    await page.screenshot({ path: file, clip: { x: 0, y: 0, width: w, height: clipH } });
    results.push({ view, width: w, ...analysis });
    const flag = analysis.overlapCount > 0 || (analysis.pageOverflowX || 0) > 2 || (analysis.headerChildrenBeyondRight || []).length > 0;
    console.log(`${flag ? 'PROBLEM' : 'ok     '} ${view}@${w} overlaps=${analysis.overlapCount} overflowX=${analysis.pageOverflowX} beyondRight=${(analysis.headerChildrenBeyondRight || []).length}`);
  }
}

fs.writeFileSync(path.join(OUT, `analysis${LABEL}.json`), JSON.stringify(results, null, 2));
await browser.close();
console.log('DONE');
