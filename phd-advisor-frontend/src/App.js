import React, { useState } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import HomePage from './pages/HomePage';
import ChatPage from './pages/ChatPage';
import './styles/components.css';

function App() {
  const [currentView, setCurrentView] = useState('home');

  const navigateToChat = () => {
    setCurrentView('chat');
  };

  const navigateToHome = () => {
    setCurrentView('home');
    // Reset session when going home
    fetch('http://localhost:8000/reset-session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    }).catch(console.error);
  };

  return (
    <ThemeProvider>
      <div className="App">
        {currentView === 'home' ? (
          <HomePage onNavigateToChat={navigateToChat} />
        ) : (
          <ChatPage onNavigateToHome={navigateToHome} />
        )}
      </div>
    </ThemeProvider>
  );
}

export default App;