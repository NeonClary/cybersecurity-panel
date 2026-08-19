import { pinElementToScrollerTop, findLatestUserMessage } from './pinLatestQuestion';

describe('pin latest question', () => {
  test('scrolls so the question sits at the top of the scroller', () => {
    const scrollTo = jest.fn();
    const scroller = {
      scrollTop: 40,
      scrollTo,
      getBoundingClientRect: () => ({ top: 100, bottom: 700 }),
    };
    const element = {
      getBoundingClientRect: () => ({ top: 220, bottom: 280 }),
    };
    expect(pinElementToScrollerTop(scroller, element, { behavior: 'auto' })).toBe(true);
    expect(scrollTo).toHaveBeenCalledWith({ top: 160, behavior: 'auto' });
  });

  test('finds the newest real user question, skipping reference snippets', () => {
    const latest = findLatestUserMessage([
      { id: '1', type: 'user', content: 'old' },
      { id: '2', type: 'advisor', content: 'ans' },
      { id: '3', type: 'user', content: 'new question' },
      { id: '4', type: 'user', content: 'Here are references', isReferenceSnippet: true },
    ]);
    expect(latest).toMatchObject({ id: '3', content: 'new question' });
  });
});
