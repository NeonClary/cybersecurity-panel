/**
 * Keep the latest user question at the top of the messages viewport while
 * advisor answers stream in. Call once after send — do not re-pin on every
 * token, or the view will jump.
 */

export function pinElementToScrollerTop(scroller, element, { behavior = 'smooth' } = {}) {
  if (!scroller || !element) return false;
  const scrollerRect = scroller.getBoundingClientRect();
  const elRect = element.getBoundingClientRect();
  const nextTop = scroller.scrollTop + (elRect.top - scrollerRect.top);
  const top = Math.max(0, nextTop);
  if (typeof scroller.scrollTo === 'function') {
    scroller.scrollTo({ top, behavior });
  } else {
    scroller.scrollTop = top;
  }
  return true;
}

export function findLatestUserMessage(messages) {
  if (!Array.isArray(messages)) return null;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message?.type === 'user' && !message.isReferenceSnippet) {
      return message;
    }
  }
  return null;
}
