import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import {
  X, User as UserIcon, Sparkles, Check, Trash2, Pencil, Plus,
  RefreshCw, Loader2, MessageSquareQuote, Eye,
} from 'lucide-react';
import ProfileWalkthrough from './ProfileWalkthrough';

const FACT_CATEGORIES = [
  { value: 'person', label: 'Person' },
  { value: 'organization', label: 'Organization' },
  { value: 'environment', label: 'Devices & environment' },
  { value: 'needs', label: 'Needs' },
  { value: 'preferences', label: 'Preferences' },
];

const overlay = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
};

const modal = {
  background: 'var(--bg-primary)', borderRadius: 16, padding: 0, width: 560,
  maxWidth: '95vw', maxHeight: '85vh', overflow: 'hidden',
  boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column',
};

const header = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '20px 24px', borderBottom: '1px solid var(--border-primary)',
};

const tabRow = {
  display: 'flex', gap: 4, padding: '12px 16px 0',
  borderBottom: '1px solid var(--border-primary)',
  flexWrap: 'wrap',
};

const tabBtn = (active) => ({
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '10px 14px', minHeight: 44, background: 'transparent',
  border: 'none', borderBottom: active ? '2px solid var(--accent-primary)' : '2px solid transparent',
  color: active ? 'var(--accent-primary)' : 'var(--text-secondary)',
  cursor: 'pointer', fontSize: 13.5, fontWeight: 500,
  marginBottom: -1,
});

const body = { padding: 24, overflowY: 'auto', flex: 1 };

const label = {
  display: 'block', fontSize: 13, fontWeight: 600,
  color: 'var(--text-secondary)', marginBottom: 6,
};

const input = {
  width: '100%', padding: '10px 12px', borderRadius: 8, minHeight: 44,
  border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
  color: 'var(--text-primary)', fontSize: 14, boxSizing: 'border-box',
};

const primaryBtn = {
  padding: '10px 16px', minHeight: 44, background: 'var(--accent-fill, var(--accent-primary))',
  color: 'var(--accent-on-accent, #fff)', border: 'none', borderRadius: 8,
  cursor: 'pointer', fontSize: 14, fontWeight: 500,
  display: 'inline-flex', alignItems: 'center', gap: 8,
};

const ghostBtn = {
  padding: '10px 14px', minHeight: 44, minWidth: 44,
  background: 'transparent', border: '1px solid var(--border-primary)',
  borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 500,
  color: 'var(--text-primary)', display: 'inline-flex', alignItems: 'center',
  justifyContent: 'center', gap: 6,
};

const sectionTitle = {
  margin: '0 0 6px', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)',
};

const sectionHint = {
  margin: '0 0 14px', fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.45,
};

const factCard = {
  border: '1px solid var(--border-primary)', borderRadius: 10,
  padding: '12px 14px', marginBottom: 10,
  background: 'var(--bg-secondary)',
};

const extractError = (data, fallback) => {
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  return fallback;
};

