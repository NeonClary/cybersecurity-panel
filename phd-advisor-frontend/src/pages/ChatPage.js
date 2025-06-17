import React, { useState, useEffect, useRef } from 'react';
import { Home, MessageCircle, Reply, X } from 'lucide-react';
import ChatInput from '../components/ChatInput';
import MessageBubble from '../components/MessageBubble';
import ThinkingIndicator from '../components/ThinkingIndicator';
import SuggestionsPanel from '../components/SuggestionsPanel';
import ThemeToggle from '../components/ThemeToggle';
import { advisors, getAdvisorColors } from '../data/advisors';
import { useTheme } from '../contexts/ThemeContext';

const ChatPage = ({ onNavigateToHome }) => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [thinkingAdvisors, setThinkingAdvisors] = useState([]);
  const [collectedInfo, setCollectedInfo] = useState({});
  const [replyingTo, setReplyingTo] = useState(null); // { advisorId, messageId, advisorName }
  const messagesEndRef = useRef(null);
  const { isDark } = useTheme();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingAdvisors]);

  const generateMessageId = () => {
    return Date.now().toString() + Math.random().toString(36).substr(2, 9);
  };

  const handleSendMessage = async (inputMessage) => {
    // Check if this is a reply to a specific advisor
    if (replyingTo) {
      await handleReplyToAdvisor(inputMessage, replyingTo);
      return;
    }

    // Regular message flow - add user message immediately
    const userMessage = {
      id: generateMessageId(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    
    setIsLoading(true);
    setThinkingAdvisors(['system']); // Show thinking indicator for orchestrator/system

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
        throw new Error('Failed to send message');
      }

      const data = await response.json();
      setThinkingAdvisors([]);
      
      // Update collected info if provided
      if (data.collected_info) {
        setCollectedInfo(data.collected_info);
      }

      if (data.type === 'orchestrator_question') {
        // Orchestrator is asking for clarification
        const orchestratorMessage = {
          id: generateMessageId(),
          type: 'orchestrator',
          content: data.responses[0].response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, orchestratorMessage]);
        
      } else if (data.type === 'sequential_responses') {
        // Show advisor responses sequentially with realistic timing
        await showSequentialResponses(data.responses);
      }
      
    } catch (error) {
      console.error('Error sending message:', error);
      setThinkingAdvisors([]);
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'error',
        content: 'Sorry, there was an error processing your message. Please try again.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const showSequentialResponses = async (responses) => {
    const advisorOrder = ['methodist', 'theorist', 'pragmatist'];
    
    for (let i = 0; i < advisorOrder.length; i++) {
      const advisorId = advisorOrder[i];
      
      // Show thinking indicator for this specific advisor
      setThinkingAdvisors([advisorId]);
      
      // Wait a bit to simulate thinking time (since responses are pre-generated)
      await new Promise(resolve => setTimeout(resolve, 800));
      
      // Find the response for this advisor
      const advisorResponse = responses.find(r => r.persona_id === advisorId);
      
      if (advisorResponse) {
        // Remove thinking indicator and add message
        setThinkingAdvisors([]);
        
        const message = {
          id: generateMessageId(),
          type: 'advisor',
          advisorId: advisorResponse.persona_id,
          content: advisorResponse.response,
          timestamp: new Date()
        };
        
        setMessages(prev => [...prev, message]);
        
        // Small delay before next advisor starts thinking
        if (i < advisorOrder.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 300));
        }
      }
    }
    
    // Clear any remaining thinking indicators
    setThinkingAdvisors([]);
  };

  const handleReplyToAdvisor = async (inputMessage, replyInfo) => {
    // Add user reply message
    const userReplyMessage = {
      id: generateMessageId(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
      replyTo: replyInfo
    };
    setMessages(prev => [...prev, userReplyMessage]);
    
    // Show thinking for the specific advisor
    setThinkingAdvisors([replyInfo.advisorId]);
    setReplyingTo(null); // Clear reply state
    
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
        throw new Error('Failed to send reply');
      }

      const data = await response.json();
      setThinkingAdvisors([]);

      // Add advisor reply
      const advisorReplyMessage = {
        id: generateMessageId(),
        type: 'advisor',
        advisorId: data.persona_id,
        content: data.response,
        timestamp: new Date(),
        isReply: true
      };
      
      setMessages(prev => [...prev, advisorReplyMessage]);
      
    } catch (error) {
      console.error('Error sending reply:', error);
      setThinkingAdvisors([]);
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'error',
        content: 'Sorry, there was an error sending your reply. Please try again.',
        timestamp: new Date()
      }]);
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

  return (
    <div className="chat-page">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-content">
          <div className="chat-header-left">
            <button
              onClick={onNavigateToHome}
              className="home-button"
            >
              <Home className="home-icon" />
            </button>
            <div>
              <h1 className="chat-title">Advisory Panel Chat</h1>
              <p className="chat-subtitle">
                {Object.keys(collectedInfo).length > 0 
                  ? `Context: ${Object.entries(collectedInfo).map(([k,v]) => `${k}: ${v}`).join(', ')}`
                  : replyingTo 
                    ? `Replying to ${replyingTo.advisorName}`
                    : 'Consulting with your three advisors'
                }
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div className="advisor-indicators">
              {Object.entries(advisors).map(([id, advisor]) => {
                const Icon = advisor.icon;
                const colors = getAdvisorColors(id, isDark);
                return (
                  <div 
                    key={id} 
                    className="advisor-indicator" 
                    style={{ backgroundColor: colors.bgColor }}
                  >
                    <Icon style={{ color: colors.color }} />
                  </div>
                );
              })}
            </div>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <div className="chat-container">
        <div className="chat-box">
          {/* Messages */}
          <div className="messages-container">
            {messages.length === 0 && !replyingTo && (
              <SuggestionsPanel onSuggestionClick={handleSendMessage} />
            )}
            
            {messages.map((message, index) => {
              if (message.type === 'orchestrator') {
                return (
                  <div key={message.id || index} className="advisor-message-container">
                    <div className="advisor-avatar orchestrator-avatar">
                      <MessageCircle className="orchestrator-icon" />
                    </div>
                    <div className="advisor-message-bubble orchestrator-bubble">
                      <div className="advisor-message-header">
                        <h4 className="advisor-message-name orchestrator-name">
                          PhD Assistant
                        </h4>
                        <span className="message-time orchestrator-time">
                          {message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit', 
                            minute: '2-digit'
                          })}
                        </span>
                      </div>
                      <p className="advisor-message-text orchestrator-text">{message.content}</p>
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
              <div className="thinking-container">
                <div className="advisor-avatar orchestrator-avatar">
                  <MessageCircle className="orchestrator-icon" />
                </div>
                <div className="thinking-bubble orchestrator-bubble">
                  <div className="thinking-header">
                    <h4 className="advisor-name orchestrator-name">
                      Processing...
                    </h4>
                  </div>
                  <div className="thinking-dots">
                    <div className="thinking-dot orchestrator-dot" style={{ animationDelay: '0ms' }}></div>
                    <div className="thinking-dot orchestrator-dot" style={{ animationDelay: '150ms' }}></div>
                    <div className="thinking-dot orchestrator-dot" style={{ animationDelay: '300ms' }}></div>
                  </div>
                  <p className="thinking-text orchestrator-thinking-text">analyzing your question...</p>
                </div>
              </div>
            )}
            
            {thinkingAdvisors.filter(id => id !== 'system').map(advisorId => (
              <ThinkingIndicator key={advisorId} advisorId={advisorId} />
            ))}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Reply Banner */}
          {replyingTo && (
            <div className="reply-banner">
              <div className="reply-info">
                <Reply className="reply-icon" />
                <span>Replying to {replyingTo.advisorName}</span>
              </div>
              <button onClick={cancelReply} className="cancel-reply-btn">
                <X size={16} />
              </button>
            </div>
          )}

          {/* Input Area */}
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