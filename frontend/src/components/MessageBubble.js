import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Reply, Copy, Check, Maximize2, FileText, Hash, Target, Volume2, VolumeX, Search, X, Loader2, Globe } from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';
import { useTheme } from '../contexts/ThemeContext';
import {
  buildReferenceSearchQuery,
  buildPerplexityUrl,
  buildWebSearchUrl,
  getWebSearchEngine,
  setWebSearchEngine,
  WEB_SEARCH_ENGINES,
} from '../utils/referenceSearch';
const stripMarkdown = (md) => {
  if (!md) return '';
  return md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/#{1,6}\s?/g, '')
    .replace(/[*_~]{1,3}([^*_~]+)[*_~]{1,3}/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/[-*+]\s/g, '')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .trim();
};

const MessageBubble = ({ 
  message, 
  onReply, 
  onCopy, 
  onExpand,
  onSearchReferences,
  onReferenceSearchOpened,
  userQuestion = '',
  showReplyButton = false,
  inlineAvatar = false,
  userAvatarId,
  userAvatarOptions
}) => {
  const { isDark } = useTheme();
  const { allPersonas: advisors, getAllPersonaColors: getAdvisorColors } = useAppConfig();
  const [showTooltip, setShowTooltip] = useState(null);
  const [copiedStates, setCopiedStates] = useState({});
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isLoadingTTS, setIsLoadingTTS] = useState(false);
  const [searchPopover, setSearchPopover] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [promptCopied, setPromptCopied] = useState(false);
  const [webEngineId, setWebEngineId] = useState(() => getWebSearchEngine().id);
  const [bodyExpanded, setBodyExpanded] = useState(false);
  const overlayRef = useRef(null);
  const tooltipTimer = useRef(null);
  const audioRef = useRef(null);
  const SHOW_MORE_CHARS = 1100;

  const handleSpeak = useCallback(async (content) => {
    if (isSpeaking || isLoadingTTS) {
      if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
      setIsSpeaking(false);
      setIsLoadingTTS(false);
      return;
    }
    const text = (content || '').trim();
    if (!text) return;
    setIsLoadingTTS(true);
    try {
      const token = localStorage.getItem('authToken');
      const resp = await fetch(`${process.env.REACT_APP_API_URL}/voice/tts`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!resp.ok) throw new Error('TTS failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      setIsLoadingTTS(false);
      setIsSpeaking(true);
      audio.onended = () => { setIsSpeaking(false); URL.revokeObjectURL(url); audioRef.current = null; };
      audio.onerror = () => { setIsSpeaking(false); URL.revokeObjectURL(url); audioRef.current = null; };
      audio.play();
    } catch (e) {
      console.error('TTS error:', e);
      setIsLoadingTTS(false);
      setIsSpeaking(false);
    }
  }, [isSpeaking, isLoadingTTS]);

  useEffect(() => {
    return () => { if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; } };
  }, []);

  const handleCopy = async (messageId, content) => {
    try {
      await navigator.clipboard.writeText(content || '');
      setCopiedStates(prev => ({ ...prev, [messageId]: true }));
      if (onCopy) onCopy(messageId, content || '');
      setTimeout(() => {
        setCopiedStates(prev => ({ ...prev, [messageId]: false }));
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const handleExpand = (messageId, persona_id) => {
    if (onExpand) onExpand(messageId, persona_id);
  };

  const handleSearch = () => {
    const content = message?.compact_markdown || message?.content || '';
    const advisor = advisors[
      message?.persona_id || message?.personaId || message?.advisor_id || message?.advisorId
    ] || {};
    const query = buildReferenceSearchQuery({
      advisorText: content,
      userQuestion,
      advisorName: advisor.name || message?.advisorName || '',
    });
    setSearchQuery(query);
    setSearchPopover(true);
    if (onSearchReferences) onSearchReferences(message, query);
  };

  const openExternalSearch = (kind) => {
    const url = kind === 'perplexity'
      ? buildPerplexityUrl(searchQuery)
      : buildWebSearchUrl(searchQuery, webEngineId);
    window.open(url, '_blank', 'noopener,noreferrer');
    if (onReferenceSearchOpened) {
      onReferenceSearchOpened({ source: kind, query: searchQuery });
    }
  };

  const handleEngineChange = (id) => {
    const engine = setWebSearchEngine(id);
    setWebEngineId(engine.id);
  };

  const showTooltipWithDelay = (tooltipType) => {
    clearTimeout(tooltipTimer.current);
    tooltipTimer.current = setTimeout(() => setShowTooltip(tooltipType), 500);
  };

  const hideTooltip = () => {
    clearTimeout(tooltipTimer.current);
    setShowTooltip(null);
  };

  // Minimal, safe preprocessing (keep Markdown structure intact)
  const preprocessMarkdown = (content) => {
    const input = (content || '').toString();

    // 1) Strip trailing sentinel
    let processed = input.replace(/\s*<\/END>\s*$/i, '');

    // 2) Normalize EOL and trim right spaces (preserve newlines)
    processed = processed.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    processed = processed.split('\n').map(ln => ln.replace(/\s+$/, '')).join('\n');

    // 3) Unicode bullets -> '-' (so GFM parses lists)
    processed = processed.replace(/^\s*[•●▪◦]\s+/gm, '- ');

    // 4) Merge orphan numbered items: "1.\nText" => "1. Text"
    processed = processed.replace(/(^\s*(\d+)\.\s*$)\n^\s*(\S.*)$/gm, (_m, _a, num, next) => `${num}. ${next}`);

    // 5) Collapse 3+ blank lines to 2
    processed = processed.replace(/\n{3,}/g, '\n\n');

    return processed.trim();
  };

  // ENHANCED MARKDOWN COMPONENTS WITH BETTER STYLING
  const markdownComponents = {
    // Keep <strong> INLINE to avoid breaking paragraphs/lists
    strong: ({ children }) => (
      <strong style={{ 
        fontWeight: '700',
        color: isDark ? '#ffffff' : '#1f2937'
      }}>
        {children}
      </strong>
    ),
    
    // Italic text styling
    em: ({ children }) => (
      <em style={{ 
        fontStyle: 'italic',
        color: 'var(--accent-primary)',
        fontWeight: '500'
      }}>
        {children}
      </em>
    ),
    
    // Paragraph styling with proper spacing
    p: ({ children }) => (
      <p style={{ 
        marginBottom: '0.75rem',
        lineHeight: '1.7',
        color: isDark ? '#e5e7eb' : '#111827'
      }}>
        {children}
      </p>
    ),

    // Unordered list styling
    ul: ({ children }) => (
      <ul style={{ 
        listStyleType: 'disc',
        paddingLeft: '1.5rem',
        marginBottom: '1rem',
        marginTop: '0.5rem',
        color: isDark ? '#e5e7eb' : '#374151'
      }}>
        {children}
      </ul>
    ),
    
    // Ordered list styling with better spacing
    ol: ({ children }) => (
      <ol style={{ 
        listStyleType: 'decimal',
        paddingLeft: '1.5rem',
        marginBottom: '1rem',
        marginTop: '0.5rem',
        color: isDark ? '#e5e7eb' : '#374151',
        counterReset: 'list-counter'
      }}>
        {children}
      </ol>
    ),
    
    // List item styling with proper spacing
    li: ({ children }) => (
      <li style={{ 
        marginBottom: '0.75rem',
        lineHeight: '1.6',
      }}>
        {children}
      </li>
    ),
    
    // Inline code styling
    code: ({ inline, children }) => (
      inline ? (
        <code style={{ 
          backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
          padding: '0.2rem 0.35rem',
          borderRadius: '4px',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
          fontSize: '0.875rem'
        }}>
          {children}
        </code>
      ) : (
        <pre style={{ 
          backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
          padding: '0.85rem',
          borderRadius: '8px',
          overflowX: 'auto',
          margin: '0.5rem 0 1rem'
        }}>
          <code>
            {children}
          </code>
        </pre>
      )
    )
  };

  // USER MESSAGE
  if (message.type === 'user') {
    const uAvatar = userAvatarOptions?.find(a => a.id === userAvatarId);
    const UserIcon = uAvatar
      ? (LucideIcons[uAvatar.icon] || LucideIcons.User)
      : null;

    return (
      <div className="user-message-container">
        <div className="user-message">
          {message.replyTo && (
            <div className="reply-indicator">
              <Reply size={14} />
              <span>to {message.replyTo.advisorName}</span>
            </div>
          )}
          <p>{message.content}</p>
        </div>
        {UserIcon && (
          <div style={{
            width: 32, height: 32, borderRadius: '50%', flexShrink: 0, marginLeft: 8,
            backgroundColor: uAvatar.bg, color: uAvatar.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <UserIcon size={16} />
          </div>
        )}
      </div>
    );
  }

  // ADVISOR MESSAGE
  if (message.type === 'advisor') {
    const personaId =
      message?.persona_id ||
      message?.personaId ||
      message?.advisor_id ||
      message?.advisorId ||
      (typeof message?.advisor === 'string' ? message.advisor : undefined) ||
      'methodologist';

    const advisor = advisors[personaId] || advisors[message.persona_id] || {};
    const Icon = advisor.icon;
    const colors = getAdvisorColors(personaId, isDark);
    const isCopied = copiedStates[message.id];

    const avatarElement = (size = 44) => {
      const iconSize = Math.round(size * 0.52);
      return (
        <div
          className="advisor-message-avatar-ring"
          style={{ width: size, height: size }}
        >
          {advisor.avatarUrl ? (
            <img
              src={advisor.avatarUrl}
              alt={advisor.name || 'Advisor'}
            />
          ) : Icon ? (
            <Icon
              className="advisor-message-avatar-icon"
              style={{
                color: colors.color || 'var(--text-secondary)',
                width: iconSize,
                height: iconSize,
              }}
            />
          ) : (
            <span
              className="advisor-message-avatar-initial"
              style={{ color: colors.color || 'var(--text-secondary)', fontSize: iconSize }}
            >
              {advisor.name ? advisor.name.charAt(0) : 'A'}
            </span>
          )}
        </div>
      );
    };

    return (
      <div className={`advisor-message-container ${inlineAvatar ? 'inline-avatar-mode' : ''}`}>
        {!inlineAvatar && (
          <div 
            className="advisor-avatar" 
            style={{ backgroundColor: colors.bgColor || 'var(--bg-muted)', overflow: 'hidden' }}
          >
          </div>
        )}

        <div 
          className="advisor-message-bubble"
          style={{ 
            backgroundColor: colors.bgColor || 'var(--bg-primary)',
            borderColor: (colors.color ? colors.color + '40' : 'var(--border-muted)'),
            position: 'relative'
          }}
        >
          <div className="advisor-message-header">
            {inlineAvatar && avatarElement(44)}
            <h4 
              className="advisor-message-name" 
              style={{ color: colors.color || 'var(--text-primary)' }}
            >
              {advisor.name || message.advisorName || 'Advisor'}
              {message.isReply && <span className="reply-badge">↳ Reply</span>}
              {message.isExpansion && <span className="expansion-badge">⤴ Expanded</span>}
            </h4>
            <span 
              className="message-time"
              style={{ 
                color: colors.color || 'var(--text-secondary)',
                opacity: 0.7 
              }}
            >
              {message.timestamp?.toLocaleTimeString
                ? message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : ''}
            </span>
          </div>
          
          {/* Enhanced markdown rendering with preprocessing — full body text, no ellipsis clip */}
          {(() => {
            const markdownBody = preprocessMarkdown(
              message?.compact_markdown || message?.content || message?.text
            );
            const isLongBody = !message?.streaming && markdownBody.length > SHOW_MORE_CHARS;
            const collapsed = isLongBody && !bodyExpanded;
            return (
              <>
                <div
                  className={`advisor-message-text${collapsed ? ' is-collapsed' : ''}`}
                  style={{ color: colors.textColor || (isDark ? '#e5e7eb' : '#111827') }}
                >
                  <ReactMarkdown
                    components={markdownComponents}
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[]}
                  >
                    {markdownBody}
                  </ReactMarkdown>
                </div>
                {isLongBody && (
                  <button
                    type="button"
                    className="message-show-more"
                    onClick={() => setBodyExpanded((v) => !v)}
                    style={{ color: colors.color || 'var(--accent-primary)' }}
                  >
                    {bodyExpanded ? 'Show less' : 'Show more'}
                  </button>
                )}
              </>
            );
          })()}
          
          {showReplyButton && (
            <div className="message-actions">
              <div className="message-action-buttons">
                <div className="tooltip-container">
                  <button 
                    className="message-action-button"
                    onClick={() => onReply && onReply(message)}
                    onMouseEnter={() => showTooltipWithDelay('reply')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: colors.color || 'var(--text-secondary)',
                      borderColor: (colors.color ? colors.color + '40' : 'var(--border-muted)')
                    }}
                  >
                    <Reply size={14} stroke="currentColor" fill="none" />
                  </button>
                  {showTooltip === 'reply' && (
                    <div className="tooltip">Reply to this message</div>
                  )}
                </div>

                <div className="tooltip-container">
                  <button 
                    className="message-action-button"
                    onClick={() => handleCopy(message.id, message?.compact_markdown || message?.content || '')}
                    onMouseEnter={() => showTooltipWithDelay('copy')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: isCopied ? '#10B981' : (colors.color || 'var(--text-secondary)'),
                      borderColor: isCopied ? '#10B98140' : (colors.color ? colors.color + '40' : 'var(--border-muted)')
                    }}
                  >
                    {isCopied ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                  {showTooltip === 'copy' && (
                    <div className="tooltip">
                      {isCopied ? 'Copied!' : 'Copy to clipboard'}
                    </div>
                  )}
                </div>

                <div className="tooltip-container">
                  <button 
                    className="message-action-button"
                    onClick={() => handleExpand(message.id, personaId)}
                    onMouseEnter={() => showTooltipWithDelay('expand')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: colors.color || 'var(--text-secondary)',
                      borderColor: (colors.color ? colors.color + '40' : 'var(--border-muted)')
                    }}
                  >
                    <Maximize2 size={14} />
                  </button>
                  {showTooltip === 'expand' && (
                    <div className="tooltip">More</div>
                  )}
                </div>

                <div className="tooltip-container">
                  <button 
                    className="message-action-button"
                    onClick={() => handleSpeak(message?.compact_markdown || message?.content || '')}
                    onMouseEnter={() => showTooltipWithDelay('speak')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: isLoadingTTS ? (colors.color || 'var(--text-secondary)') : isSpeaking ? '#EF4444' : (colors.color || 'var(--text-secondary)'),
                      borderColor: isSpeaking ? '#EF444440' : (colors.color ? colors.color + '40' : 'var(--border-muted)'),
                      opacity: isLoadingTTS ? 0.7 : 1,
                    }}
                  >
                    {isLoadingTTS ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : isSpeaking ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  </button>
                  {showTooltip === 'speak' && (
                    <div className="tooltip">{isLoadingTTS ? 'Loading audio...' : isSpeaking ? 'Stop speaking' : 'Speak it'}</div>
                  )}
                </div>

                <div className="tooltip-container">
                  <button 
                    className="message-action-button"
                    onClick={handleSearch}
                    onMouseEnter={() => showTooltipWithDelay('search')}
                    onMouseLeave={hideTooltip}
                    style={{ 
                      color: colors.color || 'var(--text-secondary)',
                      borderColor: (colors.color ? colors.color + '40' : 'var(--border-muted)')
                    }}
                  >
                    <Search size={14} />
                  </button>
                  {showTooltip === 'search' && (
                    <div className="tooltip">Search for references</div>
                  )}
                </div>

              </div>
            </div>
          )}

          {searchPopover && (
            <div className="reference-search-popover">
              <div className="reference-search-popover-header">
                <span>Search for supporting references</span>
                <button
                  type="button"
                  onClick={() => setSearchPopover(false)}
                  aria-label="Close search"
                >
                  <X size={14} />
                </button>
              </div>
              <div className="reference-search-query">{searchQuery}</div>
              <div className="reference-search-actions">
                <button
                  type="button"
                  className="reference-search-btn reference-search-btn-primary"
                  onClick={() => openExternalSearch('perplexity')}
                >
                  Open in Perplexity
                </button>
                <button
                  type="button"
                  className="reference-search-btn reference-search-btn-primary"
                  title="Opens in your browser"
                  onClick={() => openExternalSearch('web')}
                >
                  <Globe size={12} />
                  Web search
                </button>
                <button
                  type="button"
                  className={`reference-search-btn ${promptCopied ? 'is-copied' : ''}`}
                  onClick={() => {
                    navigator.clipboard.writeText(searchQuery).then(() => {
                      setPromptCopied(true);
                      setTimeout(() => setPromptCopied(false), 2000);
                    }).catch(() => {});
                  }}
                >
                  {promptCopied ? 'Copied!' : 'Copy prompt'}
                </button>
              </div>
              <label className="reference-search-engine">
                <span>Web engine</span>
                <select
                  value={webEngineId}
                  onChange={(e) => handleEngineChange(e.target.value)}
                  aria-label="Web search engine"
                >
                  {Object.values(WEB_SEARCH_ENGINES).map((engine) => (
                    <option key={engine.id} value={engine.id}>{engine.label}</option>
                  ))}
                </select>
                <em>Opens in your browser. Sites cannot detect the default search engine.</em>
              </label>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ERROR MESSAGE
  if (message.type === 'error') {
    return (
      <div className="error-message-container">
        <div className="error-message">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  return null;
};

export default MessageBubble;

const RagChunkPreview = ({ text }) => {
  const [expanded, setExpanded] = useState(false);
  const full = (text || '').toString();
  const isLong = full.length > 240;
  const shown = !isLong || expanded ? full : full.slice(0, 240);
  return (
    <div className="rag-chunk-preview">
      {shown}
      {isLong && (
        <>
          {' '}
          <button
            type="button"
            className="message-show-more"
            onClick={() => setExpanded((v) => !v)}
            style={{ fontSize: 11 }}
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        </>
      )}
    </div>
  );
};

/** RAG Info overlay kept as-is from your original file */
const RagInfoOverlay = ({ ragMetadata, colors }) => {
  const overlayRef = useRef(null);
  const [documentChunks, setDocumentChunks] = useState([]);

  useEffect(() => {
    if (ragMetadata?.documentChunks) {
      setDocumentChunks(ragMetadata.documentChunks);
    }
  }, [ragMetadata]);

  const hasDocuments = documentChunks.length > 0;

  return (
    <div className="rag-info-overlay" ref={overlayRef}>
      <div className="rag-overlay-content">
        <div className="rag-header">
          <div className="rag-title">
            <FileText size={14} />
            <span>Response Details</span>
          </div>
        </div>

        <div className="rag-section">
          <div className="rag-metrics">
            <div className="metric-item">
              <Hash size={14} />
              <span className="metric-label">Model</span>
              <span className="metric-value">{ragMetadata?.model || 'unknown'}</span>
            </div>
            <div className="metric-item">
              <Hash size={14} />
              <span className="metric-label">Tokens</span>
              <span className="metric-value">{ragMetadata?.tokens ?? '—'}</span>
            </div>
          </div>
        </div>

        {hasDocuments && documentChunks.length > 0 && (
          <div className="rag-documents-section">
            <div className="rag-section-title">
              <FileText size={12} />
              Referenced Sources
            </div>
            
            {documentChunks.map((chunk, index) => (
              <div key={index} className="rag-document-item">
                <div className="rag-document-header">
                  <span className="rag-filename">
                    {chunk.metadata?.filename || 'Unknown file'}
                  </span>
                  <span className="rag-relevance">
                    <Target size={10} />
                    {Math.round((chunk.relevance_score || 0) * 100)}%
                  </span>
                </div>
                
                {chunk.text && (
                  <RagChunkPreview text={chunk.text} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
