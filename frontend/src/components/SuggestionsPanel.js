// src/components/SuggestionsPanel.js
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RotateCw } from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';
import { goalCacheKey } from '../utils/statedGoal';
import { loadStarterSuggestions, saveStarterSuggestions } from '../utils/starterCache';
import {
  STARTER_FALLBACK_MS,
  applyFallbackIfTimedOut,
  applySlotDelta,
  applySlotDone,
  applySlotRefreshing,
  buildStarterSlots,
  collectExcludeKeys,
  nextPromptVariation,
  normalizeSuggestion,
  slotsToFlatList,
  suggestionChatPrompt,
  suggestionDisplayText,
  visiblePrompts,
} from '../utils/starterSuggestionsUi';

async function fetchStarterSuggestions({
  authToken,
  count,
  exclude,
  categoryTitles,
  slotIndex,
  promptVariation,
  signal,
}) {
  if (!authToken) return [];
  try {
    const response = await fetch(
      `${process.env.REACT_APP_API_URL}/chat/starter-suggestions`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          count,
          exclude,
          category_titles: categoryTitles,
          slot_index: slotIndex,
          prompt_variation: promptVariation,
        }),
        signal,
      }
    );
    if (!response.ok) return [];
    const data = await response.json();
    if (!Array.isArray(data.suggestions)) return [];
    return data.suggestions
      .map((item) => normalizeSuggestion(item))
      .filter((item) => suggestionChatPrompt(item));
  } catch (err) {
    if (err?.name === 'AbortError') return [];
    return [];
  }
}

function restoreSlotsFromCache(examples, cached) {
  const slots = buildStarterSlots(examples);
  const saved = cached?.slots;
  if (!Array.isArray(saved) || saved.length === 0) return null;
  saved.forEach((item) => {
    const idx = typeof item.slot === 'number' ? item.slot : -1;
    if (idx < 0 || idx >= slots.length) return;
    const suggestion = normalizeSuggestion(item.suggestion || item.text, slots[idx].fallback);
    slots[idx] = {
      ...slots[idx],
      suggestion,
      text: suggestionDisplayText(suggestion),
      pending: false,
      generated: item.generated !== false,
      promptVariation: typeof item.promptVariation === 'number'
        ? item.promptVariation
        : slots[idx].promptVariation,
    };
  });
  if (!slots.some((s) => s.text)) return null;
  return slots;
}

function SuggestionChip({
  slotItem,
  onSelect,
  onRefresh,
}) {
  const {
    slot,
    suggestion,
    displayText,
    isPending,
    refreshing,
  } = slotItem;
  const question = (suggestion?.question || '').trim();
  const disabled = !displayText && !refreshing;
  const label = displayText || (isPending ? 'Writing a question…' : '');

  return (
    <div className="suggestion-chip-wrap">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect(slotItem)}
        className={[
          'suggestion-button',
          isPending ? 'suggestion-pending' : '',
          refreshing ? 'suggestion-refreshing' : '',
        ].filter(Boolean).join(' ')}
        aria-label={displayText || 'Suggested question'}
      >
        <span className="suggestion-chip-text">
          {question && !isPending ? (
            <strong className="suggestion-chip-question">{question}</strong>
          ) : (
            label
          )}
        </span>
      </button>
      <button
        type="button"
        className="suggestion-refresh-btn"
        aria-label="Refresh this suggestion"
        title="Refresh suggestion"
        disabled={refreshing || isPending}
        onClick={(event) => {
          event.stopPropagation();
          onRefresh(slot);
        }}
      >
        <RotateCw size={14} className={refreshing ? 'suggestion-refresh-spin' : ''} />
      </button>
    </div>
  );
}

