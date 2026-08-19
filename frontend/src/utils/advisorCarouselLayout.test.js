import {
  computeLayout,
  PREFERRED_SLIDE,
  MIN_SLIDE,
  CONTROLS_W,
  GAP,
  MAX_VISIBLE,
} from './advisorCarouselLayout';

function totalWidth(layout) {
  const reserved = layout.controlsMode === 'side' ? CONTROLS_W : 0;
  return layout.cardsWidth + reserved;
}

describe('computeLayout', () => {
  test('shows three preferred cards when the shell is wide enough', () => {
    const L = computeLayout(1600, 3);
    expect(L.visible).toBe(3);
    expect(L.controlsMode).toBe('none');
    expect(L.slideW).toBe(PREFERRED_SLIDE);
    expect(totalWidth(L)).toBeLessThanOrEqual(1600);
  });

  test('shows two preferred cards with side arrows in a typical 1280 chat pane', () => {
    // ~1280 viewport minus ~300 sidebar minus ~40 messages-scroll padding
    const L = computeLayout(940, 3);
    expect(L.visible).toBe(2);
    expect(L.controlsMode).toBe('side');
    expect(L.slideW).toBe(PREFERRED_SLIDE);
    expect(totalWidth(L)).toBeLessThanOrEqual(940);
  });

  test('does not claim three 400px cards when they cannot fit', () => {
    const width = 3 * PREFERRED_SLIDE + 2 * GAP - 1; // 1231
    const L = computeLayout(width, 3);
    expect(L.visible).toBeLessThan(3);
    expect(L.controlsMode).not.toBe('none');
    expect(totalWidth(L)).toBeLessThanOrEqual(width);
  });

  test('overlays arrows to keep three preferred cards when side controls do not fit', () => {
    const width = 3 * PREFERRED_SLIDE + 2 * GAP + 10; // 1242: 3 cards fit, 3+side do not
    const L = computeLayout(width, 4);
    expect(L.visible).toBe(3);
    expect(L.controlsMode).toBe('overlay');
    expect(L.slideW).toBe(PREFERRED_SLIDE);
    expect(totalWidth(L)).toBeLessThanOrEqual(width);
  });

  test('falls back to min-size cards rather than clipping', () => {
    const L = computeLayout(700, 3);
    expect(L.visible).toBe(2);
    expect(L.slideW).toBeGreaterThanOrEqual(MIN_SLIDE);
    expect(L.slideW).toBeLessThan(PREFERRED_SLIDE);
    expect(totalWidth(L)).toBeLessThanOrEqual(700);
  });

  test('never shows more than three cards', () => {
    const L = computeLayout(2400, 6);
    expect(L.visible).toBe(MAX_VISIBLE);
    expect(L.controlsMode).toBe('side');
  });

  test('keeps arrows when more cards exist than are visible', () => {
    const L = computeLayout(500, 3);
    expect(L.visible).toBe(1);
    expect(L.controlsMode).toMatch(/side|overlay|below/);
    expect(totalWidth(L)).toBeLessThanOrEqual(500);
  });

  test('narrow pane overlays or stacks controls instead of overflowing', () => {
    const L = computeLayout(320, 3);
    expect(L.visible).toBe(1);
    expect(L.controlsMode).toMatch(/overlay|below|side/);
    expect(totalWidth(L)).toBeLessThanOrEqual(320);
  });
});
