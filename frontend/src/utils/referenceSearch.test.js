import {
  extractAssertions,
  buildReferenceSearchQuery,
  buildWebSearchUrl,
  buildPerplexityUrl,
  truncateQuery,
  formatReferenceSnippet,
  wrapReferencesForAdvisorContext,
  getWebSearchEngine,
  setWebSearchEngine,
  SEARCH_QUERY_MAX_CHARS,
  readClipboardText,
} from './referenceSearch';

describe('reference search query builder', () => {
  test('extracts claim-like sentences from advisor markdown', () => {
    const text = `
## Guidance
You **must** enable MFA on every privileged account.
Teams should adopt a NIST CSF 2.0 program with clear ownership.
Hello there.
`;
    const claims = extractAssertions(text);
    expect(claims.some((c) => /MFA/i.test(c))).toBe(true);
    expect(claims.some((c) => /NIST/i.test(c))).toBe(true);
    expect(claims.join(' ')).not.toMatch(/Hello there/i);
  });

  test('builds a citation-oriented prompt with user context and stays under URL limits', () => {
    const query = buildReferenceSearchQuery({
      advisorName: 'Compliance Officer',
      userQuestion: 'How should we handle PCI DSS logging?',
      advisorText: 'PCI DSS requires retaining audit logs for at least one year. You must protect log integrity with WORM or equivalent controls.',
    });
    expect(query).toMatch(/primary sources, standards, and reputable citations/i);
    expect(query).toMatch(/PCI DSS/);
    expect(query).toMatch(/User question for context/);
    expect(query.length).toBeLessThanOrEqual(SEARCH_QUERY_MAX_CHARS);
  });

  test('truncates long queries on a word boundary', () => {
    const long = 'word '.repeat(800);
    const out = truncateQuery(long, 80);
    expect(out.length).toBeLessThanOrEqual(81);
    expect(out.endsWith('…')).toBe(true);
    expect(out).not.toMatch(/wo…$/);
  });

  test('builds Perplexity and web-search URLs with the encoded query', () => {
    const q = 'Find primary sources: MFA is required';
    expect(buildPerplexityUrl(q)).toBe(`https://www.perplexity.ai/?q=${encodeURIComponent(q)}`);
    expect(buildWebSearchUrl(q, 'ddg')).toBe(`https://duckduckgo.com/?q=${encodeURIComponent(q)}`);
    expect(buildWebSearchUrl(q, 'google')).toContain('google.com/search?q=');
  });

  test('persists the web search engine choice', () => {
    const store = {};
    const storage = {
      getItem: (k) => store[k] ?? null,
      setItem: (k, v) => { store[k] = v; },
    };
    expect(getWebSearchEngine(storage).id).toBe('google');
    setWebSearchEngine('brave', storage);
    expect(getWebSearchEngine(storage).id).toBe('brave');
  });

  test('formats clipboard snippets for chat context', () => {
    expect(formatReferenceSnippet('  NIST CSF 2.0  ')).toBe(
      'Here are references I found:\n\nNIST CSF 2.0'
    );
    expect(wrapReferencesForAdvisorContext('NIST CSF 2.0')).toMatch(/User-provided references/);
  });
});

describe('clipboard reader', () => {
  const original = navigator.clipboard;

  afterEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: original,
    });
  });

  test('returns clipboard text on a user-gesture read', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { readText: jest.fn().mockResolvedValue('copied citation') },
    });
    await expect(readClipboardText()).resolves.toEqual({
      text: 'copied citation',
      via: 'clipboard',
    });
  });

  test('maps permission denial to a denied error code', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { readText: jest.fn().mockRejectedValue(new Error('NotAllowedError')) },
    });
    await expect(readClipboardText()).rejects.toMatchObject({ code: 'denied' });
  });
});
