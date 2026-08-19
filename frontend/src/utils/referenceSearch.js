/**
 * Build citation-oriented search queries and URLs for advisor answers.
 *
 * Websites cannot read the browser's default search engine. Web search opens
 * in a new tab (the user's default browser); the engine is configurable via
 * localStorage key `webSearchEngine` (google | ddg | bing | brave).
 */

export const SEARCH_QUERY_MAX_CHARS = 1700;
export const WEB_SEARCH_ENGINE_KEY = 'webSearchEngine';

export const WEB_SEARCH_ENGINES = {
  google: {
    id: 'google',
    label: 'Google',
    url: 'https://www.google.com/search?q=',
  },
  ddg: {
    id: 'ddg',
    label: 'DuckDuckGo',
    url: 'https://duckduckgo.com/?q=',
  },
  bing: {
    id: 'bing',
    label: 'Bing',
    url: 'https://www.bing.com/search?q=',
  },
  brave: {
    id: 'brave',
    label: 'Brave',
    url: 'https://search.brave.com/search?q=',
  },
};

const CLAIM_HINT =
  /\b(must|should|require|requires|nist|iso|cve|cisa|owasp|because|therefore|according|standard|framework|control|risk|attack|vulnerability|encrypt|mfa|zero[- ]trust|gdpr|hipaa|pci)\b/i;

export function stripSearchMarkdown(md) {
  if (!md) return '';
  return String(md)
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/#{1,6}\s?/g, '')
    .replace(/[*_~]{1,3}([^*_~]+)[*_~]{1,3}/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '$1')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function splitAssertions(text) {
  if (!text) return [];
  return text
    .replace(/([.!?])\s+/g, '$1\n')
    .split(/\n+/)
    .map((s) => s.replace(/^[\s•●▪◦-]+/, '').trim())
    .filter((s) => s.length >= 28 && s.length <= 280)
    .filter((s) => !/^(hi|hello|thanks|thank you)\b/i.test(s));
}

export function extractAssertions(text, { maxClaims = 6 } = {}) {
  const cleaned = stripSearchMarkdown(text);
  const parts = splitAssertions(cleaned);
  const scored = parts.map((claim, index) => ({
    claim,
    index,
    score: (CLAIM_HINT.test(claim) ? 3 : 0) + Math.min(2, Math.floor(claim.length / 80)),
  }));
  scored.sort((a, b) => b.score - a.score || a.index - b.index);
  const picked = [];
  const seen = new Set();
  for (const item of scored) {
    const key = item.claim.slice(0, 48).toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    picked.push(item.claim.replace(/[.]+$/, ''));
    if (picked.length >= maxClaims) break;
  }
  if (picked.length === 0 && cleaned) {
    picked.push(cleaned.slice(0, 220).trim());
  }
  return picked;
}

export function truncateQuery(text, maxChars = SEARCH_QUERY_MAX_CHARS) {
  const value = String(text || '').trim();
  if (value.length <= maxChars) return value;
  const sliced = value.slice(0, maxChars);
  const lastBreak = Math.max(sliced.lastIndexOf(' '), sliced.lastIndexOf(','), sliced.lastIndexOf(';'));
  return `${(lastBreak > 40 ? sliced.slice(0, lastBreak) : sliced).trim()}…`;
}

export function buildReferenceSearchQuery({
  advisorText = '',
  userQuestion = '',
  advisorName = '',
} = {}) {
  const assertions = extractAssertions(advisorText);
  const claimBlock = assertions.map((c, i) => `${i + 1}. ${c}`).join(' ');
  const who = advisorName ? ` in the ${advisorName} advisor answer` : ' in the advisor answer';
  const context = userQuestion
    ? ` User question for context: "${stripSearchMarkdown(userQuestion).slice(0, 220)}".`
    : '';
  const query = [
    'Find primary sources, standards, and reputable citations that support or challenge these claims',
    `${who}:`,
    claimBlock,
    context,
    'Prefer NIST, CISA, ISO, OWASP, RFCs, vendor advisories, and peer-reviewed sources over blogs.',
  ].filter(Boolean).join(' ');
  return truncateQuery(query);
}

export function getWebSearchEngine(storage = (typeof localStorage !== 'undefined' ? localStorage : null)) {
  try {
    const id = storage?.getItem?.(WEB_SEARCH_ENGINE_KEY);
    if (id && WEB_SEARCH_ENGINES[id]) return WEB_SEARCH_ENGINES[id];
  } catch {
    /* ignore quota / private mode */
  }
  return WEB_SEARCH_ENGINES.google;
}

export function setWebSearchEngine(id, storage = (typeof localStorage !== 'undefined' ? localStorage : null)) {
  const engine = WEB_SEARCH_ENGINES[id] || WEB_SEARCH_ENGINES.google;
  try {
    storage?.setItem?.(WEB_SEARCH_ENGINE_KEY, engine.id);
  } catch {
    /* ignore */
  }
  return engine;
}

export function buildWebSearchUrl(query, engineId) {
  const engine = (engineId && WEB_SEARCH_ENGINES[engineId]) || getWebSearchEngine();
  return `${engine.url}${encodeURIComponent(query || '')}`;
}

export function buildPerplexityUrl(query) {
  return `https://www.perplexity.ai/?q=${encodeURIComponent(query || '')}`;
}

export function formatReferenceSnippet(text) {
  const trimmed = String(text || '').trim();
  return `Here are references I found:\n\n${trimmed}`;
}

export function wrapReferencesForAdvisorContext(snippet) {
  const body = String(snippet || '').trim();
  if (!body) return '';
  return [
    '[User-provided references from web search. Treat these as supporting sources; use them to support or challenge claims in your answer.]',
    body,
  ].join('\n\n');
}

export async function readClipboardText() {
  if (typeof navigator === 'undefined' || !navigator.clipboard?.readText) {
    const err = new Error('Clipboard API unavailable');
    err.code = 'unavailable';
    throw err;
  }
  try {
    const text = await navigator.clipboard.readText();
    return { text: String(text || ''), via: 'clipboard' };
  } catch (cause) {
    const err = new Error(cause?.message || 'Clipboard permission denied');
    err.code = 'denied';
    err.cause = cause;
    throw err;
  }
}
