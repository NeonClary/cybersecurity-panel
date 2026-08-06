import React, { useState, useEffect } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { AppConfigProvider } from './contexts/AppConfigContext';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';
import AuthPage from './pages/AuthPage';
import CanvasPage from './pages/CanvasPage';
import JourneyPage from './pages/JourneyPage';
import UserGuide from './components/UserGuide';
import './styles/components.css';

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [authToken, setAuthToken] = useState(null);

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
    setCurrentView('chat');

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
          setCurrentView('home');
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
  }, []);

  const navigateToAuth = () => {
    setCurrentView('auth');
  };

  const navigateToJourney = () => {
    setCurrentView('journey');
  };

  const navigateToCanvas = (canvasView) => {
    if (canvasView === 'journey') {
      setCurrentView('journey');
      return;
    }
    if (['insights', 'workspace', 'deliverables'].includes(canvasView)) {
      localStorage.setItem('canvas-view-v2', canvasView);
    }
    setCurrentView('canvas');
  };

  const navigateToChat = () => {
    setCurrentView('chat');
  };

  const navigateToHome = () => {
    setCurrentView('home');
  };

  const handleAuthSuccess = (userData, token) => {
    setUser(userData);
    setAuthToken(token);
    setIsAuthenticated(true);
    setCurrentView('chat');
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
    setCurrentView('home');
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
              onSignOut={handleSignOut}
              onUserUpdate={setUser}
            />
          )}
          <UserGuide />
        </div>
      </ThemeProvider>
    </AppConfigProvider>
  );
}

export default App;
