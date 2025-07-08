import React, { useState } from 'react';
import { Reply, Copy, Check, Maximize2 } from 'lucide-react';
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

  const showTooltipWithDelay = (tooltipType) => {
    setTimeout(() => setShowTooltip(tooltipType), 500);
  };

  const hideTooltip = () => {
    setShowTooltip(null);
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
            borderColor: colors.color + '40'
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