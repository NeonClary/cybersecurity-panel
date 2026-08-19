/** Pure helpers for Getting Started chip slots, 5s fallback, and stable order. */

export const STARTER_FALLBACK_MS = 5000;
export const MAX_STARTER_SLOTS = 12;

/**
 * Flatten example categories into stable slots 0..n (category-major order).
 * Caps at MAX_STARTER_SLOTS without reordering remaining items.
 */
export function buildStarterSlots(examples, maxSlots = MAX_STARTER_SLOTS) {
  const slots = [];
  (examples || []).forEach((category, categoryIndex) => {
    (category.suggestions || []).forEach((text, suggestionIndex) => {
      if (slots.length >= maxSlots) return;
      slots.push({
        slot: slots.length,
        categoryIndex,
        suggestionIndex,
        categoryTitle: category.title || `Starter ${slots.length + 1}`,
        fallback: typeof text === 'string' ? text : '',
        text: '',
        generated: false,
        pending: true,
      });
    });
  });
  return slots;
}

export function applySlotDelta(slots, slotIndex, chunk) {
  if (!Array.isArray(slots) || slotIndex < 0 || slotIndex >= slots.length) return slots;
  const next = slots.slice();
  const current = next[slotIndex];
  next[slotIndex] = {
    ...current,
    text: `${current.text || ''}${chunk || ''}`,
    pending: false,
    generated: true,
  };
  return next;
}

export function applySlotDone(slots, slotIndex, text) {
  if (!Array.isArray(slots) || slotIndex < 0 || slotIndex >= slots.length) return slots;
  const next = slots.slice();
  const current = next[slotIndex];
  const finalText = (text || current.text || '').trim();
  next[slotIndex] = {
    ...current,
    text: finalText,
    pending: false,
    generated: Boolean(finalText) && finalText !== current.fallback,
  };
  if (finalText && finalText === current.fallback) {
    next[slotIndex].generated = true;
  }
  if (finalText) next[slotIndex].generated = true;
  return next;
}

/** If a slot has no tokens after timeout, fill with YAML fallback. Later LLM text may replace it. */
export function applyFallbackIfTimedOut(slots, startedAt, now, timeoutMs = STARTER_FALLBACK_MS) {
  if (!Array.isArray(slots) || now - startedAt < timeoutMs) return slots;
  let changed = false;
  const next = slots.map((slot) => {
    if (!slot.pending) return slot;
    if (slot.text) return { ...slot, pending: false, generated: true };
    if (!slot.fallback) return { ...slot, pending: false };
    changed = true;
    return {
      ...slot,
      text: slot.fallback,
      pending: false,
      generated: false,
    };
  });
  return changed ? next : slots;
}

export function slotsToCategories(examples, slots) {
  return (examples || []).map((category, categoryIndex) => {
    const owned = (slots || []).filter((s) => s.categoryIndex === categoryIndex);
    return {
      ...category,
      suggestions: owned.map((s) => s.text || (s.pending ? '' : s.fallback) || ''),
      generated: owned.map((s) => Boolean(s.generated)),
      pending: owned.map((s) => Boolean(s.pending && !s.text)),
    };
  }).filter((category, categoryIndex) => (
    (slots || []).some((s) => s.categoryIndex === categoryIndex)
  ));
}

export function visiblePrompts(slots) {
  return (slots || [])
    .map((s) => (s.text || '').trim())
    .filter(Boolean);
}
