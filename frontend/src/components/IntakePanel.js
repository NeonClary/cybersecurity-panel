import React, { useState, useMemo } from 'react';
import { MessageCircle } from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';
import '../styles/IntakePanel.css';

/**
 * First-session intake: Jerry's greeting + chips + optional free-text.
 * Chips come from /api/config → chat_page.intake, filtered by guest persona when set.
 */
const IntakePanel = ({ onSubmit, guestPersona = null }) => {
  const { config } = useAppConfig();
  const intake = config?.chat_page?.intake || {};
  const greeting =
    intake.greeting ||
    "You've contacted me today — what is it that I can help you with in cybersecurity?";

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
        <MessageCircle size={28} />
      </div>
      <h2 className="intake-greeting">{greeting}</h2>
      <p className="intake-sub">
        Pick a starting point, or tell me in your own words.
      </p>
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
