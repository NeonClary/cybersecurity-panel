/** Persist starter greeting + Getting Started chips per user/goal. */

const SUGGESTIONS_PREFIX = 'csa.starterSuggestions.v1:';
const GREETING_PREFIX = 'csa.starterGreeting.v1:';

function storage() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function localStore() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readJson(store, key) {
  if (!store) return null;
  try {
    const raw = store.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeJson(store, key, value) {
  if (!store) return;
  try {
    store.setItem(key, JSON.stringify(value));
  } catch {
    /* quota / private mode */
  }
}

export function loadStarterSuggestions(cacheKey) {
  if (!cacheKey) return null;
  const key = SUGGESTIONS_PREFIX + cacheKey;
  return readJson(storage(), key) || readJson(localStore(), key);
}

export function saveStarterSuggestions(cacheKey, payload) {
  if (!cacheKey) return;
  const key = SUGGESTIONS_PREFIX + cacheKey;
  const body = { ...payload, ts: Date.now() };
  writeJson(storage(), key, body);
  writeJson(localStore(), key, body);
}

export function loadStarterGreeting(cacheKey) {
  if (!cacheKey) return null;
  const key = GREETING_PREFIX + cacheKey;
  return readJson(storage(), key) || readJson(localStore(), key);
}

export function saveStarterGreeting(cacheKey, payload) {
  if (!cacheKey) return;
  const key = GREETING_PREFIX + cacheKey;
  const body = { ...payload, ts: Date.now() };
  writeJson(storage(), key, body);
  writeJson(localStore(), key, body);
}
