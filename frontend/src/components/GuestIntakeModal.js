import React, { useState } from 'react';
import { Shield, Building2, PenLine, X, Loader2, ArrowRight } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Explore-as-guest intake: two persona chips + free-text "something else".
 */
const GuestIntakeModal = ({ onClose, onSuccess }) => {
  const { isDark } = useTheme();
  const [choice, setChoice] = useState(null); // personal | business | other
  const [freeText, setFreeText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const bg = isDark ? 'rgba(15,23,42,0.92)' : 'rgba(15,23,42,0.45)';
  const card = {
    background: isDark ? '#1e293b' : '#fff',
    color: isDark ? '#f8fafc' : '#0f172a',
    border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
    borderRadius: 16,
    maxWidth: 480,
    width: '92%',
    padding: '1.5rem 1.4rem 1.25rem',
    boxShadow: '0 24px 48px rgba(15,23,42,0.25)',
  };
  const chip = (active) => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 12,
    textAlign: 'left',
    width: '100%',
    padding: '14px 14px',
    minHeight: 44,
    borderRadius: 12,
    border: active ? '2px solid var(--accent-primary, #0B7A8A)' : `1px solid ${isDark ? '#475569' : '#cbd5e1'}`,
    background: active
      ? (isDark ? 'rgba(15,118,110,0.2)' : 'rgba(15,118,110,0.08)')
      : (isDark ? '#0f172a' : '#f8fafc'),
    cursor: 'pointer',
    color: 'inherit',
    marginBottom: 10,
  });

  const start = async () => {
    if (!choice) {
      setError('Pick a path or describe what you need.');
      return;
    }
    if (choice === 'other' && !freeText.trim()) {
      setError('Tell us a bit about what you need help with.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL || ''}/auth/guest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          choice,
          free_text: choice === 'other' ? freeText.trim() : null,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Could not start guest session');
      }
      const data = await resp.json();
      localStorage.setItem('authToken', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      onSuccess?.(data.user, data.access_token);
    } catch (e) {
      setError(e.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="guest-intake-title"
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onMouseDown={(e) => { if (e.target === e.currentTarget && !loading) onClose?.(); }}
    >
      <div style={card} onMouseDown={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <h2 id="guest-intake-title" style={{ margin: 0, fontSize: '1.25rem' }}>Explore as guest</h2>
            <p style={{ margin: '6px 0 0', color: isDark ? '#94a3b8' : '#64748b', fontSize: 14, lineHeight: 1.45 }}>
              No account needed. We&apos;ll load a realistic demo so Chat, Journey, Workspace, and About You feel useful right away.
            </p>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            disabled={loading}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: isDark ? '#94a3b8' : '#64748b', padding: 4, minHeight: 44, minWidth: 44,
            }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ marginTop: 18 }}>
          <button type="button" style={chip(choice === 'personal')} onClick={() => setChoice('personal')} disabled={loading}>
            <Shield size={22} style={{ color: 'var(--accent-primary, #0B7A8A)', flexShrink: 0, marginTop: 2 }} />
            <span>
              <strong style={{ display: 'block', marginBottom: 2 }}>I&apos;m securing my personal digital life</strong>
              <span style={{ fontSize: 13, color: isDark ? '#94a3b8' : '#64748b' }}>
                Passwords, MFA, backups, phishing — sample Journey &amp; chat for individuals
              </span>
            </span>
          </button>

          <button type="button" style={chip(choice === 'business')} onClick={() => setChoice('business')} disabled={loading}>
            <Building2 size={22} style={{ color: 'var(--accent-primary, #0B7A8A)', flexShrink: 0, marginTop: 2 }} />
            <span>
              <strong style={{ display: 'block', marginBottom: 2 }}>I help protect a business or organization</strong>
              <span style={{ fontSize: 13, color: isDark ? '#94a3b8' : '#64748b' }}>
                SMB / IT baseline, CIS IG1 sample track, policies &amp; Workspace demo
              </span>
            </span>
          </button>

          <button type="button" style={chip(choice === 'other')} onClick={() => setChoice('other')} disabled={loading}>
            <PenLine size={22} style={{ color: 'var(--accent-primary, #0B7A8A)', flexShrink: 0, marginTop: 2 }} />
            <span>
              <strong style={{ display: 'block', marginBottom: 2 }}>Something else</strong>
              <span style={{ fontSize: 13, color: isDark ? '#94a3b8' : '#64748b' }}>
                Describe your situation — we&apos;ll tailor the demo
              </span>
            </span>
          </button>

          {choice === 'other' && (
            <textarea
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="e.g. Preparing for a Security+ exam, or reviewing our ransomware readiness…"
              rows={3}
              disabled={loading}
              style={{
                width: '100%', boxSizing: 'border-box', marginTop: 4, padding: 12,
                borderRadius: 10, border: `1px solid ${isDark ? '#475569' : '#cbd5e1'}`,
                background: isDark ? '#0f172a' : '#fff', color: 'inherit',
                fontFamily: 'inherit', fontSize: 14, resize: 'vertical', minHeight: 88,
              }}
            />
          )}
        </div>

        {error && (
          <p style={{ color: '#dc2626', fontSize: 13, margin: '10px 0 0' }}>{error}</p>
        )}

        <div style={{ display: 'flex', gap: 10, marginTop: 18, justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            style={{
              padding: '10px 16px', minHeight: 44, borderRadius: 10,
              border: `1px solid ${isDark ? '#475569' : '#cbd5e1'}`,
              background: 'transparent', color: 'inherit', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={start}
            disabled={loading || !choice}
            style={{
              padding: '10px 16px', minHeight: 44, borderRadius: 10, border: 'none',
              background: 'var(--accent-fill, var(--accent-primary, #0B7A8A))', color: 'var(--accent-on-accent, #fff)',
              cursor: loading || !choice ? 'not-allowed' : 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 600,
              opacity: loading || !choice ? 0.6 : 1,
            }}
          >
            {loading ? <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} /> : <ArrowRight size={16} />}
            {loading ? 'Setting up demo…' : 'Enter guest demo'}
          </button>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  );
};

export default GuestIntakeModal;
