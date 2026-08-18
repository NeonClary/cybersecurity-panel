/** Persist whether below-input chat follow-up suggestion chips are shown. Default: visible. */

export const CHAT_INPUT_FOLLOWUPS_STORAGE_KEY = 'chat-input-followups-visible';
export const CHAT_INPUT_FOLLOWUPS_EVENT = 'chat-input-followups-pref-changed';

export function readChatInputFollowupsVisible() {
  try {
    const raw = localStorage.getItem(CHAT_INPUT_FOLLOWUPS_STORAGE_KEY);
    if (raw === null) return true;
    return raw !== 'false';
  } catch {
    return true;
  }
}

export function writeChatInputFollowupsVisible(visible) {
  const next = Boolean(visible);
  try {
    localStorage.setItem(CHAT_INPUT_FOLLOWUPS_STORAGE_KEY, String(next));
  } catch {
    /* ignore quota / private mode */
  }
  if (typeof window !== 'undefined') {
    queueMicrotask(() => {
      window.dispatchEvent(
        new CustomEvent(CHAT_INPUT_FOLLOWUPS_EVENT, { detail: { visible: next } })
      );
    });
  }
  return next;
}
