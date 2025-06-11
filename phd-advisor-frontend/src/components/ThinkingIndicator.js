import React from 'react';
import { advisors } from '../data/advisors';

const ThinkingIndicator = ({ advisorId }) => {
  const advisor = advisors[advisorId];
  const Icon = advisor.icon;

  return (
    <div className="thinking-container">
      <div 
        className="advisor-avatar" 
        style={{ backgroundColor: advisor.bgColor }}
      >
        <Icon style={{ color: advisor.color }} />
      </div>
      <div className="thinking-bubble">
        <div className="thinking-header">
          <h4 
            className="advisor-name" 
            style={{ color: advisor.color }}
          >
            {advisor.name}
          </h4>
        </div>
        <div className="thinking-dots">
          <div 
            className="thinking-dot" 
            style={{ 
              backgroundColor: advisor.color, 
              animationDelay: '0ms' 
            }}
          ></div>
          <div 
            className="thinking-dot" 
            style={{ 
              backgroundColor: advisor.color, 
              animationDelay: '150ms' 
            }}
          ></div>
          <div 
            className="thinking-dot" 
            style={{ 
              backgroundColor: advisor.color, 
              animationDelay: '300ms' 
            }}
          ></div>
        </div>
        <p className="thinking-text">thinking...</p>
      </div>
    </div>
  );
};

export default ThinkingIndicator;