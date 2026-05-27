import React, { useState } from 'react';
import { User, Mail, Save, Trash2, AlertTriangle, X, Loader2, CheckCircle, Lock, ChevronDown, ChevronUp, Eye, EyeOff } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const AccountModal = ({ user, authToken, onClose, onAccountUpdated, onAccountDeleted }) => {
  const { isDark } = useTheme();
  const [firstName, setFirstName] = useState(user?.firstName || '');
  const [lastName, setLastName] = useState(user?.lastName || '');
  const [email, setEmail] = useState(user?.email || '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPw, setChangingPw] = useState(false);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState(null);
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteInput, setDeleteInput] = useState('');

  const hasChanges =
    firstName !== (user?.firstName || '') ||
    lastName !== (user?.lastName || '') ||
    email !== (user?.email || '');

  const handleSave = async () => {
    if (!firstName.trim() || !email.trim()) {
      setError('First name and email are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/auth/me`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ firstName: firstName.trim(), lastName: lastName.trim(), email: email.trim() }),
      });
      if (resp.ok) {
        const updated = await resp.json();
        setSaved(true);
        if (onAccountUpdated) onAccountUpdated(updated);
        setTimeout(() => setSaved(false), 2000);
      } else {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || 'Failed to update account.');
      }
    } catch {
      setError('Network error.');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    setPwError(null);
    if (!currentPassword) { setPwError('Enter your current password.'); return; }
    if (newPassword.length < 6) { setPwError('New password must be at least 6 characters.'); return; }
    if (newPassword !== confirmPassword) { setPwError('New passwords do not match.'); return; }
    setChangingPw(true);
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/auth/me/password`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (resp.ok) {
        setPwSuccess(true);
        setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
        setTimeout(() => { setPwSuccess(false); setShowPassword(false); }, 2000);
      } else {
        const data = await resp.json().catch(() => ({}));
        setPwError(data.detail || 'Failed to change password.');
      }
    } catch {
      setPwError('Network error.');
    } finally {
      setChangingPw(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/auth/me`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` },
      });
      if (resp.ok) {
        if (onAccountDeleted) onAccountDeleted();
      } else {
        setError('Failed to delete account.');
        setShowDeleteConfirm(false);
      }
    } catch {
      setError('Network error.');
      setShowDeleteConfirm(false);
    } finally {
      setDeleting(false);
    }
  };

  const overlay = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
  };
  const modal = {
    background: isDark ? '#1f2937' : '#fff',
    borderRadius: 16, padding: 28, width: 420, maxWidth: '92vw',
    boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
    color: isDark ? '#f3f4f6' : '#111827',
  };
  const inputStyle = {
    width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 14,
    border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
    background: isDark ? '#111827' : '#f9fafb',
    color: isDark ? '#f3f4f6' : '#111827', outline: 'none',
    boxSizing: 'border-box',
  };
  const labelStyle = {
    display: 'block', fontSize: 12, fontWeight: 600,
    color: isDark ? '#9ca3af' : '#6b7280', marginBottom: 5,
  };

  if (showDeleteConfirm) {
    return (
      <div style={overlay} onClick={() => setShowDeleteConfirm(false)}>
        <div style={modal} onClick={e => e.stopPropagation()}>
          <div style={{ textAlign: 'center', padding: '8px 0' }}>
            <AlertTriangle size={48} style={{ color: '#ef4444', marginBottom: 14 }} />
            <h3 style={{ margin: '0 0 10px', fontSize: 18 }}>Delete Account?</h3>
            <p style={{ color: isDark ? '#9ca3af' : '#6b7280', fontSize: 13, lineHeight: 1.6, marginBottom: 18 }}>
              This will <strong>permanently</strong> delete your account and all associated data
              (profile, chats, canvas). This action cannot be undone.
            </p>
            <p style={{ fontSize: 13, marginBottom: 10 }}>
              Type <strong>DELETE</strong> to confirm:
            </p>
            <input
              value={deleteInput}
              onChange={e => setDeleteInput(e.target.value)}
              placeholder="DELETE"
              style={{ ...inputStyle, textAlign: 'center', maxWidth: 200, margin: '0 auto 18px' }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                style={{
                  padding: '10px 24px', borderRadius: 10,
                  border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
                  background: 'transparent', color: isDark ? '#d1d5db' : '#374151',
                  fontSize: 14, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteInput !== 'DELETE' || deleting}
                style={{
                  padding: '10px 24px', borderRadius: 10, border: 'none',
                  background: deleteInput === 'DELETE' ? '#ef4444' : (isDark ? '#374151' : '#e5e7eb'),
                  color: deleteInput === 'DELETE' ? '#fff' : (isDark ? '#6b7280' : '#9ca3af'),
                  fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8,
                  cursor: deleteInput === 'DELETE' ? 'pointer' : 'default',
                  opacity: deleting ? 0.7 : 1,
                }}
              >
                {deleting ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Trash2 size={16} />}
                {deleting ? 'Deleting...' : 'Delete Forever'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={overlay} onClick={onClose}>
      <div style={modal} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <User size={22} style={{ color: isDark ? '#60a5fa' : '#3b82f6' }} />
            <h3 style={{ margin: 0, fontSize: 18 }}>Account</h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: isDark ? '#9ca3af' : '#6b7280', padding: 4 }}>
            <X size={20} />
          </button>
        </div>

        {/* Fields */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>First Name</label>
            <input value={firstName} onChange={e => setFirstName(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Last Name</label>
            <input value={lastName} onChange={e => setLastName(e.target.value)} style={inputStyle} />
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={labelStyle}>Email Address</label>
          <div style={{ position: 'relative' }}>
            <Mail size={16} style={{ position: 'absolute', left: 12, top: 12, color: isDark ? '#6b7280' : '#9ca3af' }} />
            <input value={email} onChange={e => setEmail(e.target.value)} type="email" style={{ ...inputStyle, paddingLeft: 36 }} />
          </div>
        </div>

        {/* Change Password */}
        <div style={{
          border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`, borderRadius: 12,
          marginBottom: 20, overflow: 'hidden',
        }}>
          <button
            onClick={() => { setShowPassword(!showPassword); setPwError(null); }}
            style={{
              width: '100%', padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8,
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: isDark ? '#d1d5db' : '#374151', fontSize: 13, fontWeight: 600,
            }}
          >
            <Lock size={15} />
            Change Password
            <span style={{ marginLeft: 'auto' }}>
              {showPassword ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </span>
          </button>
          {showPassword && (
            <div style={{ padding: '0 14px 14px' }}>
              <div style={{ marginBottom: 10 }}>
                <label style={labelStyle}>Current Password</label>
                <div style={{ position: 'relative' }}>
                  <input value={currentPassword} onChange={e => setCurrentPassword(e.target.value)}
                    type={showCurrent ? 'text' : 'password'} style={inputStyle} placeholder="Enter current password" />
                  <button onClick={() => setShowCurrent(!showCurrent)} style={{
                    position: 'absolute', right: 8, top: 8, background: 'none', border: 'none',
                    cursor: 'pointer', color: isDark ? '#6b7280' : '#9ca3af', padding: 2,
                  }}>
                    {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div style={{ marginBottom: 10 }}>
                <label style={labelStyle}>New Password</label>
                <div style={{ position: 'relative' }}>
                  <input value={newPassword} onChange={e => setNewPassword(e.target.value)}
                    type={showNew ? 'text' : 'password'} style={inputStyle} placeholder="At least 6 characters" />
                  <button onClick={() => setShowNew(!showNew)} style={{
                    position: 'absolute', right: 8, top: 8, background: 'none', border: 'none',
                    cursor: 'pointer', color: isDark ? '#6b7280' : '#9ca3af', padding: 2,
                  }}>
                    {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>Confirm New Password</label>
                <input value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                  type={showNew ? 'text' : 'password'} style={inputStyle} placeholder="Re-enter new password" />
              </div>
              {pwError && (
                <div style={{
                  background: isDark ? 'rgba(239,68,68,0.12)' : '#fef2f2',
                  color: '#ef4444', padding: '6px 10px', borderRadius: 8, fontSize: 12, marginBottom: 10,
                }}>{pwError}</div>
              )}
              <button
                onClick={handleChangePassword}
                disabled={changingPw || !currentPassword || !newPassword}
                style={{
                  padding: '8px 20px', borderRadius: 10, border: 'none', fontSize: 13, fontWeight: 600,
                  background: (currentPassword && newPassword) ? '#3b82f6' : (isDark ? '#374151' : '#e5e7eb'),
                  color: (currentPassword && newPassword) ? '#fff' : (isDark ? '#6b7280' : '#9ca3af'),
                  cursor: (currentPassword && newPassword) ? 'pointer' : 'default',
                  display: 'flex', alignItems: 'center', gap: 7, opacity: changingPw ? 0.7 : 1,
                }}
              >
                {changingPw ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> :
                 pwSuccess ? <CheckCircle size={14} /> : <Lock size={14} />}
                {changingPw ? 'Updating...' : pwSuccess ? 'Password Changed!' : 'Update Password'}
              </button>
            </div>
          )}
        </div>

        {error && (
          <div style={{
            background: isDark ? 'rgba(239,68,68,0.12)' : '#fef2f2',
            color: '#ef4444', padding: '8px 12px', borderRadius: 8, fontSize: 13, marginBottom: 14,
          }}>
            {error}
          </div>
        )}

        {/* Save */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            style={{
              padding: '10px 24px', borderRadius: 10, border: 'none',
              background: hasChanges ? '#3b82f6' : (isDark ? '#374151' : '#e5e7eb'),
              color: hasChanges ? '#fff' : (isDark ? '#6b7280' : '#9ca3af'),
              fontSize: 14, fontWeight: 600, cursor: hasChanges ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', gap: 8, opacity: saving ? 0.7 : 1,
            }}
          >
            {saving ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> :
             saved ? <CheckCircle size={16} /> : <Save size={16} />}
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
          </button>

          <button
            onClick={() => setShowDeleteConfirm(true)}
            style={{
              padding: '10px 16px', borderRadius: 10, border: 'none',
              background: 'transparent', color: '#ef4444', fontSize: 13,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Trash2 size={14} />
            Delete Account
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccountModal;
