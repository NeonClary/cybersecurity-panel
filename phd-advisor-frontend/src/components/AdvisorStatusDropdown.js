import React, { useState, useEffect } from 'react';
import { Users, ChevronDown, Pencil } from 'lucide-react';
import AvatarPickerModal from './AvatarPickerModal';

const AdvisorStatusDropdown = ({
  advisors,
  activeAdvisorIds = [],
  onToggleAdvisor,
  onSetActiveAdvisors,
  thinkingAdvisors,
  getAdvisorColors,
  isDark,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hoveredId, setHoveredId] = useState(null);
  const [pickerAdvisor, setPickerAdvisor] = useState(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (isOpen && !event.target.closest('.advisor-status-dropdown')) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  if (!advisors || typeof advisors !== 'object') {
    return null;
  }

  const advisorEntries = Object.entries(advisors);
  const allIds = advisorEntries.map(([id]) => id);
  const activeSet = new Set(activeAdvisorIds);
  const activeCount = allIds.filter((id) => activeSet.has(id)).length;
  const thinkingCount = Array.isArray(thinkingAdvisors)
    ? thinkingAdvisors.filter((id) => id !== 'system' && activeSet.has(id)).length
    : 0;
  const totalAdvisors = advisorEntries.length;

  const handleToggle = () => {
    setIsOpen(!isOpen);
  };

  const handleCheckboxChange = (id, event) => {
    event.stopPropagation();
    if (onToggleAdvisor) {
      onToggleAdvisor(id);
    }
  };

  const selectAll = (event) => {
    event.stopPropagation();
    if (onSetActiveAdvisors) {
      onSetActiveAdvisors([...allIds]);
    }
  };

  const selectNone = (event) => {
    event.stopPropagation();
    if (onSetActiveAdvisors && allIds.length > 0) {
      onSetActiveAdvisors([allIds[0]]);
    }
  };

  return (
    <div className="advisor-status-dropdown">
      <button
        type="button"
        className={`advisor-status-button ${isOpen ? 'open' : ''}`}
        onClick={handleToggle}
        title="Choose which advisors are active"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <div className="advisor-status-info">
          <Users size={16} />
          <span className="advisor-count">
            {activeCount}/{totalAdvisors} Active
          </span>
          {thinkingCount > 0 && (
            <div className="thinking-badge">
              {thinkingCount} thinking
            </div>
          )}
        </div>
        <ChevronDown size={14} className={`dropdown-arrow ${isOpen ? 'rotated' : ''}`} />
      </button>

      {pickerAdvisor && (
        <AvatarPickerModal
          advisorId={pickerAdvisor.id}
          advisorName={pickerAdvisor.name}
          onClose={() => setPickerAdvisor(null)}
        />
      )}
      {isOpen && (
        <div className="advisor-dropdown-panel" role="listbox" aria-label="Active advisors">
          <div className="advisor-panel-header">
            <div className="advisor-panel-title">Active advisors</div>
            <div className="advisor-panel-subtitle">
              Only checked advisors respond to your messages.
            </div>
            <div className="advisor-panel-actions">
              <button type="button" className="advisor-panel-link" onClick={selectAll}>
                Select all
              </button>
              <span className="advisor-panel-sep">·</span>
              <button type="button" className="advisor-panel-link" onClick={selectNone}>
                Minimize
              </button>
            </div>
          </div>
          <div className="advisor-list">
            {advisorEntries.map(([id, advisor]) => {
              const IconComponent = advisor.icon;
              const colors = getAdvisorColors(id, isDark);
              const isThinking = Array.isArray(thinkingAdvisors) && thinkingAdvisors.includes(id);
              const isActive = activeSet.has(id);

              return (
                <div
                  key={id}
                  className={`advisor-item ${isThinking ? 'thinking' : ''} ${isActive ? '' : 'inactive'}`}
                  style={{ '--advisor-color': colors.color, '--advisor-bg': colors.bgColor }}
                >
                  <label className="advisor-active-toggle" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isActive}
                      onChange={(e) => handleCheckboxChange(id, e)}
                      aria-label={`${isActive ? 'Deactivate' : 'Activate'} ${advisor.name}`}
                    />
                  </label>
                  <div
                    className="advisor-icon"
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setPickerAdvisor({ id, name: advisor.name });
                      }
                    }}
                    onClick={() => setPickerAdvisor({ id, name: advisor.name })}
                    onMouseEnter={() => setHoveredId(id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    {advisor.avatarUrl
                      ? <img src={advisor.avatarUrl} alt={advisor.name} />
                      : <IconComponent size={16} />}
                    {hoveredId === id && (
                      <div className="advisor-icon-edit">
                        <Pencil size={10} color="#fff" />
                      </div>
                    )}
                  </div>
                  <div className="advisor-details">
                    <div className="advisor-name">{advisor.name}</div>
                    <div className="advisor-description">{advisor.description}</div>
                  </div>
                  <div className="advisor-status">
                    {!isActive ? (
                      <div className="status-inactive">Off</div>
                    ) : isThinking ? (
                      <div className="status-thinking">
                        <div className="thinking-dots">
                          <div className="dot" />
                          <div className="dot" />
                          <div className="dot" />
                        </div>
                      </div>
                    ) : (
                      <div className="status-ready">Ready</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <style>{`
        .advisor-status-dropdown {
          position: relative;
          display: inline-block;
        }

        .advisor-status-button {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background: var(--bg-primary);
          border: 1px solid var(--border-primary);
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 13px;
          min-width: 140px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
          color: var(--text-primary);
        }

        .advisor-status-button:hover {
          background: var(--bg-secondary);
          border-color: var(--accent-primary);
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .advisor-status-button.open {
          background: var(--bg-secondary);
          border-color: var(--accent-primary);
        }

        .advisor-status-info {
          display: flex;
          align-items: center;
          gap: 6px;
          flex: 1;
        }

        .advisor-count {
          font-weight: 600;
          color: var(--text-primary);
          white-space: nowrap;
        }

        .thinking-badge {
          background: var(--accent-primary);
          color: white;
          padding: 2px 6px;
          border-radius: 8px;
          font-size: 10px;
          font-weight: 600;
          animation: pulse 2s ease-in-out infinite;
        }

        .dropdown-arrow {
          color: var(--text-secondary);
          transition: transform 0.2s ease;
          flex-shrink: 0;
        }

        .dropdown-arrow.rotated {
          transform: rotate(180deg);
        }

        .advisor-dropdown-panel {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          min-width: 300px;
          max-width: 340px;
          background: var(--bg-primary);
          border: 1px solid var(--border-primary);
          border-radius: 12px;
          box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
          z-index: 1000;
          overflow: hidden;
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
        }

        [data-theme="dark"] .advisor-dropdown-panel {
          box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
        }

        .advisor-panel-header {
          padding: 12px 16px 8px;
          border-bottom: 1px solid var(--border-primary);
        }

        .advisor-panel-title {
          font-size: 13px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .advisor-panel-subtitle {
          font-size: 11px;
          color: var(--text-secondary);
          margin-top: 2px;
          line-height: 1.35;
        }

        .advisor-panel-actions {
          margin-top: 8px;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .advisor-panel-link {
          background: none;
          border: none;
          padding: 0;
          font-size: 11px;
          font-weight: 600;
          color: var(--accent-primary);
          cursor: pointer;
        }

        .advisor-panel-link:hover {
          text-decoration: underline;
        }

        .advisor-panel-sep {
          color: var(--text-tertiary);
          font-size: 11px;
        }

        .advisor-list {
          max-height: 320px;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: var(--border-primary) transparent;
        }

        .advisor-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 14px;
          border-bottom: 1px solid var(--border-primary);
          transition: background-color 0.2s ease, opacity 0.2s ease;
        }

        .advisor-item.inactive {
          opacity: 0.55;
        }

        .advisor-item:last-child {
          border-bottom: none;
        }

        .advisor-item:hover {
          background: var(--bg-secondary);
        }

        .advisor-item.thinking {
          background: var(--advisor-bg);
          opacity: 1;
        }

        .advisor-active-toggle {
          display: flex;
          align-items: center;
          flex-shrink: 0;
          cursor: pointer;
        }

        .advisor-active-toggle input {
          width: 16px;
          height: 16px;
          accent-color: var(--accent-primary);
          cursor: pointer;
        }

        .advisor-icon {
          position: relative;
          cursor: pointer;
          overflow: hidden;
          width: 32px;
          height: 32px;
          border-radius: 8px;
          flex-shrink: 0;
          background: var(--advisor-bg);
          color: var(--advisor-color);
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--advisor-color);
        }

        .advisor-icon img {
          width: 32px;
          height: 32px;
          object-fit: cover;
          display: block;
        }

        .advisor-icon-edit {
          position: absolute;
          inset: 0;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.45);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .advisor-details {
          flex: 1;
          min-width: 0;
        }

        .advisor-name {
          font-weight: 600;
          color: var(--text-primary);
          font-size: 13px;
          margin-bottom: 2px;
        }

        .advisor-description {
          font-size: 11px;
          color: var(--text-secondary);
          line-height: 1.3;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .advisor-status {
          flex-shrink: 0;
        }

        .status-inactive {
          font-size: 11px;
          color: var(--text-tertiary);
          font-weight: 500;
        }

        .status-thinking {
          display: flex;
          align-items: center;
        }

        .thinking-dots {
          display: flex;
          gap: 2px;
        }

        .thinking-dots .dot {
          width: 4px;
          height: 4px;
          background: var(--advisor-color);
          border-radius: 50%;
          animation: thinking-bounce 1.4s infinite ease-in-out both;
        }

        .thinking-dots .dot:nth-child(1) { animation-delay: -0.32s; }
        .thinking-dots .dot:nth-child(2) { animation-delay: -0.16s; }

        .status-ready {
          font-size: 11px;
          color: var(--text-tertiary);
          font-weight: 500;
        }

        @keyframes thinking-bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }

        @media (max-width: 768px) {
          .advisor-status-dropdown {
            display: none;
          }
        }
      `}</style>
    </div>
  );
};

export default AdvisorStatusDropdown;
