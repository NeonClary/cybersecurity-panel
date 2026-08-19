// src/components/SuggestionsPanel.js
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppConfig } from '../contexts/AppConfigContext';
import { goalCacheKey } from '../utils/statedGoal';
import { loadStarterSuggestions, saveStarterSuggestions } from '../utils/starterCache';
import {
  STARTER_FALLBACK_MS,
  applyFallbackIfTimedOut,
  applySlotDelta,
  applySlotDone,
  buildStarterSlots,
  slotsToCategories,
  visiblePrompts,
} from '../utils/starterSuggestionsUi';

async function fetchStarterSuggestions({
  authToken,
  count,
  exclude,
  categoryTitles,
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
        }),
        signal,
      }
    );
    if (!response.ok) return [];
    const data = await response.json();
    if (!Array.isArray(data.suggestions)) return [];
    return data.suggestions
      .map((item) => (typeof item === 'string' ? item.trim() : ''))
      .filter(Boolean);
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
    if (idx < 0 || idx >= slots.length || !item.text) return;
    slots[idx] = {
      ...slots[idx],
      text: item.text,
      pending: false,
      generated: item.generated !== false,
    };
  });
  if (!slots.some((s) => s.text)) return null;
  return slots;
}

const SuggestionsPanel = ({
  onSuggestionClick,
  guestPersona = null,
  authToken = null,
  user = null,
  statedGoal = '',
  onSuggestionsReady = null,
}) => {
  const { config, resolveIcon } = useAppConfig();

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

  const categories = useMemo(
    () => slotsToCategories(examples, slots),
    [examples, slots],
  );

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
              setSlots((prev) => applySlotDone(prev, payload.slot, payload.text || ''));
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
        generated: s.generated,
      })),
    });
  }, [slots, cacheKey]);

  const handleChipClick = (categoryIndex, suggestionIndex, text) => {
    if (!text) return;
    onSuggestionClick(text);
    usedRef.current.add(text);
    if (!authToken) return;

    const visible = visiblePrompts(slotsRef.current);
    const exclude = [...new Set([...usedRef.current, ...visible])];
    const title = examples[categoryIndex]?.title;
    const slot = slotsRef.current.find(
      (s) => s.categoryIndex === categoryIndex && s.suggestionIndex === suggestionIndex,
    );

    fetchStarterSuggestions({
      authToken,
      count: 1,
      exclude,
      categoryTitles: title ? [title] : [],
    }).then((generated) => {
      const replacement = generated[0];
      if (!replacement || slot == null) return;
      setSlots((prev) => applySlotDone(prev, slot.slot, replacement));
    });
  };

  return (
    <div className="suggestions-panel">
      <div className="suggestions-header">
        <h2 className="suggestions-title">Getting Started</h2>
      </div>
      
      <div className="suggestions-grid">
        {categories.map((category, categoryIndex) => {
          const Icon = resolveIcon(category.icon);
          return (
            <div key={categoryIndex} className="suggestion-category">
              <div className="category-header">
                <div 
                  className="category-icon"
                  style={{ 
                    backgroundColor: category.bg_color || '#F3F4F6',
                    color: category.color || '#6B7280'
                  }}
                >
                  <Icon size={16} />
                </div>
                <h3 
                  className="category-title"
                  style={{ color: category.color || '#6B7280' }}
                >
                  {category.title}
                </h3>
              </div>
              
              <div className="suggestion-buttons">
                {(category.suggestions || []).map((suggestion, suggestionIndex) => {
                  const pending = category.pending?.[suggestionIndex];
                  const label = suggestion || (pending ? 'Writing a question…' : '');
                  return (
                    <button
                      key={`${categoryIndex}-${suggestionIndex}`}
                      type="button"
                      disabled={!suggestion}
                      onClick={() => handleChipClick(categoryIndex, suggestionIndex, suggestion)}
                      className={
                        pending
                          ? 'suggestion-button suggestion-pending'
                          : 'suggestion-button'
                      }
                      style={{
                        borderColor: (category.color || '#6B7280') + '20',
                        '--hover-bg': category.bg_color || '#F3F4F6',
                        '--hover-border': category.color || '#6B7280',
                        '--hover-text': category.color || '#6B7280',
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SuggestionsPanel;
