import React, { useEffect, useMemo, useState } from 'react';
import { useAppConfig } from '../contexts/AppConfigContext';
import SecurityChatBotIcon from './icons/SecurityChatBotIcon';
import { goalCacheKey } from '../utils/statedGoal';
import { loadStarterGreeting, saveStarterGreeting } from '../utils/starterCache';
import '../styles/IntakePanel.css';

const STATIC_GREETING = 'What cybersecurity problem should we work on first?';
const STATIC_SUBHEADER =
  'I can help with threats, controls, incidents, compliance, or your security career.';

/**
 * First-session intake: goal-specific greeting + chips + optional free-text.
 * Chips come from /api/config → chat_page.intake, filtered by guest persona when set.
 */
const IntakePanel = ({
  onSubmit,
  guestPersona = null,
  authToken = null,
  user = null,
  statedGoal = '',
}) => {
  const { config } = useAppConfig();
  const intake = config?.chat_page?.intake || {};
  const yamlGreeting = intake.greeting || STATIC_GREETING;
  const yamlSubheader = intake.greeting_subheader || STATIC_SUBHEADER;

  const cacheKey = useMemo(
    () => goalCacheKey(statedGoal, user?.id || user?._id || user?.email || (user?.is_guest ? 'guest' : '')),
    [statedGoal, user],
  );

  const cached = useMemo(() => loadStarterGreeting(cacheKey), [cacheKey]);

  const [greeting, setGreeting] = useState(cached?.greeting || yamlGreeting);
  const [subheader, setSubheader] = useState(cached?.subheader || yamlSubheader);

  useEffect(() => {
    const stored = loadStarterGreeting(cacheKey);
    if (stored?.greeting) {
      setGreeting(stored.greeting);
      setSubheader(stored.subheader || yamlSubheader);
      return undefined;
    }
    if (!authToken) {
      setGreeting(yamlGreeting);
      setSubheader(yamlSubheader);
      return undefined;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    (async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_API_URL}/chat/starter-greeting`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${authToken}`,
            },
            signal: controller.signal,
          },
        );
        if (!response.ok) return;
        const data = await response.json();
        if (!data?.greeting) return;
        setGreeting(data.greeting);
        if (data.subheader) setSubheader(data.subheader);
        saveStarterGreeting(cacheKey, {
          greeting: data.greeting,
          subheader: data.subheader || yamlSubheader,
        });
      } catch {
        /* keep static fallback */
      }
    })();
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [authToken, cacheKey, yamlGreeting, yamlSubheader]);

  const chips = useMemo(() => {
    const byPersona = intake.by_persona || {};
    const personaKey = (guestPersona || '').toLowerCase();
    const personaChips = personaKey && Array.isArray(byPersona[personaKey])
      ? byPersona[personaKey]
      : null;
    if (personaChips && personaChips.length > 0) return personaChips;
    return Array.isArray(intake.chips) ? intake.chips : [];
  }, [intake, guestPersona]);

  const [freeText, setFreeText] = useState('');
  const [showFreeText, setShowFreeText] = useState(false);

  const handleChip = (chip) => {
    if (chip.free_text) {
      setShowFreeText(true);
      return;
    }
    if (chip.prompt) onSubmit(chip.prompt);
  };

  const handleFreeSubmit = (e) => {
    e.preventDefault();
    const text = freeText.trim();
    if (!text) return;
    onSubmit(text);
    setFreeText('');
  };

  return (
    <div className="intake-panel" role="region" aria-label="Getting started">
      <div className="intake-avatar" aria-hidden="true">
        <SecurityChatBotIcon size={22} />
      </div>
      <h2 className="intake-greeting">{greeting}</h2>
      {subheader ? <p className="intake-sub">{subheader}</p> : null}
      <div className="intake-chips">
        {chips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`intake-chip${chip.free_text ? ' intake-chip--other' : ''}`}
            onClick={() => handleChip(chip)}
          >
            {chip.label}
          </button>
        ))}
      </div>
      {(showFreeText || chips.length === 0) && (
        <form className="intake-freetext" onSubmit={handleFreeSubmit}>
          <label htmlFor="intake-free" className="sr-only">
            Describe your cybersecurity need
          </label>
          <textarea
            id="intake-free"
            rows={3}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="Tell me about the cybersecurity problem or goal you have today…"
          />
          <button type="submit" className="intake-submit" disabled={!freeText.trim()}>
            Start
          </button>
        </form>
      )}
    </div>
  );
};

export default IntakePanel;