const AboutYouModal = ({
  authToken,
  onClose,
  existingProfile,
  initialTab = 'about',
}) => {
  const [activeTab, setActiveTab] = useState(initialTab === 'profile' ? 'profile' : 'about');
  const [facts, setFacts] = useState([]);
  const [summaries, setSummaries] = useState({ short: '', long: '' });
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [regenerating, setRegenerating] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newFact, setNewFact] = useState({ category: 'person', key: '', value: '' });
  const [adding, setAdding] = useState(false);

  const apiUrl = process.env.REACT_APP_API_URL || '';
  const mouseDownOnOverlay = useRef(false);

  const handleOverlayMouseDown = (e) => {
    mouseDownOnOverlay.current = e.target === e.currentTarget;
  };
  const handleOverlayMouseUp = (e) => {
    if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose();
    mouseDownOnOverlay.current = false;
  };

  const authHeaders = useCallback(() => ({
    Authorization: `Bearer ${authToken}`,
    'Content-Type': 'application/json',
  }), [authToken]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setMessage(null);
    try {
      const [factsResp, sumsResp] = await Promise.all([
        fetch(`${apiUrl}/api/users/me/facts`, { headers: { Authorization: `Bearer ${authToken}` } }),
        fetch(`${apiUrl}/api/users/me/summaries`, { headers: { Authorization: `Bearer ${authToken}` } }),
      ]);
      if (factsResp.ok) {
        const data = await factsResp.json();
        setFacts(Array.isArray(data.facts) ? data.facts : []);
      } else {
        setMessage({ type: 'error', text: 'Could not load profile facts.' });
      }
      if (sumsResp.ok) {
        const data = await sumsResp.json();
        setSummaries({ short: data.short || '', long: data.long || '' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Network error loading knowledge profile.' });
    } finally {
      setLoading(false);
    }
  }, [apiUrl, authToken]);

  useEffect(() => {
    if (activeTab === 'about') loadData();
  }, [activeTab, loadData]);

  useEffect(() => {
    setActiveTab(initialTab === 'profile' ? 'profile' : 'about');
  }, [initialTab]);

  const statedFacts = facts.filter((f) => f.source === 'stated');
  const inferredFacts = facts.filter((f) => f.source === 'inferred');

  const handleConfirm = async (fact) => {
    setBusyId(fact.id);
    setMessage(null);
    try {
      const resp = await fetch(`${apiUrl}/api/users/me/facts/${fact.id}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ source: 'stated' }),
      });
      const data = await resp.json().catch(() => null);
      if (!resp.ok) {
        setMessage({ type: 'error', text: extractError(data, 'Could not confirm fact.') });
        return;
      }
      setFacts((prev) => prev.map((f) => (f.id === fact.id ? { ...f, ...data, source: 'stated' } : f)));
      setMessage({ type: 'success', text: 'Fact confirmed as something you told us.' });
    } catch {
      setMessage({ type: 'error', text: 'Network error.' });
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (fact) => {
    setBusyId(fact.id);
    setMessage(null);
    try {
      const resp = await fetch(`${apiUrl}/api/users/me/facts/${fact.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!resp.ok && resp.status !== 204) {
        const data = await resp.json().catch(() => null);
        setMessage({ type: 'error', text: extractError(data, 'Could not delete fact.') });
        return;
      }
      setFacts((prev) => prev.filter((f) => f.id !== fact.id));
      if (editingId === fact.id) {
        setEditingId(null);
        setEditValue('');
      }
    } catch {
      setMessage({ type: 'error', text: 'Network error.' });
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (fact) => {
    setEditingId(fact.id);
    setEditValue(fact.value || '');
    setMessage(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };

  const saveEdit = async (fact) => {
    const trimmed = editValue.trim();
    if (!trimmed) {
      setMessage({ type: 'error', text: 'Value cannot be empty.' });
      return;
    }
    setBusyId(fact.id);
    setMessage(null);
    try {
      const resp = await fetch(`${apiUrl}/api/users/me/facts/${fact.id}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ value: trimmed }),
      });
      const data = await resp.json().catch(() => null);
      if (!resp.ok) {
        setMessage({ type: 'error', text: extractError(data, 'Could not update fact.') });
        return;
      }
      setFacts((prev) => prev.map((f) => (f.id === fact.id ? { ...f, ...data } : f)));
      setEditingId(null);
      setEditValue('');
    } catch {
      setMessage({ type: 'error', text: 'Network error.' });
    } finally {
      setBusyId(null);
    }
  };

  const handleAdd = async () => {
    const key = newFact.key.trim();
    const value = newFact.value.trim();
    if (!key || !value) {
      setMessage({ type: 'error', text: 'Key and value are required.' });
      return;
    }
    setAdding(true);
    setMessage(null);
    try {
      const resp = await fetch(`${apiUrl}/api/users/me/facts`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          category: newFact.category,
          key,
          value,
        }),
      });
      const data = await resp.json().catch(() => null);
      if (!resp.ok) {
        setMessage({ type: 'error', text: extractError(data, 'Could not add fact.') });
        return;
      }
      setFacts((prev) => [...prev, data]);
      setNewFact({ category: 'person', key: '', value: '' });
      setShowAdd(false);
      setMessage({ type: 'success', text: 'Fact added.' });
    } catch {
      setMessage({ type: 'error', text: 'Network error.' });
    } finally {
      setAdding(false);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    setMessage(null);
    try {
      const resp = await fetch(`${apiUrl}/api/users/me/summaries/regenerate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await resp.json().catch(() => null);
      if (!resp.ok) {
        setMessage({ type: 'error', text: extractError(data, 'Could not regenerate summaries.') });
        return;
      }
      setSummaries({ short: data.short || '', long: data.long || '' });
      setMessage({ type: 'success', text: 'Summaries regenerated.' });
    } catch {
      setMessage({ type: 'error', text: 'Network error.' });
    } finally {
      setRegenerating(false);
    }
  };

  const messageStyle = (type) => ({
    padding: '10px 12px', borderRadius: 8, marginBottom: 16, fontSize: 13,
    background: type === 'error'
      ? 'rgba(220,38,38,0.1)'
      : type === 'success'
        ? 'rgba(22,163,74,0.1)'
        : 'var(--bg-secondary)',
    color: type === 'error'
      ? '#dc2626'
      : type === 'success'
        ? '#16a34a'
        : 'var(--text-secondary)',
    border: `1px solid ${
      type === 'error'
        ? 'rgba(220,38,38,0.3)'
        : type === 'success'
          ? 'rgba(22,163,74,0.3)'
          : 'var(--border-primary)'
    }`,
  });

  const formatKey = (key) => (key || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  const renderFactRow = (fact, { inferred = false } = {}) => {
    const isBusy = busyId === fact.id;
    const isEditing = editingId === fact.id;

    return (
      <div key={fact.id} style={factCard}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
              letterSpacing: '0.04em', color: 'var(--text-secondary)', marginBottom: 4,
            }}>
              {formatKey(fact.key)}
              {fact.category ? (
                <span style={{ fontWeight: 500, opacity: 0.75 }}> · {fact.category}</span>
              ) : null}
            </div>
            {isEditing ? (
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                rows={2}
                style={{ ...input, minHeight: 64, resize: 'vertical' }}
                autoFocus
              />
            ) : (
              <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.45, wordBreak: 'break-word' }}>
                {fact.value}
              </div>
            )}
            {inferred && fact.confidence != null && (
              <div style={{ marginTop: 6, fontSize: 11.5, color: 'var(--text-secondary)' }}>
                Confidence: {Math.round(Number(fact.confidence) * 100)}%
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {isEditing ? (
            <>
              <button
                type="button"
                onClick={() => saveEdit(fact)}
                disabled={isBusy}
                style={primaryBtn}
              >
                {isBusy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Check size={16} />}
                Save
              </button>
              <button type="button" onClick={cancelEdit} disabled={isBusy} style={ghostBtn}>
                Cancel
              </button>
            </>
          ) : inferred ? (
            <>
              <button
                type="button"
                onClick={() => handleConfirm(fact)}
                disabled={isBusy}
                style={primaryBtn}
                title="Promote to something you told us"
              >
                {isBusy ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Check size={16} />}
                Confirm
              </button>
              <button
                type="button"
                onClick={() => handleDelete(fact)}
                disabled={isBusy}
                style={{ ...ghostBtn, color: '#dc2626', borderColor: 'rgba(220,38,38,0.35)' }}
              >
                <Trash2 size={16} />
                Delete
              </button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => startEdit(fact)} disabled={isBusy} style={ghostBtn}>
                <Pencil size={16} />
                Edit
              </button>
              <button
                type="button"
                onClick={() => handleDelete(fact)}
                disabled={isBusy}
                style={{ ...ghostBtn, color: '#dc2626', borderColor: 'rgba(220,38,38,0.35)' }}
              >
                <Trash2 size={16} />
                Delete
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  const aboutContent = loading ? (
    <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)', fontSize: 14 }}>
      <Loader2 size={22} style={{ animation: 'spin 1s linear infinite', marginBottom: 10 }} />
      <div>Loading what we know about you…</div>
    </div>
  ) : (
    <>
      {/* Summaries */}
      <section style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <h4 style={sectionTitle}>Your summary</h4>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={regenerating}
            style={ghostBtn}
          >
            {regenerating
              ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              : <RefreshCw size={16} />}
            Regenerate
          </button>
        </div>
        <p style={sectionHint}>
          Short and long previews built from your profile facts. Regenerate after confirming or editing facts.
        </p>
        <div style={{
          border: '1px solid var(--border-primary)', borderRadius: 10,
          padding: 14, marginBottom: 10, background: 'var(--bg-secondary)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-secondary)', marginBottom: 6 }}>
            Short
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
            {summaries.short || <span style={{ color: 'var(--text-secondary)' }}>No short summary yet.</span>}
          </div>
        </div>
        <div style={{
          border: '1px solid var(--border-primary)', borderRadius: 10,
          padding: 14, background: 'var(--bg-secondary)',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-secondary)', marginBottom: 6 }}>
            Long
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
            {summaries.long || <span style={{ color: 'var(--text-secondary)' }}>No long summary yet.</span>}
          </div>
        </div>
      </section>

      {/* Stated */}
      <section style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <MessageSquareQuote size={18} style={{ color: 'var(--accent-primary)' }} />
          <h4 style={{ ...sectionTitle, margin: 0 }}>Things you told us</h4>
        </div>
        <p style={sectionHint}>
          Facts you stated explicitly — editable anytime.
        </p>
        {statedFacts.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 12px' }}>
            Nothing here yet. Add a fact or confirm something we noticed.
          </p>
        ) : (
          statedFacts.map((f) => renderFactRow(f))
        )}

        {showAdd ? (
          <div style={{ ...factCard, marginTop: 4 }}>
            <div style={{ marginBottom: 12 }}>
              <label style={label}>Category</label>
              <select
                value={newFact.category}
                onChange={(e) => setNewFact((p) => ({ ...p, category: e.target.value }))}
                style={input}
              >
                {FACT_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={label}>Key</label>
              <input
                value={newFact.key}
                onChange={(e) => setNewFact((p) => ({ ...p, key: e.target.value }))}
                placeholder="e.g. role, employer, goal"
                style={input}
              />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={label}>Value</label>
              <textarea
                value={newFact.value}
                onChange={(e) => setNewFact((p) => ({ ...p, value: e.target.value }))}
                placeholder="What should we remember?"
                rows={2}
                style={{ ...input, minHeight: 64, resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={handleAdd} disabled={adding} style={primaryBtn}>
                {adding ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Plus size={16} />}
                Add fact
              </button>
              <button
                type="button"
                onClick={() => { setShowAdd(false); setNewFact({ category: 'person', key: '', value: '' }); }}
                style={ghostBtn}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => setShowAdd(true)} style={{ ...ghostBtn, marginTop: 4 }}>
            <Plus size={16} />
            Add fact
          </button>
        )}
      </section>

      {/* Inferred */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <Eye size={18} style={{ color: 'var(--accent-primary)' }} />
          <h4 style={{ ...sectionTitle, margin: 0 }}>Things we noticed</h4>
        </div>
        <p style={sectionHint}>
          Inferred from conversation. Confirm to keep, or delete if wrong.
        </p>
        {inferredFacts.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
            No inferred facts yet — they appear as you chat.
          </p>
        ) : (
          inferredFacts.map((f) => renderFactRow(f, { inferred: true }))
        )}
      </section>
    </>
  );

  return ReactDOM.createPortal(
    <div style={overlay} onMouseDown={handleOverlayMouseDown} onMouseUp={handleOverlayMouseUp}>
      <div style={modal} onClick={(e) => e.stopPropagation()}>
        <div style={header}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Sparkles size={20} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: 18 }}>About You</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-secondary)', minWidth: 44, minHeight: 44,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={tabRow}>
          <button
            type="button"
            style={tabBtn(activeTab === 'profile')}
            onClick={() => { setActiveTab('profile'); setMessage(null); }}
          >
            <UserIcon size={15} /> Profile form
          </button>
          <button
            type="button"
            style={tabBtn(activeTab === 'about')}
            onClick={() => { setActiveTab('about'); setMessage(null); }}
          >
            <Sparkles size={15} /> About You
          </button>
        </div>

        <div style={body}>
          {message && <div style={messageStyle(message.type)}>{message.text}</div>}

          {activeTab === 'profile' ? (
            <ProfileWalkthrough
              authToken={authToken}
              existingProfile={existingProfile}
              embedded
              onClose={onClose}
            />
          ) : (
            aboutContent
          )}
        </div>
      </div>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>,
    document.body
  );
};

export default AboutYouModal;
