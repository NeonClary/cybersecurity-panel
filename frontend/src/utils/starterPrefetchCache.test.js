import {
  PREFETCH_TTL_MS,
  getPrefetchedStream,
  isFailedStream,
  putPrefetchedStream,
} from './starterPrefetchCache';

const ok = ['{"type": "advisor", "data": {"persona_id": "threat_modeler", "content": "### Thought\\nFine."}}'];
const failed = ['{"type": "advisor", "data": {"content": "I apologize, but I\'m having technical difficulties."}}'];

beforeEach(() => sessionStorage.clear());

test('caches healthy streams per user key', () => {
  putPrefetchedStream('u1@v1', 'Help me', ok);
  expect(getPrefetchedStream('u1@v1', 'Help me').lines).toEqual(ok);
  expect(getPrefetchedStream('u1@v2', 'Help me')).toBeNull();
});

test('never caches failed or fallback streams', () => {
  expect(isFailedStream(failed)).toBe(true);
  expect(isFailedStream(['{"type": "error", "data": {"detail": "x"}}'])).toBe(true);
  expect(isFailedStream(ok)).toBe(false);
  putPrefetchedStream('u2@v1', 'Was I hacked?', failed);
  expect(getPrefetchedStream('u2@v1', 'Was I hacked?')).toBeNull();
});

test('expires entries older than the TTL', () => {
  const realNow = Date.now;
  try {
    Date.now = () => 1_000_000;
    putPrefetchedStream('u3@v1', 'Old prompt', ok);
    Date.now = () => 1_000_000 + PREFETCH_TTL_MS + 1;
    expect(getPrefetchedStream('u3@v1', 'Old prompt')).toBeNull();
  } finally {
    Date.now = realNow;
  }
});
