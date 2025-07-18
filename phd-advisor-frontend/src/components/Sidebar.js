import React, { useState, useEffect } from 'react';
import { 
  MessageSquare, 
  Plus, 
  Search, 
  MoreVertical, 
  Trash2, 
  Edit3,
  LogOut,
  User,
  Settings
} from 'lucide-react';
import '../styles/Sidebar.css';

const Sidebar = ({ 
  user, 
  currentSessionId, 
  onSelectSession, 
  onNewChat, 
  onSignOut,
  authToken 
}) => {
  const [chatSessions, setChatSessions] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    if (authToken) {
      fetchChatSessions();
    }
  }, [authToken]);

  const fetchChatSessions = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/chat-sessions', {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const sessions = await response.json();
        setChatSessions(sessions);
      } else {
        console.error('Failed to fetch chat sessions');
      }
    } catch (error) {
      console.error('Error fetching chat sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/chat-sessions', {
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
        const newSession = await response.json();
        setChatSessions(prev => [newSession, ...prev]);
        onNewChat(newSession.id);
      }
    } catch (error) {
      console.error('Error creating new chat:', error);
    }
  };

  const handleDeleteSession = async (sessionId, event) => {
    event.stopPropagation();
    
    if (window.confirm('Are you sure you want to delete this chat?')) {
      try {
        const response = await fetch(`http://localhost:8000/api/chat-sessions/${sessionId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          setChatSessions(prev => prev.filter(session => session.id !== sessionId));
          if (currentSessionId === sessionId) {
            onNewChat(); // Create new session if current one was deleted
          }
        }
      } catch (error) {
        console.error('Error deleting chat session:', error);
      }
    }
  };

  const filteredSessions = chatSessions.filter(session =>
    session.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 1) return 'Today';
    if (diffDays === 2) return 'Yesterday';
    if (diffDays <= 7) return `${diffDays - 1} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="user-section">
          <div className="user-info">
            <div className="user-avatar">
              <User size={20} />
            </div>
            <div className="user-details">
              <span className="user-name">{user.firstName} {user.lastName}</span>
              <span className="user-email">{user.email}</span>
            </div>
          </div>
          
          <div className="user-menu-container">
            <button 
              className="user-menu-button"
              onClick={() => setShowUserMenu(!showUserMenu)}
            >
              <MoreVertical size={16} />
            </button>
            
            {showUserMenu && (
              <div className="user-menu">
                <button className="user-menu-item">
                  <Settings size={16} />
                  <span>Settings</span>
                </button>
                <button className="user-menu-item sign-out" onClick={onSignOut}>
                  <LogOut size={16} />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>

        <button className="new-chat-button" onClick={handleNewChat}>
          <Plus size={16} />
          <span>New Chat</span>
        </button>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <div className="search-container">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search chats..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
      </div>

      {/* Chat Sessions */}
      <div className="chat-sessions">
        {isLoading ? (
          <div className="loading-sessions">
            <div className="loading-spinner"></div>
            <span>Loading chats...</span>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="no-sessions">
            {searchTerm ? 'No chats found' : 'No chats yet'}
          </div>
        ) : (
          <div className="sessions-list">
            {filteredSessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${currentSessionId === session.id ? 'active' : ''}`}
                onClick={() => onSelectSession(session.id)}
              >
                <div className="session-content">
                  <div className="session-icon">
                    <MessageSquare size={16} />
                  </div>
                  <div className="session-details">
                    <div className="session-title">{session.title}</div>
                    <div className="session-meta">
                      <span className="session-date">{formatDate(session.updated_at)}</span>
                      <span className="session-messages">{session.message_count} messages</span>
                    </div>
                  </div>
                </div>
                
                <button
                  className="session-menu-button"
                  onClick={(e) => handleDeleteSession(session.id, e)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;