const SuggestionsPanel = ({
  onSuggestionClick,
  guestPersona = null,
  authToken = null,
  user = null,
  statedGoal = '',
  onSuggestionsReady = null,
}) => {
  const { config } = useAppConfig();

  const examples = useMemo(() => {
    const chatPage = config?.chat_page || {};
    const byPersona = chatPage.examples_by_persona || {};
    const personaKey = (guestPersona || '').toLowerCase();
    const personaExamples = personaKey && Array.isArray(byPersona[personaKey])
      ? byPersona[personaKey]
      : null;
    if (personaExamples && personaExamples.length > 0) return personaExamples;
    return chatPage.examples || [];
  }, [config, guestPersona]);

  const cacheKey = useMemo(
    () => goalCacheKey(statedGoal, user?.id || user?._id || user?.email || (user?.is_guest ? 'guest' : '')),
    [statedGoal, user],
  );

  const [slots, setSlots] = useState(() => buildStarterSlots(examples));
  const slotsRef = useRef(slots);
  const usedRef = useRef(new Set());
  slotsRef.current = slots;
  const readyNotified = useRef('');
  const refreshAbortRef = useRef(null);

  const flatSlots = useMemo(() => slotsToFlatList(slots), [slots]);

  useEffect(() => {
    const current = slotsRef.current || [];
    if (current.length === 0 || current.some((s) => s.pending)) return;
    const prompts = visiblePrompts(current);
    if (!onSuggestionsReady || prompts.length === 0) return;
    const sig = prompts.join('\n');
    if (readyNotified.current === sig) return;
    readyNotified.current = sig;
    onSuggestionsReady(prompts);
  }, [slots, onSuggestionsReady]);

  useEffect(() => {
    const cached = loadStarterSuggestions(cacheKey);
    const restored = restoreSlotsFromCache(examples, cached);
    if (restored) {
      setSlots(restored);
      slotsRef.current = restored;
      return undefined;
    }

    const initial = buildStarterSlots(examples);
    setSlots(initial);
    slotsRef.current = initial;
    usedRef.current = new Set();

    if (!authToken || initial.length === 0) {
      setSlots(applyFallbackIfTimedOut(initial, 0, STARTER_FALLBACK_MS));
      return undefined;
    }

    const controller = new AbortController();
    const startedAt = Date.now();
    const fallbackTimer = setTimeout(() => {
      setSlots((prev) => applyFallbackIfTimedOut(prev, startedAt, Date.now()));
    }, STARTER_FALLBACK_MS);

    const titles = initial.map((slot) => slot.categoryTitle);
    const exclude = initial.map((slot) => slot.fallback).filter(Boolean);

    (async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_API_URL}/chat/starter-suggestions-stream`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify({
              count: titles.length,
              exclude,
              category_titles: titles,
            }),
            signal: controller.signal,
          },
        );
        if (!response.ok || !response.body) return;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.trim()) continue;
            let payload;
            try {
              payload = JSON.parse(line);
            } catch {
              continue;
            }
            if (payload.type === 'delta') {
              setSlots((prev) => applySlotDelta(prev, payload.slot, payload.text || ''));
            } else if (payload.type === 'done') {
              setSlots((prev) => applySlotDone(prev, payload.slot, payload));
            }
          }
        }
      } catch (err) {
        if (err?.name !== 'AbortError') {
          setSlots((prev) => applyFallbackIfTimedOut(prev, 0, STARTER_FALLBACK_MS));
        }
      }
    })();

    return () => {
      clearTimeout(fallbackTimer);
      controller.abort();
    };
  }, [authToken, cacheKey, examples]);

  useEffect(() => {
    const filled = (slots || []).filter((s) => (s.text || '').trim());
    if (filled.length === 0 || filled.length < slots.length) return;
    saveStarterSuggestions(cacheKey, {
      slots: slots.map((s) => ({
        slot: s.slot,
        text: s.text,
        suggestion: s.suggestion,
        generated: s.generated,
        promptVariation: s.promptVariation,
      })),
    });
  }, [slots, cacheKey]);

  const regenerateSlot = useCallback(async (slotIndex, { markUsed = null } = {}) => {
    if (!authToken) return;
    const slot = slotsRef.current.find((s) => s.slot === slotIndex);
    if (!slot) return;

    refreshAbortRef.current?.abort();
    const controller = new AbortController();
    refreshAbortRef.current = controller;

    const variation = nextPromptVariation(slot.promptVariation);
    setSlots((prev) => applySlotRefreshing(prev, slotIndex, true));

    const exclude = collectExcludeKeys(
      slotsRef.current.filter((s) => s.slot !== slotIndex),
      markUsed ? [markUsed] : [...usedRef.current],
    );

    const generated = await fetchStarterSuggestions({
      authToken,
      count: 1,
      exclude,
      categoryTitles: slot.categoryTitle ? [slot.categoryTitle] : [],
      slotIndex,
      promptVariation: variation,
      signal: controller.signal,
    });

    const replacement = generated[0];
    if (!replacement) {
      setSlots((prev) => applySlotRefreshing(prev, slotIndex, false));
      return;
    }

    setSlots((prev) => {
      const next = applySlotDone(prev, slotIndex, { suggestion: replacement });
      const updated = next[slotIndex];
      if (updated) {
        next[slotIndex] = {
          ...updated,
          promptVariation: variation,
        };
      }
      return next;
    });
  }, [authToken]);

  const handleChipClick = (slotItem) => {
    const chatPrompt = suggestionChatPrompt(slotItem.suggestion);
    if (!chatPrompt) return;
    onSuggestionClick(chatPrompt);
    usedRef.current.add(chatPrompt);
    regenerateSlot(slotItem.slot, { markUsed: chatPrompt });
  };

  const handleRefreshClick = (slotIndex) => {
    regenerateSlot(slotIndex);
  };

  useEffect(() => () => refreshAbortRef.current?.abort(), []);

  return (
    <div className="suggestions-panel">
      <div className="suggestions-header">
        <h2 className="suggestions-title">Practical Next Steps</h2>
      </div>

      <div className="suggestions-flat-list">
        {flatSlots.map((slotItem) => (
          <SuggestionChip
            key={slotItem.slot}
            slotItem={slotItem}
            onSelect={handleChipClick}
            onRefresh={handleRefreshClick}
          />
        ))}
      </div>
    </div>
  );
};

export default SuggestionsPanel;
