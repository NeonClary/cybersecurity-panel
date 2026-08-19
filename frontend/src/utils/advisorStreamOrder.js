/**
 * Apply chat-stream advisor events. Display order is first-start order:
 * new cards append; they are never sorted by rank or finish time.
 */

function trailingAdvisorStart(messages) {
  let i = messages.length;
  while (i > 0 && messages[i - 1].type === 'advisor') i -= 1;
  return i;
}

function findTrailingAdvisorIndex(messages, personaId) {
  const start = trailingAdvisorStart(messages);
  for (let i = start; i < messages.length; i += 1) {
    if (messages[i].persona_id === personaId) return i;
  }
  return -1;
}

export function applyAdvisorStreamEvent(messages, payload, { generateId, now } = {}) {
  const type = payload?.type;
  const d = payload?.data || {};
  const idFactory = generateId || (() => `msg-${Date.now()}`);
  const timestamp = now ? now() : new Date();

  if (type === 'advisor_start') {
    if (findTrailingAdvisorIndex(messages, d.persona_id) !== -1) {
      return messages;
    }
    const msg = {
      id: idFactory(),
      type: 'advisor',
      persona_id: d.persona_id,
      content: '',
      timestamp,
      advisorName: d.persona_name || d.persona_id,
      used_documents: false,
      document_chunks_used: 0,
      streaming: true,
    };
    return [...messages, msg];
  }

  if (type === 'advisor_delta') {
    const idx = findTrailingAdvisorIndex(messages, d.persona_id);
    const delta = d.delta || '';
    if (idx === -1) {
      const created = applyAdvisorStreamEvent(
        messages,
        { type: 'advisor_start', data: d },
        { generateId: idFactory, now: () => timestamp },
      );
      return applyAdvisorStreamEvent(
        created,
        payload,
        { generateId: idFactory, now: () => timestamp },
      );
    }
    const next = messages.slice();
    const prev = next[idx];
    next[idx] = {
      ...prev,
      content: `${prev.content || ''}${delta}`,
      streaming: true,
    };
    return next;
  }

  if (type === 'advisor_done') {
    const idx = findTrailingAdvisorIndex(messages, d.persona_id);
    const doneFields = {
      content: d.content ?? '',
      advisorName: d.persona_name || d.persona_id,
      used_documents: d.used_documents || false,
      document_chunks_used: d.document_chunks_used || 0,
      streaming: false,
    };
    if (idx === -1) {
      return [
        ...messages,
        {
          id: idFactory(),
          type: 'advisor',
          persona_id: d.persona_id,
          timestamp,
          ...doneFields,
        },
      ];
    }
    const next = messages.slice();
    next[idx] = { ...next[idx], ...doneFields };
    return next;
  }

  if (type === 'advisor') {
    const idx = findTrailingAdvisorIndex(messages, d.persona_id);
    const msg = {
      id: idx === -1 ? idFactory() : messages[idx].id,
      type: 'advisor',
      persona_id: d.persona_id,
      content: d.content,
      timestamp: idx === -1 ? timestamp : messages[idx].timestamp,
      advisorName: d.persona_name || d.persona_id,
      used_documents: d.used_documents || false,
      document_chunks_used: d.document_chunks_used || 0,
      streaming: false,
    };
    if (idx === -1) return [...messages, msg];
    const next = messages.slice();
    next[idx] = { ...messages[idx], ...msg };
    return next;
  }

  return messages;
}

export function advisorDisplayOrder(messages) {
  return messages
    .filter((m) => m.type === 'advisor')
    .map((m) => m.persona_id);
}
