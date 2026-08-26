/** Pure helpers for Practical Next Steps chip slots, fallback, and stable order. */

export const STARTER_FALLBACK_MS = 5000;
export const MAX_STARTER_SLOTS = 12;
export const PROMPT_VARIATION_COUNT = 6;

const FILLER_OPENER_RE = /^(?:to begin(?:\s+with)?|to shape(?:\s+your\s+path)?|to start(?:\s+with)?|to identify|to dissect|to analyze|to explore|to consider|to examine|to discuss|let'?s|first off|as a first step|i'?d like|i would like|so,?|now,?|here,?|for(?:\s+a)?\s+start|getting started|to get started|to understand|in order to|when it comes to)\b[\s,:-]*/i;
const TOPIC_COMMA_LEAD_RE = /^for\s+[^?]{1,48}?,[\s]*/i;
const ADVISOR_TO_USER_RE = /\b(?:let'?s|let us|have you considered|have you thought|have you looked|you should|you might|you need to|you can start|for instance|this idea blends|the core concept|to identify the|which creates a unique)\b/i;
const FIRST_PERSON_RE = /\b(?:i|i'm|i'd|i've|i'll|my|mine)\b/i;
const SECOND_PERSON_YOUR_RE = /\byour\b/i;

function looksLikeJsonPayload(text) {
  const trimmed = String(text || '').trim();
  return trimmed.startsWith('{') || trimmed.startsWith('[');
}

function extractQuestionFromPayload(raw) {
  const text = String(raw || '').trim();
  if (!looksLikeJsonPayload(text)) return text;
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return String(parsed.question || parsed.text || '').trim();
    }
    if (Array.isArray(parsed) && parsed[0]) {
      return extractQuestionFromPayload(parsed[0]);
    }
  } catch {
    const match = text.match(/"question"\s*:\s*"((?:\\.|[^"\\])*)/);
    if (match) {
      try {
        return JSON.parse(`"${match[1]}"`);
      } catch {
        return match[1].replace(/\\"/g, '"');
      }
    }
  }
  return '';
}

function isMultiSentence(text) {
  let body = String(text || '').trim();
  if (body.endsWith('?')) body = body.slice(0, -1);
  body = body.replace(/\b(?:e\.g|i\.e|etc)\./gi, ' ').replace(/\.{2,}/g, ' ');
  return /[.!?]/.test(body);
}

export function looksLikeAdvisorToUser(text) {
  const cleaned = String(text || '').replace(/\s+/g, ' ').trim();
  if (!cleaned) return false;
  if (ADVISOR_TO_USER_RE.test(cleaned)) return true;
  if (isMultiSentence(cleaned)) return true;
  if (SECOND_PERSON_YOUR_RE.test(cleaned) && !FIRST_PERSON_RE.test(cleaned)) return true;
  return false;
}

function userFacingChatPrompt(chatPrompt, question) {
  const chat = String(chatPrompt || '').trim();
  const q = String(question || '').trim();
  if (chat && !looksLikeAdvisorToUser(chat)) return chat;
  if (q && !looksLikeAdvisorToUser(q)) return q;
  return q || chat;
}

