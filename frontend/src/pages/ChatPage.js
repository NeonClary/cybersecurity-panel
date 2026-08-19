import React, { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback } from 'react';
import { MessageCircle, Reply, X, FileText, HelpCircle, BookmarkPlus, ClipboardPaste } from 'lucide-react';
import EnhancedChatInput from '../components/EnhancedChatInput';
import ThinkingIndicator from '../components/ThinkingIndicator';
import SuggestionsPanel from '../components/SuggestionsPanel';
import AppHeader from '../components/AppHeader';
import AdvisorStatusDropdown from '../components/AdvisorStatusDropdown';
import Sidebar from '../components/Sidebar';
import AdvisorCarousel from '../components/AdvisorCarousel';
import ClipboardPreviewModal from '../components/ClipboardPreviewModal';
import { useAppConfig } from '../contexts/AppConfigContext';
import { useTheme } from '../contexts/ThemeContext';
import '../styles/ChatPage.css';
import '../styles/EnhancedChatInput.css';
import { applyAdvisorStreamEvent } from '../utils/advisorStreamOrder';
import { pinElementToScrollerTop, findLatestUserMessage } from '../utils/pinLatestQuestion';
import {
  formatReferenceSnippet,
  wrapReferencesForAdvisorContext,
  readClipboardText,
} from '../utils/referenceSearch';
import OnboardingChat from '../components/OnboardingChat';
import AboutYouModal from '../components/AboutYouModal';
import ClearDataModal from '../components/ClearDataModal';
import SettingsModal from '../components/SettingsModal';
import IntakePanel from '../components/IntakePanel';
import useChatInputFollowupsVisible from '../hooks/useChatInputFollowupsVisible';
import useStatedGoal from '../hooks/useStatedGoal';
import {
  dropPrefetchedStream,
  getPrefetchedStream,
  MAX_PREFETCH_PROMPTS,
  putPrefetchedStream,
  readNdjsonLines,
} from '../utils/starterPrefetchCache';

const ACTIVE_ADVISORS_STORAGE_KEY = 'cybersecurityActiveAdvisorIds';

/** Persona-matched starter prompts used when a guest lands on a seeded demo chat. */
function guestStarterPrompts(config, guestPersona) {
  const intake = config?.chat_page?.intake || {};
  const byPersona = intake.by_persona || {};
  const key = (guestPersona || '').toLowerCase();
  const chips = (key && Array.isArray(byPersona[key]) ? byPersona[key] : null)
    || (Array.isArray(intake.chips) ? intake.chips : []);
  return chips
    .filter((c) => c && c.prompt && !c.free_text)
    .map((c) => c.prompt)
    .slice(0, 4);
}

