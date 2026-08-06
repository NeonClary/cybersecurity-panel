import React, { useCallback, useEffect, useState } from 'react';
import ReactDOM from 'react-dom';
import { Activity, RefreshCw, X } from 'lucide-react';

const overlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1100,
};

const modal = {
  background: 'var(--bg-primary, #fff)',
  borderRadius: 16,
  width: 560,
  maxWidth: '95vw',
  maxHeight: '85vh',
  overflow: 'hidden',
  boxShadow: 'var(--shadow-xl, 0 20px 40px rgba(0,0,0,0.2))',
  display: 'flex',
  flexDirection: 'column',
};

const statusColor = {
  online: '#059669',
  unavailable: '#b45309',
  error: '#dc2626',
};

/**
 * Settings → Model Status modal. Calls backend /models/status (probes).
 * Secrets never leave the server.
 */
const ModelStatusModal = ({ onClose, onStatusLoaded }) => {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const url = `${process.env.REACT_APP_API_URL || ''}/models/status${refresh ? '?refresh=true' : ''}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Status request failed (${resp.status})`);
      const data = await resp.json();
      setPayload(data);
      if (typeof onStatusLoaded === 'function') onStatusLoaded(data);
    } catch (e) {
      setError(e.message || 'Failed to load model status');
      // Fail open for the picker: parent keeps unfiltered list
      if (typeof onStatusLoaded === 'function') {
        onStatusLoaded({ check_failed: true, online_providers: null, models: [] });
      }
    } finally {
      setLoading(false);
    }
  }, [onStatusLoaded]);

  useEffect(() => {
    load(false);
  }, [load]);

  const models = payload?.models || [];

  return ReactDOM.createPortal(
    <div
      style={overlay}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Model Status"
    >
      <div style={modal}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-primary, #e2e8f0)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Activity size={18} />
            <strong>Model Status</strong>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => load(true)}
              disabled={loading}
              title="Refresh probes"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 12px',
                borderRadius: 8,
                border: '1px solid var(--border-primary, #e2e8f0)',
                background: 'var(--bg-secondary, #f8fafc)',
                cursor: loading ? 'wait' : 'pointer',
                minHeight: 44,
              }}
            >
              <RefreshCw size={16} className={loading ? 'spinning' : undefined} />
              Refresh
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                padding: 8,
                minHeight: 44,
                minWidth: 44,
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
          {error && (
            <p style={{ color: '#dc2626', marginTop: 0 }}>
              {error}. Provider list left unfiltered (fail open).
            </p>
          )}
          {payload?.check_failed && (
            <p style={{ color: '#b45309' }}>
              Full status check failed. Showing last known results if any; selection list was not
              restricted.
            </p>
          )}
          {payload?.checked_at && (
            <p style={{ color: 'var(--text-secondary, #64748b)', fontSize: 13 }}>
              Checked {new Date(payload.checked_at).toLocaleString()}
              {payload.cached ? ' (cached)' : ''}
            </p>
          )}
          {loading && !payload ? (
            <p>Probing models…</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {models.map((m) => (
                <li
                  key={m.id}
                  style={{
                    border: '1px solid var(--border-primary, #e2e8f0)',
                    borderRadius: 12,
                    padding: '12px 14px',
                    marginBottom: 10,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div>
                      <strong>{m.name}</strong>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary, #64748b)' }}>
                        {m.model || m.provider}
                        {!m.selectable ? ' · fallback only' : ''}
                      </div>
                    </div>
                    <span
                      style={{
                        color: statusColor[m.status] || '#64748b',
                        fontWeight: 600,
                        textTransform: 'capitalize',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {m.status}
                    </span>
                  </div>
                  {m.status === 'error' && m.error && (
                    <pre
                      style={{
                        margin: '8px 0 0',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        fontSize: 12,
                        color: '#991b1b',
                        background: '#fef2f2',
                        padding: 8,
                        borderRadius: 8,
                      }}
                    >
                      {m.error}
                    </pre>
                  )}
                  {typeof m.latency_ms === 'number' && (
                    <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 6 }}>
                      {m.latency_ms} ms
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ModelStatusModal;
