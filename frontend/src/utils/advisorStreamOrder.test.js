import { applyAdvisorStreamEvent, advisorDisplayOrder } from './advisorStreamOrder';

describe('advisor stream display order', () => {
  const opts = () => {
    let n = 0;
    return {
      generateId: () => `id-${++n}`,
      now: () => new Date('2026-01-01T00:00:00Z'),
    };
  };

  test('first token becomes the front card; later starts append', () => {
    const o = opts();
    let messages = [{ id: 'u1', type: 'user', content: 'hi' }];
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_start',
      data: { persona_id: 'threat_modeler', persona_name: 'Threat' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_start',
      data: { persona_id: 'jerry_huaute', persona_name: 'Jerry' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_start',
      data: { persona_id: 'incident_responder', persona_name: 'IR' },
    }, o);

    expect(advisorDisplayOrder(messages)).toEqual([
      'threat_modeler',
      'jerry_huaute',
      'incident_responder',
    ]);
  });

  test('does not reorder when a later-ranked advisor finishes first', () => {
    const o = opts();
    let messages = [];
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_start',
      data: { persona_id: 'compliance_officer', persona_name: 'Compliance' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_delta',
      data: { persona_id: 'compliance_officer', delta: 'A' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_start',
      data: { persona_id: 'jerry_huaute', persona_name: 'Jerry' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_done',
      data: { persona_id: 'jerry_huaute', persona_name: 'Jerry', content: 'Jerry final' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_done',
      data: {
        persona_id: 'compliance_officer',
        persona_name: 'Compliance',
        content: 'Compliance final',
      },
    }, o);

    expect(advisorDisplayOrder(messages)).toEqual([
      'compliance_officer',
      'jerry_huaute',
    ]);
    expect(messages[0].content).toBe('Compliance final');
    expect(messages[1].content).toBe('Jerry final');
  });

  test('deltas append live text on the existing card', () => {
    const o = opts();
    let messages = [];
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_start',
      data: { persona_id: 'jerry_huaute', persona_name: 'Jerry' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_delta',
      data: { persona_id: 'jerry_huaute', delta: 'Hel' },
    }, o);
    messages = applyAdvisorStreamEvent(messages, {
      type: 'advisor_delta',
      data: { persona_id: 'jerry_huaute', delta: 'lo' },
    }, o);
    expect(messages[0].content).toBe('Hello');
    expect(messages[0].streaming).toBe(true);
  });
});