const ChatPage = ({
  user,
  authToken,
  onNavigateToHome,
  onNavigateToCanvas,
  onNavigateToJourney,
  onSignOut,
  chatNavView = null,
  chatStarterNonce = 0,
  onChatBecameActive,
  onChatReturnedToStarter,
}) => {
  const { config, advisors, getAdvisorColors } = useAppConfig();
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [thinkingAdvisors, setThinkingAdvisors] = useState([]);
  const [followupChips, setFollowupChips] = useState([]);
  const [activeAdvisorIds, setActiveAdvisorIds] = useState([]);
  const [replyingTo, setReplyingTo] = useState(null);
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
  const messagesEndRef = useRef(null);
  const messagesScrollRef = useRef(null);
  const latestQuestionRef = useRef(null);
  const pinQuestionAfterRenderRef = useRef(false);
  const scrollSessionToEndRef = useRef(false);
  const pendingReferenceContextRef = useRef('');
  const rankedAdvisorIdsRef = useRef([]);
  const { isDark } = useTheme();
  const {
    followupsVisible,
    setFollowupsVisible,
  } = useChatInputFollowupsVisible();
  const guestPersona = user?.is_guest ? (user?.guest_persona || null) : null;

  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [currentSessionTitle, setCurrentSessionTitle] = useState('');
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [sidebarRefreshTrigger, setSidebarRefreshTrigger] = useState(0);

  const [userAvatarId, setUserAvatarId] = useState(
    () => localStorage.getItem('userAvatarId') || (user?.avatarId ?? null)
  );
  const handleAvatarChange = async (id) => {
    setUserAvatarId(id);
    localStorage.setItem('userAvatarId', id);
    try {
      await fetch(`${process.env.REACT_APP_API_URL}/auth/me`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ avatarId: id }),
      });
    } catch (e) {
      console.error('Failed to save avatar:', e);
    }
  };

  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showAboutYou, setShowAboutYou] = useState(false);
  const [aboutYouInitialTab, setAboutYouInitialTab] = useState('about');
  const [showClearData, setShowClearData] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState('profile');
  const [userProfile, setUserProfile] = useState(null);
  const [searchIncorporate, setSearchIncorporate] = useState(null);
  const [clipboardModal, setClipboardModal] = useState({ open: false, text: '', error: '' });
  const [composeDraft, setComposeDraft] = useState('');
  const statedGoal = useStatedGoal(authToken, user);
  const parkedConversationRef = useRef(null);
  const prefetchQueueRef = useRef([]);
  const prefetchBusyRef = useRef(false);
  const prefetchAbortRef = useRef(null);
  const prefetchUserKey = user?.id || user?._id || user?.email || (user?.is_guest ? 'guest' : 'user');

  const loadProfile = async () => {
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/api/users/me/profile`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (resp.ok) setUserProfile(await resp.json());
    } catch (e) {
      /* ignore */
    }
  };

  useEffect(() => {
    if (authToken) loadProfile();
  }, [authToken]);

  useEffect(() => {
    if (!chatStarterNonce) return;
    if (!messages.length) return;
    parkedConversationRef.current = {
      messages,
      currentSessionId,
      currentSessionTitle,
      followupChips,
    };
    setMessages([]);
    setCurrentSessionId(null);
    setCurrentSessionTitle('');
    setFollowupChips([]);
    setThinkingAdvisors([]);
    setReplyingTo(null);
    setIsLoading(false);
    // Intentionally keyed on nonce only: Back from an active chat parks the thread.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatStarterNonce]);

  useEffect(() => {
    if (chatNavView !== 'active') return;
    const parked = parkedConversationRef.current;
    if (!parked?.messages?.length) return;
    setMessages(parked.messages);
    setCurrentSessionId(parked.currentSessionId);
    setCurrentSessionTitle(parked.currentSessionTitle);
    setFollowupChips(parked.followupChips || []);
    parkedConversationRef.current = null;
  }, [chatNavView]);

  const runPrefetchQueue = useCallback(async () => {
    if (prefetchBusyRef.current || !authToken) return;
    prefetchBusyRef.current = true;
    const advisorsForRequest = activeAdvisorIds.length > 0
      ? activeAdvisorIds
      : Object.keys(advisors || {});
    while (prefetchQueueRef.current.length) {
      const prompt = prefetchQueueRef.current.shift();
      if (!prompt || getPrefetchedStream(prefetchUserKey, prompt)) continue;
      const controller = new AbortController();
      prefetchAbortRef.current = controller;
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/chat-stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({
            user_input: prompt,
            response_length: 'medium',
            prefetch: true,
            active_advisors: advisorsForRequest,
          }),
          signal: controller.signal,
        });
        if (!response.ok) continue;
        const lines = await readNdjsonLines(response);
        if (lines.length) putPrefetchedStream(prefetchUserKey, prompt, lines);
      } catch (err) {
        if (err?.name === 'AbortError') break;
      }
    }
    prefetchBusyRef.current = false;
    prefetchAbortRef.current = null;
  }, [authToken, activeAdvisorIds, advisors, prefetchUserKey]);

  const handleSuggestionsReady = useCallback((prompts) => {
    const next = (prompts || [])
      .map((p) => String(p || '').trim())
      .filter(Boolean)
      .slice(0, MAX_PREFETCH_PROMPTS)
      .filter((p) => !getPrefetchedStream(prefetchUserKey, p));
    if (next.length === 0) return;
    prefetchQueueRef.current = next;
    runPrefetchQueue();
  }, [prefetchUserKey, runPrefetchQueue]);

  useEffect(() => {
    const allIds = Object.keys(advisors || {});
    if (allIds.length === 0) return;

    setActiveAdvisorIds((prev) => {
      let next = prev.filter((id) => allIds.includes(id));
      if (next.length === 0) {
        try {
          const stored = JSON.parse(localStorage.getItem(ACTIVE_ADVISORS_STORAGE_KEY) || 'null');
          if (Array.isArray(stored)) {
            const valid = stored.filter((id) => allIds.includes(id));
            if (valid.length > 0) next = valid;
          }
        } catch {
          /* ignore */
        }
      }
      if (next.length === 0) next = [...allIds];
      if (
        prev.length === next.length &&
        prev.every((id, index) => id === next[index])
      ) {
        return prev;
      }
      return next;
    });
  }, [advisors]);

  const persistActiveAdvisorIds = (ids) => {
    localStorage.setItem(ACTIVE_ADVISORS_STORAGE_KEY, JSON.stringify(ids));
  };

  const handleSetActiveAdvisors = (ids) => {
    setActiveAdvisorIds(ids);
    persistActiveAdvisorIds(ids);
  };

  const handleToggleAdvisor = (id) => {
    setActiveAdvisorIds((prev) => {
      const set = new Set(prev);
      if (set.has(id)) {
        if (set.size <= 1) return prev;
        set.delete(id);
      } else {
        set.add(id);
      }
      const next = Array.from(set);
      persistActiveAdvisorIds(next);
      return next;
    });
  };

  const handleMobileMenuToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const consumePendingReferences = (inputMessage) => {
    const pending = pendingReferenceContextRef.current;
    if (!pending) return inputMessage;
    pendingReferenceContextRef.current = '';
    return `${pending}\n\n${inputMessage}`;
  };

  const handleComposeDraftApplied = useCallback(() => setComposeDraft(''), []);

  const handleReferenceSearchOpened = useCallback(({ source } = {}) => {
    const label = source === 'perplexity' ? 'Perplexity' : 'web search';
    setSearchIncorporate({ source: label });
  }, []);

  const handlePasteFromClipboard = async () => {
    try {
      const { text } = await readClipboardText();
      const trimmed = (text || '').trim();
      setClipboardModal({
        open: true,
        text: trimmed ? formatReferenceSnippet(trimmed) : '',
        error: trimmed ? '' : 'Clipboard was empty — paste the text you want to add.',
      });
    } catch (err) {
      setClipboardModal({
        open: true,
        text: '',
        error: err.code === 'denied'
          ? 'Clipboard access was blocked. Paste the text into the box below.'
          : 'Could not read the clipboard. Paste the text into the box below.',
      });
    }
  };

  const handleApproveClipboard = (draft) => {
    const snippet = (draft || '').trim();
    setClipboardModal({ open: false, text: '', error: '' });
    setSearchIncorporate(null);
    if (!snippet) return;
    const stored = snippet.startsWith('Here are references I found:')
      ? snippet
      : formatReferenceSnippet(snippet);
    pendingReferenceContextRef.current = wrapReferencesForAdvisorContext(stored);
    const card = {
      id: generateMessageId(),
      type: 'user',
      content: stored,
      timestamp: new Date(),
      isReferenceSnippet: true,
    };
    setMessages((prev) => [...prev, card]);
    saveMessageToSession(card).catch((err) =>
      console.error('Failed to persist reference snippet:', err)
    );
    setComposeDraft('Please use the references I just added when you answer.');
  };

  useLayoutEffect(() => {
    if (pinQuestionAfterRenderRef.current) {
      pinQuestionAfterRenderRef.current = false;
      const pin = () => pinElementToScrollerTop(
        messagesScrollRef.current,
        latestQuestionRef.current,
        { behavior: 'auto' }
      );
      pin();
      requestAnimationFrame(pin);
      return;
    }
    if (scrollSessionToEndRef.current) {
      scrollSessionToEndRef.current = false;
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    }
  }, [messages]);

  const generateMessageId = () => {
    return Date.now().toString() + Math.random().toString(36).substr(2, 9);
  };

  const createNewSession = async (firstMessage = null) => {
    try {
      const title = firstMessage 
        ? `${firstMessage.substring(0, 30)}...` 
        : `Chat ${new Date().toLocaleDateString()}`;

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chat-sessions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title })
      });

      if (response.ok) {
        const newSession = await response.json();
        
        // Update state immediately
        setCurrentSessionId(newSession.id);
        setCurrentSessionTitle(newSession.title);
        
        console.log('MongoDB session created:', newSession.id);
        return newSession.id;
      }

      console.error('Failed to create new session', response.status);
      if (response.status === 401 && typeof onSignOut === 'function') {
        onSignOut();
      }
      return null;
    } catch (error) {
      console.error('Error creating new session:', error);
      return null;
    }
  };


// Load an existing chat session
const loadChatSession = async (sessionId) => {
  if (!sessionId || isLoadingSession) return;
  setIsLoadingSession(true);
  try {
    // Use the new switch-chat endpoint that syncs context
    const response = await fetch(`${process.env.REACT_APP_API_URL}/switch-chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        chat_session_id: sessionId
      })
    });

    if (response.ok) {
      const result = await response.json();
      if (result.status === 'success') {
        setCurrentSessionId(sessionId);
        setCurrentSessionTitle(''); // Will be set from MongoDB data
        setFollowupChips([]);
        
        // Load the messages from the synced context
        const formattedMessages = result.context.messages.map(msg => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
          persona_id: msg.persona_id || msg.advisor || msg.advisorId
        }));
        
        setMessages(formattedMessages);
        setReplyingTo(null);
        setThinkingAdvisors([]);
        pendingReferenceContextRef.current = '';
        scrollSessionToEndRef.current = true;

        // Guest demo: seed persona-aligned starter prompts so suggestions match intake type
        if (user?.is_guest && formattedMessages.length > 0) {
          const starters = guestStarterPrompts(config, user.guest_persona);
          if (starters.length > 0) setFollowupChips(starters);
        }
        
        // Also get the session title from MongoDB
        const sessionResponse = await fetch(`${process.env.REACT_APP_API_URL}/api/chat-sessions/${sessionId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });
        if (sessionResponse.ok) {
          const sessionData = await sessionResponse.json();
          setCurrentSessionTitle(sessionData.title);
        }
      }
    }
  } catch (error) {
    console.error('Error loading session:', error);
  } finally {
    setIsLoadingSession(false);
  }
};

// Save a message to the current session (optional sessionId when state is not updated yet)
const saveMessageToSession = async (message, sessionIdOverride) => {
  const sid = sessionIdOverride || currentSessionId;
  if (!sid || !authToken) return;

  try {
    await fetch(`${process.env.REACT_APP_API_URL}/api/chat-sessions/${sid}/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        session_id: sid,
        message: {
          ...message,
          timestamp: message.timestamp.toISOString()
        }
      })
    });
  } catch (error) {
    console.error('Error saving message to session:', error);
  }
};

