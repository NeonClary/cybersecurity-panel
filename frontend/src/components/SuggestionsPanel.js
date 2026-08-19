// src/components/SuggestionsPanel.js
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppConfig } from '../contexts/AppConfigContext';

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

const SuggestionsPanel = ({
  onSuggestionClick,
  guestPersona = null,
  authToken = null,
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

  const cloneExamples = useCallback(
    () => examples.map((category) => ({
      ...category,
      suggestions: [...(category.suggestions || [])],
      generated: (category.suggestions || []).map(() => false),
    })),
    [examples]
  );

  const [categories, setCategories] = useState(cloneExamples);
  const categoriesRef = useRef(categories);
  const usedRef = useRef(new Set());
  categoriesRef.current = categories;

  useEffect(() => {
    const next = cloneExamples();
    setCategories(next);
    usedRef.current = new Set();
    categoriesRef.current = next;

    if (!authToken || examples.length === 0) return undefined;

    const controller = new AbortController();
    const titles = examples.map((category) => category.title).filter(Boolean);
    const exclude = examples.flatMap((category) => category.suggestions || []);

    (async () => {
      const generated = await fetchStarterSuggestions({
        authToken,
        count: titles.length || examples.length,
        exclude,
        categoryTitles: titles,
        signal: controller.signal,
      });
      if (controller.signal.aborted || generated.length === 0) return;
      setCategories((prev) => prev.map((category, index) => {
        const text = generated[index];
        if (!text) return category;
        const suggestions = [...category.suggestions];
        if (suggestions.length === 0) {
          return { ...category, suggestions: [text], generated: [true] };
        }
        const slot = suggestions.length - 1;
        suggestions[slot] = text;
        const flags = [...(category.generated || suggestions.map(() => false))];
        flags[slot] = true;
        return { ...category, suggestions, generated: flags };
      }));
    })();

    return () => controller.abort();
  }, [authToken, cloneExamples, examples]);

  const handleChipClick = (categoryIndex, suggestionIndex, text) => {
    onSuggestionClick(text);
    usedRef.current.add(text);
    if (!authToken) return;

    const visible = (categoriesRef.current || []).flatMap(
      (category) => category.suggestions || []
    );
    const exclude = [...new Set([...usedRef.current, ...visible])];
    const title = categoriesRef.current?.[categoryIndex]?.title;

    fetchStarterSuggestions({
      authToken,
      count: 1,
      exclude,
      categoryTitles: title ? [title] : [],
    }).then((generated) => {
      const replacement = generated[0];
      if (!replacement) return;
      setCategories((prev) => prev.map((category, index) => {
        if (index !== categoryIndex) return category;
        return {
          ...category,
          suggestions: category.suggestions.map((item, itemIndex) => (
            itemIndex === suggestionIndex ? replacement : item
          )),
          generated: (category.generated || []).map((flag, itemIndex) => (
            itemIndex === suggestionIndex ? true : flag
          )),
        };
      }));
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
                {(category.suggestions || []).map((suggestion, suggestionIndex) => (
                  <button
                    key={`${categoryIndex}-${suggestionIndex}`}
                    type="button"
                    onClick={() => handleChipClick(categoryIndex, suggestionIndex, suggestion)}
                    className={
                      category.generated?.[suggestionIndex]
                        ? 'suggestion-button suggestion-generated'
                        : 'suggestion-button'
                    }
                    style={{
                      borderColor: (category.color || '#6B7280') + '20',
                      '--hover-bg': category.bg_color || '#F3F4F6',
                      '--hover-border': category.color || '#6B7280',
                      '--hover-text': category.color || '#6B7280',
                      '--generated-accent': category.color || '#6B7280'
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SuggestionsPanel;
