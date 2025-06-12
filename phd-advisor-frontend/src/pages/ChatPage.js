import React, { useState, useEffect, useRef } from 'react';
import { Home, MessageCircle } from 'lucide-react';
import ChatInput from '../components/ChatInput';
import MessageBubble from '../components/MessageBubble';
import ThinkingIndicator from '../components/ThinkingIndicator';
import { advisors } from '../data/advisors';

const ChatPage = ({ onNavigateToHome }) => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [thinkingAdvisors, setThinkingAdvisors] = useState([]);
  const [collectedInfo, setCollectedInfo] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingAdvisors]);

  const handleSendMessage = async (inputMessage) => {
    // Add user message immediately
    const userMessage = {
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    
    setIsLoading(true);
    setThinkingAdvisors(['system']); // Show thinking indicator for orchestrator/system

    try {
      const response = await fetch('http://localhost:8000/chat', {
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
          type: 'orchestrator',
          content: data.responses[0].response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, orchestratorMessage]);
        
      } else if (data.type === 'advisor_responses') {
        // Show thinking indicators for advisors before their responses
        setThinkingAdvisors(['methodist', 'theorist', 'pragmatist']);
        
        // Add a small delay then show advisor responses
        setTimeout(() => {
          setThinkingAdvisors([]);
          
          // Add advisor responses with staggered timing
          data.responses.forEach((advisorResponse, index) => {
            setTimeout(() => {
              let advisorId = 'methodist';
              
              if (advisorResponse.persona.toLowerCase().includes('methodist')) {
                advisorId = 'methodist';
              } else if (advisorResponse.persona.toLowerCase().includes('theorist')) {
                advisorId = 'theorist';
              } else if (advisorResponse.persona.toLowerCase().includes('pragmatist')) {
                advisorId = 'pragmatist';
              }
              
              const message = {
                type: 'advisor',
                advisorId,
                content: advisorResponse.response,
                timestamp: new Date()
              };
              
              setMessages(prev => [...prev, message]);
            }, index * 800);
          });
        }, 1000); // Small delay to show advisor thinking
        
      } else if (data.type === 'error') {
        // Handle error response
        const errorMessage = {
          type: 'error',
          content: data.responses[0].response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
      }
      
    } catch (error) {
      console.error('Error sending message:', error);
      setThinkingAdvisors([]);
      setMessages(prev => [...prev, {
        type: 'error',
        content: 'Sorry, there was an error processing your message. Please try again.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
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
                  : 'Consulting with your three advisors'
                }
              </p>
            </div>
          </div>
          <div className="advisor-indicators">
            {Object.entries(advisors).map(([id, advisor]) => {
              const Icon = advisor.icon;
              return (
                <div 
                  key={id} 
                  className="advisor-indicator" 
                  style={{ backgroundColor: advisor.bgColor }}
                >
                  <Icon style={{ color: advisor.color }} />
                </div>
              );
            })}
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <div className="chat-container">
        <div className="chat-box">
          {/* Messages */}
          <div className="messages-container">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <MessageCircle />
                </div>
                <h3 className="empty-state-title">Start Your Consultation</h3>
                <p className="empty-state-text">
                  Ask a question and get insights from all three advisors
                </p>
              </div>
            )}
            
            {messages.map((message, index) => {
              if (message.type === 'orchestrator') {
                return (
                  <div key={index} className="advisor-message-container">
                    <div className="advisor-avatar" style={{ backgroundColor: '#F3F4F6' }}>
                      <MessageCircle style={{ color: '#6B7280' }} />
                    </div>
                    <div className="advisor-message-bubble">
                      <div className="advisor-message-header">
                        <h4 className="advisor-message-name" style={{ color: '#6B7280' }}>
                          PhD Assistant
                        </h4>
                        <span className="message-time">
                          {message.timestamp.toLocaleTimeString([], {
                            hour: '2-digit', 
                            minute: '2-digit'
                          })}
                        </span>
                      </div>
                      <p className="advisor-message-text">{message.content}</p>
                    </div>
                  </div>
                );
              }
              return <MessageBubble key={index} message={message} />;
            })}
            
            {/* Thinking Indicators */}
            {thinkingAdvisors.includes('system') && (
              <div className="thinking-container">
                <div className="advisor-avatar" style={{ backgroundColor: '#F3F4F6' }}>
                  <MessageCircle style={{ color: '#6B7280' }} />
                </div>
                <div className="thinking-bubble">
                  <div className="thinking-header">
                    <h4 className="advisor-name" style={{ color: '#6B7280' }}>
                      Processing...
                    </h4>
                  </div>
                  <div className="thinking-dots">
                    <div className="thinking-dot" style={{ backgroundColor: '#6B7280', animationDelay: '0ms' }}></div>
                    <div className="thinking-dot" style={{ backgroundColor: '#6B7280', animationDelay: '150ms' }}></div>
                    <div className="thinking-dot" style={{ backgroundColor: '#6B7280', animationDelay: '300ms' }}></div>
                  </div>
                  <p className="thinking-text">analyzing your question...</p>
                </div>
              </div>
            )}
            
            {thinkingAdvisors.filter(id => id !== 'system').map(advisorId => (
              <ThinkingIndicator key={advisorId} advisorId={advisorId} />
            ))}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
};

export default ChatPage;