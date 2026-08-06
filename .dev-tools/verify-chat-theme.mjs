/*
 * Live verify: guest auth → send chat message → expect advisor stream;
 * sidebar brand title; cream theme tokens; header at 900px with sidebar open.
 *
 * Usage: node .dev-tools/verify-chat-theme.mjs [outDir]
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
  const texts = ['Skip tour', 'Skip', 'Maybe later', 'Got it', 'Close', 'Dismiss', 'No thanks', 'Later'];
  for (let round = 0; round < 4; round++) {
    let clicked = false;
    for (const t of texts) {
      const btn = page.locator(`button:has-text("${t}")`).first();
      try {
        if (await btn.isVisible({ timeout: 200 })) {
          await btn.click({ timeout: 1000 });
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
console.log('GUEST ok', guest.user?.email);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await ctx.addInitScript(([token, user]) => {
  localStorage.setItem('authToken', token);
  localStorage.setItem('user', JSON.stringify(user));
  localStorage.setItem('theme', 'light');
}, [guest.access_token, guest.user]);

const page = await ctx.newPage();
const consoleErrors = [];
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 240));
});

await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.sidebar, .floating-header', { timeout: 30000 });
await page.waitForTimeout(1500);
await dismissOverlays(page);

// --- Brand in sidebar ---
const brand = await page.evaluate(() => {
  const el = document.querySelector('.sidebar-brand-title');
  return el ? el.textContent.trim() : null;
});
console.log('BRAND:', brand);
await page.screenshot({ path: path.join(OUT, 'sidebar-brand.png') });

// --- Cream theme tokens ---
const theme = await page.evaluate(() => {
  const s = getComputedStyle(document.documentElement);
  return {
    dataTheme: document.documentElement.getAttribute('data-theme'),
    bgPrimary: s.getPropertyValue('--bg-primary').trim(),
    sidebarBg: s.getPropertyValue('--sidebar-bg').trim(),
    headerBg: s.getPropertyValue('--header-bg').trim(),
    accent: s.getPropertyValue('--accent-primary').trim(),
    cardBg: s.getPropertyValue('--card-bg').trim(),
  };
});
console.log('THEME:', JSON.stringify(theme));

// --- Send a real chat message ---
await dismissOverlays(page);
const input = page.locator('textarea.main-textarea, .floating-input-box textarea, textarea').first();
await input.waitFor({ timeout: 15000 });
await input.fill('In one short sentence, what is MFA?');
await page.locator('button.send-button.enabled, button.send-button').first().click();

// Wait for advisor reply bubble or error
const deadline = Date.now() + 90000;
let advisorCount = 0;
let errorText = null;
while (Date.now() < deadline) {
  const state = await page.evaluate(() => {
    const advisors = document.querySelectorAll(
      '.advisor-message-bubble, .advisor-message-container, .advisor-message-text'
    );
    const errs = Array.from(document.querySelectorAll('.error-message, .error-message-container'))
      .map((e) => e.textContent.trim())
      .filter(Boolean);
    const thinking = document.querySelectorAll('.thinking-indicator, [class*="Thinking"]').length;
    const bodySnip = document.body.innerText.slice(0, 2500);
    return {
      advisorCount: advisors.length,
      errs,
      thinking,
      hasMfaInBody: /multi[- ]factor|MFA/i.test(bodySnip) && /authentication|factor/i.test(bodySnip),
    };
  });
  advisorCount = state.advisorCount;
  if (state.errs.length) errorText = state.errs[0].slice(0, 200);
  if (advisorCount > 0 || state.hasMfaInBody) {
    console.log('CHAT OK advisors=', advisorCount, 'mfaHint=', state.hasMfaInBody);
    break;
  }
  if (errorText && !state.thinking) {
    console.log('CHAT ERROR', errorText);
    break;
  }
  await page.waitForTimeout(1000);
}
await page.screenshot({ path: path.join(OUT, 'chat-after-send.png'), fullPage: false });

// --- Header @ 900 with sidebar open ---
await page.setViewportSize({ width: 900, height: 800 });
await page.waitForTimeout(500);
await dismissOverlays(page);
const collapsed = await page.evaluate(() =>
  document.querySelector('.sidebar')?.classList.contains('collapsed')
);
if (collapsed) {
  const toggle = page.locator('.collapsed-toggle-avatar, .sidebar-toggle').first();
  try { await toggle.click({ timeout: 2000 }); } catch { /* ok */ }
  await page.waitForTimeout(400);
}
await page.screenshot({
  path: path.join(OUT, 'header-900-sidebar.png'),
  clip: { x: 0, y: 0, width: 900, height: 120 },
});

const summary = {
  brand,
  theme,
  advisorCount,
  errorText,
  consoleErrors: consoleErrors.slice(0, 10),
  chatOk: advisorCount > 0 && !errorText,
  creamOk:
    theme.bgPrimary.toUpperCase() === '#FAF7F1' &&
    theme.sidebarBg.toUpperCase() === '#E8E0D4' &&
    theme.accent.toUpperCase() === '#5558E3',
  brandOk: Boolean(brand && /cybersecurity advisor/i.test(brand)),
};
fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2));
console.log('SUMMARY', JSON.stringify(summary, null, 2));

await browser.close();
if (!summary.chatOk || !summary.creamOk || !summary.brandOk) {
  process.exitCode = 1;
}
