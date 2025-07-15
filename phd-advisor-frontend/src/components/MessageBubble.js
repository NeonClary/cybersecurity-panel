import React, { useState, useRef, useEffect } from 'react';
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
      
      // Reset the copied state after 2 seconds
      setTimeout(() => {
        setCopiedStates(prev => ({ ...prev, [messageId]: false }));
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const handleExpand = (messageId, advisorId) => {
    if (onExpand) onExpand(messageId, advisorId);
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
          {/* Basic Stats */}
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

          {/* Document Details */}
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

          {/* No Documents Message */}
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
    const advisor = advisors[message.advisorId];
    const Icon = advisor.icon;
    const colors = getAdvisorColors(message.advisorId, isDark);
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
            position: 'relative' // For overlay positioning
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
          <p 
            className="advisor-message-text"
            style={{ 
              color: colors.textColor
            }}
          >
            {message.content}
          </p>
          {showReplyButton && (
            <div className="message-actions">
              <div className="action-buttons">
                {/* Reply Button */}
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

                {/* Copy Button */}
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

                {/* Expand/Elaborate Button */}
                <div className="tooltip-container">
                  <button 
                    className="action-button"
                    onClick={() => handleExpand(message.id, message.advisorId)}
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

          {/* RAG Info Overlay */}
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