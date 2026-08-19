import {
  STARTER_FALLBACK_MS,
  applyFallbackIfTimedOut,
  applySlotDelta,
  applySlotDone,
  buildStarterSlots,
  slotsToCategories,
  visiblePrompts,
} from './starterSuggestionsUi';

const examples = [
  { title: 'A', suggestions: ['A1', 'A2', 'A3'] },
  { title: 'B', suggestions: ['B1', 'B2', 'B3'] },
  { title: 'C', suggestions: ['C1', 'C2'] },
];

describe('starter suggestion slots', () => {
  test('builds stable category-major slots and does not reorder on populate', () => {
    const slots = buildStarterSlots(examples);
    expect(slots.map((s) => s.fallback)).toEqual([
      'A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2',
    ]);
    let next = applySlotDelta(slots, 2, 'How');
    next = applySlotDelta(next, 0, 'What');
    next = applySlotDone(next, 2, 'How should I start?');
    expect(next[0].text).toBe('What');
    expect(next[2].text).toBe('How should I start?');
    expect(next[1].fallback).toBe('A2');
    expect(next.map((s) => s.slot)).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });

  test('uses YAML fallback only after 5s without tokens', () => {
    const slots = buildStarterSlots([{ title: 'A', suggestions: ['Static A'] }]);
    const t0 = 1000;
    expect(applyFallbackIfTimedOut(slots, t0, t0 + 4999)[0].text).toBe('');
    const timed = applyFallbackIfTimedOut(slots, t0, t0 + STARTER_FALLBACK_MS);
    expect(timed[0].text).toBe('Static A');
    expect(timed[0].generated).toBe(false);
    const afterStream = applySlotDone(timed, 0, 'Generated for this user?');
    expect(afterStream[0].text).toBe('Generated for this user?');
    expect(afterStream[0].generated).toBe(true);
  });

  test('persisted slot payload round-trips into categories without shuffle', () => {
    let slots = buildStarterSlots(examples.slice(0, 2));
    slots = applySlotDone(slots, 0, 'Gen A1');
    slots = applySlotDone(slots, 1, 'Gen A2');
    const cats = slotsToCategories(examples.slice(0, 2), slots);
    expect(cats[0].suggestions[0]).toBe('Gen A1');
    expect(cats[0].suggestions[1]).toBe('Gen A2');
    expect(visiblePrompts(slots).slice(0, 2)).toEqual(['Gen A1', 'Gen A2']);
  });
});
