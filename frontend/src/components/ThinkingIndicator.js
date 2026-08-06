import React from 'react';
import { useAppConfig } from '../contexts/AppConfigContext';
import { useTheme } from '../contexts/ThemeContext';

const ThinkingIndicator = ({ advisorId }) => {
  const { advisors, getAdvisorColors } = useAppConfig();
  const advisor = advisors[advisorId];
  const { isDark } = useTheme();
  const colors = getAdvisorColors(advisorId, isDark);

  if (!advisor) return null;

  const Icon = advisor.icon;

  return (
    <div className="thinking-container">
      <div className="advisor-message-avatar-ring" style={{ width: 44, height: 44 }}>
        {Icon ? (
          <Icon
            className="advisor-message-avatar-icon"
            style={{ color: colors.color, width: 23, height: 23 }}
          />
        ) : null}
      </div>
      <div
        className="thinking-bubble"
        style={{
          backgroundColor: colors.bgColor,
          borderColor: colors.color + '40',
        }}
      >
        <div className="thinking-header">
          <h4 className="advisor-name" style={{ color: colors.color }}>
            {advisor.name}
          </h4>
        </div>
        <div className="thinking-dots">
          <div
            className="thinking-dot"
            style={{ backgroundColor: colors.color, animationDelay: '0ms' }}
          />
          <div
            className="thinking-dot"
            style={{ backgroundColor: colors.color, animationDelay: '150ms' }}
          />
          <div
            className="thinking-dot"
            style={{ backgroundColor: colors.color, animationDelay: '300ms' }}
          />
        </div>
        <p className="thinking-text" style={{ color: colors.color, opacity: 0.8 }}>
          thinking...
        </p>
      </div>
    </div>
  );
};

export default ThinkingIndicator;
