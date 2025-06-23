// src/pages/ChatPage.js
import React, { useState, useEffect, useRef } from 'react';
import { Home, MessageCircle, Reply, X, Sparkles, Users, Settings2 } from 'lucide-react';
import ChatInput from '../components/ChatInput';
import MessageBubble from '../components/MessageBubble';
import ThinkingIndicator from '../components/ThinkingIndicator';
import SuggestionsPanel from '../components/SuggestionsPanel';
import ThemeToggle from '../components/ThemeToggle';
import ProviderDropdown from '../components/ProviderDropdown';
import { advisors, getAdvisorColors } from '../data/advisors';
import { useTheme } from '../contexts/ThemeContext';
import '../styles/ChatPage.css';

const ChatPage = ({ onNavigateToHome }) => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [thinkingAdvisors, setThinkingAdvisors] = useState([]);
  const [collectedInfo, setCollectedInfo] = useState({});
  const [replyingTo, setReplyingTo] = useState(null);
  const [currentProvider, setCurrentProvider] = useState('gemini');
  const [isProviderSwitching, setIsProviderSwitching] = useState(false);
  const messagesEndRef = useRef(null);
  const { isDark } = useTheme();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingAdvisors]);

  useEffect(() => {
    fetchCurrentProvider();
  }, []);

  const fetchCurrentProvider = async () => {
    try {
      const response = await fetch('http://localhost:8000/current-provider');
      if (response.ok) {
        const data = await response.json();
        setCurrentProvider(data.current_provider);
        console.log('Loaded provider:', data.current_provider, 'Available:', data.available_providers);
      }
    } catch (error) {
      console.error('Error fetching current provider:', error);
    }
  };

  const handleProviderSwitch = async (newProvider) => {
    if (newProvider === currentProvider || isProviderSwitching) return;

    setIsProviderSwitching(true);
    try {
      const response = await fetch('http://localhost:8000/switch-provider', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          provider: newProvider
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCurrentProvider(newProvider);
        
        const switchMessage = {
          id: generateMessageId(),
          type: 'system',
          content: `✨ Switched to ${newProvider.charAt(0).toUpperCase() + newProvider.slice(1)} provider. Your advisors are now ready with the new AI model.`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, switchMessage]);
      } else {
        const error = await response.json();
        console.error('Failed to switch provider:', error);
        const errorMessage = {
          id: generateMessageId(),
          type: 'error',
          content: `Failed to switch to ${newProvider}: ${error.detail || 'Unknown error'}`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Error switching provider:', error);
      const errorMessage = {
        id: generateMessageId(),
        type: 'error',
        content: `Error switching to ${newProvider}. Please try again.`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsProviderSwitching(false);
    }
  };

  const generateMessageId = () => {
    return Date.now().toString() + Math.random().toString(36).substr(2, 9);
  };

  const handleSendMessage = async (inputMessage) => {
    if (replyingTo) {
      await handleReplyToAdvisor(inputMessage, replyingTo);
      return;
    }

    const userMessage = {
      id: generateMessageId(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    
    setIsLoading(true);
    setThinkingAdvisors(['system']);

    try {
      const response = await fetch('http://localhost:8000/chat-sequential', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_input: inputMessage
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setCollectedInfo(data.collected_info || {});
      setThinkingAdvisors([]);

      if (data.type === 'orchestrator_question') {
        const orchestratorMessage = {
          id: generateMessageId(),
          type: 'orchestrator',
          content: data.responses[0].response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, orchestratorMessage]);
      } else if (data.type === 'sequential_responses') {
        const advisorIds = ['methodist', 'theorist', 'pragmatist'];
        
        for (let i = 0; i < advisorIds.length; i++) {
          const advisorId = advisorIds[i];
          const response = data.responses.find(r => r.persona_id === advisorId);
          
          if (response) {
            setThinkingAdvisors([advisorId]);
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const advisorMessage = {
              id: generateMessageId(),
              type: 'advisor',
              advisorId: advisorId,
              content: response.response,
              timestamp: new Date()
            };
            
            setMessages(prev => [...prev, advisorMessage]);
            setThinkingAdvisors([]);
            
            if (i < advisorIds.length - 1) {
              await new Promise(resolve => setTimeout(resolve, 500));
            }
          }
        }
      } else if (data.type === 'error') {
        const errorMessage = {
          id: generateMessageId(),
          type: 'error',
          content: data.responses[0].response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: generateMessageId(),
        type: 'error',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setThinkingAdvisors([]);
    }
  };

  const handleReplyToAdvisor = async (inputMessage, replyInfo) => {
    const userReplyMessage = {
      id: generateMessageId(),
      type: 'user',
      content: inputMessage,
      replyTo: {
        advisorId: replyInfo.advisorId,
        advisorName: replyInfo.advisorName,
        messageId: replyInfo.messageId
      },
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userReplyMessage]);

    setThinkingAdvisors([replyInfo.advisorId]);
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/reply-to-advisor', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_input: inputMessage,
          advisor_id: replyInfo.advisorId,
          original_message_id: replyInfo.messageId
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      const advisorReplyMessage = {
        id: generateMessageId(),
        type: 'advisor',
        advisorId: replyInfo.advisorId,
        content: data.response,
        isReply: true,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, advisorReplyMessage]);

    } catch (error) {
      console.error('Error sending reply:', error);
      const errorMessage = {
        id: generateMessageId(),
        type: 'error',
        content: 'Sorry, I encountered an error with your reply. Please try again.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setThinkingAdvisors([]);
      setReplyingTo(null);
    }
  };

  const handleMessageClick = (message) => {
    if (message.type === 'advisor') {
      const advisor = advisors[message.advisorId];
      setReplyingTo({
        advisorId: message.advisorId,
        messageId: message.id,
        advisorName: advisor.name
      });
    }
  };

  const cancelReply = () => {
    setReplyingTo(null);
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="modern-chat-page">
      {/* Floating Header */}
      <div className="floating-header">
        <div className="header-left">
          <button onClick={onNavigateToHome} className="modern-home-btn">
            <Home size={20} />
          </button>
          <div className="header-brand">
            <div className="brand-icon">
              <Users size={24} />
            </div>
            <div className="brand-text">
              <h1>PhD Advisory</h1>
              <p>AI-Powered Academic Guidance</p>
            </div>
          </div>
        </div>
        
        <div className="header-right">
          <div className="advisor-pills">
            {Object.entries(advisors).map(([id, advisor]) => {
              const Icon = advisor.icon;
              const colors = getAdvisorColors(id, isDark);
              const isThinking = thinkingAdvisors.includes(id);
              
              return (
                <div 
                  key={id} 
                  className={`advisor-pill ${isThinking ? 'thinking' : ''}`}
                  style={{ 
                    backgroundColor: colors.bgColor,
                    borderColor: colors.color + '20'
                  }}
                >
                  <Icon size={16} style={{ color: colors.color }} />
                  <span style={{ color: colors.color }}>{advisor.name.split(' ')[1]}</span>
                  {isThinking && <div className="thinking-pulse" style={{ backgroundColor: colors.color }}></div>}
                </div>
              );
            })}
          </div>
          
          <div className="header-controls">
            <ProviderDropdown 
              currentProvider={currentProvider}
              onProviderChange={handleProviderSwitch}
              isLoading={isProviderSwitching}
            />
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="main-content">
        {!hasMessages ? (
          /* Welcome State - Just Suggestions */
          <div className="welcome-state">
            <div className="suggestions-container">
              <SuggestionsPanel onSuggestionClick={handleSendMessage} />
            </div>
          </div>
        ) : (
          /* Chat State */
          <div className="chat-state">
            <div className="messages-area">
              <div className="messages-scroll">
                {messages.map((message, index) => {
                  if (message.type === 'orchestrator') {
                    return (
                      <div key={message.id || index} className="orchestrator-message">
                        <div className="orchestrator-avatar">
                          <MessageCircle size={20} />
                        </div>
                        <div className="orchestrator-content">
                          <div className="orchestrator-header">
                            <span className="orchestrator-name">PhD Assistant</span>
                            <span className="message-timestamp">
                              {message.timestamp.toLocaleTimeString([], {
                                hour: '2-digit', 
                                minute: '2-digit'
                              })}
                            </span>
                          </div>
                          <div className="orchestrator-text">{message.content}</div>
                        </div>
                      </div>
                    );
                  }
                  
                  if (message.type === 'system') {
                    return (
                      <div key={message.id || index} className="system-notification">
                        <div className="system-content">
                          {message.content}
                        </div>
                      </div>
                    );
                  }
                  
                  return (
                    <MessageBubble 
                      key={message.id || index} 
                      message={message} 
                      onClick={() => handleMessageClick(message)}
                      showReplyButton={message.type === 'advisor'}
                    />
                  );
                })}
                
                {/* Thinking Indicators */}
                {thinkingAdvisors.includes('system') && (
                  <div className="orchestrator-thinking">
                    <div className="orchestrator-avatar">
                      <MessageCircle size={20} />
                    </div>
                    <div className="thinking-content">
                      <span className="thinking-label">PhD Assistant is thinking...</span>
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

      {/* Floating Input Area */}
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
        
        <div className="input-wrapper">
          <ChatInput 
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            placeholder={
              replyingTo 
                ? `Reply to ${replyingTo.advisorName}...`
                : "Ask your advisors anything about your PhD journey..."
            }
          />
        </div>
      </div>
    </div>
  );
};

export default ChatPage;