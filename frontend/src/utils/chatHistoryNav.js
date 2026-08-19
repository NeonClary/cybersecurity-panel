/** Browser-history mapping for chat starter vs active conversation.

The SPA does not use React Router. Navigation uses history.pushState so the
first Back in an active chat returns to the starter screen, the next Back
returns home, and further Back can leave the site. Do not trap the user.
*/

export const VIEW_HOME = 'home';
export const VIEW_CHAT_STARTER = 'chat-starter';
export const VIEW_CHAT_ACTIVE = 'chat-active';
export const VIEW_CANVAS = 'canvas';
export const VIEW_JOURNEY = 'journey';
export const VIEW_AUTH = 'auth';

export function homeState() {
  return { view: VIEW_HOME };
}

export function chatStarterState() {
  return { view: VIEW_CHAT_STARTER };
}

export function chatActiveState(sessionId) {
  return { view: VIEW_CHAT_ACTIVE, sessionId: sessionId || null };
}

export function appViewState(view, extra = {}) {
  return { view, ...extra };
}

export function sameHistoryState(a, b) {
  if (!a && !b) return true;
  if (!a || !b) return false;
  return a.view === b.view && (a.sessionId || null) === (b.sessionId || null);
}

/**
 * Map a popstate `event.state` to the SPA surface.
 *
 * Leaving chat-active → starter chat. Leaving starter → home.
 * Null/unknown state is treated as home so the original page-load entry
 * is not trapped.
 */
export function mapPopState(state) {
  if (!state || !state.view || state.view === VIEW_HOME) {
    return { currentView: 'home', chatNavView: null, sessionId: null };
  }
  if (state.view === VIEW_CHAT_STARTER) {
    return { currentView: 'chat', chatNavView: 'starter', sessionId: null };
  }
  if (state.view === VIEW_CHAT_ACTIVE) {
    return {
      currentView: 'chat',
      chatNavView: 'active',
      sessionId: state.sessionId || null,
    };
  }
  if (state.view === VIEW_CANVAS) {
    return { currentView: 'canvas', chatNavView: null, sessionId: null };
  }
  if (state.view === VIEW_JOURNEY) {
    return { currentView: 'journey', chatNavView: null, sessionId: null };
  }
  if (state.view === VIEW_AUTH) {
    return { currentView: 'auth', chatNavView: null, sessionId: null };
  }
  return { currentView: 'home', chatNavView: null, sessionId: null };
}

/** True when a chat-active history entry should collapse to the starter screen. */
export function isLeavingChatActive(previousView, nextMapped) {
  return previousView === VIEW_CHAT_ACTIVE && nextMapped.chatNavView === 'starter';
}
