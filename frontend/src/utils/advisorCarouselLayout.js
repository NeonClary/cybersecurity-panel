/** Layout math for the advisor-answer carousel. Keep in sync with ChatPage.css. */

export const GAP = 16;
/** Arrow column (52px) + stage gap (10px). Overlay/below modes do not reserve this. */
export const CONTROLS_W = 62;
export const PREFERRED_SLIDE = 400;
export const MIN_SLIDE = 280;
export const ABS_MIN_SLIDE = 200;
export const MAX_VISIBLE = 3;

function cardsNeeded(visible, slideW) {
  if (visible < 1) return 0;
  return visible * slideW + GAP * (visible - 1);
}

function pack(width, visible, reserved, minSlide) {
  const usable = width - reserved;
  const gaps = GAP * Math.max(0, visible - 1);
  if (visible < 1 || usable < minSlide) return null;

  let slideW = Math.min(PREFERRED_SLIDE, Math.floor((usable - gaps) / visible));
  slideW = Math.max(minSlide, slideW);

  const cardsWidth = cardsNeeded(visible, slideW);
  if (cardsWidth + reserved > width) return null;

  return { visible, slideW, cardsWidth };
}

/**
 * Fit 1–3 full advisor cards into the chat message pane.
 * Never returns a layout that would clip a partial card.
 *
 * @param {number} availableWidth visible width of the carousel shell (content box)
 * @param {number} messageCount number of advisor answers in the group
 * @returns {{ visible: number, slideW: number, cardsWidth: number, controlsMode: 'none'|'side'|'overlay'|'below' }}
 */
export function computeLayout(availableWidth, messageCount) {
  const width = Math.max(0, Math.floor(Number(availableWidth) || 0));
  const n = Math.max(1, Math.floor(Number(messageCount) || 1));
  const maxCards = Math.min(MAX_VISIBLE, n);

  const needControls = (visible) => n > visible;

  const tryPack = (visible, minSlide) => {
    const need = needControls(visible);
    if (!need) {
      const fit = pack(width, visible, 0, minSlide);
      return fit ? { ...fit, controlsMode: 'none' } : null;
    }
    const side = pack(width, visible, CONTROLS_W, minSlide);
    if (side) return { ...side, controlsMode: 'side' };
    const overlay = pack(width, visible, 0, minSlide);
    if (overlay) return { ...overlay, controlsMode: 'overlay' };
    return null;
  };

  for (let visible = maxCards; visible >= 2; visible--) {
    const fit = tryPack(visible, PREFERRED_SLIDE);
    if (fit) return fit;
  }

  for (let visible = maxCards; visible >= 2; visible--) {
    const fit = tryPack(visible, MIN_SLIDE);
    if (fit) return fit;
  }

  const onePreferred = tryPack(1, PREFERRED_SLIDE);
  if (onePreferred) return onePreferred;

  const oneSide = pack(width, 1, CONTROLS_W, ABS_MIN_SLIDE);
  if (n > 1 && oneSide) return { ...oneSide, controlsMode: 'side' };

  const oneOverlay = pack(width, 1, 0, ABS_MIN_SLIDE);
  if (n > 1 && oneOverlay) return { ...oneOverlay, controlsMode: 'overlay' };

  const slideW = Math.max(ABS_MIN_SLIDE, Math.min(PREFERRED_SLIDE, width || ABS_MIN_SLIDE));
  return {
    visible: 1,
    slideW,
    cardsWidth: slideW,
    controlsMode: n > 1 ? 'below' : 'none',
  };
}
