/** Resolve the user's stated goal from profile, facts, or guest label. */

const EMPTY = new Set(['', 'n/a', 'na', 'none', 'not specified', 'unknown', 'unspecified']);

export function normalizeGoalText(value) {
  if (value == null) return '';
  const text = String(value).replace(/\s+/g, ' ').trim();
  if (!text || EMPTY.has(text.toLowerCase())) return '';
  return text;
}

export function resolveStatedGoal({ profile, facts, user } = {}) {
  const fromFacts = (facts || []).find((fact) => {
    const key = String(fact?.key || '').toLowerCase();
    return key === 'stated_goal' && normalizeGoalText(fact.value);
  });
  if (fromFacts) return normalizeGoalText(fromFacts.value);

  const fromProfile = normalizeGoalText(profile?.current_goals);
  if (fromProfile) return fromProfile;

  if (user?.is_guest) {
    const label = normalizeGoalText(user.guest_label);
    if (label) return label;
  }
  return '';
}

export function goalCacheKey(goal, userId) {
  const uid = userId || 'anon';
  const g = (goal || '').trim().toLowerCase().slice(0, 180);
  return `${uid}::${g}`;
}
