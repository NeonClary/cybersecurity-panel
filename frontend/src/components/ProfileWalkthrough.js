import React, { useState, useEffect, useMemo } from 'react';
import { X, ChevronLeft, ChevronRight, Check } from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';

const buildSteps = (config) => {
  const knowledgeLevels = (config?.login?.knowledge_levels || config?.login?.academic_stages || [])
    .filter((o) => o.value)
    .map((o) => ({ value: o.value, label: o.label }));

  const timezones = (config?.login?.timezones || [])
    .filter((o) => o.value)
    .map((o) => ({ value: o.value, label: o.label }));

  return [
    {
      title: 'Background',
      fields: [
        {
          key: 'knowledge_level',
          label: 'Cybersecurity knowledge level',
          type: 'select',
          options: knowledgeLevels.length
            ? knowledgeLevels
            : [
                { value: 'newcomer', label: 'New to cybersecurity' },
                { value: 'practitioner', label: 'Practitioner' },
              ],
        },
        {
          key: 'timezone',
          label: 'Time zone',
          type: 'select',
          options: timezones.length
            ? timezones
            : [{ value: 'UTC', label: 'UTC' }],
        },
      ],
    },
    {
      title: 'Role & environment',
      fields: [
        { key: 'cyber_role', label: 'Your role', type: 'select', options: ['Student / Learner', 'Career changer', 'SOC analyst', 'Security engineer', 'Architect / lead', 'Manager / director', 'Consultant', 'Other'] },
        { key: 'organization_type', label: 'Organization type', type: 'select', options: ['Startup', 'Mid-size company', 'Enterprise', 'Government / public sector', 'Education', 'MSP / MSSP', 'Independent / job seeker'] },
      ],
    },
    {
      title: 'Focus & tools',
      fields: [
        { key: 'primary_domains', label: 'Primary domains (comma-separated)', type: 'text', placeholder: 'e.g. cloud, appsec, IR, GRC, identity' },
        { key: 'certifications', label: 'Certifications (comma-separated)', type: 'text', placeholder: 'e.g. Security+, CISSP, OSCP, or none yet' },
        { key: 'tools_stack', label: 'Tools & platforms (comma-separated)', type: 'text', placeholder: 'e.g. Splunk, CrowdStrike, AWS, Jira' },
      ],
    },
    {
      title: 'Goals & learning',
      fields: [
        { key: 'compliance_focus', label: 'Compliance / frameworks', type: 'text', placeholder: 'e.g. SOC 2, NIST CSF, ISO 27001, HIPAA' },
        { key: 'current_goals', label: 'Current goals', type: 'textarea', placeholder: 'Audit prep, cert study, incident readiness, architecture review...' },
        { key: 'learning_preferences', label: 'How you learn best', type: 'text', placeholder: 'Labs, reading, CTFs, mentorship, certifications...' },
      ],
    },
  ];
};

const initFormFromProfile = (steps, profile) => {
  const init = {};
  steps.forEach((s) => s.fields.forEach((f) => {
    const val = profile[f.key];
    if (Array.isArray(val)) init[f.key] = val.join(', ');
    else if (val) init[f.key] = val;
  }));
  return init;
};

