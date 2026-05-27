import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  SquarePen,
  Search,
  MoreVertical,
  Trash2,
  LogOut,
  User,
  UserCircle,
  DatabaseZap,
  KeyRound,
  PanelLeft,
  FileText,
  ChevronRight,
  Clock
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';
import UserAvatarPicker from './UserAvatarPicker';
import CopyrightNotice from './CopyrightNotice';
import '../styles/Sidebar.css';

const Sidebar = ({
  user,
  currentSessionId,
  onSelectSession,
  onNewChat,
  onSignOut,
  authToken,
  onSidebarToggle,
  isMobileOpen = false,
  onMobileToggle,
  refreshTrigger,
  onCurrentSessionDeleted,
  pageContext = 'chat',
  canvasItems = [],
  canvasSubview = 'workspace',
  widgetGroups = [],
  deliverableProjects = [],
  insightSections = [],
  userAvatarId,
  onAvatarChange,
  onOpenProfile,
  onOpenAccount,
  onOpenClearData,
}) => {
  const { config } = useAppConfig();
  const isOnCanvas = pageContext === 'canvas';
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const avatarOptions = config?.app?.user_avatars || [];
  const currentAvatar = avatarOptions.find(a => a.id === userAvatarId);
  const AvatarIcon = currentAvatar ? (LucideIcons[currentAvatar.icon] || User) : User;
  const [expanded, setExpanded] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sidebar-expanded-v1') || '{}'); } catch { return {}; }
  });
  const toggleExpanded = (key) => {
    setExpanded(prev => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem('sidebar-expanded-v1', JSON.stringify(next));
      return next;
    });
  };
  const [chatSessions, setChatSessions] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isCreatingNewChat, setIsCreatingNewChat] = useState(false);

  useEffect(() => {
    if (authToken) {
      fetchChatSessions();
    }
  }, [authToken]);

  useEffect(() => {
    const handleOverlayClick = (e) => {
      // Only close if clicking the overlay itself, not the sidebar
      if (e.target.classList.contains('mobile-sidebar-overlay')) {
        onMobileToggle(false);
      }
    };

    if (isMobileOpen) {
      document.addEventListener('click', handleOverlayClick);
      return () => document.removeEventListener('click', handleOverlayClick);
    }
  }, [isMobileOpen, onMobileToggle]);

  // Notify parent when sidebar state changes
  useEffect(() => {
    if (onSidebarToggle) {
      onSidebarToggle(isCollapsed);
    }
  }, [isCollapsed, onSidebarToggle]);

  // Add effect to refresh when currentSessionId changes (new session created)
  useEffect(() => {
    if (currentSessionId && authToken) {
      // Small delay to ensure the session is saved to database
      const timer = setTimeout(() => {
        fetchChatSessions();
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [currentSessionId, authToken]);

  // Refresh session list when parent signals a message exchange completed
  useEffect(() => {
    if (refreshTrigger > 0 && authToken) {
      fetchChatSessions();
    }
  }, [refreshTrigger]);


  const fetchChatSessions = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chat-sessions`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const sessions = await response.json();
        setChatSessions(sessions);
      } else {
        console.error('Failed to fetch chat sessions');
      }
    } catch (error) {
      console.error('Error fetching chat sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = async () => {
    setIsCreatingNewChat(true);
    
    try {
      // Call the parent's new chat handler and wait for it to complete
      await onNewChat();
      
      // Refresh the sessions list immediately after new chat is created
      // The parent should have updated currentSessionId by now
      await fetchChatSessions();
      
    } catch (error) {
      console.error('Error creating new chat:', error);
      // Optionally show an error message to the user
    } finally {
      setIsCreatingNewChat(false);
    }
  };

  const handleDeleteSession = async (sessionId, event) => {
    event.stopPropagation();
    
    if (window.confirm('Are you sure you want to delete this chat?')) {
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chat-sessions/${sessionId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          setChatSessions(prev => prev.filter(session => session.id !== sessionId));
          if (currentSessionId === sessionId) {
            onCurrentSessionDeleted?.();
          }
        }
      } catch (error) {
        console.error('Error deleting chat session:', error);
      }
    }
  };

  const toggleSidebar = () => {
    setIsCollapsed(!isCollapsed);
    // Close user menu when collapsing
    if (!isCollapsed) {
      setShowUserMenu(false);
    }
  };

  const filteredSessions = chatSessions.filter(session =>
    session.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 1) return 'Today';
    if (diffDays === 2) return 'Yesterday';
    if (diffDays <= 7) return `${diffDays - 1} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <>
      <div className={`sidebar ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : ''}`}>
        {/* Header */}
        <div className="sidebar-header">
          {!isCollapsed && (
            <>
              <div className="user-section">
                <div className="user-info">
                  <div
                    className="user-avatar"
                    onClick={() => onAvatarChange && setShowAvatarPicker(true)}
                    style={{
                      cursor: onAvatarChange ? 'pointer' : undefined,
                      backgroundColor: currentAvatar?.bg || undefined,
                      color: currentAvatar?.color || undefined,
                    }}
                    title={onAvatarChange ? 'Change avatar' : undefined}
                  >
                    <AvatarIcon size={20} />
                  </div>
                  <div className="user-details">
                    <span className="user-name">{user.firstName} {user.lastName}</span>
                    <span className="user-email">{user.email}</span>
                  </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {/* Toggle button next to user menu when expanded */}
                  <button 
                    className="sidebar-toggle"
                    onClick={toggleSidebar} 
                    title="Collapse sidebar"
                  >
                    <PanelLeft size={18} />
                  </button>
                  
                  <div className="user-menu-container">
                    <button 
                      className="user-menu-button"
                      onClick={() => setShowUserMenu(!showUserMenu)}
                    >
                      <MoreVertical size={16} />
                    </button>
                    
                    {showUserMenu && (
                      <div className="user-menu">
                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); setShowAvatarPicker(true); }}>
                          <User size={16} />
                          <span>Change Avatar</span>
                        </button>
                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); if (onOpenProfile) onOpenProfile(); }}>
                          <UserCircle size={16} />
                          <span>Profile</span>
                        </button>
                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); if (onOpenAccount) onOpenAccount(); }}>
                          <KeyRound size={16} />
                          <span>Account</span>
                        </button>
                        <button className="user-menu-item" onClick={() => { setShowUserMenu(false); if (onOpenClearData) onOpenClearData(); }}>
                          <DatabaseZap size={16} />
                          <span>Clear User Data</span>
                        </button>
                        <button className="user-menu-item sign-out" onClick={onSignOut}>
                          <LogOut size={16} />
                          <span>Sign Out</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

            </>
          )}

          {isCollapsed && (
            <div className="collapsed-header">
              {/* Toggle button replaces user avatar when collapsed */}
              <button 
                className="collapsed-toggle-avatar"
                onClick={toggleSidebar} 
                title="Expand sidebar"
              >
                <PanelLeft size={20} />
              </button>
              <button
                className="collapsed-new-chat"
                onClick={handleNewChat}
                title="New Chat"
                disabled={isCreatingNewChat}
              >
                <SquarePen size={20} />
              </button>
            </div>
          )}
        </div>

        {/* Search + New Chat - only show when expanded */}
        {!isCollapsed && (
          <div className="sidebar-search">
            <div className="search-container">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder={
                  isOnCanvas
                    ? (canvasSubview === 'deliverables' ? 'Search drafts...'
                       : canvasSubview === 'insights' ? 'Search sections...'
                       : 'Search widgets...')
                    : 'Search chats...'
                }
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="search-input"
              />
            </div>
            {!isOnCanvas && (
              <button
                className="new-chat-icon-btn"
                onClick={handleNewChat}
                disabled={isCreatingNewChat}
                title={isCreatingNewChat ? 'Creating...' : 'New Chat'}
              >
                <SquarePen size={18} />
              </button>
            )}
          </div>
        )}

        {/* Canvas sidebar — subview-aware (Insights / Workspace / Deliverables) */}
        {isOnCanvas ? (
          <div className="canvas-sidebar-menu">
            {!isCollapsed && (() => {
              const q = searchTerm.toLowerCase();

              // ---------- DELIVERABLES: project list with expandable section dropdown ----------
              if (canvasSubview === 'deliverables') {
                const projects = deliverableProjects.filter(p =>
                  !q || p.name.toLowerCase().includes(q) || p.sections.some(s => s.name.toLowerCase().includes(q))
                );
                if (projects.length === 0) {
                  return (
                    <div className="no-sessions">
                      {searchTerm ? 'No drafts match' : 'No drafts yet — create one in Documents'}
                    </div>
                  );
                }
                return projects.map(p => {
                  const open = expanded[`p-${p.id}`] ?? p.isActive;
                  const totalWords = p.sections.reduce((s, x) => s + x.wc, 0);
                  return (
                    <div key={p.id} className={`csm-project ${p.isActive ? 'active' : ''}`}>
                      <button
                        className="csm-project-head"
                        onClick={() => toggleExpanded(`p-${p.id}`)}
                      >
                        <ChevronRight size={12} className={`csm-chevron ${open ? 'open' : ''}`}/>
                        <FileText size={13}/>
                        <span className="csm-project-name">{p.name}</span>
                        {p.versions > 0 && (
                          <span className="csm-versions" title={`${p.versions} version${p.versions === 1 ? '' : 's'} saved`}>
                            <Clock size={10}/>{p.versions}
                          </span>
                        )}
                      </button>
                      {open && (
                        <div className="csm-project-body">
                          <button className="csm-row" onClick={p.onOpen}>
                            <span className="csm-row-icon">📂</span>
                            <span>Open editor</span>
                          </button>
                          {p.sections.map(s => (
                            <button key={s.id} className="csm-row csm-row-section" onClick={s.onClick}>
                              <span className="csm-row-bullet"/>
                              <span className="csm-row-label">{s.name}</span>
                              {s.wc > 0 && <span className="csm-row-meta">{s.wc}</span>}
                            </button>
                          ))}
                          <div className="csm-row csm-row-foot">
                            <Clock size={11}/>
                            <span>{p.versions} version{p.versions === 1 ? '' : 's'} · auto-saved</span>
                          </div>
                          <div className="csm-row csm-row-foot">
                            <span style={{ color: 'var(--text-tertiary, #9CA3AF)' }}>{totalWords} words total</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                });
              }

              // ---------- WORKSPACE: widgets grouped by category ----------
              if (canvasSubview === 'workspace') {
                const groups = widgetGroups
                  .map(g => ({
                    ...g,
                    items: g.items.filter(it => !q || it.label.toLowerCase().includes(q)),
                  }))
                  .filter(g => g.items.length > 0);
                if (groups.length === 0) {
                  return (
                    <div className="no-sessions">
                      {searchTerm ? 'No widgets match' : 'Workspace is empty — add widgets'}
                    </div>
                  );
                }
                return groups.map(g => {
                  const open = expanded[`g-${g.id}`] ?? true;
                  return (
                    <div key={g.id} className="csm-group">
                      <button className="csm-group-head" onClick={() => toggleExpanded(`g-${g.id}`)}>
                        <ChevronRight size={11} className={`csm-chevron ${open ? 'open' : ''}`}/>
                        <span className="csm-group-name">{g.label}</span>
                        <span className="csm-group-count">{g.items.length}</span>
                      </button>
                      {open && (
                        <div className="csm-group-body">
                          {g.items.map(it => (
                            <button key={it.id} className={`csm-row ${it.critic ? 'critic' : ''}`} onClick={it.onClick}>
                              <span className="csm-row-bullet"/>
                              <span className="csm-row-label">{it.label}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                });
              }

              // ---------- INSIGHTS: section list with confidence badges ----------
              if (canvasSubview === 'insights') {
                const sections = insightSections.filter(s => !q || s.name.toLowerCase().includes(q));
                if (sections.length === 0) {
                  return <div className="no-sessions">{searchTerm ? 'No sections match' : 'No insights yet'}</div>;
                }
                return (
                  <div className="csm-group">
                    <div className="csm-group-head" style={{ cursor: 'default' }}>
                      <span className="csm-group-name">Sections</span>
                      <span className="csm-group-count">{sections.length}</span>
                    </div>
                    <div className="csm-group-body">
                      {sections.map(s => {
                        const complete = s.taskCount > 0 && s.doneCount === s.taskCount;
                        return (
                          <button key={s.id} className={`csm-row ${complete ? 'csm-row-done' : ''}`} onClick={s.onClick}>
                            <span className="csm-row-bullet"/>
                            <span className="csm-row-label">{s.name}</span>
                            {s.taskCount > 0 && (
                              <span className="csm-row-meta">{s.doneCount}/{s.taskCount}</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              }

              // ---------- Fallback: flat list (legacy) ----------
              const items = canvasItems.filter(it => !q || it.label.toLowerCase().includes(q));
              if (items.length === 0) {
                return <div className="no-sessions">{searchTerm ? 'No matches' : 'Nothing here yet'}</div>;
              }
              return (
                <div className="sessions-list">
                  {items.map((it) => (
                    <div key={it.id} className="session-item" onClick={it.onClick}>
                      <div className="session-content">
                        <div className="session-icon"><FileText size={16}/></div>
                        <div className="session-details">
                          <div className="session-title">{it.label}</div>
                          {it.sub && <div className="session-meta"><span>{it.sub}</span></div>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        ) : (
        /* Chat Sessions */
        <div className="chat-sessions">
          {isLoading ? (
            <div className="loading-sessions">
              <div className="loading-spinner"></div>
              {!isCollapsed && <span>Loading chats...</span>}
            </div>
          ) : isCreatingNewChat ? (
            <div className="loading-sessions">
              <div className="loading-spinner"></div>
              {!isCollapsed && <span>Creating new chat...</span>}
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="no-sessions">
              {!isCollapsed && (searchTerm ? 'No chats found' : 'No chats yet')}
            </div>
          ) : (
            <div className="sessions-list">
              {filteredSessions.map((session) => (
                <div
                  key={session.id}
                  className={`session-item ${currentSessionId === session.id ? 'active' : ''} ${isCollapsed ? 'collapsed' : ''}`}
                  onClick={() => onSelectSession(session.id)}
                  title={isCollapsed ? session.title : ''}
                >
                  <div className="session-content">
                    <div className="session-icon">
                      <MessageSquare size={16} />
                    </div>
                    {!isCollapsed && (
                      <div className="session-details">
                        <div className="session-title">{session.title}</div>
                        <div className="session-meta">
                          <span className="session-date">{formatDate(session.updated_at)}</span>
                          <span className="session-messages">{session.message_count} messages</span>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {!isCollapsed && (
                    <button
                      className="session-menu-button"
                      onClick={(e) => handleDeleteSession(session.id, e)}
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        )}

        {/* Footer */}
        <div className={`sidebar-footer ${isCollapsed ? 'collapsed' : ''}`}>
          <a 
            href="https://neon.ai" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="sidebar-neon-link"
            title="Neon.ai"
          >
            <img src="/neon-logo.png" alt="" className="sidebar-neon-logo" />
            {!isCollapsed && <span className="sidebar-neon-text">Neon.ai</span>}
          </a>
          {!isCollapsed && <CopyrightNotice variant="sidebar" />}
        </div>
      </div>
      
      {showAvatarPicker && (
        <UserAvatarPicker
          options={avatarOptions}
          currentId={userAvatarId}
          onSelect={(id) => { onAvatarChange?.(id); setShowAvatarPicker(false); }}
          onClose={() => setShowAvatarPicker(false)}
        />
      )}

      {isMobileOpen && (
        <div 
          className="mobile-sidebar-overlay visible" 
          onClick={() => onMobileToggle(false)}
        />
      )}
    </>
  );
};

export default Sidebar;