import React from 'react';
import { advisors } from '../data/advisors';

const MessageBubble = ({ message }) => {
  if (message.type === 'user') {
    return (
      <div className="user-message-container">
        <div className="user-message">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.type === 'advisor') {
    const advisor = advisors[message.advisorId];
    const Icon = advisor.icon;

    return (
      <div className="advisor-message-container">
        <div 
          className="advisor-avatar" 
          style={{ backgroundColor: advisor.bgColor }}
        >
          <Icon style={{ color: advisor.color }} />
        </div>
        <div className="advisor-message-bubble">
          <div className="advisor-message-header">
            <h4 
              className="advisor-message-name" 
              style={{ color: advisor.color }}
            >
              {advisor.name}
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