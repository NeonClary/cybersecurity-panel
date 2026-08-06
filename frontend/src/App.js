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
    const token = localStorage.getItem('authToken');
    const userData = localStorage.getItem('user');

    if (token && userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setAuthToken(token);
        setUser(parsedUser);
        setIsAuthenticated(true);
        setCurrentView('chat');
      } catch (error) {
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');
      }
    }
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
