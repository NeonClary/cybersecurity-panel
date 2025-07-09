// src/pages/ChatPage.js
import React, { useState, useEffect, useRef } from 'react';
import { Home, MessageCircle, Reply, X, Sparkles, Users, Settings2, FileText } from 'lucide-react';
import EnhancedChatInput from '../components/EnhancedChatInput';
import MessageBubble from '../components/MessageBubble';
import ThinkingIndicator from '../components/ThinkingIndicator';
import SuggestionsPanel from '../components/SuggestionsPanel';
import ThemeToggle from '../components/ThemeToggle';
import ProviderDropdown from '../components/ProviderDropdown';
import { advisors, getAdvisorColors } from '../data/advisors';
import { useTheme } from '../contexts/ThemeContext';
import '../styles/ChatPage.css';
import '../styles/EnhancedChatInput.css';

const ChatPage = ({ onNavigateToHome }) => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [thinkingAdvisors, setThinkingAdvisors] = useState([]);
  const [collectedInfo, setCollectedInfo] = useState({});
  const [replyingTo, setReplyingTo] = useState(null);
  const [currentProvider, setCurrentProvider] = useState('gemini');
  const [isProviderSwitching, setIsProviderSwitching] = useState(false);
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
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

  const handleFileUploaded = (file, response) => {
    // Add the uploaded document to our list
    const docInfo = {
      id: generateMessageId(),
      name: file.name,
      size: file.size,
      type: file.type,
      uploadTime: new Date()
    };
    setUploadedDocuments(prev => [...prev, docInfo]);

    // Add a system message about the upload
    const uploadMessage = {
      id: generateMessageId(),
      type: 'document_upload',
      content: `Successfully uploaded "${file.name}". Your advisors can now reference this document in their responses.`,
      timestamp: new Date(),
      documentInfo: docInfo
    };
    
    // Force update messages state
    setMessages(prev => {
      const newMessages = [...prev, uploadMessage];
      console.log('Added upload message:', uploadMessage); // Debug log
      return newMessages;
    });

    // Scroll to bottom to show the new message
    setTimeout(() => {
      scrollToBottom();
    }, 100);
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
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    console.log('Backend response:', data); // Debug log

    if (data.type === 'persona_responses' && data.responses) {
      // Map each advisor response with RAG metadata
      const advisorMessages = data.responses.map((advisor, index) => ({
        id: generateMessageId(),
        type: 'advisor',
        advisorId: advisor.persona_id,
        advisorName: advisor.persona_name,
        content: advisor.response,
        timestamp: new Date(),
        // NEW: Map RAG metadata to the structure MessageBubble expects
        ragMetadata: {
          usedDocuments: advisor.used_documents || false,
          chunksUsed: advisor.document_chunks_used || 0,
          documentChunks: advisor.retrieved_chunks || []
        }
      }));

      setMessages(prev => [...prev, ...advisorMessages]);

      // Optional: Add RAG summary message if documents were used
      const ragInfo = data.rag_info || {};
      if (ragInfo.personas_using_documents > 0) {
        const ragSummaryMessage = {
          id: generateMessageId(),
          type: 'system',
          content: `📚 ${ragInfo.personas_using_documents}/${data.responses.length} advisors referenced your uploaded documents (${ragInfo.total_document_chunks_used} chunks used)`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, ragSummaryMessage]);
      }

    } else if (data.type === 'error') {
      const errorMessage = {
        id: generateMessageId(),
        type: 'error',
        content: data.message || 'An error occurred. Please try again.',
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
  }

    setIsLoading(false);
    setThinkingAdvisors([]);
  };

  const handleReplyToAdvisor = async (inputMessage, replyContext) => {
  const replyMessage = {
    id: generateMessageId(),
    type: 'user',
    content: inputMessage,
    replyTo: {
      advisorId: replyContext.advisorId,
      advisorName: replyContext.advisorName,
      messageId: replyContext.messageId
    },
    timestamp: new Date()
  };
  setMessages(prev => [...prev, replyMessage]);
  
  setIsLoading(true);
  setThinkingAdvisors([replyContext.advisorId]);

  try {
    const response = await fetch('http://localhost:8000/reply-to-advisor', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_input: inputMessage,
        advisor_id: replyContext.advisorId,
        original_message_id: replyContext.messageId
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();

    if (data.type === 'advisor_reply') {
      const replyResponseMessage = {
        id: generateMessageId(),
        type: 'advisor',
        advisorId: data.persona_id,
        advisorName: data.persona,
        content: data.response,
        isReply: true,
        timestamp: new Date(),
        // NEW: Map RAG metadata for reply responses too
        ragMetadata: {
          usedDocuments: data.used_documents || false,
          chunksUsed: data.document_chunks_used || 0,
          documentChunks: data.retrieved_chunks || []
        }
      };
      setMessages(prev => [...prev, replyResponseMessage]);
    }

  } catch (error) {
    console.error('Error replying to advisor:', error);
    const errorMessage = {
      id: generateMessageId(),
      type: 'error',
      content: 'Sorry, I encountered an error with your reply. Please try again.',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, errorMessage]);
  }

    setIsLoading(false);
    setThinkingAdvisors([]);
    setReplyingTo(null);
  };

  const handleCopyMessage = (messageId, content) => {
  // Optional: Show a toast notification or add to message history
  console.log(`Copied message ${messageId}: ${content.substring(0, 50)}...`);
  };

