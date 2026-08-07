// src/components/SuggestionsPanel.js
import React, { useMemo } from 'react';
import { useAppConfig } from '../contexts/AppConfigContext';

const SuggestionsPanel = ({ onSuggestionClick, guestPersona = null }) => {
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

  return (
    <div className="suggestions-panel">
      <div className="suggestions-header">
        <h2 className="suggestions-title">Getting Started</h2>
        <p className="suggestions-subtitle">
          Choose a topic to get advice from your advisors
        </p>
      </div>
      
      <div className="suggestions-grid">
        {examples.map((category, categoryIndex) => {
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
                  <Icon size={20} />
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
                    key={suggestionIndex}
                    onClick={() => onSuggestionClick(suggestion)}
                    className="suggestion-button"
                    style={{
                      borderColor: (category.color || '#6B7280') + '20',
                      '--hover-bg': category.bg_color || '#F3F4F6',
                      '--hover-border': category.color || '#6B7280',
                      '--hover-text': category.color || '#6B7280'
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
