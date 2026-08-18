/*
 * Local smoke: welcome fit, preachy gone, follow-up chip row, carousel multi-card.
 * Usage: node .dev-tools/verify-qa-smoke.mjs
 */
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:3000';
const BACKEND = 'http://localhost:8000';
const OUT = path.join('.dev-tools', 'verify-out');
fs.mkdirSync(OUT, { recursive: true });

async function makeGuest(choice = 'personal') {
  const r = await fetch(`${BACKEND}/auth/guest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choice, free_text: null }),
  });
  if (!r.ok) throw new Error(`guest auth failed: ${r.status} ${await r.text()}`);
  return r.json();
}

async function dismissOverlays(page) {
  await page.evaluate(() => {
    document.getElementById('webpack-dev-server-client-overlay')?.remove();
  }).catch(() => {});
  const texts = ['Skip tour', 'Skip', 'Maybe later', 'Got it', 'Close', 'Dismiss', 'No thanks', 'Later'];
  for (let round = 0; round < 4; round++) {
    let clicked = false;
    for (const t of texts) {
      const btn = page.locator(`button:has-text("${t}")`).first();
      try {
        if (await btn.isVisible({ timeout: 200 })) {
          await btn.click({ timeout: 1000, force: true });
          clicked = true;
          await page.waitForTimeout(200);
          break;
        }
      } catch { /* continue */ }
    }
    if (!clicked) break;
  }
}

const guest = await makeGuest();
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await ctx.addInitScript(([token, user]) => {
  localStorage.setItem('authToken', token);
  localStorage.setItem('user', JSON.stringify(user));
  localStorage.setItem('theme', 'light');
  localStorage.removeItem('chat-input-followups-visible');
}, [guest.access_token, guest.user]);

const page = await ctx.newPage();
const pageErrors = [];
page.on('pageerror', (e) => pageErrors.push(String(e).slice(0, 300)));
page.on('console', (m) => {
  if (m.type() === 'error') pageErrors.push(m.text().slice(0, 300));
});

await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.welcome-state, .floating-input-area', { timeout: 30000 });
await page.waitForTimeout(1500);
await dismissOverlays(page);

const bodyText = await page.locator('body').innerText();
const hasPreachy = /preachy/i.test(bodyText);
const hasLecturing = /lecturing/i.test(bodyText);

const welcome = await page.evaluate(() => {
  const pane = document.querySelector('.welcome-state');
  if (!pane) return { missing: true };
  const input = document.querySelector('.floating-input-area');
  const lastCard = pane.querySelector('.suggestion-category:last-child, .suggestions-grid > :last-child');
  return {
    paneScroll: pane.scrollHeight - pane.clientHeight,
    lastCardBottom: lastCard ? lastCard.getBoundingClientRect().bottom : null,
    inputTop: input ? input.getBoundingClientRect().top : null,
  };
});
await page.screenshot({ path: path.join(OUT, 'qa-welcome-1280.png'), fullPage: true });

const newChat = page.locator('button:has-text("New Chat"), button:has-text("New chat")').first();
if (await newChat.isVisible({ timeout: 1500 }).catch(() => false)) {
  await newChat.click();
  await page.waitForTimeout(500);
}

const ta = page.locator('textarea, [contenteditable="true"]').first();
await ta.click({ force: true });
await ta.fill('What should a household do first to stay safer online?');
await page.keyboard.press('Enter');

const carousel = page.locator('.advisor-carousel');
await carousel.waitFor({ timeout: 120000 }).catch(() => null);
await page.waitForTimeout(2500);
await page.screenshot({ path: path.join(OUT, 'qa-chat-1280.png') });

const chatMetrics = await page.evaluate(() => {
  const slides = [...document.querySelectorAll('.advisor-carousel .carousel-slide')];
  const visibleSlides = slides.filter((el) => {
    const r = el.getBoundingClientRect();
    const vp = el.closest('.carousel-viewport');
    if (!vp) return r.width > 40;
    const vr = vp.getBoundingClientRect();
    return r.left < vr.right - 8 && r.right > vr.left + 8 && r.width > 40;
  });
  const row = document.querySelector('.followup-chips-row');
  const chips = [...document.querySelectorAll('.followup-chip')];
  const chipTops = chips.map((c) => Math.round(c.getBoundingClientRect().top));
  const uniqueTops = [...new Set(chipTops)];
  const input = document.querySelector('.enhanced-chat-input-container, .floating-input-box');
  return {
    slideCount: slides.length,
    visibleSlideCount: visibleSlides.length,
    showingAll: !!document.querySelector('.advisor-carousel.showing-all'),
    hasArrows: !!document.querySelector('.carousel-arrow'),
    chipCount: chips.length,
    chipRowTops: uniqueTops.length,
    chipRowWidth: row ? Math.round(row.getBoundingClientRect().width) : 0,
    inputWidth: input ? Math.round(input.getBoundingClientRect().width) : 0,
    overlay: !!document.getElementById('webpack-dev-server-client-overlay'),
  };
});

await page.setViewportSize({ width: 420, height: 800 });
await page.waitForTimeout(400);
const narrowChips = await page.evaluate(() => {
  const chips = [...document.querySelectorAll('.followup-chip')];
  const tops = [...new Set(chips.map((c) => Math.round(c.getBoundingClientRect().top)))];
  return { chipCount: chips.length, chipRowTops: tops.length };
});
await page.screenshot({ path: path.join(OUT, 'qa-chat-420.png') });

await browser.close();

const result = {
  hasPreachy,
  hasLecturing,
  welcome,
  chatMetrics,
  narrowChips,
  pageErrors: pageErrors.slice(0, 8),
};
fs.writeFileSync(path.join(OUT, 'qa-smoke.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));

const compileErr = pageErrors.some((e) => /Compiled with problems|is not defined/i.test(e));
if (compileErr) {
  console.error('FAIL compile errors');
  process.exit(1);
}
if (hasPreachy) {
  console.error('FAIL preachy still present');
  process.exit(1);
}
if (welcome && !welcome.missing && welcome.paneScroll > 8) {
  console.error('FAIL welcome still scrolls', welcome.paneScroll);
  process.exit(1);
}
console.log('QA smoke finished');
