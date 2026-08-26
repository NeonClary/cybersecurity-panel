import {
  getAvailableSteps,
  isNodeVisible,
  markStepComplete,
  mergeAutoCompletions,
} from './advisorPathProgress';

describe('advisorPathProgress', () => {
  test('root steps are available with empty progress', () => {
    const steps = getAvailableSteps({ completed: [], isGuest: false, limit: 4 });
    expect(steps.map((s) => s.id)).toEqual([
      'first-question',
      'your-profile',
      'your-journey',
      'your-workspace',
    ]);
  });

  test('completing a root step unlocks dependent steps', () => {
    const completed = markStepComplete([], 'your-profile');
    const steps = getAvailableSteps({ completed, isGuest: false, limit: 6 });
    expect(steps.some((s) => s.id === 'stated-goal')).toBe(true);
    expect(steps.some((s) => s.id === 'your-profile')).toBe(false);
  });

  test('guest-only save-progress appears for guests after first exploration', () => {
    const completed = ['first-question'];
    const visible = getAvailableSteps({ completed, isGuest: true, limit: 8 });
    expect(visible.some((s) => s.id === 'save-progress')).toBe(true);
    expect(visible.some((s) => s.id === 'model-status')).toBe(false);
  });

  test('model-status hidden for guests', () => {
    const completed = ['first-question'];
    const steps = getAvailableSteps({ completed, isGuest: true, limit: 8 });
    expect(steps.some((s) => s.id === 'model-status')).toBe(false);
  });

  test('mergeAutoCompletions detects profile and goal signals', () => {
    const merged = mergeAutoCompletions([], {
      hasProfileFacts: true,
      hasStatedGoal: true,
      hasChats: true,
    });
    expect(merged).toEqual(
      expect.arrayContaining(['first-question', 'your-profile', 'stated-goal']),
    );
  });

  test('isNodeVisible respects prerequisites', () => {
    const completedSet = new Set(['first-question']);
    expect(isNodeVisible(
      { id: 'pick-advisors', requires: ['first-question'], tier: 1 },
      { completedSet, isGuest: false },
    )).toBe(true);
    expect(isNodeVisible(
      { id: 'stated-goal', requiresAny: ['your-profile'], tier: 1 },
      { completedSet, isGuest: false },
    )).toBe(false);
  });
});
