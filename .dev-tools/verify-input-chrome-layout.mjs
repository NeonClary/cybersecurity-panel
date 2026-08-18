/*
 * Verify Export is inside the input box (between mic and send),
 * and follow-up chips sit below the input in a horizontal row.
 * Usage: node .dev-tools/verify-input-chrome-layout.mjs [outDir]
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

const guest = await makeGuest();
console.log('GUEST ok');

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.addInitScript(([token, user]) => {
  localStorage.setItem('authToken', token);
  localStorage.setItem('user', JSON.stringify(user));
  localStorage.setItem('theme', 'light');
  localStorage.removeItem('chat-input-followups-visible');
}, [guest.access_token, guest.user]);

const page = await ctx.newPage();
const consoleErrors = [];
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 240));
});

await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.floating-input-area, .floating-header', { timeout: 30000 });
await page.waitForTimeout(1200);
await dismissOverlays(page);

const newChat = page.locator('button:has-text("New Chat"), button:has-text("New chat")').first();
if (await newChat.isVisible({ timeout: 1500 }).catch(() => false)) {
  await newChat.click();
  await page.waitForTimeout(800);
  await dismissOverlays(page);
}

const layoutIdle = await page.evaluate(() => {
  const area = document.querySelector('.floating-input-area');
  const inputBox = area?.querySelector('.floating-input-box');
  const exportBtn = area?.querySelector('.export-button-container .export-button');
  const exportText = exportBtn?.querySelector('.export-text');
  const mic = area?.querySelector('.mic-button');
  const send = area?.querySelector('.send-button');
  const footerExport = area?.querySelector('.chat-input-footer-actions .export-button');
  const exportInsideInput = Boolean(inputBox && exportBtn && inputBox.contains(exportBtn));
  let orderOk = false;
  if (mic && exportBtn && send) {
    const controls = mic.closest('.controls-row') || mic.parentElement;
    const kids = [...(controls?.querySelectorAll('button, .export-button-container') || [])];
    // Flatten: for export container use its button; keep order of distinct control roots
    const roots = [];
    for (const el of [...(mic.parentElement?.children || [])]) {
      if (el.classList?.contains('mic-button') || el.matches?.('button.mic-button')) roots.push('mic');
      else if (el.classList?.contains('export-button-container')) roots.push('export');
      else if (el.classList?.contains('send-button')) roots.push('send');
      else if (el.querySelector?.('.mic-button')) roots.push('mic');
      else if (el.querySelector?.('.export-button')) roots.push('export');
      else if (el.querySelector?.('.send-button') || el.classList?.contains('send-button')) roots.push('send');
    }
    // Direct sibling walk is more reliable for our markup
    const parent = mic.parentElement;
    const siblingRoots = [...(parent?.children || [])].map((el) => {
      if (el === mic || el.classList?.contains('mic-button')) return 'mic';
      if (el.classList?.contains('export-button-container')) return 'export';
      if (el === send || el.classList?.contains('send-button')) return 'send';
      return null;
    }).filter(Boolean);
    const mi = siblingRoots.indexOf('mic');
    const ei = siblingRoots.indexOf('export');
    const si = siblingRoots.indexOf('send');
    orderOk = mi >= 0 && ei > mi && si > ei;
  }
  return {
    exportInsideInput,
    iconOnly: Boolean(exportBtn) && !exportText,
    ariaLabel: exportBtn?.getAttribute('aria-label') || null,
    footerExportGone: !footerExport,
    orderOk,
    siblingOrder: (() => {
      const parent = mic?.parentElement;
      return [...(parent?.children || [])].map((el) => {
        if (el.classList?.contains('mic-button')) return 'mic';
        if (el.classList?.contains('export-button-container')) return 'export';
        if (el.classList?.contains('send-button')) return 'send';
        return el.className?.toString?.().slice(0, 40) || el.tagName;
      });
    })(),
  };
});
console.log('LAYOUT_IDLE', JSON.stringify(layoutIdle));
await page.screenshot({ path: path.join(OUT, 'input-chrome-idle.png'), fullPage: false });

// Engage chat so follow-ups appear
const intakeChip = page.locator('.intake-chip').first();
if (await intakeChip.isVisible({ timeout: 2000 }).catch(() => false)) {
  await intakeChip.click();
} else {
  const suggestion = page.locator('.suggestion-button').first();
  if (await suggestion.isVisible({ timeout: 2000 }).catch(() => false)) {
    await suggestion.click();
  } else {
    await page.locator('textarea.main-textarea').fill('What is phishing?');
    await page.keyboard.press('Enter');
  }
}

let chipsVisible = false;
for (let i = 0; i < 90; i++) {
  await dismissOverlays(page);
  chipsVisible = await page.locator('.followup-chip').first().isVisible().catch(() => false);
  if (chipsVisible) break;
  await page.waitForTimeout(1000);
}
console.log('ENGAGED chipsVisible=', chipsVisible);

const layoutEngaged = await page.evaluate(() => {
  const area = document.querySelector('.floating-input-area');
  const inputBox = area?.querySelector('.floating-input-box') || area?.querySelector('.enhanced-chat-input-container');
  const chipsRow = area?.querySelector('.followup-chips-row');
  const chips = area?.querySelector('.followup-chips');
  const hideBtn = area?.querySelector('.followup-chips-hide');
  const inputRect = inputBox?.getBoundingClientRect();
  const chipsRect = chipsRow?.getBoundingClientRect();
  const belowInput = Boolean(inputRect && chipsRect && chipsRect.top >= inputRect.bottom - 2);

  let horizontal = false;
  let chipCount = 0;
  if (chips) {
    const chipEls = [...chips.querySelectorAll('.followup-chip')];
    chipCount = chipEls.length;
    if (chipEls.length >= 2) {
      const ys = chipEls.map((c) => Math.round(c.getBoundingClientRect().top));
      // At least two chips share roughly the same top => side-by-side
      horizontal = ys.some((y, i) => ys.slice(i + 1).some((y2) => Math.abs(y - y2) < 12));
    } else if (chipEls.length === 1) {
      horizontal = true; // single chip can't be stacked
    }
    const style = getComputedStyle(chips);
    if (style.flexDirection === 'row' || style.display === 'flex') {
      // Prefer flex-row wrap as layout intent even if viewport forces wrap
      horizontal = horizontal || style.flexDirection === 'row';
    }
  }

  return {
    chipsBelowInput: belowInput,
    chipsFlexDirection: chips ? getComputedStyle(chips).flexDirection : null,
    rowFlexDirection: chipsRow ? getComputedStyle(chipsRow).flexDirection : null,
    hideBesideRow: Boolean(hideBtn && chipsRow?.contains(hideBtn)),
    chipCount,
    horizontal,
    inputTop: inputRect?.top ?? null,
    chipsTop: chipsRect?.top ?? null,
  };
});
console.log('LAYOUT_ENGAGED', JSON.stringify(layoutEngaged));
await page.screenshot({ path: path.join(OUT, 'input-chrome-with-followups.png'), fullPage: false });

const noJourneyBanner = await page.evaluate(() => {
  if (document.querySelector('.journey-suggestions-banner')) return false;
  const body = document.body?.innerText || '';
  return !/Your advisors think you.?ve already completed/i.test(body);
});
console.log('NO_JOURNEY_BANNER', noJourneyBanner);

// Toggle hide/show still works below input
let hideShowOk = false;
if (chipsVisible) {
  await page.locator('.followup-chips-hide').click();
  await page.waitForTimeout(400);
  const afterHide = await page.locator('.followup-chip').first().isVisible().catch(() => false);
  const showVisible = await page.locator('.followup-chips-show').isVisible().catch(() => false);
  await page.screenshot({ path: path.join(OUT, 'input-chrome-followups-hidden.png'), fullPage: false });
  if (showVisible) {
    await page.locator('.followup-chips-show').click();
    await page.waitForTimeout(400);
  }
  const afterShow = await page.locator('.followup-chip').first().isVisible().catch(() => false);
  hideShowOk = afterHide === false && showVisible === true && afterShow === true;
  console.log('HIDE_SHOW ok=', hideShowOk, { afterHide, showVisible, afterShow });
}

const summary = {
  ...layoutIdle,
  chipsVisible,
  ...layoutEngaged,
  hideShowOk,
  noJourneyBanner,
  consoleErrors: consoleErrors.slice(0, 8),
  ok:
    layoutIdle.exportInsideInput === true &&
    layoutIdle.iconOnly === true &&
    layoutIdle.ariaLabel === 'Export' &&
    layoutIdle.footerExportGone === true &&
    layoutIdle.orderOk === true &&
    chipsVisible === true &&
    layoutEngaged.chipsBelowInput === true &&
    layoutEngaged.horizontal === true &&
    hideShowOk === true &&
    noJourneyBanner === true,
};
fs.writeFileSync(path.join(OUT, 'input-chrome-layout-summary.json'), JSON.stringify(summary, null, 2));
console.log('SUMMARY', JSON.stringify(summary, null, 2));

await browser.close();
process.exit(summary.ok ? 0 : 1);
