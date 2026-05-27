import React, { useState } from 'react';
import { Trash2, AlertTriangle, X, Loader2, CheckCircle } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const ClearDataModal = ({ authToken, onClose, onDataCleared }) => {
  const { isDark } = useTheme();
  const [profile, setProfile] = useState(false);
  const [chats, setChats] = useState(false);
  const [canvas, setCanvas] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [result, setResult] = useState(null);

  const noneSelected = !profile && !chats && !canvas;

  const handleClear = async () => {
    if (noneSelected) return;
    setClearing(true);
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/api/users/me/clear-data`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ profile, chats, canvas }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setResult(data.cleared);
        if (onDataCleared) onDataCleared({ profile, chats, canvas });
      } else {
        setResult(['Error clearing data']);
      }
    } catch {
      setResult(['Network error']);
    } finally {
      setClearing(false);
    }
  };

  const overlay = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
  };

  const modal = {
    background: isDark ? '#1f2937' : '#fff',
    borderRadius: 16, padding: 28, width: 400, maxWidth: '90vw',
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
    color: isDark ? '#f3f4f6' : '#111827',
  };

  const checkRow = {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '12px 14px', borderRadius: 10, cursor: 'pointer',
    border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
    marginBottom: 10, transition: 'all 0.15s ease',
  };

  const checkRowActive = (active) => ({
    ...checkRow,
    background: active
      ? (isDark ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.06)')
      : 'transparent',
    borderColor: active ? '#ef4444' : (isDark ? '#374151' : '#e5e7eb'),
  });

  const checkbox = (checked) => ({
    width: 20, height: 20, borderRadius: 4, flexShrink: 0,
    border: `2px solid ${checked ? '#ef4444' : (isDark ? '#6b7280' : '#9ca3af')}`,
    background: checked ? '#ef4444' : 'transparent',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.15s ease', color: '#fff', fontSize: 13, fontWeight: 700,
  });

  if (result) {
    return (
      <div style={overlay} onClick={onClose}>
        <div style={modal} onClick={(e) => e.stopPropagation()}>
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <CheckCircle size={48} style={{ color: '#22c55e', marginBottom: 16 }} />
            <h3 style={{ margin: '0 0 12px', fontSize: 18 }}>Data Cleared</h3>
            <p style={{ color: isDark ? '#9ca3af' : '#6b7280', fontSize: 14, lineHeight: 1.6 }}>
              {result.join(', ')}
            </p>
            <button
              onClick={onClose}
              style={{
                marginTop: 20, padding: '10px 32px', borderRadius: 10,
                border: 'none', background: '#3b82f6', color: '#fff',
                fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <AlertTriangle size={22} style={{ color: '#f59e0b' }} />
            <h3 style={{ margin: 0, fontSize: 18 }}>Clear User Data</h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: isDark ? '#9ca3af' : '#6b7280', padding: 4 }}>
            <X size={20} />
          </button>
        </div>

        <p style={{ color: isDark ? '#9ca3af' : '#6b7280', fontSize: 13, marginBottom: 18, lineHeight: 1.5 }}>
          Select which data to clear. Profile data removal will reset your onboarding progress.
        </p>

        {/* Checkboxes */}
        <div onClick={() => setProfile(!profile)} style={checkRowActive(profile)}>
          <div style={checkbox(profile)}>{profile && '✓'}</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Profile Information</div>
            <div style={{ fontSize: 12, color: isDark ? '#9ca3af' : '#6b7280', marginTop: 2 }}>
              Major, GPA, career goals, learning style, etc. Resets "Tell us about yourself."
            </div>
          </div>
        </div>

        <div onClick={() => setChats(!chats)} style={checkRowActive(chats)}>
          <div style={checkbox(chats)}>{chats && '✓'}</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Chat History</div>
            <div style={{ fontSize: 12, color: isDark ? '#9ca3af' : '#6b7280', marginTop: 2 }}>
              All conversation sessions and messages.
            </div>
          </div>
        </div>

        <div onClick={() => setCanvas(!canvas)} style={checkRowActive(canvas)}>
          <div style={checkbox(canvas)}>{canvas && '✓'}</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Canvas</div>
            <div style={{ fontSize: 12, color: isDark ? '#9ca3af' : '#6b7280', marginTop: 2 }}>
              All collected insights and research notes.
            </div>
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10, marginTop: 22, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '10px 20px', borderRadius: 10,
              border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
              background: 'transparent', color: isDark ? '#d1d5db' : '#374151',
              fontSize: 14, cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleClear}
            disabled={noneSelected || clearing}
            style={{
              padding: '10px 20px', borderRadius: 10, border: 'none',
              background: noneSelected ? (isDark ? '#374151' : '#e5e7eb') : '#ef4444',
              color: noneSelected ? (isDark ? '#6b7280' : '#9ca3af') : '#fff',
              fontSize: 14, fontWeight: 600, cursor: noneSelected ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: clearing ? 0.7 : 1,
            }}
          >
            {clearing ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Trash2 size={16} />}
            {clearing ? 'Clearing...' : 'Clear Selected'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClearDataModal;
