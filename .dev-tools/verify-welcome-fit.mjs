/*
 * Verify empty/first chat (welcome + Getting Started + input) fits without
 * vertical scroll in the chat main pane.
 * Usage: node .dev-tools/verify-welcome-fit.mjs [outDir]
 */
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = 'http://localhost:3000';
const BACKEND = 'http://localhost:8000';
const OUT = process.argv[2] || path.join('.dev-tools', 'verify-out');
fs.mkdirSync(OUT, { recursive: true });

async function makeGuest() {
  const r = await fetch(`${BACKEND}/auth/guest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ choice: 'personal', free_text: null }),
  });
  if (!r.ok) throw new Error(`guest auth failed: ${r.status} ${await r.text()}`);
  return r.json();
}

async function dismissOverlays(page) {
  await page.evaluate(() => {
    document.getElementById('webpack-dev-server-client-overlay')?.remove();
    document.querySelector('iframe#webpack-dev-server-client-overlay')?.remove();
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
          await page.waitForTimeout(250);
          break;
        }
      } catch { /* keep going */ }
    }
    if (!clicked) break;
  }
}

function measureWelcome() {
  const welcome = document.querySelector('.welcome-state');
  const greeting = document.querySelector('.intake-greeting');
  const gettingStarted = document.querySelector('.suggestions-title');
  const lastCard = [...document.querySelectorAll('.suggestion-category')].pop();
  const input = document.querySelector('.floating-input-box')
    || document.querySelector('.floating-input-area');
  const chatContent = document.querySelector('.chat-content');
  const header = document.querySelector('.floating-header, .app-header');
  if (!welcome) return { error: 'no .welcome-state' };

  const wRect = welcome.getBoundingClientRect();
  const gRect = greeting?.getBoundingClientRect();
  const gsRect = gettingStarted?.getBoundingClientRect();
  const cardRect = lastCard?.getBoundingClientRect();
  const inRect = input?.getBoundingClientRect();
  const headerRect = header?.getBoundingClientRect();

  const scrollOverflow = Math.max(0, welcome.scrollHeight - welcome.clientHeight);
  const pageScroll = Math.max(
    0,
    document.documentElement.scrollHeight - window.innerHeight,
  );
  const cardsAboveInput = Boolean(
    cardRect && inRect && cardRect.bottom <= inRect.top + 2,
  );
  const greetingGap = gRect && headerRect
    ? Math.round(gRect.top - headerRect.bottom)
    : null;
  const chipsEl = document.querySelector('.intake-chips');
  const chipEl = document.querySelector('.intake-chip');
  const cardTitle = document.querySelector('.category-title');
  const gettingStartedGap = gsRect && gRect
    ? Math.round(gsRect.top - (chipsEl?.getBoundingClientRect().bottom || gRect.bottom))
    : null;
  const cs = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    return { fontSize: s.fontSize, fontWeight: s.fontWeight, lineHeight: s.lineHeight };
  };

  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    welcome: {
      clientHeight: Math.round(welcome.clientHeight),
      scrollHeight: Math.round(welcome.scrollHeight),
      scrollTop: welcome.scrollTop,
      overflowY: getComputedStyle(welcome).overflowY,
      paddingTop: getComputedStyle(welcome).paddingTop,
    },
    chatContentPadBottom: chatContent ? getComputedStyle(chatContent).paddingBottom : null,
    headerBottom: headerRect ? Math.round(headerRect.bottom) : null,
    greetingTop: gRect ? Math.round(gRect.top) : null,
    greetingGapFromHeader: greetingGap,
    gettingStartedTop: gsRect ? Math.round(gsRect.top) : null,
    chipsToGettingStartedGap: gettingStartedGap,
    lastCardBottom: cardRect ? Math.round(cardRect.bottom) : null,
    inputTop: inRect ? Math.round(inRect.top) : null,
    scrollOverflow,
    pageScroll,
    noWelcomeScroll: scrollOverflow <= 1 && welcome.scrollTop === 0,
    cardsFullyAboveInput: cardsAboveInput,
    greetingVisible: Boolean(gRect && gRect.top >= 0 && gRect.bottom <= window.innerHeight),
    gettingStartedVisible: Boolean(gsRect && gsRect.top >= 0 && gsRect.bottom <= window.innerHeight),
    type: {
      greeting: cs(greeting),
      gettingStarted: cs(gettingStarted),
      intakeChip: cs(chipEl),
      cardTitle: cs(cardTitle),
    },
  };
}

const guest = await makeGuest();
console.log('GUEST ok');

const browser = await chromium.launch({
  headless: true,
  channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge',
});
const viewports = [
  { width: 1280, height: 800 },
  { width: 1280, height: 768 },
  { width: 1280, height: 720 },
];
const results = [];

for (const vp of viewports) {
  const ctx = await browser.newContext({ viewport: vp });
  await ctx.addInitScript(([token, user]) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('theme', 'light');
    localStorage.removeItem('chat-input-followups-visible');
  }, [guest.access_token, guest.user]);

  const page = await ctx.newPage();
  await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.welcome-state, .floating-header', { timeout: 30000 });
  await page.waitForTimeout(1400);
  await dismissOverlays(page);

  const newChat = page.locator('button:has-text("New Chat"), button:has-text("New chat")').first();
  if (await newChat.isVisible({ timeout: 1500 }).catch(() => false)) {
    await newChat.click();
    await page.waitForTimeout(800);
    await dismissOverlays(page);
  }

  await page.waitForSelector('.welcome-state .intake-greeting, .intake-greeting', { timeout: 15000 });
  await page.waitForSelector('.suggestions-title', { timeout: 10000 });
  await page.waitForTimeout(400);

  const metrics = await page.evaluate(measureWelcome);
  const name = `${vp.width}x${vp.height}`;
  await page.screenshot({
    path: path.join(OUT, `welcome-fit-${name}.png`),
    fullPage: false,
  });
  const ok =
    metrics.noWelcomeScroll === true &&
    metrics.cardsFullyAboveInput === true &&
    metrics.greetingVisible === true &&
    metrics.gettingStartedVisible === true &&
    metrics.pageScroll <= 1;
  results.push({ name, ok, metrics });
  console.log('VIEWPORT', name, JSON.stringify({ ok, metrics }, null, 2));
  await ctx.close();
}

const summary = {
  ok: results.every((r) => r.ok),
  results,
};
fs.writeFileSync(path.join(OUT, 'welcome-fit-summary.json'), JSON.stringify(summary, null, 2));
console.log('SUMMARY', JSON.stringify(summary, null, 2));

await browser.close();
process.exit(summary.ok ? 0 : 1);
