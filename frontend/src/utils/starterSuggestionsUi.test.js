import {
  STARTER_FALLBACK_MS,
  applyFallbackIfTimedOut,
  applySlotDelta,
  applySlotDone,
  buildStarterSlots,
  collectExcludeKeys,
  fallbackToSuggestion,
  nextPromptVariation,
  normalizeSuggestion,
  slotsToCategories,
  slotsToFlatList,
  stripForbiddenOpeners,
  suggestionChatPrompt,
  suggestionDisplayText,
  visiblePrompts,
  looksLikeAdvisorToUser,
} from './starterSuggestionsUi';

const examples = [
  { title: 'A', suggestions: ['A1', 'A2', 'A3'] },
  { title: 'B', suggestions: ['B1', 'B2', 'B3'] },
  { title: 'C', suggestions: ['C1', 'C2'] },
];

describe('starter suggestion slots', () => {
  test('builds stable category-major slots and does not reorder on populate', () => {
    const slots = buildStarterSlots(examples);
    expect(slots.map((s) => s.fallback)).toEqual([
      'A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2',
    ]);
    let next = applySlotDelta(slots, 2, 'How');
    next = applySlotDelta(next, 0, 'What');
    next = applySlotDone(next, 2, {
      suggestion: {
        lead: 'For backups,',
        question: 'How should I start?',
        chat_prompt: 'Given my backup goal, how should I start?',
      },
    });
    expect(next[0].text).toBe('What');
    expect(next[2].text).toBe('How should I start?');
    expect(next[2].suggestion.lead).toBe('');
    expect(next[1].fallback).toBe('A2');
    expect(next.map((s) => s.slot)).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
  });

  test('uses YAML fallback only after 5s without tokens', () => {
    const slots = buildStarterSlots([{ title: 'A', suggestions: ['Static A'] }]);
    const t0 = 1000;
    expect(applyFallbackIfTimedOut(slots, t0, t0 + 4999)[0].text).toBe('');
    const timed = applyFallbackIfTimedOut(slots, t0, t0 + STARTER_FALLBACK_MS);
    expect(timed[0].text).toBe('Static A');
    expect(timed[0].generated).toBe(false);
    const afterStream = applySlotDone(timed, 0, {
      suggestion: {
        lead: '',
        question: 'Generated for this user?',
        chat_prompt: 'Given my goal, what should I tackle first?',
      },
    });
    expect(afterStream[0].text).toBe('Generated for this user?');
    expect(suggestionChatPrompt(afterStream[0].suggestion)).toBe(
      'Given my goal, what should I tackle first?',
    );
    expect(afterStream[0].generated).toBe(true);
  });

  test('flat list preserves slot order without category headers or lead prefixes', () => {
    let slots = buildStarterSlots(examples.slice(0, 2));
    slots = applySlotDone(slots, 0, {
      suggestion: {
        lead: 'For MFA,',
        question: 'Gen A1?',
        chat_prompt: 'For MFA rollout, what is Gen A1?',
      },
    });
    slots = applySlotDone(slots, 1, {
      suggestion: {
        lead: '',
        question: 'Gen A2?',
        chat_prompt: 'What is Gen A2 for my goal?',
      },
    });
    const flat = slotsToFlatList(slots);
    expect(flat[0].displayText).toBe('Gen A1?');
    expect(flat[0].suggestion.lead).toBe('');
    expect(flat[1].displayText).toBe('Gen A2?');
    expect(visiblePrompts(slots).slice(0, 2)).toEqual([
      'For MFA rollout, what is Gen A1?',
      'What is Gen A2 for my goal?',
    ]);
  });

  test('persisted slot payload round-trips into categories without shuffle', () => {
    let slots = buildStarterSlots(examples.slice(0, 2));
    slots = applySlotDone(slots, 0, { suggestion: fallbackToSuggestion('Gen A1') });
    slots = applySlotDone(slots, 1, { suggestion: fallbackToSuggestion('Gen A2') });
    const cats = slotsToCategories(examples.slice(0, 2), slots);
    expect(cats[0].suggestions[0]).toBe('Gen A1');
    expect(cats[0].suggestions[1]).toBe('Gen A2');
  });

  test('normalizeSuggestion drops lead and strips For-topic openers', () => {
    const item = normalizeSuggestion({
      lead: 'For IR,',
      question: 'What is step one?',
      chat_prompt: 'For incident response, what is step one?',
    });
    expect(item.lead).toBe('');
    expect(suggestionDisplayText(item)).toBe('What is step one?');
    expect(suggestionChatPrompt(item)).toBe('For incident response, what is step one?');

    const prefixed = normalizeSuggestion({
      lead: '',
      question: 'For MFA, what should we prioritize first?',
      chat_prompt: 'I am rolling out MFA — what should we prioritize first?',
    });
    expect(suggestionDisplayText(prefixed)).toBe('What should we prioritize first?');
  });

  test('stripForbiddenOpeners removes filler and topic-comma leads', () => {
    expect(stripForbiddenOpeners('To begin, what MFA should I use?')).toBe(
      'What MFA should I use?',
    );
    expect(stripForbiddenOpeners('To shape your path, how do I start?')).toBe(
      'How do I start?',
    );
    expect(stripForbiddenOpeners('For backups, what should I test first?')).toBe(
      'What should I test first?',
    );
    const slots = applySlotDelta(
      buildStarterSlots([{ title: 'A', suggestions: ['A1'] }]),
      0,
      '{"lead":"","question":"Can you explain phishing and how it connects to MFA?"',
    );
    expect(slots[0].text).toBe('Can you explain phishing and how it connects to MFA?');
  });

  test('does not show raw JSON or chop a long question ending', () => {
    const fromJson = normalizeSuggestion(
      '{"lead":"","question":"Can you explain phishing and how it connects to MFA?","chat_prompt":"To understand how phishing',
    );
    expect(fromJson.question).toBe('Can you explain phishing and how it connects to MFA?');
    expect(fromJson.question.startsWith('{')).toBe(false);

    const longQ = (
      'Which is the better first step for you: enabling MFA for your email '
      + 'and social media accounts or a password manager?'
    );
    const item = normalizeSuggestion({
      lead: '',
      question: longQ,
      chat_prompt: `Given my goal, ${longQ[0].toLowerCase()}${longQ.slice(1)}`,
    });
    expect(suggestionDisplayText(item)).toBe(longQ);
    expect(item.question.endsWith('password manager?')).toBe(true);
  });

  test('collectExcludeKeys deduplicates chat and display strings', () => {
    const slots = buildStarterSlots([{ title: 'A', suggestions: ['One'] }]);
    const filled = applySlotDone(slots, 0, {
      suggestion: {
        lead: 'Ctx,',
        question: 'Question?',
        chat_prompt: 'Chat prompt?',
      },
    });
    const keys = collectExcludeKeys(filled, ['Extra']);
    expect(keys).toEqual(expect.arrayContaining(['Chat prompt?', 'Question?', 'Extra']));
    expect(keys).not.toEqual(expect.arrayContaining(['Ctx, Question?']));
  });

  test('nextPromptVariation cycles through six prompt styles', () => {
    expect(nextPromptVariation(0)).toBe(1);
    expect(nextPromptVariation(5)).toBe(0);
  });

  test('click payload drops advisor-to-user lectures in favor of the chip question', () => {
    const lecture = (
      'To identify the most critical security risk in your sci-fi novel, '
      + "let's dissect the core concept: feline hackers. Have you considered "
      + "how this hybrid nature might reshape strategies in your novel's universe?"
    );
    expect(looksLikeAdvisorToUser(lecture)).toBe(true);
    const item = normalizeSuggestion({
      lead: '',
      question: 'What is the most critical security risk with feline hackers?',
      chat_prompt: lecture,
    });
    expect(suggestionDisplayText(item)).toBe(
      'What is the most critical security risk with feline hackers?',
    );
    expect(suggestionChatPrompt(item)).toBe(
      'What is the most critical security risk with feline hackers?',
    );
    expect(looksLikeAdvisorToUser(suggestionChatPrompt(item))).toBe(false);

    const good = (
      'What is the most critical security risk if feline hackers in my '
      + 'sci-fi novel have cybernetic enhancements?'
    );
    expect(looksLikeAdvisorToUser(good)).toBe(false);
    expect(suggestionChatPrompt(normalizeSuggestion({
      question: 'What is the biggest risk with feline hackers?',
      chat_prompt: good,
    }))).toBe(good);
  });
});