export function stripForbiddenOpeners(text) {
  let cleaned = extractQuestionFromPayload(text);
  cleaned = String(cleaned || '').trim().replace(/^["']+|["']+$/g, '');
  cleaned = cleaned.replace(/\s+/g, ' ').trim();
  if (looksLikeJsonPayload(cleaned)) return '';
  let prev = null;
  while (cleaned && cleaned !== prev) {
    prev = cleaned;
    cleaned = cleaned.replace(FILLER_OPENER_RE, '').replace(TOPIC_COMMA_LEAD_RE, '').trim();
  }
  if (!cleaned) return '';
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export function fallbackToSuggestion(text) {
  const question = stripForbiddenOpeners(text) || String(text || '').trim();
  return {
    lead: '',
    question,
    chat_prompt: question,
  };
}

export function normalizeSuggestion(raw, fallbackText = '') {
  if (raw && typeof raw === 'object') {
    const question = stripForbiddenOpeners(raw.question || raw.text || '');
    const chatPrompt = String(raw.chat_prompt || raw.chatPrompt || '').trim();
    if (question || chatPrompt) {
      const display = question || stripForbiddenOpeners(chatPrompt);
      return {
        lead: '',
        question: display,
        chat_prompt: userFacingChatPrompt(chatPrompt, display),
      };
    }
  }
  const text = String(raw || fallbackText || '').trim();
  return fallbackToSuggestion(text);
}

export function suggestionDisplayText(suggestion) {
  return (suggestion?.question || '').trim();
}

export function suggestionChatPrompt(suggestion) {
  const question = (suggestion?.question || suggestionDisplayText(suggestion) || '').trim();
  return userFacingChatPrompt(suggestion?.chat_prompt, question);
}

export function suggestionExcludeKeys(suggestion) {
  const keys = [
    suggestionChatPrompt(suggestion),
    suggestionDisplayText(suggestion),
    suggestion?.question,
  ];
  return [...new Set(keys.map((k) => String(k || '').trim()).filter(Boolean))];
}

/**
 * Flatten example categories into stable slots 0..n (category-major order).
 * Caps at MAX_STARTER_SLOTS without reordering remaining items.
 */
export function buildStarterSlots(examples, maxSlots = MAX_STARTER_SLOTS) {
  const slots = [];
  (examples || []).forEach((category, categoryIndex) => {
    (category.suggestions || []).forEach((text, suggestionIndex) => {
      if (slots.length >= maxSlots) return;
      const fallback = typeof text === 'string' ? text : '';
      slots.push({
        slot: slots.length,
        categoryIndex,
        suggestionIndex,
        categoryTitle: category.title || `Starter ${slots.length + 1}`,
        fallback,
        suggestion: fallbackToSuggestion(fallback),
        text: '',
        generated: false,
        pending: true,
        promptVariation: slots.length % PROMPT_VARIATION_COUNT,
        refreshing: false,
      });
    });
  });
  return slots;
}

export function applySlotDelta(slots, slotIndex, chunk) {
  if (!Array.isArray(slots) || slotIndex < 0 || slotIndex >= slots.length) return slots;
  const question = stripForbiddenOpeners(String(chunk || ''));
  if (!question) return slots;
  const next = slots.slice();
  const current = next[slotIndex];
  next[slotIndex] = {
    ...current,
    text: question,
    suggestion: {
      lead: '',
      question,
      chat_prompt: current.suggestion?.chat_prompt || question,
    },
    pending: false,
    generated: true,
  };
  return next;
}

export function applySlotDone(slots, slotIndex, payload) {
  if (!Array.isArray(slots) || slotIndex < 0 || slotIndex >= slots.length) return slots;
  const next = slots.slice();
  const current = next[slotIndex];
  const suggestion = normalizeSuggestion(
    payload?.suggestion ?? payload,
    typeof payload === 'string' ? payload : current.text || current.fallback,
  );
  const finalText = suggestionDisplayText(suggestion) || (current.text || '').trim();
  next[slotIndex] = {
    ...current,
    suggestion,
    text: finalText,
    pending: false,
    refreshing: false,
    generated: Boolean(finalText) && finalText !== current.fallback,
  };
  if (finalText) next[slotIndex].generated = true;
  return next;
}

export function applySlotRefreshing(slots, slotIndex, refreshing = true) {
  if (!Array.isArray(slots) || slotIndex < 0 || slotIndex >= slots.length) return slots;
  const next = slots.slice();
  next[slotIndex] = {
    ...next[slotIndex],
    refreshing,
    pending: refreshing,
  };
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
    const suggestion = fallbackToSuggestion(slot.fallback);
    return {
      ...slot,
      suggestion,
      text: suggestionDisplayText(suggestion),
      pending: false,
      generated: false,
    };
  });
  return changed ? next : slots;
}

export function slotsToFlatList(slots) {
  return (slots || [])
    .slice()
    .sort((a, b) => a.slot - b.slot)
    .map((slot) => ({
      ...slot,
      suggestion: slot.suggestion || fallbackToSuggestion(slot.fallback),
      displayText: slot.text || suggestionDisplayText(slot.suggestion) || slot.fallback || '',
      isPending: Boolean(slot.pending && !slot.text && !slot.refreshing),
    }));
}

/** @deprecated Use slotsToFlatList — kept for tests migrating off category grid. */
export function slotsToCategories(examples, slots) {
  return (examples || []).map((category, categoryIndex) => {
    const owned = (slots || []).filter((s) => s.categoryIndex === categoryIndex);
    return {
      ...category,
      suggestions: owned.map((s) => s.text || (s.pending ? '' : s.fallback) || ''),
      generated: owned.map((s) => Boolean(s.generated)),
      pending: owned.map((s) => Boolean(s.pending && !s.text)),
    };
  }).filter((_category, categoryIndex) => (
    (slots || []).some((s) => s.categoryIndex === categoryIndex)
  ));
}

export function visiblePrompts(slots) {
  return (slots || [])
    .map((s) => suggestionChatPrompt(s.suggestion || fallbackToSuggestion(s.text || s.fallback)))
    .filter(Boolean);
}

export function collectExcludeKeys(slots, extra = []) {
  const normalize = (value) => String(value || '').trim().replace(/[.?!]+$/g, '').toLowerCase();
  const fromSlots = (slots || []).flatMap((slot) => suggestionExcludeKeys(
    slot.suggestion || fallbackToSuggestion(slot.text || slot.fallback),
  ));
  const merged = [...(extra || []), ...fromSlots]
    .map((s) => String(s || '').trim())
    .filter(Boolean);
  const seen = new Set();
  return merged.filter((item) => {
    const key = normalize(item);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function nextPromptVariation(current = 0) {
  return (Number(current) + 1) % PROMPT_VARIATION_COUNT;
}