const handleExpandMessage = async (messageId, advisorId) => {
  const advisor = advisors[advisorId];
  if (!advisor) return;

  const originalMessage = messages.find(msg => msg.id === messageId);
  if (!originalMessage) return;

  const expandPrompt = `Please expand on your previous response: "${originalMessage.content.substring(0, 100)}..." Provide more detail and depth.`;
  
  const expandMessage = {
    id: generateMessageId(),
    type: 'user',
    content: expandPrompt,
    timestamp: new Date(),
    isExpandRequest: true,
    expandsMessageId: messageId
  };
  setMessages(prev => [...prev, expandMessage]);
  
  setIsLoading(true);
  setThinkingAdvisors([advisorId]);

  try {
    const response = await fetch(`http://localhost:8000/chat/${advisorId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_input: expandPrompt,
        response_length: 'long'
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();

    if (data.type === 'single_persona_response' && data.persona) {
      const expandedMessage = {
        id: generateMessageId(),
        type: 'advisor',
        advisorId: advisorId,
        advisorName: advisor.name,
        content: data.persona.response,
        isExpansion: true,
        expandsMessageId: messageId,
        timestamp: new Date(),
        // NEW: Map RAG metadata for expanded responses
        ragMetadata: {
          usedDocuments: data.persona.used_documents || false,
          chunksUsed: data.persona.document_chunks_used || 0,
          documentChunks: data.persona.retrieved_chunks || []
        }
      };
      setMessages(prev => [...prev, expandedMessage]);
    }

  } catch (error) {
    console.error('Error expanding message:', error);
    const errorMessage = {
      id: generateMessageId(),
      type: 'error',
      content: 'Sorry, I encountered an error expanding the response. Please try again.',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, errorMessage]);
  }

    setIsLoading(false);
    setThinkingAdvisors([]);
  };

  const handleReplyToMessage = (message) => {
    const advisor = advisors[message.advisorId];
    setReplyingTo({
      advisorId: message.advisorId,
      messageId: message.id,
      advisorName: advisor.name
    });
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
            {/* Document Count Indicator */}
            {uploadedDocuments.length > 0 && (
              <div className="document-indicator" title={`${uploadedDocuments.length} document(s) uploaded`}>
                <FileText size={16} />
                <span className="doc-count">{uploadedDocuments.length}</span>
              </div>
            )}
            
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
                            <span className="orchestrator-name">Orchestrator</span>
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

                  if (message.type === 'document_upload') {
                    return (
                      <div key={message.id || index} className="document-upload-notification">
                        <div className="upload-notification-content">
                          <FileText size={16} className="upload-icon" />
                          <span>{message.content}</span>
                        </div>
                      </div>
                    );
                  }
                  
                  return (
                    <MessageBubble 
                      key={message.id || index} 
                      message={message} 
                      onReply={handleReplyToMessage}
                      onCopy={handleCopyMessage}
                      onExpand={handleExpandMessage}
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
                      <span className="thinking-label">Orchestrator is thinking...</span>
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
        
        <EnhancedChatInput 
          onSendMessage={handleSendMessage}
          onFileUploaded={handleFileUploaded}
          uploadedDocuments={uploadedDocuments}
          isLoading={isLoading}
          placeholder={
            replyingTo 
              ? `Reply to ${replyingTo.advisorName}...`
              : "Ask your advisors anything about your PhD journey..."
          }
        />
      </div>
    </div>
  );
};

export default ChatPage;