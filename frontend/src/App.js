import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { AppConfigProvider } from './contexts/AppConfigContext';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';
import AuthPage from './pages/AuthPage';
import CanvasPage from './pages/CanvasPage';
import JourneyPage from './pages/JourneyPage';
import UserGuide from './components/UserGuide';
import './styles/components.css';
import {
  chatActiveState,
  chatStarterState,
  homeState,
  mapPopState,
  sameHistoryState,
} from './utils/chatHistoryNav';

let didSeedRestoredChatHistory = false;

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [chatNavView, setChatNavView] = useState(null);
  const [chatStarterNonce, setChatStarterNonce] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [authToken, setAuthToken] = useState(null);
  const historyStateRef = useRef(null);
  const chatNavViewRef = useRef(null);
  chatNavViewRef.current = chatNavView;

  const applyHistoryState = useCallback((state, { fromPop = false, replace = false } = {}) => {
    const mapped = mapPopState(state);
    if (!fromPop) {
      if (sameHistoryState(historyStateRef.current, state)) {
        setCurrentView(mapped.currentView);
        setChatNavView(mapped.chatNavView);
        return;
      }
      if (replace) {
        window.history.replaceState(state, '');
      } else {
        window.history.pushState(state, '');
      }
    }
    historyStateRef.current = state || null;
    setCurrentView(mapped.currentView);
    if (mapped.chatNavView === 'starter' && chatNavViewRef.current === 'active') {
      setChatStarterNonce((n) => n + 1);
    }
    setChatNavView(mapped.chatNavView);
  }, []);

  useEffect(() => {
    const onPop = (event) => {
      applyHistoryState(event.state, { fromPop: true });
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [applyHistoryState]);

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem('authToken');
    const userData = localStorage.getItem('user');

    if (!token || !userData) return undefined;

    let parsedUser;
    try {
      parsedUser = JSON.parse(userData);
    } catch {
      localStorage.removeItem('authToken');
      localStorage.removeItem('user');
      return undefined;
    }

    // Restore UI immediately, then prove the JWT still works. Stale tokens
    // (rotated secret, deleted guest, etc.) previously left the user in chat
    // with every API call 401'ing and send silently failing.
    setAuthToken(token);
    setUser(parsedUser);
    setIsAuthenticated(true);
    if (!didSeedRestoredChatHistory) {
      didSeedRestoredChatHistory = true;
      applyHistoryState(chatStarterState());
    } else {
      setCurrentView('chat');
      setChatNavView('starter');
    }

    (async () => {
      try {
        const apiUrl = process.env.REACT_APP_API_URL || '';
        const resp = await fetch(`${apiUrl}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;
        if (!resp.ok) {
          localStorage.removeItem('authToken');
          localStorage.removeItem('user');
          setUser(null);
          setAuthToken(null);
          setIsAuthenticated(false);
          applyHistoryState(homeState(), { replace: true });
          return;
        }
        const me = await resp.json();
        if (cancelled || !me) return;
        setUser(me);
        try {
          localStorage.setItem('user', JSON.stringify(me));
        } catch { /* ignore quota */ }
      } catch {
        // Network blip — keep optimistic session; next API call will re-check.
      }
    })();

    return () => { cancelled = true; };
  }, [applyHistoryState]);

  const navigateToAuth = () => {
    applyHistoryState({ view: 'auth' });
  };

  const navigateToJourney = () => {
    applyHistoryState({ view: 'journey' });
  };

  const navigateToCanvas = (canvasView) => {
    if (canvasView === 'journey') {
      applyHistoryState({ view: 'journey' });
      return;
    }
    if (['insights', 'workspace', 'deliverables'].includes(canvasView)) {
      localStorage.setItem('canvas-view-v2', canvasView);
    }
    applyHistoryState({ view: 'canvas' });
  };

  const navigateToChat = () => {
    applyHistoryState(chatStarterState());
  };

  const navigateToHome = () => {
    applyHistoryState(homeState());
  };

  const handleChatBecameActive = (sessionId) => {
    applyHistoryState(chatActiveState(sessionId));
  };

  const handleChatReturnedToStarter = () => {
    applyHistoryState(chatStarterState(), { replace: true });
  };

  const handleAuthSuccess = (userData, token) => {
    setUser(userData);
    setAuthToken(token);
    setIsAuthenticated(true);
    applyHistoryState(chatStarterState(), {
      replace: historyStateRef.current?.view === 'auth',
    });
  };

  const handleSignOut = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    try {
      localStorage.removeItem('canvas-layout-v2');
      localStorage.removeItem('canvas-states-v2');
      localStorage.removeItem('canvas-deliverables-v2');
      localStorage.removeItem('canvas-view-v2');
      localStorage.removeItem('canvas-task-status-v1');
    } catch { /* ignore */ }
    setUser(null);
    setAuthToken(null);
    setIsAuthenticated(false);
    applyHistoryState(homeState(), { replace: true });
  };

  return (
    <AppConfigProvider>
      <ThemeProvider>
        <div className="App">
          {currentView === 'home' && (
            <HomePage
              onNavigateToHome={navigateToHome}
              onNavigateToChat={isAuthenticated ? navigateToChat : navigateToAuth}
              onNavigateToCanvas={isAuthenticated ? navigateToCanvas : navigateToAuth}
              onNavigateToJourney={isAuthenticated ? navigateToJourney : navigateToAuth}
              onExploreAsGuest={handleAuthSuccess}
              isAuthenticated={isAuthenticated}
            />
          )}
          {currentView === 'auth' && (
            <AuthPage onAuthSuccess={handleAuthSuccess} />
          )}
          {currentView === 'canvas' && isAuthenticated && (
            <CanvasPage
              user={user}
              authToken={authToken}
              onNavigateToHome={navigateToHome}
              onNavigateToChat={navigateToChat}
              onNavigateToJourney={navigateToJourney}
              onNavigateToCanvas={navigateToCanvas}
              onSignOut={handleSignOut}
              onUserUpdate={setUser}
            />
          )}
          {currentView === 'journey' && isAuthenticated && (
            <JourneyPage
              user={user}
              authToken={authToken}
              onNavigateToHome={navigateToHome}
              onNavigateToChat={navigateToChat}
              onNavigateToCanvas={navigateToCanvas}
              onNavigateToJourney={navigateToJourney}
              onSignOut={handleSignOut}
              onUserUpdate={setUser}
            />
          )}
          {currentView === 'chat' && isAuthenticated && (
            <ChatPage
              user={user}
              authToken={authToken}
              onNavigateToHome={navigateToHome}
              onNavigateToCanvas={navigateToCanvas}
              onNavigateToJourney={navigateToJourney}
              onNavigateToSignup={navigateToAuth}
              onSignOut={handleSignOut}
              onUserUpdate={setUser}
              chatNavView={chatNavView}
              chatStarterNonce={chatStarterNonce}
              onChatBecameActive={handleChatBecameActive}
              onChatReturnedToStarter={handleChatReturnedToStarter}
            />
          )}
          <UserGuide />
        </div>
      </ThemeProvider>
    </AppConfigProvider>
  );
}

export default App;