// Update session title based on first message
const updateSessionTitle = async (sessionId, newTitle) => {
  if (!sessionId || !authToken) return;

  try {
    await fetch(`${process.env.REACT_APP_API_URL}/api/chat-sessions/${sessionId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ title: newTitle })
    });
    setCurrentSessionTitle(newTitle);
  } catch (error) {
    console.error('Error updating session title:', error);
  }
};

// Handle selecting a session from sidebar
const handleSelectSession = async (sessionId) => {
  if (sessionId === currentSessionId) return;
  parkedConversationRef.current = null;
  await loadChatSession(sessionId);
  onChatBecameActive?.(sessionId);
};

// Sidebar deleted the currently-active chat. Clear local state without
// creating a replacement session.
const handleCurrentSessionDeleted = () => {
  setCurrentSessionId(null);
  setCurrentSessionTitle('');
  setMessages([]);
  setReplyingTo(null);
  setThinkingAdvisors([]);
  setFollowupChips([]);
  setUploadedDocuments([]);
};

// Handle creating new chat from sidebar
const handleNewChat = async (sessionId = null) => {
  if (sessionId) {
    // Loading existing session
    await loadChatSession(sessionId);
    return; // Return early for existing session loading
  } else {
    // Creating completely new chat with fresh context
    try {
      // Step 1: Reset memory session
      const response = await fetch(`${process.env.REACT_APP_API_URL}/new-chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: `Chat ${new Date().toLocaleDateString()}`
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.status === 'success') {
          // Step 2: Immediately create MongoDB session
          const newSessionId = await createNewSession(`Chat ${new Date().toLocaleDateString()}`);
          
          if (newSessionId) {
            // Reset all state to fresh with the new session
            setMessages([]);
            setCurrentSessionId(newSessionId); // Set the new session ID immediately
            setCurrentSessionTitle(`Chat ${new Date().toLocaleDateString()}`);
            setReplyingTo(null);
            setFollowupChips([]);
            setThinkingAdvisors([]);
            setUploadedDocuments([]);
            pendingReferenceContextRef.current = '';
            setSearchIncorporate(null);
            onChatReturnedToStarter?.();
            
            console.log('New chat created with MongoDB session:', newSessionId);
            
            // Wait a bit to ensure state has updated
            await new Promise(resolve => setTimeout(resolve, 100));
            return newSessionId; // Return the session ID for the sidebar
          } else {
            throw new Error('Failed to create MongoDB session');
          }
        } else {
          throw new Error('Failed to create memory session');
        }
      } else {
        throw new Error(`HTTP error: ${response.status}`);
      }
    } catch (error) {
      console.error('Error creating new chat:', error);
      
      // Fallback to local reset
      setMessages([]);
      setCurrentSessionId(null);
      setCurrentSessionTitle('');
      setReplyingTo(null);
      setThinkingAdvisors([]);
      setUploadedDocuments([]);
      onChatReturnedToStarter?.();
      
      // Re-throw the error so the sidebar knows something went wrong
      throw error;
    }
  }
};

  

  const handleFileUploaded = async (file, uploadResult) => {
    // FIXED: Use the upload result data for better messaging
    const documentMessage = {
      id: generateMessageId(),
      type: 'document_upload',
      content: `Document uploaded: ${uploadResult.filename || file.name} (${uploadResult.chunks_created || 0} sections processed)`,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, documentMessage]);
    setUploadedDocuments(prev => [...prev, file]);
    
    // FIXED: Log document access info
    console.log('File uploaded to session:', {
      filename: uploadResult.filename,
      session_id: uploadResult.session_id,
      chat_session_id: uploadResult.chat_session_id,
      current_session_id: currentSessionId
    });
    
    // Save document upload message to database if we have a current session
    if (currentSessionId) {
      await saveMessageToSession(documentMessage);
    }
  };

  const applyStreamPayload = (payload, sessionId) => {
    const d = payload.data || {};
    switch (payload.type) {
      case 'advisor_start':
      case 'advisor_delta':
      case 'advisor_done':
      case 'advisor': {
        setMessages(prev => applyAdvisorStreamEvent(prev, payload, {
          generateId: generateMessageId,
        }));
        if (payload.type === 'advisor_start' || payload.type === 'advisor') {
          setThinkingAdvisors(prev => prev.filter(a => a !== d.persona_id));
        }
        if (payload.type === 'advisor_done' || payload.type === 'advisor') {
          saveMessageToSession({
            id: generateMessageId(),
            type: 'advisor',
            persona_id: d.persona_id,
            content: d.content,
            timestamp: new Date(),
            advisorName: d.persona_name || d.persona_id,
            used_documents: d.used_documents || false,
            document_chunks_used: d.document_chunks_used || 0,
          }, sessionId).catch(err =>
            console.error('Failed to persist advisor message:', err)
          );
        }
        break;
      }
      case 'clarification':
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          type: 'clarification',
          content: d.message,
          suggestions: d.suggestions || [],
          timestamp: new Date(),
        }]);
        break;
      case 'followups':
        if (Array.isArray(d.suggestions) && d.suggestions.length > 0) {
          setFollowupChips(d.suggestions);
        }
        break;
      case 'journey_suggestions':
        break;
      case 'progress':
        if (d.phase === 'selected' && Array.isArray(d.selected_advisors)) {
          rankedAdvisorIdsRef.current = d.selected_advisors;
          setThinkingAdvisors(prev => {
            const next = new Set(prev);
            next.add('system');
            d.selected_advisors.forEach(id => next.add(id));
            return Array.from(next);
          });
          break;
        }
        if (d.phase === 'complete') {
          setIsLoading(false);
          setThinkingAdvisors([]);
          break;
        }
        if (d.persona_id != null) {
          setThinkingAdvisors(prev => prev.filter(a => a !== d.persona_id));
        }
        break;
      case 'error':
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          type: 'error',
          content: d.detail || 'An error occurred',
          timestamp: new Date(),
        }]);
        break;
      default:
        break;
    }
  };

  const replayCachedLines = async (lines, sessionId) => {
    for (const line of lines) {
      if (!line || !String(line).trim()) continue;
      try {
        applyStreamPayload(JSON.parse(line), sessionId);
      } catch {
        /* skip */
      }
    }
    try {
      await fetch(`${process.env.REACT_APP_API_URL}/switch-chat`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ chat_session_id: sessionId }),
      });
    } catch (err) {
      console.error('Failed to hydrate session from prefetch cache:', err);
    }
  };


  const handleSendMessage = async (inputMessage) => {
    if (!inputMessage.trim()) return;

    // Create user message
    const userMessage = {
      id: generateMessageId(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    // Add to local state immediately
    setMessages(prev => [...prev, userMessage]);
    pinQuestionAfterRenderRef.current = true;

    // Create new session if we don't have one
    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = await createNewSession(inputMessage);
      if (!sessionId) {
        console.error('Failed to create session');
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          type: 'error',
          content: 'Could not start a chat session. Your sign-in may have expired — please sign in again (or Explore as guest).',
          timestamp: new Date(),
        }]);
        return;
      }
    }

    saveMessageToSession(userMessage, sessionId).catch(err =>
      console.error('Failed to persist user message:', err)
    );

    if (messages.length === 0) {
      onChatBecameActive?.(sessionId);
    }

    // Update session title if this is the first message and title is generic
    if (messages.length === 0 && currentSessionTitle.includes('Chat ')) {
      const newTitle = inputMessage.length > 30 
        ? `${inputMessage.substring(0, 30)}...` 
        : inputMessage;
      setCurrentSessionTitle(newTitle);
      updateSessionTitle(sessionId, newTitle).catch(err =>
        console.error('Failed to update session title:', err)
      );
    }

    // Set loading state
    setIsLoading(true);
    const advisorsForRequest = activeAdvisorIds.length > 0
      ? activeAdvisorIds
      : Object.keys(advisors || {});
    // Start with just the orchestrator's thinking bubble. The backend will
    // emit a `progress { phase: 'selected', selected_advisors: [...] }` event
    // naming the advisors it picked (ranked), and that handler will add their
    // ThinkingIndicators. This prevents the brief flash of thinking indicators
    // for every advisor in the active pool before ranking has run.
    setThinkingAdvisors(['system']);
    setFollowupChips([]);
    rankedAdvisorIdsRef.current = [];
    prefetchAbortRef.current?.abort();
    prefetchQueueRef.current = [];

    const cached = !pendingReferenceContextRef.current
      && getPrefetchedStream(prefetchUserKey, inputMessage);
    if (cached?.lines?.length) {
      try {
        await replayCachedLines(cached.lines, sessionId);
        dropPrefetchedStream(prefetchUserKey, inputMessage);
        setIsLoading(false);
        setThinkingAdvisors([]);
        setSidebarRefreshTrigger(prev => prev + 1);
        return;
      } catch (error) {
        console.error('Prefetch replay failed, using live stream:', error);
      }
    }

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/chat-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          user_input: consumePendingReferences(inputMessage),
          response_length: 'medium',
          chat_session_id: sessionId,
          active_advisors: advisorsForRequest,
        }),
      });

      if (!response.ok) {
        if (response.status === 401 && typeof onSignOut === 'function') {
          onSignOut();
          throw new Error('Session expired. Please sign in again.');
        }
        let detail = `HTTP error! status: ${response.status}`;
        try {
          const errBody = await response.json();
          if (errBody?.detail) {
            detail = typeof errBody.detail === 'string'
              ? errBody.detail
              : JSON.stringify(errBody.detail);
          }
        } catch { /* keep status text */ }
        throw new Error(detail);
      }

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
          } catch (parseErr) {
            console.error('Failed to parse chat-stream line:', line, parseErr);
            continue;
          }
          applyStreamPayload(payload, sessionId);
        }
      }

    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'error',
        content: `Failed to send message: ${error.message}`,
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
      setThinkingAdvisors([]);
      setSidebarRefreshTrigger(prev => prev + 1);
    }
  };

  const handleReplyToAdvisor = async (inputMessage, replyContext) => {
  // Ensure we have a session before proceeding
  let sessionId = currentSessionId;
  if (!sessionId) {
    sessionId = await createNewSession(inputMessage);
    if (!sessionId) {
      console.error('Failed to create session for reply');
      return;
    }
  }

  const replyMessage = {
    id: generateMessageId(),
    type: 'user',
    content: inputMessage,
    replyTo: {
      advisorId: replyContext.persona_id,
      advisorName: replyContext.advisorName,
      messageId: replyContext.messageId
    },
    timestamp: new Date()
  };

  setMessages(prev => [...prev, replyMessage]);
  pinQuestionAfterRenderRef.current = true;
  
  // Save reply message to database with explicit session ID
  await saveMessageToSession(replyMessage, sessionId);
  
  setIsLoading(true);
  setThinkingAdvisors([replyContext.persona_id]);

  try {
    const response = await fetch(`${process.env.REACT_APP_API_URL}/reply-to-advisor`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        user_input: consumePendingReferences(inputMessage),
        advisor_id: replyContext.advisorId,
        original_message_id: replyContext.messageId,
        chat_session_id: sessionId // Use confirmed session ID
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();

    if (data.type === 'advisor_reply') {
      const replyResponseMessage = {
        id: generateMessageId(),
        type: 'advisor',
        persona_id: data.persona_id,
        advisorName: data.persona,
        content: data.response,
        isReply: true,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, replyResponseMessage]);
      
      // Save advisor reply to database
      await saveMessageToSession(replyResponseMessage, sessionId);
    }

  } catch (error) {
    console.error('Error replying to advisor:', error);
    const errorMessage = {
      id: generateMessageId(),
      type: 'error',
      content: 'Sorry, I encountered an error with your reply. Please try again.',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, errorMessage]);
    
    // Save error message to database
    await saveMessageToSession(errorMessage, sessionId);
  }

  setIsLoading(false);
  setThinkingAdvisors([]);
};

  const handleExpandMessage = async (messageId, advisorId) => {
    const advisor = advisors[advisorId];
    if (!advisor) return;

    const originalMessage = messages.find(msg => msg.id === messageId);
    if (!originalMessage) return;

    const expandPrompt = `Please expand on your previous response: "${originalMessage.content.substring(0, 100)}..." Provide more detail and depth.`;
    
    const expandMessage = {
      id: generateMessageId(),
      type: 'user',
      content: expandPrompt,
      timestamp: new Date(),
      isExpandRequest: true,
      expandsMessageId: messageId
    };
    setMessages(prev => [...prev, expandMessage]);
    pinQuestionAfterRenderRef.current = true;
    
    // Save expand request to database
    await saveMessageToSession(expandMessage);
    
    setIsLoading(true);
    setThinkingAdvisors([advisorId]);

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/chat/${advisorId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          user_input: expandPrompt,
          response_length: 'long'
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }

      const data = await response.json();

      if (data.persona && data.response) {
        const expandedMessage = {
          id: generateMessageId(),
          type: 'advisor',
          persona_id: advisorId,
          advisorName: advisor.name,
          content: data.response,
          isExpansion: true,
          expandsMessageId: messageId,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, expandedMessage]);
        
        // Save expanded response to database
        await saveMessageToSession(expandedMessage);
      } else {
        const errorMessage = {
          id: generateMessageId(),
          type: 'error',
          content: 'Sorry, I received an unexpected response format. Please try again.',
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
        
        // Save error message to database
        await saveMessageToSession(errorMessage);
      }

    } catch (error) {
      console.error('Error expanding message:', error);
      const errorMessage = {
        id: generateMessageId(),
        type: 'error',
        content: 'Sorry, I encountered an error while expanding the message. Please try again.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
      
      // Save error message to database
      await saveMessageToSession(errorMessage);
    }

    setIsLoading(false);
    setThinkingAdvisors([]);
  };

  const handleReplyToMessage = (message) => {
    const advisor = advisors[message.persona_id];
    setReplyingTo({
      advisorId: message.persona_id,
      messageId: message.id,
      advisorName: advisor?.name || message.advisorName || 'Advisor',
      persona_id: message.persona_id
    });
  };

  const handleMessageClick = (message) => {
    if (message.type === 'advisor') {
      const advisor = advisors[message.persona_id];
      setReplyingTo({
        advisorId: message.persona_id,
        messageId: message.id,
        advisorName: advisor?.name || message.advisorName || 'Advisor',
        persona_id: message.persona_id
      });
    }
  };

  /** Group consecutive advisor messages so we can render them in a horizontal carousel */
  const messageGroups = useMemo(() => {
    const groups = [];
    let i = 0;
    let lastUserContent = '';
    while (i < messages.length) {
      if (messages[i].type === 'advisor') {
        const advisorGroup = [];
        while (i < messages.length && messages[i].type === 'advisor') {
          advisorGroup.push(messages[i]);
          i++;
        }
        groups.push({
          type: 'advisor_group',
          messages: advisorGroup,
          userQuestion: lastUserContent,
        });
      } else {
        if (messages[i].type === 'user' && !messages[i].isReferenceSnippet) {
          lastUserContent = messages[i].content;
        }
        groups.push({ type: 'single', message: messages[i] });
        i++;
      }
    }
    return groups;
  }, [messages]);

  const latestUserMessageId = useMemo(
    () => findLatestUserMessage(messages)?.id || null,
    [messages]
  );

  const handleInputSubmit = async (inputMessage) => {
  if (replyingTo) {
    // This is a reply to a specific message
    await handleReplyToAdvisor(inputMessage, replyingTo);
  } else {
    // This is a regular message
    await handleSendMessage(inputMessage);
  }
};

  const cancelReply = () => {
    setReplyingTo(null);
  };

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const handleSidebarToggle = (isCollapsed) => {
    setIsSidebarCollapsed(isCollapsed);
  };

  const hasMessages = messages.length > 0;
  const hasConversationMessages = messages.filter(m => m.type !== 'system' && m.type !== 'document_upload').length > 0;

  const chatPlaceholder = config?.chat_page?.placeholder || "Ask your advisors anything...";

  return (
    <div className="chat-page-with-sidebar">
      {/* Sidebar Component */}
      <Sidebar 
        user={user}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onCurrentSessionDeleted={handleCurrentSessionDeleted}
        onSignOut={onSignOut}
        authToken={authToken}
        onSidebarToggle={handleSidebarToggle}
        isMobileOpen={isMobileMenuOpen}
        onMobileToggle={setIsMobileMenuOpen}
        onNavigateToCanvas={onNavigateToCanvas}
        refreshTrigger={sidebarRefreshTrigger}
        userAvatarId={userAvatarId}
        onAvatarChange={handleAvatarChange}
        onOpenProfile={() => {
          setAboutYouInitialTab('about');
          setShowAboutYou(true);
        }}
        onOpenAccount={() => {
          setSettingsInitialTab('profile');
          setShowSettings(true);
        }}
        onOpenClearData={() => setShowClearData(true)}
        onOpenModelStatus={() => {
          setSettingsInitialTab('model-status');
          setShowSettings(true);
        }}
        onNavigateToJourney={onNavigateToJourney}
        statedGoal={statedGoal}
        onRemoveSampleData={user?.is_guest ? async () => {
          if (!window.confirm('Remove all sample demo data? You stay in guest mode with a clean slate.')) return;
          try {
            const { removeGuestSampleData } = await import('../utils/guestSample');
            await removeGuestSampleData(authToken);
            setMessages([]);
            setCurrentSessionId(null);
            setCurrentSessionTitle('');
            setSidebarRefreshTrigger((n) => (n || 0) + 1);
            window.alert('Sample data removed.');
          } catch (e) {
            window.alert(e.message || 'Failed to remove sample data');
          }
        } : undefined}
      />
      
      <div className={`main-chat-area ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        <div className="modern-chat-page">
          <AppHeader
            currentPage="chat"
            onNavigateToHome={onNavigateToHome}
            onNavigateToChat={() => {}}
            onNavigateToCanvas={onNavigateToCanvas}
            onNavigateToJourney={onNavigateToJourney}
            onMobileMenu={handleMobileMenuToggle}
          >
            <AdvisorStatusDropdown
              advisors={advisors}
              activeAdvisorIds={activeAdvisorIds}
              onToggleAdvisor={handleToggleAdvisor}
              onSetActiveAdvisors={handleSetActiveAdvisors}
              thinkingAdvisors={thinkingAdvisors}
              getAdvisorColors={getAdvisorColors}
              isDark={isDark}
            />
            {/* User guide button (from main) — slotted into AppHeader's children */}
            <button
              className="icon-btn header-help-btn"
              onClick={() => window.dispatchEvent(new CustomEvent('open-user-guide'))}
              title="Open user guide"
            >
              <HelpCircle size={18} />
            </button>
          </AppHeader>

          {/* Main Content */}
          <div className="chat-content">
            {!hasMessages ? (
              <div className="welcome-state">
                <IntakePanel
                  onSubmit={handleSendMessage}
                  guestPersona={guestPersona}
                  authToken={authToken}
                  user={user}
                  statedGoal={statedGoal}
                />
                <SuggestionsPanel
                  onSuggestionClick={handleSendMessage}
                  guestPersona={guestPersona}
                  authToken={authToken}
                  user={user}
                  statedGoal={statedGoal}
                  onSuggestionsReady={handleSuggestionsReady}
                />
              </div>
            ) : (
              <div className="messages-container">
                {/* Add loading session indicator */}
                {isLoadingSession && (
                  <div className="loading-session">
                    <div className="loading-spinner"></div>
                    <span>Loading chat session...</span>
                  </div>
                )}
                
                <div className="messages-list">
                  <div className="messages-scroll" ref={messagesScrollRef}>
                    {messageGroups.map((group) => (
                      group.type === 'advisor_group' ? (
                        <AdvisorCarousel
                          key={group.messages[0]?.id || 'advisor-group'}
                          messages={group.messages}
                          onReply={handleReplyToMessage}
                          onExpand={handleExpandMessage}
                          onClick={handleMessageClick}
                          onReferenceSearchOpened={handleReferenceSearchOpened}
                          userQuestion={group.userQuestion}
                        />
                      ) : (
                      <div key={group.message.id}>
                        {group.message.type === 'user' && group.message.isReferenceSnippet && (
                          <div className="system-message-container">
                            <div className="system-message reference-snippet-card">
                              <BookmarkPlus size={16} />
                              <div>
                                <p className="reference-snippet-title">Added to context</p>
                                <p className="reference-snippet-body">{group.message.content}</p>
                              </div>
                            </div>
                          </div>
                        )}

                        {group.message.type === 'user' && !group.message.isReferenceSnippet && (
                          <div
                            className={`user-message-container${group.message.id === latestUserMessageId && isLoading ? ' is-pinned-question' : ''}`}
                            ref={group.message.id === latestUserMessageId ? latestQuestionRef : null}
                            data-latest-question={group.message.id === latestUserMessageId ? 'true' : undefined}
                          >
                            <div className="user-message">
                              {group.message.replyTo && (
                                <div className="reply-indicator">
                                  <Reply size={12} />
                                  <span>Reply to {group.message.replyTo.advisorName}</span>
                                </div>
                              )}
                              <p>{group.message.content}</p>
                            </div>
                          </div>
                        )}

                        {group.message.type === 'error' && (
                          <div className="error-message-container">
                            <div className="error-message">
                              <p>{group.message.content}</p>
                            </div>
                          </div>
                        )}

                        {group.message.type === 'system' && (
                          <div className="system-message-container">
                            <div className="system-message">
                              <p>{group.message.content}</p>
                            </div>
                          </div>
                        )}

                        {group.message.type === 'document_upload' && (
                          <div className="system-message-container">
                            <div className="system-message document-upload">
                              <FileText size={16} />
                              <p>{group.message.content}</p>
                            </div>
                          </div>
                        )}

                        {group.message.type === 'clarification' && (
                          <div className="clarification-message-container">
                            <div className="clarification-message">
                              <div className="clarification-header">
                                <MessageCircle size={16} />
                                <span>I need a bit more information</span>
                              </div>
                              <p>{group.message.content}</p>
                              
                              {group.message.suggestions && group.message.suggestions.length > 0 && (
                                <div className="clarification-suggestions">
                                  <p className="suggestions-label">Here are some ways you could be more specific:</p>
                                  <div className="suggestions-list">
                                    {group.message.suggestions.map((suggestion, index) => (
                                      <button
                                        key={index}
                                        className="suggestion-button"
                                        onClick={() => handleSendMessage(suggestion)}
                                      >
                                        {suggestion}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                      )
                    ))}

                    {thinkingAdvisors.includes('system') && (
                      <div className="orchestrator-thinking">
                        <div className="thinking-bubble">
                          <MessageCircle size={20} />
                        </div>
                        <div className="thinking-content">
                          <span className="thinking-label">Orchestrator is thinking...</span>
                          <div className="thinking-animation">
                            <div className="dot"></div>
                            <div className="dot"></div>
                            <div className="dot"></div>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {thinkingAdvisors.filter(id => id !== 'system').map(advisorId => (
                      <ThinkingIndicator key={advisorId} advisorId={advisorId} />
                    ))}

                    <div ref={messagesEndRef} />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="floating-input-area">
            {replyingTo && (
              <div className="reply-banner">
                <div className="reply-info">
                  <Reply size={16} />
                  <span>Replying to <strong>{replyingTo.advisorName}</strong></span>
                </div>
                <button onClick={cancelReply} className="cancel-reply">
                  <X size={16} />
                </button>
              </div>
            )}

            {searchIncorporate && (
              <div className="search-incorporate-banner" role="status">
                <div className="reply-info">
                  <ClipboardPaste size={16} />
                  <span>
                    Copy what you want from <strong>{searchIncorporate.source}</strong>, then come back and paste it here.
                  </span>
                </div>
                <div className="search-incorporate-actions">
                  <button
                    type="button"
                    className="search-incorporate-btn"
                    onClick={handlePasteFromClipboard}
                    title="I copied something"
                  >
                    Paste from clipboard
                  </button>
                  <button
                    type="button"
                    className="cancel-reply"
                    onClick={() => setSearchIncorporate(null)}
                    aria-label="Dismiss"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            )}

            <EnhancedChatInput
              onSendMessage={handleInputSubmit}
              onFileUploaded={handleFileUploaded}
              uploadedDocuments={uploadedDocuments}
              isLoading={isLoading}
              currentChatSessionId={currentSessionId}
              authToken={authToken}
              placeholder={
                replyingTo
                  ? `Reply to ${replyingTo.advisorName}...`
                  : chatPlaceholder
              }
              showProfileButtons={!userProfile}
              onOpenOnboarding={() => setShowOnboarding(true)}
              onOpenProfileForm={() => {
                setAboutYouInitialTab('profile');
                setShowAboutYou(true);
              }}
              showExport
              exportHasMessages={hasConversationMessages}
              exportSessionId={currentSessionId}
              composeDraft={composeDraft}
              onComposeDraftApplied={handleComposeDraftApplied}
            />
            {followupsVisible && followupChips.length > 0 && !isLoading && (
              <div className="followup-chips-row">
                <div className="followup-chips" role="group" aria-label="Suggested follow-ups">
                  {followupChips.map((chip, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="followup-chip"
                      onClick={() => {
                        setFollowupChips([]);
                        handleInputSubmit(chip);
                      }}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="followup-chips-hide"
                  onClick={() => setFollowupsVisible(false)}
                  aria-label="Hide suggested follow-ups"
                  title="Hide suggested follow-ups"
                >
                  <X size={14} aria-hidden="true" />
                  <span>Hide suggestions</span>
                </button>
              </div>
            )}
            {!followupsVisible && hasMessages && !isLoading && (
              <div className="followup-chips-show-bar">
                <button
                  type="button"
                  className="followup-chips-show"
                  onClick={() => setFollowupsVisible(true)}
                >
                  Show suggestions
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {showAboutYou && (
        <AboutYouModal
          authToken={authToken}
          existingProfile={userProfile}
          initialTab={aboutYouInitialTab}
          onClose={() => { setShowAboutYou(false); loadProfile(); }}
        />
      )}
      {showOnboarding && (
        <OnboardingChat
          authToken={authToken}
          userName={user?.firstName}
          onClose={() => { setShowOnboarding(false); loadProfile(); }}
        />
      )}
      {showSettings && (
        <SettingsModal
          user={user}
          authToken={authToken}
          initialTab={settingsInitialTab}
          onClose={() => setShowSettings(false)}
          onSignOut={onSignOut}
          onUserUpdate={(u) => {
            localStorage.setItem('user', JSON.stringify(u));
          }}
        />
      )}
      {showClearData && (
        <ClearDataModal
          authToken={authToken}
          onClose={() => setShowClearData(false)}
          onDataCleared={() => { loadProfile(); setShowClearData(false); }}
        />
      )}
      <ClipboardPreviewModal
        isOpen={clipboardModal.open}
        initialText={clipboardModal.text}
        clipboardError={clipboardModal.error}
        onCancel={() => setClipboardModal({ open: false, text: '', error: '' })}
        onApprove={handleApproveClipboard}
      />
    </div>
  );
};

export default ChatPage;
