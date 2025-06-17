import React from 'react';
import { Reply } from 'lucide-react';
import { advisors, getAdvisorColors } from '../data/advisors';
import { useTheme } from '../contexts/ThemeContext';

const MessageBubble = ({ message, onClick, showReplyButton = false }) => {
  const { isDark } = useTheme();

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

    return (
      <div className="advisor-message-container">
        <div 
          className="advisor-avatar" 
          style={{ backgroundColor: colors.bgColor }}
        >
          <Icon style={{ color: colors.color }} />
        </div>
        <div 
          className={`advisor-message-bubble ${showReplyButton ? 'clickable' : ''}`}
          style={{ 
            backgroundColor: colors.bgColor,
            borderColor: colors.color + '40'
          }}
          onClick={onClick}
        >
          <div className="advisor-message-header">
            <h4 
              className="advisor-message-name" 
              style={{ color: colors.color }}
            >
              {advisor.name}
              {message.isReply && <span className="reply-badge">↳ Reply</span>}
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
              <button 
                className="reply-button"
                onClick={(e) => {
                  e.stopPropagation();
                  onClick();
                }}
                style={{ 
                  color: colors.color,
                  borderColor: colors.color + '40'
                }}
              >
                <Reply size={14} />
                <span>Reply</span>
              </button>
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