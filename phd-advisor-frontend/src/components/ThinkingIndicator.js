import React from 'react';
import { advisors, getAdvisorColors } from '../data/advisors';
import { useTheme } from '../contexts/ThemeContext';

const ThinkingIndicator = ({ advisorId }) => {
  const advisor = advisors[advisorId];
  const Icon = advisor.icon;
  const { isDark } = useTheme();
  const colors = getAdvisorColors(advisorId, isDark);

  return (
    <div className="thinking-container">
      <div 
        className="advisor-avatar" 
        style={{ backgroundColor: colors.bgColor }}
      >
        <Icon style={{ color: colors.color }} />
      </div>
      <div 
        className="thinking-bubble"
        style={{ 
          backgroundColor: colors.bgColor,
          borderColor: colors.color + '40' // Adding transparency to the border
        }}
      >
        <div className="thinking-header">
          <h4 
            className="advisor-name" 
            style={{ color: colors.color }}
          >
            {advisor.name}
          </h4>
        </div>
        <div className="thinking-dots">
          <div 
            className="thinking-dot" 
            style={{ 
              backgroundColor: colors.color, 
              animationDelay: '0ms' 
            }}
          ></div>
          <div 
            className="thinking-dot" 
            style={{ 
              backgroundColor: colors.color, 
              animationDelay: '150ms' 
            }}
          ></div>
          <div 
            className="thinking-dot" 
            style={{ 
              backgroundColor: colors.color, 
              animationDelay: '300ms' 
            }}
          ></div>
        </div>
        <p 
          className="thinking-text"
          style={{ 
            color: colors.color,
            opacity: 0.8 
          }}
        >
          thinking...
        </p>
      </div>
    </div>
  );
};

export default ThinkingIndicator;