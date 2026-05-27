import React from 'react';
import * as LucideIcons from 'lucide-react';
import { X } from 'lucide-react';

const UserAvatarPicker = ({ avatarOptions, currentAvatarId, onSelect, onClose }) => {
  const resolveIcon = (name) => LucideIcons[name] || LucideIcons.User;

  return (
    <div className="avatar-picker-overlay" onClick={onClose}>
      <div className="avatar-picker-modal" onClick={e => e.stopPropagation()}>
        <div className="avatar-picker-header">
          <h3>Choose Your Avatar</h3>
          <button onClick={onClose} className="avatar-picker-close"><X size={18} /></button>
        </div>
        <div className="avatar-picker-grid">
          {avatarOptions.map(opt => {
            const Icon = resolveIcon(opt.icon);
            const isSelected = currentAvatarId === opt.id;
            return (
              <button
                key={opt.id}
                className={`avatar-option ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelect(opt.id)}
                style={{
                  '--av-color': opt.color,
                  '--av-bg': opt.bg,
                  border: isSelected ? `2px solid ${opt.color}` : '2px solid transparent',
                }}
              >
                <div className="avatar-option-icon" style={{ backgroundColor: opt.bg, color: opt.color }}>
                  <Icon size={24} />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <style jsx>{`
        .avatar-picker-overlay {
          position: fixed; inset: 0; z-index: 9999;
          background: rgba(0,0,0,0.5); display: flex;
          align-items: center; justify-content: center;
        }
        .avatar-picker-modal {
          background: var(--bg-primary); border-radius: 16px;
          padding: 24px; min-width: 320px; max-width: 400px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .avatar-picker-header {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 16px;
        }
        .avatar-picker-header h3 {
          margin: 0; color: var(--text-primary); font-size: 16px;
        }
        .avatar-picker-close {
          background: none; border: none; cursor: pointer;
          color: var(--text-secondary); padding: 4px;
        }
        .avatar-picker-grid {
          display: grid; grid-template-columns: repeat(5, 1fr);
          gap: 10px;
        }
        .avatar-option {
          background: none; cursor: pointer; padding: 6px;
          border-radius: 12px; transition: all 0.15s;
          display: flex; align-items: center; justify-content: center;
        }
        .avatar-option:hover { transform: scale(1.1); }
        .avatar-option.selected { background: var(--av-bg); }
        .avatar-option-icon {
          width: 44px; height: 44px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
        }
      `}</style>
    </div>
  );
};

export default UserAvatarPicker;
