/** Bound in-memory + sessionStorage cache of prefetch NDJSON chat streams. */

const STORE_KEY = 'csa.starterPrefetch.v1';
export const MAX_PREFETCH_PROMPTS = 8;

const memory = new Map();

function normalizePrompt(prompt) {
  return String(prompt || '').replace(/\s+/g, ' ').trim();
}

function readStore(userKey) {
  try {
    const raw = sessionStorage.getItem(`${STORE_KEY}:${userKey}`);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(userKey, data) {
  try {
    sessionStorage.setItem(`${STORE_KEY}:${userKey}`, JSON.stringify(data));
  } catch {
    /* ignore */
  }
}

function touchMemory(userKey, prompt, entry) {
  const key = `${userKey}::${prompt}`;
  memory.set(key, entry);
  while (memory.size > MAX_PREFETCH_PROMPTS * 4) {
    const first = memory.keys().next().value;
    memory.delete(first);
  }
}

export function getPrefetchedStream(userKey, prompt) {
  const p = normalizePrompt(prompt);
  if (!p) return null;
  const mem = memory.get(`${userKey}::${p}`);
  if (mem?.lines?.length) return mem;
  const stored = readStore(userKey)[p];
  if (stored?.lines?.length) {
    touchMemory(userKey, p, stored);
    return stored;
  }
  return null;
}

export function putPrefetchedStream(userKey, prompt, lines) {
  const p = normalizePrompt(prompt);
  if (!p || !Array.isArray(lines) || lines.length === 0) return;
  const entry = { lines, ts: Date.now() };
  touchMemory(userKey, p, entry);
  const stored = readStore(userKey);
  stored[p] = entry;
  const keys = Object.keys(stored);
  if (keys.length > MAX_PREFETCH_PROMPTS) {
    keys
      .sort((a, b) => (stored[a].ts || 0) - (stored[b].ts || 0))
      .slice(0, keys.length - MAX_PREFETCH_PROMPTS)
      .forEach((k) => { delete stored[k]; });
  }
  writeStore(userKey, stored);
}

export function dropPrefetchedStream(userKey, prompt) {
  const p = normalizePrompt(prompt);
  memory.delete(`${userKey}::${p}`);
  const stored = readStore(userKey);
  if (stored[p]) {
    delete stored[p];
    writeStore(userKey, stored);
  }
}

export async function readNdjsonLines(response) {
  if (!response?.body) return [];
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const lines = [];
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n');
    buffer = parts.pop() ?? '';
    parts.forEach((line) => {
      if (line.trim()) lines.push(line);
    });
  }
  if (buffer.trim()) lines.push(buffer);
  return lines;
}
