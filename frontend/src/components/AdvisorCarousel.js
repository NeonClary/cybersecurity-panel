import React, { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import MessageBubble from './MessageBubble';

const CONTROLS_W = 62;
const GAP = 16;
const PREFERRED_SLIDE = 400;
const MIN_SLIDE = 280;

const findScrollParent = (node) => {
  let el = node?.parentElement;
  while (el) {
    const { overflowY } = window.getComputedStyle(el);
    if (overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') {
      return el;
    }
    el = el.parentElement;
  }
  return null;
};

function computeLayout(paneWidth, messageCount) {
  const n = Math.max(1, messageCount);
  const usable = Math.max(MIN_SLIDE, paneWidth - CONTROLS_W);
  let visible = Math.floor((usable + GAP) / (PREFERRED_SLIDE + GAP));
  visible = Math.max(1, Math.min(n, visible));
  if (visible === 1 && n > 1 && 2 * MIN_SLIDE + GAP <= usable) {
    visible = Math.min(n, Math.floor((usable + GAP) / (MIN_SLIDE + GAP)));
  }
  const slideW = Math.max(
    MIN_SLIDE,
    Math.min(PREFERRED_SLIDE, Math.floor((usable - GAP * (visible - 1)) / visible))
  );
  return { visible, slideW };
}

/**
 * Show as many advisor answers as fit side-by-side; carousel when they don't.
 * Messages should already be ordered most-relevant-first (orchestrator rank).
 *
 * Controls sit just to the right of the visible answer(s). They stay vertically
 * centered in the answer stack when it is shorter than the chat pane, and
 * centered in the visible pane when the stack fills (or exceeds) the viewport.
 */
const AdvisorCarousel = ({ messages = [], onReply, onExpand, onClick, onSearchReferences, userAvatarId, userAvatarOptions }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const [layout, setLayout] = useState({ visible: 1, slideW: PREFERRED_SLIDE });
  const shellRef = useRef(null);
  const stageRef = useRef(null);
  const controlsColRef = useRef(null);
  const controlsInnerRef = useRef(null);

  const messageKey = messages.map((m) => m.id).join('|');
  const visibleCount = Math.min(layout.visible, messages.length || 1);
  const maxIndex = Math.max(0, messages.length - visibleCount);
  const showAll = visibleCount >= messages.length && messages.length > 1;
  const showControls = messages.length > visibleCount;

  useEffect(() => {
    setActiveIndex(0);
  }, [messageKey]);

  useEffect(() => {
    setActiveIndex((i) => Math.min(i, maxIndex));
  }, [maxIndex]);

  const goPrev = useCallback(() => {
    setActiveIndex((i) => Math.max(0, i - 1));
  }, []);

  const goNext = useCallback(() => {
    setActiveIndex((i) => Math.min(maxIndex, i + 1));
  }, [maxIndex]);

  const measurePane = useCallback(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const pane = findScrollParent(shell) || shell;
    const paneWidth = Math.round(pane.getBoundingClientRect().width);
    const next = computeLayout(paneWidth, messages.length);
    setLayout((prev) => (
      prev.visible === next.visible && prev.slideW === next.slideW ? prev : next
    ));
  }, [messages.length]);

  const updateControlPosition = useCallback(() => {
    const col = controlsColRef.current;
    const inner = controlsInnerRef.current;
    const stage = stageRef.current;
    if (!col || !inner || !stage) return;

    const scrollParent = findScrollParent(stage);
    const colRect = col.getBoundingClientRect();
    const viewRect = scrollParent
      ? scrollParent.getBoundingClientRect()
      : { top: 0, bottom: window.innerHeight };

    const inputEl = document.querySelector('.floating-input-area');
    const inputTop = inputEl ? inputEl.getBoundingClientRect().top : viewRect.bottom;
    const viewTop = viewRect.top;
    const viewBottom = Math.min(viewRect.bottom, inputTop);

    const overlapTop = Math.max(colRect.top, viewTop);
    const overlapBottom = Math.min(colRect.bottom, viewBottom);
    const innerH = inner.offsetHeight || 0;
    const colH = col.offsetHeight || 0;

    if (overlapBottom > overlapTop && innerH > 0 && colH > 0) {
      const mid = (overlapTop + overlapBottom) / 2;
      const maxTop = Math.max(0, colH - innerH);
      const top = Math.max(0, Math.min(maxTop, mid - colRect.top - innerH / 2));
      inner.style.top = `${Math.round(top)}px`;
    }
  }, []);

  useLayoutEffect(() => {
    measurePane();
    const shell = shellRef.current;
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measurePane) : null;
    if (shell) ro?.observe(shell);
    const scrollParent = shell ? findScrollParent(shell) : null;
    if (scrollParent) ro?.observe(scrollParent);
    window.addEventListener('resize', measurePane);
    return () => {
      window.removeEventListener('resize', measurePane);
      ro?.disconnect();
    };
  }, [measurePane]);

  useLayoutEffect(() => {
    if (messages.length <= 1) return undefined;

    updateControlPosition();
    const raf = window.requestAnimationFrame(() => updateControlPosition());

    const stage = stageRef.current;
    const scrollParent = stage ? findScrollParent(stage) : null;
    const onScrollOrResize = () => updateControlPosition();

    scrollParent?.addEventListener('scroll', onScrollOrResize, { passive: true });
    window.addEventListener('resize', onScrollOrResize);

    const ro = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(onScrollOrResize)
      : null;
    if (stage) ro?.observe(stage);
    if (scrollParent) ro?.observe(scrollParent);

    return () => {
      window.cancelAnimationFrame(raf);
      scrollParent?.removeEventListener('scroll', onScrollOrResize);
      window.removeEventListener('resize', onScrollOrResize);
      ro?.disconnect();
    };
  }, [messages.length, activeIndex, messageKey, visibleCount, updateControlPosition]);

  if (messages.length === 1) {
    return (
      <div className="single-response-wide">
        <MessageBubble
          message={messages[0]}
          onReply={onReply}
          onExpand={onExpand}
          onClick={onClick}
          onSearchReferences={onSearchReferences}
          showReplyButton={true}
          userAvatarId={userAvatarId}
          userAvatarOptions={userAvatarOptions}
        />
      </div>
    );
  }

  const viewportWidth = visibleCount * layout.slideW + GAP * (visibleCount - 1);
  const offset = showAll ? 0 : activeIndex * (layout.slideW + GAP);

  return (
    <div
      className={`advisor-carousel carousel-mode${showAll ? ' is-showing-all' : ''}`}
      ref={shellRef}
    >
      <div className="carousel-stage" ref={stageRef}>
        <div
          className="carousel-viewport"
          style={{ width: `${viewportWidth}px` }}
        >
          <div
            className="carousel-track"
            style={{
              gap: `${GAP}px`,
              transform: `translateX(-${offset}px)`,
            }}
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className="carousel-slide"
                style={{ width: `${layout.slideW}px`, flex: `0 0 ${layout.slideW}px` }}
              >
                <MessageBubble
                  message={message}
                  onReply={onReply}
                  onExpand={onExpand}
                  onClick={onClick}
                  onSearchReferences={onSearchReferences}
                  showReplyButton={true}
                  inlineAvatar={true}
                  userAvatarId={userAvatarId}
                  userAvatarOptions={userAvatarOptions}
                />
              </div>
            ))}
          </div>
        </div>

        {showControls && (
          <div className="carousel-controls" ref={controlsColRef}>
            <div className="carousel-controls-inner" ref={controlsInnerRef}>
              <button
                type="button"
                className="carousel-arrow carousel-prev"
                onClick={goPrev}
                disabled={activeIndex === 0}
                aria-label="Previous advisor"
              >
                <ChevronLeft size={28} strokeWidth={2.4} />
              </button>
              <button
                type="button"
                className="carousel-arrow carousel-next"
                onClick={goNext}
                disabled={activeIndex >= maxIndex}
                aria-label="Next advisor"
              >
                <ChevronRight size={28} strokeWidth={2.4} />
              </button>
            </div>
          </div>
        )}
      </div>

      {showControls && (
        <div className="carousel-dots" role="tablist" aria-label="Advisor answers">
          {Array.from({ length: maxIndex + 1 }, (_, i) => (
            <button
              key={messages[i].id}
              type="button"
              className={`carousel-dot ${i === activeIndex ? 'active' : ''}`}
              onClick={() => setActiveIndex(i)}
              aria-label={`Show answers starting at ${i + 1}`}
              aria-selected={i === activeIndex}
              role="tab"
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default AdvisorCarousel;
