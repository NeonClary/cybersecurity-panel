import { resolveStatedGoal } from './statedGoal';

describe('resolveStatedGoal', () => {
  test('prefers stated_goal fact, then profile current_goals, then guest label', () => {
    expect(resolveStatedGoal({
      facts: [{ key: 'stated_goal', value: 'Write a novel about cat hackers' }],
      profile: { current_goals: 'IG1 hygiene' },
      user: { is_guest: true, guest_label: 'Custom' },
    })).toBe('Write a novel about cat hackers');

    expect(resolveStatedGoal({
      profile: { current_goals: 'IG1 hygiene' },
      user: { is_guest: true, guest_label: 'Custom' },
    })).toBe('IG1 hygiene');

    expect(resolveStatedGoal({
      user: { is_guest: true, guest_label: 'Custom path' },
    })).toBe('Custom path');
  });

  test('hides empty / placeholder goals', () => {
    expect(resolveStatedGoal({
      profile: { current_goals: 'not specified' },
    })).toBe('');
  });
});
