/**
 * Server persistence helpers for Workspace + Documents (phd-canvas API).
 * Failures are soft — callers keep localStorage as a fallback cache.
 */

const apiBase = () => process.env.REACT_APP_API_URL || '';

const authHeaders = (token) => ({
  Authorization: `Bearer ${token}`,
  'Content-Type': 'application/json',
});

export async function fetchCanvas(authToken) {
  if (!authToken) return null;
  try {
    const resp = await fetch(`${apiBase()}/api/phd-canvas`, {
      headers: authHeaders(authToken),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

export async function saveWorkspace(authToken, workspace) {
  if (!authToken) return false;
  try {
    const resp = await fetch(`${apiBase()}/api/phd-canvas/workspace`, {
      method: 'PUT',
      headers: authHeaders(authToken),
      body: JSON.stringify({
        layout: workspace.layout || [],
        states: workspace.states || {},
        view: workspace.view ?? undefined,
        task_statuses: workspace.task_statuses ?? undefined,
      }),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function saveDeliverables(authToken, store) {
  if (!authToken) return false;
  try {
    const resp = await fetch(`${apiBase()}/api/phd-canvas/deliverables`, {
      method: 'PUT',
      headers: authHeaders(authToken),
      body: JSON.stringify({
        activeProjectId: store.activeProjectId ?? null,
        projects: store.projects || {},
      }),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

/** Simple debounce — returns a cancelable scheduler. */
export function debounce(fn, ms = 800) {
  let t = null;
  const wrapped = (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => {
      t = null;
      fn(...args);
    }, ms);
  };
  wrapped.cancel = () => {
    if (t) clearTimeout(t);
    t = null;
  };
  wrapped.flush = (...args) => {
    if (t) clearTimeout(t);
    t = null;
    fn(...args);
  };
  return wrapped;
}
