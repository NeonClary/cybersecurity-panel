import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom';
import { BookmarkPlus, X } from 'lucide-react';
import '../styles/ConfirmDialog.css';

/**
 * Preview clipboard (or pasted) text before adding it to chat context.
 * Clipboard is only read from a user gesture in the parent.
 */
const ClipboardPreviewModal = ({
  isOpen,
  title = 'Add copied references',
  initialText = '',
  clipboardError = '',
  onCancel,
  onApprove,
}) => {
  const [draft, setDraft] = useState(initialText);

  useEffect(() => {
    if (!isOpen) return undefined;
    setDraft(initialText);
    const onKey = (e) => e.key === 'Escape' && onCancel?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, initialText, onCancel]);

  if (!isOpen) return null;

  const canApprove = Boolean(draft.trim());

  return ReactDOM.createPortal(
    <div
      className="confirm-overlay clipboard-preview-overlay"
      onClick={(e) => e.target === e.currentTarget && onCancel?.()}
    >
      <div
        className="confirm-dialog clipboard-preview-dialog"
        role="dialog"
        aria-labelledby="clipboard-preview-title"
      >
        <div className="confirm-icon">
          <BookmarkPlus size={22} />
        </div>
        <h2 id="clipboard-preview-title" className="confirm-title">{title}</h2>
        <p className="confirm-message">
          Preview what you copied, edit if needed, then add it to this chat.
          Advisors will see it on your next question.
        </p>
        {clipboardError ? (
          <p className="clipboard-preview-error">{clipboardError}</p>
        ) : null}
        <label className="clipboard-preview-label" htmlFor="clipboard-preview-text">
          Reference snippet
        </label>
        <textarea
          id="clipboard-preview-text"
          className="clipboard-preview-textarea"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Paste citations, excerpts, or links here…"
          rows={10}
          autoFocus
        />
        <div className="confirm-actions">
          <button
            type="button"
            className="confirm-btn confirm-btn-cancel"
            onClick={onCancel}
          >
            <X size={14} />
            Cancel
          </button>
          <button
            type="button"
            className="confirm-btn confirm-btn-primary"
            onClick={() => canApprove && onApprove?.(draft.trim())}
            disabled={!canApprove}
          >
            Add to context
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ClipboardPreviewModal;
