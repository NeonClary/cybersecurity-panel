import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Circle, Map, RefreshCw } from 'lucide-react';
import AppHeader from '../components/AppHeader';
import Sidebar from '../components/Sidebar';
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tracksResp, meResp] = await Promise.all([
        api('/api/journey/tracks', authToken),
        api('/api/journey/me', authToken),
      ]);
      if (!tracksResp.ok) throw new Error('Failed to load tracks');
      if (!meResp.ok) throw new Error('Failed to load progress');
      const trackList = await tracksResp.json();
      const me = await meResp.json();
      const list = Array.isArray(trackList) ? trackList : trackList.tracks || [];
      setTracks(list);
      setProgress(me);
      setActiveTrack(list.find((t) => t.id === me.active_track_id) || null);
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
                  <strong>{progress?.level_name || 'No track selected'}</strong>
                  <span>
                    {typeof progress?.pct_overall === 'number'
                      ? `${Math.round(progress.pct_overall)}% overall`
                      : 'Pick a track to begin'}
                  </span>
                </div>
                <div className="journey-progress-bar" role="progressbar" aria-valuenow={progress?.pct_overall || 0} aria-valuemin={0} aria-valuemax={100}>
                  <div
                    className="journey-progress-fill"
                    style={{ width: `${Math.min(100, progress?.pct_overall || 0)}%` }}
                  />
                </div>
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
    </div>
  );
};

export default JourneyPage;
