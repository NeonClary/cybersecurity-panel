import React, { useState, useEffect, useRef } from 'react';
import { X, Send, MessageCircle } from 'lucide-react';

const OnboardingChat = ({ authToken, onClose, userName }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [complete, setComplete] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    startOnboarding();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startOnboarding = async () => {
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/api/onboarding/start`, {
        headers: { 'Authorization': `Bearer ${authToken}` },
      });
      if (resp.ok) {
        const data = await resp.json();
        setMessages(data.messages || [{ role: 'agent', text: data.reply }]);
        setProgress(data.progress);
        setComplete(data.complete || false);
      }
    } catch (e) {
      setMessages([{ role: 'agent', text: "Hi! What is your security role and what are you trying to accomplish right now?" }]);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userText = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setLoading(true);
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/api/onboarding/chat`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userText }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setMessages(prev => [...prev, { role: 'agent', text: data.reply }]);
        setProgress(data.progress);
        setComplete(data.complete);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'agent', text: "Sorry, I had trouble processing that. Try again?" }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--bg-primary)', borderRadius: 16,
        width: '90%', maxWidth: 500, height: '70vh', maxHeight: 600,
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        {/* Header */}
        <div style={{
          padding: '14px 18px', borderBottom: '1px solid var(--border-primary)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <MessageCircle size={18} style={{ color: 'var(--accent-primary)' }} />
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}>
              Tell us about yourself
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: '4px 10px',
              fontSize: 11, fontWeight: 600, color: 'var(--accent-primary)',
            }}>{progress}% complete</div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {messages.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '80%',
              background: m.role === 'user' ? 'var(--accent-primary)' : 'var(--bg-secondary)',
              color: m.role === 'user' ? '#fff' : 'var(--text-primary)',
              padding: '10px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.5,
            }}>
              {m.text}
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', color: 'var(--text-secondary)', fontSize: 12 }}>
              Thinking...
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input */}
        {!complete && (
          <div style={{
            padding: '10px 14px', borderTop: '1px solid var(--border-primary)',
            display: 'flex', gap: 8,
          }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()}
              placeholder="Type your answer..."
              disabled={loading}
              style={{
                flex: 1, padding: '8px 12px', borderRadius: 8,
                border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
                color: 'var(--text-primary)', fontSize: 13, outline: 'none',
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              style={{
                padding: '8px 12px', borderRadius: 8, border: 'none',
                background: input.trim() ? 'var(--accent-primary)' : 'var(--bg-secondary)',
                color: input.trim() ? '#fff' : 'var(--text-secondary)',
                cursor: input.trim() ? 'pointer' : 'default',
              }}
            >
              <Send size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default OnboardingChat;
