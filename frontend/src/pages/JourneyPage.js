import React, { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2, Circle, Map, RefreshCw,
  TrendingUp, TrendingDown, Minus, ClipboardCheck,
} from 'lucide-react';
import AppHeader from '../components/AppHeader';
import Sidebar from '../components/Sidebar';
import AboutYouModal from '../components/AboutYouModal';
import ClearDataModal from '../components/ClearDataModal';
import SettingsModal from '../components/SettingsModal';
import useStatedGoal from '../hooks/useStatedGoal';
import '../styles/JourneyPage.css';

const api = (path, token, options = {}) =>
  fetch(`${process.env.REACT_APP_API_URL || ''}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });

const JourneyPage = ({
  user,
  authToken,
  onNavigateToHome,
  onNavigateToChat,
  onNavigateToCanvas,
  onNavigateToJourney,
  onSignOut,
}) => {
  const [tracks, setTracks] = useState([]);
  const [progress, setProgress] = useState(null);
  const [activeTrack, setActiveTrack] = useState(null);
  const [assessments, setAssessments] = useState([]);
  const [showAssessmentForm, setShowAssessmentForm] = useState(false);
  const [newScores, setNewScores] = useState({ confidence: 3, coverage: 3, readiness: 3 });
  const [assessmentNotes, setAssessmentNotes] = useState('');
  const [savingAssessment, setSavingAssessment] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const statedGoal = useStatedGoal(authToken, user);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [showAboutYou, setShowAboutYou] = useState(false);
  const [showClearData, setShowClearData] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState('profile');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tracksResp, meResp, assessResp] = await Promise.all([
        api('/api/journey/tracks', authToken),
        api('/api/journey/me', authToken),
        api('/api/journey/me/assessments', authToken),
      ]);
      if (!tracksResp.ok) throw new Error('Failed to load tracks');
      if (!meResp.ok) throw new Error('Failed to load progress');
      const trackList = await tracksResp.json();
      const me = await meResp.json();
      const list = Array.isArray(trackList) ? trackList : trackList.tracks || [];
      setTracks(list);
      setProgress(me);
      setActiveTrack(list.find((t) => t.id === me.active_track_id) || null);
      if (assessResp.ok) {
        const items = await assessResp.json();
        setAssessments(Array.isArray(items) ? items : []);
      }
    } catch (e) {
      setError(e.message || 'Could not load journey');
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    if (authToken) load();
  }, [authToken, load]);

  const selectTrack = async (trackId) => {
    const resp = await api('/api/journey/me', authToken, {
      method: 'PUT',
      body: JSON.stringify({ active_track_id: trackId }),
    });
    if (resp.ok) await load();
  };

  const toggleItem = async (itemId, checked) => {
    const path = checked
      ? `/api/journey/me/items/${encodeURIComponent(itemId)}/uncomplete`
      : `/api/journey/me/items/${encodeURIComponent(itemId)}/complete`;
    const resp = await api(path, authToken, { method: 'POST' });
    if (resp.ok) {
      const me = await resp.json();
      setProgress(me);
      if (me.active_track_id) {
        setActiveTrack((prev) =>
          prev?.id === me.active_track_id
            ? prev
            : tracks.find((t) => t.id === me.active_track_id) || prev
        );
      }
    }
  };

  const submitAssessment = async () => {
    setSavingAssessment(true);
    try {
      const resp = await api('/api/journey/me/assessments', authToken, {
        method: 'POST',
        body: JSON.stringify({
          scores: newScores,
          notes: assessmentNotes.trim() || null,
        }),
      });
      if (resp.ok) {
        setShowAssessmentForm(false);
        setAssessmentNotes('');
        setNewScores({ confidence: 3, coverage: 3, readiness: 3 });
        await load();
      }
    } finally {
      setSavingAssessment(false);
    }
  };

  const avgScore = (a) => {
    const vals = Object.values(a?.scores || {}).filter((v) => typeof v === 'number');
    if (!vals.length) return null;
    return vals.reduce((s, v) => s + v, 0) / vals.length;
  };

  // Assessments arrive newest-first; trend compares latest vs previous
  const latestAvg = assessments.length > 0 ? avgScore(assessments[0]) : null;
  const prevAvg = assessments.length > 1 ? avgScore(assessments[1]) : null;
  const trendDelta = latestAvg != null && prevAvg != null ? latestAvg - prevAvg : null;

  const checked = new Set(progress?.checked_item_ids || []);

  return (
    <div className="journey-page-with-sidebar">
      <Sidebar
        user={user}
        onNewChat={onNavigateToChat}
        onSignOut={onSignOut}
        authToken={authToken}
        onSidebarToggle={setIsSidebarCollapsed}
        isMobileOpen={isMobileMenuOpen}
        onMobileToggle={setIsMobileMenuOpen}
        onNavigateToCanvas={onNavigateToCanvas}
        onNavigateToJourney={onNavigateToJourney}
        onSelectSession={() => onNavigateToChat()}
        pageContext="journey"
        statedGoal={statedGoal}
        onOpenProfile={() => setShowAboutYou(true)}
        onOpenAccount={() => {
          setSettingsInitialTab('profile');
          setShowSettings(true);
        }}
        onOpenClearData={() => setShowClearData(true)}
        onOpenModelStatus={() => {
          setSettingsInitialTab('model-status');
          setShowSettings(true);
        }}
        onRemoveSampleData={user?.is_guest ? async () => {
          if (!window.confirm('Remove all sample demo data? You stay in guest mode with a clean slate.')) return;
          try {
            const { removeGuestSampleData } = await import('../utils/guestSample');
            await removeGuestSampleData(authToken);
            await load();
            window.alert('Sample data removed.');
          } catch (e) {
            window.alert(e.message || 'Failed to remove sample data');
          }
        } : undefined}
      />
      <div className={`journey-main ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        <AppHeader
          currentPage="journey"
          onNavigateToHome={onNavigateToHome}
          onNavigateToChat={onNavigateToChat}
          onNavigateToCanvas={onNavigateToCanvas}
          onNavigateToJourney={onNavigateToJourney}
          onMobileMenu={() => setIsMobileMenuOpen(true)}
        >
          <button type="button" className="icon-btn" onClick={load} title="Refresh">
            <RefreshCw size={18} />
          </button>
        </AppHeader>

        <div className="journey-content">
          <header className="journey-hero">
            <Map size={28} />
            <div>
              <h1>Security Journey</h1>
              <p>Track progress toward your cybersecurity goals.</p>
            </div>
          </header>

          {error && <p className="journey-error">{error}</p>}
          {loading ? (
            <p>Loading journey…</p>
          ) : (
            <>
              <section className="journey-progress-card">
                <div className="journey-progress-meta">
                  <strong>
                    {progress?.level_name
                      ? `Level ${(progress.level_index ?? 0) + 1} of ${progress.level_count || '?'}: ${progress.level_name}`
                      : 'No track selected'}
                  </strong>
                  <span>
                    {progress?.active_track_id
                      ? `${Math.round(progress.pct_overall || 0)}% overall · ${Math.round(progress.pct_in_level || 0)}% of current level`
                      : 'Pick a track to begin'}
                  </span>
                </div>
                <div className="journey-progress-bar" role="progressbar" aria-valuenow={progress?.pct_overall || 0} aria-valuemin={0} aria-valuemax={100}>
                  <div
                    className="journey-progress-fill"
                    style={{ width: `${Math.min(100, progress?.pct_overall || 0)}%` }}
                  />
                </div>
                {progress?.active_track_id && (
                  <div
                    className="journey-progress-bar journey-progress-bar--level"
                    role="progressbar"
                    aria-label="Current level progress"
                    aria-valuenow={progress?.pct_in_level || 0}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div
                      className="journey-progress-fill journey-progress-fill--level"
                      style={{ width: `${Math.min(100, progress?.pct_in_level || 0)}%` }}
                    />
                  </div>
                )}
              </section>

              <section className="journey-assessments">
                <div className="journey-assessments-head">
                  <h2>
                    <ClipboardCheck size={18} />
                    Self-assessments
                  </h2>
                  <button
                    type="button"
                    className="journey-assess-new"
                    onClick={() => setShowAssessmentForm((v) => !v)}
                  >
                    {showAssessmentForm ? 'Cancel' : 'New assessment'}
                  </button>
                </div>

                {trendDelta != null && (
                  <p className={`journey-trend ${trendDelta > 0 ? 'up' : trendDelta < 0 ? 'down' : 'flat'}`}>
                    {trendDelta > 0 ? <TrendingUp size={16} /> : trendDelta < 0 ? <TrendingDown size={16} /> : <Minus size={16} />}
                    {trendDelta > 0
                      ? `Improving: +${trendDelta.toFixed(1)} since your previous assessment`
                      : trendDelta < 0
                        ? `Down ${Math.abs(trendDelta).toFixed(1)} since your previous assessment`
                        : 'Holding steady since your previous assessment'}
                  </p>
                )}

                {showAssessmentForm && (
                  <div className="journey-assess-form">
                    {Object.entries(newScores).map(([dim, val]) => (
                      <label key={dim} className="journey-assess-slider">
                        <span className="journey-assess-dim">{dim}</span>
                        <input
                          type="range"
                          min={1}
                          max={5}
                          step={1}
                          value={val}
                          onChange={(e) =>
                            setNewScores((prev) => ({ ...prev, [dim]: Number(e.target.value) }))
                          }
                        />
                        <span className="journey-assess-val">{val}/5</span>
                      </label>
                    ))}
                    <textarea
                      rows={2}
                      placeholder="Notes (optional) — what changed since last time?"
                      value={assessmentNotes}
                      onChange={(e) => setAssessmentNotes(e.target.value)}
                    />
                    <button
                      type="button"
                      className="journey-assess-save"
                      disabled={savingAssessment}
                      onClick={submitAssessment}
                    >
                      {savingAssessment ? 'Saving…' : 'Save assessment'}
                    </button>
                  </div>
                )}

                {assessments.length === 0 && !showAssessmentForm ? (
                  <p className="journey-assess-empty">
                    No assessments yet. Rate your confidence, coverage, and readiness to
                    see your trend over time.
                  </p>
                ) : (
                  <ul className="journey-assess-list">
                    {assessments.slice(0, 5).map((a) => {
                      const avg = avgScore(a);
                      return (
                        <li key={a.id}>
                          <span className="journey-assess-date">
                            {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                          </span>
                          <span className="journey-assess-score">
                            {avg != null ? `${avg.toFixed(1)}/5` : '—'}
                          </span>
                          <span className="journey-assess-notes">{a.notes || ''}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>

              <section className="journey-tracks">
                <h2>Tracks</h2>
                <div className="journey-track-grid">
                  {tracks.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={`journey-track-card${progress?.active_track_id === t.id ? ' active' : ''}`}
                      onClick={() => selectTrack(t.id)}
                    >
                      <strong>{t.name}</strong>
                      <span>{t.description}</span>
                    </button>
                  ))}
                </div>
              </section>

              {activeTrack && (
                <section className="journey-levels">
                  <h2>{activeTrack.name}</h2>
                  {(activeTrack.levels || []).map((level) => (
                    <div key={level.id} className="journey-level">
                      <h3>
                        {level.name}
                        {progress?.level_id === level.id ? ' · current' : ''}
                      </h3>
                      <p>{level.description}</p>
                      <ul>
                        {(level.items || []).map((item) => {
                          const isDone = checked.has(item.id);
                          return (
                            <li key={item.id}>
                              <button
                                type="button"
                                className={`journey-check${isDone ? ' done' : ''}`}
                                onClick={() => toggleItem(item.id, isDone)}
                              >
                                {isDone ? <CheckCircle2 size={18} /> : <Circle size={18} />}
                                <span>
                                  <strong>{item.title}</strong>
                                  <em>{item.description}</em>
                                </span>
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </section>
              )}
            </>
          )}
        </div>
      </div>
      {showAboutYou && (
        <AboutYouModal
          authToken={authToken}
          onClose={() => setShowAboutYou(false)}
        />
      )}
      {showSettings && (
        <SettingsModal
          user={user}
          authToken={authToken}
          initialTab={settingsInitialTab}
          onClose={() => setShowSettings(false)}
          onSignOut={onSignOut}
          onUserUpdate={(u) => {
            localStorage.setItem('user', JSON.stringify(u));
          }}
        />
      )}
      {showClearData && (
        <ClearDataModal
          authToken={authToken}
          onClose={() => setShowClearData(false)}
        />
      )}
    </div>
  );
};

export default JourneyPage;
