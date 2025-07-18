import React, { useState } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';
import AuthPage from './pages/AuthPage';
import './styles/components.css';

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const navigateToAuth = () => {
  setCurrentView('auth');
};

const navigateToHome = () => {
  setCurrentView('home');
  setIsAuthenticated(false); // Reset auth when going home
  // Reset session when going home
  fetch('http://localhost:8000/reset-session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  }).catch(console.error);
};

const handleAuthSuccess = () => {
  setIsAuthenticated(true);
  setCurrentView('chat');
};

  return (
  <ThemeProvider>
    <div className="App">
      {currentView === 'home' && (
        <HomePage onNavigateToChat={navigateToAuth} />
      )}
      {currentView === 'auth' && (
        <AuthPage onAuthSuccess={handleAuthSuccess} />
      )}
      {currentView === 'chat' && (
        <ChatPage onNavigateToHome={navigateToHome} />
      )}
    </div>
  </ThemeProvider>
);
}

export default App;