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
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingAdvisors]);

  const handleSendMessage = async (inputMessage) => {
    const userMessage = {
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    
    // Show thinking indicators for all advisors
    setThinkingAdvisors(['methodist', 'theorist', 'pragmatist']);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_input: inputMessage,
          active_personas: ['methodist', 'theorist', 'pragmatist']
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();
      
      // Clear thinking indicators
      setThinkingAdvisors([]);
      
      // Add advisor responses with staggered timing for better UX
      data.forEach((advisorResponse, index) => {
        setTimeout(() => {
          // Map the API persona names to our advisor IDs
          let advisorId = 'methodist'; // default fallback
          
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
        }, index * 800); // Stagger responses by 800ms
      });
      
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
              <p className="chat-subtitle">Consulting with your three advisors</p>
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
            
            {messages.map((message, index) => (
              <MessageBubble key={index} message={message} />
            ))}
            
            {/* Thinking Indicators */}
            {thinkingAdvisors.map(advisorId => (
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