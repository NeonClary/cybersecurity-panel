import React, { useCallback, useEffect, useMemo, useState } from 'react';
import * as LucideIcons from 'lucide-react';
import { ChevronRight } from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';
import SecurityChatBotIcon from './icons/SecurityChatBotIcon';
import { goalCacheKey } from '../utils/statedGoal';
import { loadStarterGreeting, saveStarterGreeting } from '../utils/starterCache';
import { PATH_SECTION_TITLE } from '../data/advisorPaths';
import {
  getAvailableSteps,
  loadPathProgress,
  markStepComplete,
  mergeAutoCompletions,
  savePathProgress,
} from '../utils/advisorPathProgress';
import '../styles/IntakePanel.css';

const STATIC_GREETING = 'What cybersecurity problem should we work on first?';
const STATIC_SUBHEADER =
  'Explore the panel step by step — or jump straight to a suggested question below.';

const IntakePanel = ({
  guestPersona = null,
  authToken = null,
  user = null,
  statedGoal = '',
  pathSignals = {},
  onOpenProfile,
  onNavigateToJourney,
  onNavigateToCanvas,
  onOpenUserGuide,
  onOpenModelStatus,
  onNavigateToSignup,
  onPathStepComplete,
}) => {
  const { config } = useAppConfig();
  const intake = config?.chat_page?.intake || {};
  const yamlGreeting = intake.greeting || STATIC_GREETING;
  const yamlSubheader = intake.greeting_subheader || STATIC_SUBHEADER;
  const isGuest = Boolean(user?.is_guest);

  const userKey = user?.id || user?._id || user?.email || (isGuest ? 'guest' : '');
  const cacheKey = useMemo(
    () => goalCacheKey(statedGoal, userKey),
    [statedGoal, userKey],
  );

  const cached = useMemo(() => loadStarterGreeting(cacheKey), [cacheKey]);

  const [greeting, setGreeting] = useState(cached?.greeting || yamlGreeting);
  const [subheader, setSubheader] = useState(cached?.subheader || yamlSubheader);
  const [expandedId, setExpandedId] = useState(null);
  const [progress, setProgress] = useState(() => loadPathProgress(userKey));

  useEffect(() => {
    setProgress(loadPathProgress(userKey));
  }, [userKey]);

  useEffect(() => {
    setProgress((prev) => {
      const merged = mergeAutoCompletions(prev.completed, pathSignals);
      if (
        merged.length === prev.completed.length
        && merged.every((id, i) => id === prev.completed[i])
      ) {
        return prev;
      }
      const next = { ...prev, completed: merged };
      savePathProgress(userKey, next);
      return next;
    });
  }, [pathSignals, userKey]);

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

  const completed = progress.completed;
  const nextSteps = useMemo(
    () => getAvailableSteps({ completed, isGuest, limit: 4 }),
    [completed, isGuest],
  );

  const completeStep = useCallback((stepId) => {
    const nextCompleted = markStepComplete(completed, stepId);
    const next = { completed: nextCompleted, activeId: null };
    setProgress(next);
    savePathProgress(userKey, next);
    setExpandedId(null);
    onPathStepComplete?.(stepId);
  }, [completed, onPathStepComplete, userKey]);

  const runAction = useCallback((node) => {
    const { type, label } = node.action;
    switch (type) {
      case 'scroll_suggestions':
        document.querySelector('.suggestions-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        break;
      case 'open_profile':
        onOpenProfile?.();
        break;
      case 'navigate_journey':
        onNavigateToJourney?.();
        break;
      case 'navigate_canvas':
        onNavigateToCanvas?.();
        break;
      case 'open_user_guide':
        if (onOpenUserGuide) onOpenUserGuide();
        else window.dispatchEvent(new CustomEvent('open-user-guide'));
        break;
      case 'open_model_status':
        onOpenModelStatus?.();
        break;
      case 'navigate_signup':
        onNavigateToSignup?.();
        break;
      case 'none':
      default:
        break;
    }
    completeStep(node.id);
    return label;
  }, [
    completeStep,
    onNavigateToCanvas,
    onNavigateToJourney,
    onNavigateToSignup,
    onOpenModelStatus,
    onOpenProfile,
    onOpenUserGuide,
  ]);

  const resolveIcon = (name) => LucideIcons[name] || LucideIcons.Circle;

  return (
    <div className="intake-panel" role="region" aria-label="Get oriented">
      <div className="intake-avatar" aria-hidden="true">
        <SecurityChatBotIcon size={22} />
      </div>
      <h2 className="intake-greeting">{greeting}</h2>
      {subheader ? <p className="intake-sub">{subheader}</p> : null}

      <div className="advisor-path">
        <div className="advisor-path-header">
          <h3 className="advisor-path-title">{PATH_SECTION_TITLE}</h3>
        </div>

        {nextSteps.length === 0 ? (
          <p className="advisor-path-all-done">
            You&apos;ve explored the main paths — use the suggestions below for your next question.
          </p>
        ) : (
          <ul className="advisor-path-steps">
            {nextSteps.map((node) => {
              const Icon = resolveIcon(node.icon);
              const expanded = expandedId === node.id;
              return (
                <li key={node.id} className={`advisor-path-step${expanded ? ' is-expanded' : ''}`}>
                  <button
                    type="button"
                    className="advisor-path-step-btn"
                    aria-expanded={expanded}
                    onClick={() => setExpandedId(expanded ? null : node.id)}
                  >
                    <span className="advisor-path-step-icon" aria-hidden="true">
                      <Icon size={16} />
                    </span>
                    <span className="advisor-path-step-text">
                      <span className="advisor-path-step-title">{node.title}</span>
                      <span className="advisor-path-step-tagline">{node.tagline}</span>
                    </span>
                    <ChevronRight
                      size={16}
                      className={`advisor-path-step-chevron${expanded ? ' is-open' : ''}`}
                      aria-hidden="true"
                    />
                  </button>
                  {expanded && (
                    <div className="advisor-path-step-detail">
                      <p>{node.guide}</p>
                      <button
                        type="button"
                        className="advisor-path-action"
                        onClick={() => runAction(node)}
                      >
                        {node.action.label || 'Continue'}
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {isGuest && (
          <p className="advisor-path-guest-note">
            <KeyRoundIcon />
            Guest mode — progress is saved in this browser only.
            {' '}
            <button
              type="button"
              className="advisor-path-guest-link"
              onClick={() => onNavigateToSignup?.()}
            >
              Create an account
            </button>
            {' '}
            to keep chats, profile, and journey across devices.
          </p>
        )}
      </div>
    </div>
  );
};

function KeyRoundIcon() {
  const Icon = LucideIcons.KeyRound;
  return <Icon size={14} className="advisor-path-guest-icon" aria-hidden="true" />;
}

export default IntakePanel;