const ProfileWalkthrough = ({ authToken, onClose, existingProfile }) => {
  const { config } = useAppConfig();
  const steps = useMemo(() => buildSteps(config), [config]);
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchProfile = async () => {
      try {
        const resp = await fetch(`${process.env.REACT_APP_API_URL}/api/users/me/profile`, {
          headers: { 'Authorization': `Bearer ${authToken}` },
        });
        if (resp.ok && !cancelled) {
          const profile = await resp.json();
          setFormData(initFormFromProfile(steps, profile));
        }
      } catch (e) {
        if (!cancelled && existingProfile) {
          setFormData(initFormFromProfile(steps, existingProfile));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchProfile();
    return () => { cancelled = true; };
  }, [authToken, existingProfile, steps]);

  const handleChange = (key, value) => setFormData((prev) => ({ ...prev, [key]: value }));

  const saveProfile = async () => {
    const payload = { ...formData };
    ['primary_domains', 'certifications', 'tools_stack'].forEach((k) => {
      if (typeof payload[k] === 'string') {
        payload[k] = payload[k].split(',').map((s) => s.trim()).filter(Boolean);
      }
    });
    const hasData = Object.values(payload).some((v) =>
      (Array.isArray(v) ? v.length > 0 : Boolean(v))
    );
    if (!hasData) return;
    try {
      await fetch(`${process.env.REACT_APP_API_URL}/api/users/me/profile`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      console.error('Failed to save profile:', e);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    await saveProfile();
    setSaving(false);
    onClose();
  };

  const handleClose = async () => {
    await saveProfile();
    onClose();
  };

  const currentStep = steps[step];
  const isLast = step === steps.length - 1;

  const renderSelectOptions = (options) => options.map((o) => {
    if (o && typeof o === 'object' && o.value != null) {
      return <option key={o.value} value={o.value}>{o.label}</option>;
    }
    return <option key={o} value={o}>{o}</option>;
  });

  return (
    <div onClick={handleClose} style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: 'var(--bg-primary)', borderRadius: 16,
        width: '90%', maxWidth: 480, padding: 24,
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)', fontSize: 14 }}>
            Loading profile...
          </div>
        ) : <>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 16, color: 'var(--text-primary)' }}>
            {currentStep.title} ({step + 1}/{steps.length})
          </h3>
          <button onClick={handleClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ height: 4, background: 'var(--bg-secondary)', borderRadius: 2, marginBottom: 20 }}>
          <div style={{
            height: '100%', borderRadius: 2, background: 'var(--accent-primary)',
            width: `${((step + 1) / steps.length) * 100}%`, transition: 'width 0.3s',
          }} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {currentStep.fields.map((f) => (
            <div key={f.key}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>
                {f.label}
              </label>
              {f.type === 'select' ? (
                <select
                  value={formData[f.key] || ''}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  style={{
                    width: '100%', padding: '8px 10px', borderRadius: 8,
                    border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
                    color: 'var(--text-primary)', fontSize: 13,
                  }}
                >
                  <option value="">Select...</option>
                  {renderSelectOptions(f.options)}
                </select>
              ) : f.type === 'textarea' ? (
                <textarea
                  value={formData[f.key] || ''}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  rows={3}
                  style={{
                    width: '100%', padding: '8px 10px', borderRadius: 8,
                    border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
                    color: 'var(--text-primary)', fontSize: 13, resize: 'vertical',
                  }}
                />
              ) : (
                <input
                  type="text"
                  value={formData[f.key] || ''}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  style={{
                    width: '100%', padding: '8px 10px', borderRadius: 8,
                    border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
                    color: 'var(--text-primary)', fontSize: 13,
                  }}
                />
              )}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            style={{
              display: 'flex', alignItems: 'center', gap: 4, padding: '8px 14px',
              borderRadius: 8, border: '1px solid var(--border-primary)',
              background: 'var(--bg-secondary)', color: 'var(--text-primary)',
              cursor: step === 0 ? 'default' : 'pointer', opacity: step === 0 ? 0.4 : 1,
              fontSize: 13,
            }}
          >
            <ChevronLeft size={14} /> Back
          </button>
          {isLast ? (
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                display: 'flex', alignItems: 'center', gap: 4, padding: '8px 16px',
                borderRadius: 8, border: 'none',
                background: 'var(--accent-primary)', color: '#fff',
                cursor: 'pointer', fontSize: 13, fontWeight: 600,
              }}
            >
              <Check size={14} /> {saving ? 'Saving...' : 'Save Profile'}
            </button>
          ) : (
            <button
              onClick={() => setStep((s) => s + 1)}
              style={{
                display: 'flex', alignItems: 'center', gap: 4, padding: '8px 14px',
                borderRadius: 8, border: 'none',
                background: 'var(--accent-primary)', color: '#fff',
                cursor: 'pointer', fontSize: 13, fontWeight: 600,
              }}
            >
              Next <ChevronRight size={14} />
            </button>
          )}
        </div>
        </>}
      </div>
    </div>
  );
};

export default ProfileWalkthrough;
