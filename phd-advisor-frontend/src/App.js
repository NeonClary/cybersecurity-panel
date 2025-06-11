import React, { useState } from 'react';
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
  };

  return (
    <div className="App">
      {currentView === 'home' ? (
        <HomePage onNavigateToChat={navigateToChat} />
      ) : (
        <ChatPage onNavigateToHome={navigateToHome} />
      )}
    </div>
  );
}

export default App;