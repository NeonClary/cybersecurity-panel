import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Reply, Copy, Check, Maximize2, Info, FileText, Hash, Target } from 'lucide-react';
import { advisors, getAdvisorColors } from '../data/advisors';
import { useTheme } from '../contexts/ThemeContext';

const MessageBubble = ({ 
  message, 
  onReply, 
  onCopy, 
  onExpand,
  showReplyButton = false 
}) => {
  const { isDark } = useTheme();
  const [showTooltip, setShowTooltip] = useState(null);
  const [copiedStates, setCopiedStates] = useState({});
  const [showInfoOverlay, setShowInfoOverlay] = useState(false);
  const overlayRef = useRef(null);

  const handleCopy = async (messageId, content) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedStates(prev => ({ ...prev, [messageId]: true }));
      if (onCopy) onCopy(messageId, content);
      
      setTimeout(() => {
        setCopiedStates(prev => ({ ...prev, [messageId]: false }));
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const handleExpand = (messageId, persona_id) => {
    if (onExpand) onExpand(messageId, persona_id);
  };

  const handleInfoToggle = () => {
    setShowInfoOverlay(!showInfoOverlay);
  };

  const showTooltipWithDelay = (tooltipType) => {
    setTimeout(() => setShowTooltip(tooltipType), 500);
  };

  const hideTooltip = () => {
    setShowTooltip(null);
  };

  // Close overlay when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (overlayRef.current && !overlayRef.current.contains(event.target)) {
        setShowInfoOverlay(false);
      }
    };

    if (showInfoOverlay) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showInfoOverlay]);

  // Preprocess markdown content to fix common formatting issues
  const preprocessMarkdown = (content) => {
    if (!content) return '';
    
    // Ensure proper line breaks before numbered lists
    let processed = content.replace(/(\d+\.\s\*\*[^*]+\*\*)/g, '\n\n$1');
    
    // Ensure proper line breaks after list items
    processed = processed.replace(/(\d+\.\s[^\n]+)(?=\s+\d+\.)/g, '$1\n');
    
    // Fix spacing around bold headers
    processed = processed.replace(/(\*\*[^*]+\*\*)/g, '\n\n$1\n\n');
    
    // Clean up multiple consecutive line breaks
    processed = processed.replace(/\n{3,}/g, '\n\n');
    
    // Ensure proper paragraph breaks
    processed = processed.replace(/([.!?])\s+([A-Z])/g, '$1\n\n$2');
    
    return processed.trim();
  };

  // ENHANCED MARKDOWN COMPONENTS WITH BETTER STYLING
  const markdownComponents = {
    // Bold text styling - for headers and key terms
    strong: ({ children }) => (
      <strong style={{ 
        fontWeight: '700',
        color: isDark ? '#ffffff' : '#1f2937',
        display: 'block',
        marginBottom: '0.5rem',
        marginTop: '1rem'
      }}>
        {children}
      </strong>
    ),
    
    // Italic text styling
    em: ({ children }) => (
      <em style={{ 
        fontStyle: 'italic',
        color: isDark ? '#93c5fd' : '#3b82f6',
        fontWeight: '500'
      }}>
        {children}
      </em>
    ),
    
    // Paragraph styling with proper spacing
    p: ({ children }) => (
      <p style={{ 
        marginBottom: '1rem',
        lineHeight: '1.7',
        color: isDark ? '#e5e7eb' : '#374151',
        fontSize: '14px'
      }}>
        {children}
      </p>
    ),
    
    // Unordered list styling
    ul: ({ children }) => (
      <ul style={{ 
        listStyleType: 'disc',
        paddingLeft: '1.5rem',
        marginBottom: '1rem',
        marginTop: '0.5rem',
        color: isDark ? '#e5e7eb' : '#374151'
      }}>
        {children}
      </ul>
    ),
    
    // Ordered list styling with better spacing
    ol: ({ children }) => (
      <ol style={{ 
        listStyleType: 'decimal',
        paddingLeft: '1.5rem',
        marginBottom: '1rem',
        marginTop: '0.5rem',
        color: isDark ? '#e5e7eb' : '#374151',
        counterReset: 'list-counter'
      }}>
        {children}
      </ol>
    ),
    
    // List item styling with proper spacing
    li: ({ children }) => (
      <li style={{ 
        marginBottom: '0.75rem',
        lineHeight: '1.6',
        paddingLeft: '0.25rem'
      }}>
        {children}
      </li>
    ),

    // Headers (in case they use them)
    h1: ({ children }) => (
      <h1 style={{
        fontSize: '1.5rem',
        fontWeight: '700',
        color: isDark ? '#ffffff' : '#1f2937',
        marginBottom: '1rem',
        marginTop: '1.5rem',
        borderBottom: `2px solid ${isDark ? '#374151' : '#e5e7eb'}`,
        paddingBottom: '0.5rem'
      }}>
        {children}
      </h1>
    ),

    h2: ({ children }) => (
      <h2 style={{
        fontSize: '1.25rem',
        fontWeight: '600',
        color: isDark ? '#ffffff' : '#1f2937',
        marginBottom: '0.75rem',
        marginTop: '1.25rem'
      }}>
        {children}
      </h2>
    ),

    h3: ({ children }) => (
      <h3 style={{
        fontSize: '1.125rem',
        fontWeight: '600',
        color: isDark ? '#ffffff' : '#1f2937',
        marginBottom: '0.5rem',
        marginTop: '1rem'
      }}>
        {children}
      </h3>
    ),

    // Code styling
    code: ({ children }) => (
      <code style={{ 
        backgroundColor: isDark ? '#374151' : '#f3f4f6',
        padding: '0.125rem 0.375rem',
        borderRadius: '0.25rem',
        fontSize: '0.875rem',
        fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
        color: isDark ? '#fbbf24' : '#d97706'
      }}>
        {children}
      </code>
    ),

    // Block quote styling
    blockquote: ({ children }) => (
      <blockquote style={{
        borderLeft: '4px solid ' + (isDark ? '#374151' : '#e5e7eb'),
        paddingLeft: '1rem',
        marginLeft: '0',
        marginBottom: '1rem',
        fontStyle: 'italic',
        color: isDark ? '#9ca3af' : '#6b7280'
      }}>
        {children}
      </blockquote>
    )
  };

  // RAG Metadata Component
  const RagInfoOverlay = ({ ragMetadata, colors }) => {
    const hasDocuments = ragMetadata?.usedDocuments || false;
    const chunksUsed = ragMetadata?.chunksUsed || 0;
    const documentChunks = ragMetadata?.documentChunks || [];

    return (
      <div 
        ref={overlayRef}
        className="rag-info-overlay"
        style={{ 
          borderColor: colors.color + '40',
          backgroundColor: isDark ? '#1f2937' : '#ffffff'
        }}
      >
        <div className="rag-overlay-header" style={{ color: colors.color }}>
          <Info size={14} />
          <span>RAG Information</span>
        </div>
        
        <div className="rag-overlay-content">
          <div className="rag-stat-row">
            <div className="rag-stat-label">Used Documents:</div>
            <div className={`rag-stat-value ${hasDocuments ? 'positive' : 'negative'}`}>
              {hasDocuments ? 'Yes' : 'No'}
            </div>
          </div>

          <div className="rag-stat-row">
            <div className="rag-stat-label">Document Chunks:</div>
            <div className="rag-stat-value">{chunksUsed}</div>
          </div>

          {hasDocuments && documentChunks.length > 0 && (
            <div className="rag-documents-section">
              <div className="rag-section-title">
                <FileText size={12} />
                Referenced Sources
              </div>
              
              {documentChunks.map((chunk, index) => (
                <div key={index} className="rag-document-item">
                  <div className="rag-document-header">
                    <span className="rag-filename">
                      {chunk.metadata?.filename || 'Unknown file'}
                    </span>
                    <span className="rag-relevance">
                      <Target size={10} />
                      {Math.round((chunk.relevance_score || 0) * 100)}%
                    </span>
                  </div>
                  
                  {chunk.text && (
                    <div className="rag-chunk-preview">
                      {chunk.text.substring(0, 120)}
                      {chunk.text.length > 120 && '...'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {!hasDocuments && (
            <div className="rag-no-documents">
              <Hash size={12} />
              <span>This response was generated without referencing uploaded documents.</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  if (message.type === 'user') {
    return (
      <div className="user-message-container">
        <div className="user-message">
          {message.replyTo && (
            <div className="reply-indicator">
              <Reply size={14} />
              <span>to {message.replyTo.advisorName}</span>
            </div>
          )}
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.type === 'advisor') {
    const advisor = advisors[message.persona_id];
    const Icon = advisor.icon;
    const colors = getAdvisorColors(message.persona_id, isDark);
    const isCopied = copiedStates[message.id];

    return (
      <div className="advisor-message-container">
        <div 
          className="advisor-avatar" 
          style={{ backgroundColor: colors.bgColor }}
        >
          <Icon style={{ color: colors.color }} />
        </div>
        <div 
          className="advisor-message-bubble"
          style={{ 
            backgroundColor: colors.bgColor,
            borderColor: colors.color + '40',
            position: 'relative'
          }}
        >
          <div className="advisor-message-header">
            <h4 
              className="advisor-message-name" 
              style={{ color: colors.color }}
            >
              {advisor.name}
              {message.isReply && <span className="reply-badge">↳ Reply</span>}
              {message.isExpansion && <span className="expansion-badge">⤴ Expanded</span>}
            </h4>
            <span 
              className="message-time"
              style={{ 
                color: colors.color,
                opacity: 0.7 
              }}
            >
              {message.timestamp.toLocaleTimeString([], {
                hour: '2-digit', 
                minute: '2-digit'
              })}
            </span>
          </div>
          
          {/* Enhanced markdown rendering with preprocessing */}
          <div 
            className="advisor-message-text"
            style={{ 
              color: colors.textColor
            }}
          >
            <ReactMarkdown 
              components={markdownComponents}
              // Add these props for better parsing
              remarkPlugins={[]}
              rehypePlugins={[]}
            >
              {preprocessMarkdown(message.content)}
            </ReactMarkdown>
          </div>
          
          {showReplyButton && (
            <div className="message-actions">
              <div className="action-buttons">
                <div className="tooltip-container">
                  <button 
                    className="action-button"
                    onClick={() => onReply && onReply(message)}
                    onMouseEnter={() => showTooltipWithDelay('reply')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: colors.color,
                      borderColor: colors.color + '40'
                    }}
                  >
                    <Reply size={14} />
                  </button>
                  {showTooltip === 'reply' && (
                    <div className="tooltip">Reply to this message</div>
                  )}
                </div>

                <div className="tooltip-container">
                  <button 
                    className="action-button"
                    onClick={() => handleCopy(message.id, message.content)}
                    onMouseEnter={() => showTooltipWithDelay('copy')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: isCopied ? '#10B981' : colors.color,
                      borderColor: isCopied ? '#10B98140' : colors.color + '40'
                    }}
                  >
                    {isCopied ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                  {showTooltip === 'copy' && (
                    <div className="tooltip">
                      {isCopied ? 'Copied!' : 'Copy response'}
                    </div>
                  )}
                </div>

                <div className="tooltip-container">
                  <button 
                    className="action-button"
                    onClick={() => handleExpand(message.id, message.persona_id)}
                    onMouseEnter={() => showTooltipWithDelay('expand')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: colors.color,
                      borderColor: colors.color + '40'
                    }}
                  >
                    <Maximize2 size={14} />
                  </button>
                  {showTooltip === 'expand' && (
                    <div className="tooltip">Expand on this response</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {showInfoOverlay && (
            <RagInfoOverlay 
              ragMetadata={message.ragMetadata} 
              colors={colors}
            />
          )}
        </div>
      </div>
    );
  }

  if (message.type === 'error') {
    return (
      <div className="error-message-container">
        <div className="error-message">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  return null;
};

export default MessageBubble;