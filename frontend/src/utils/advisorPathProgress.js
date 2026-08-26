import { PATH_NODES, getPathNode } from '../data/advisorPaths';

const STORAGE_PREFIX = 'advisor-path-progress::';

export function pathProgressKey(userId) {
  const uid = userId || 'anon';
  return `${STORAGE_PREFIX}${uid}`;
}

/** @returns {{ completed: string[], activeId: string|null, updatedAt: number }} */
export function loadPathProgress(userId) {
  try {
    const raw = localStorage.getItem(pathProgressKey(userId));
    if (!raw) return { completed: [], activeId: null, updatedAt: 0 };
    const parsed = JSON.parse(raw);
    const completed = Array.isArray(parsed.completed)
      ? parsed.completed.filter((id) => getPathNode(id))
      : [];
    const activeId = parsed.activeId && getPathNode(parsed.activeId) ? parsed.activeId : null;
    return {
      completed,
      activeId,
      updatedAt: typeof parsed.updatedAt === 'number' ? parsed.updatedAt : 0,
    };
  } catch {
    return { completed: [], activeId: null, updatedAt: 0 };
  }
}

export function savePathProgress(userId, state) {
  try {
    localStorage.setItem(
      pathProgressKey(userId),
      JSON.stringify({
        completed: state.completed || [],
        activeId: state.activeId || null,
        updatedAt: Date.now(),
      }),
    );
  } catch {
    /* quota / private mode */
  }
}

function prerequisitesMet(node, completedSet) {
  if (node.requires?.length) {
    if (!node.requires.every((id) => completedSet.has(id))) return false;
  }
  if (node.requiresAny?.length) {
    if (!node.requiresAny.some((id) => completedSet.has(id))) return false;
  }
  return true;
}

export function isNodeVisible(node, { completedSet, isGuest }) {
  if (node.guestOnly && !isGuest) return false;
  if (node.signedInOnly && isGuest) return false;
  if (completedSet.has(node.id)) return false;
  return prerequisitesMet(node, completedSet);
}

/**
 * Next steps to show (max `limit`), preferring lower tier then definition order.
 */
export function getAvailableSteps({ completed = [], isGuest = false, limit = 4 } = {}) {
  const completedSet = new Set(completed);
  return PATH_NODES.filter((node) => isNodeVisible(node, { completedSet, isGuest }))
    .sort((a, b) => a.tier - b.tier || PATH_NODES.indexOf(a) - PATH_NODES.indexOf(b))
    .slice(0, limit);
}

/** Highest tier among completed nodes, or 0 if none. */
export function currentTier(completed = []) {
  let max = 0;
  completed.forEach((id) => {
    const node = getPathNode(id);
    if (node && node.tier > max) max = node.tier;
  });
  return max;
}

/** Most recently completed node id for the “current focus” strip. */
export function latestCompleted(completed = []) {
  if (!completed.length) return null;
  return completed[completed.length - 1];
}

export function markStepComplete(completed, stepId) {
  if (!getPathNode(stepId) || completed.includes(stepId)) return completed;
  return [...completed, stepId];
}

/** Auto-detect completions from app state (does not remove manual completions). */
export function mergeAutoCompletions(completed, signals = {}) {
  const next = new Set(completed);
  const {
    hasChats,
    hasProfileFacts,
    hasStatedGoal,
    visitedJourney,
    visitedWorkspace,
  } = signals;

  if (hasChats) next.add('first-question');
  if (hasProfileFacts) next.add('your-profile');
  if (hasStatedGoal) next.add('stated-goal');
  if (visitedJourney) next.add('your-journey');
  if (visitedWorkspace) next.add('your-workspace');

  return PATH_NODES.map((n) => n.id).filter((id) => next.has(id));
}

export function recordVisit(userId, area) {
  const key = `${STORAGE_PREFIX}visits::${userId || 'anon'}`;
  try {
    const raw = localStorage.getItem(key);
    const visits = raw ? JSON.parse(raw) : {};
    visits[area] = true;
    localStorage.setItem(key, JSON.stringify(visits));
  } catch {
    /* ignore */
  }
}

export function loadVisits(userId) {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}visits::${userId || 'anon'}`);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}
