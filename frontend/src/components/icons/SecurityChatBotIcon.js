import React from 'react';

/**
 * Compact welcome mark: a friendly security-robot head with a small chat bubble.
 * Stroke/fill use currentColor so parent accent (IntakePanel) applies in light and dark themes.
 */
const SecurityChatBotIcon = ({ size = 22, className, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    className={className}
    aria-hidden="true"
    {...props}
  >
    {/* Antenna */}
    <path
      d="M8.8 6.3V3.7"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
    />
    <circle cx="8.8" cy="2.55" r="1.15" fill="currentColor" />

    {/* Head */}
    <rect
      x="2.3"
      y="6.3"
      width="12.8"
      height="13.2"
      rx="3.6"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinejoin="round"
    />

    {/* Friendly eyes */}
    <circle cx="6.6" cy="12.15" r="1.35" fill="currentColor" />
    <circle cx="11" cy="12.15" r="1.35" fill="currentColor" />

    {/* Smile */}
    <path
      d="M6.4 15.7c1.25 1.4 4.55 1.4 5.8 0"
      stroke="currentColor"
      strokeWidth="1.55"
      strokeLinecap="round"
    />

    {/* Chat bubble */}
    <rect
      x="15.15"
      y="2.7"
      width="7.15"
      height="5.7"
      rx="1.85"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinejoin="round"
    />
    <path
      d="M16.7 8.4 15.5 10.7"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
    />
    <circle cx="17.35" cy="5.55" r="0.8" fill="currentColor" />
    <circle cx="19.55" cy="5.55" r="0.8" fill="currentColor" />
  </svg>
);

export default SecurityChatBotIcon;
