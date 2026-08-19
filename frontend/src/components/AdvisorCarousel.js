import React, { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import MessageBubble from './MessageBubble';
import { computeLayout, GAP, PREFERRED_SLIDE } from '../utils/advisorCarouselLayout';

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

/**
 * Show as many advisor answers as fit side-by-side; carousel when they don't.
 * Messages should already be in start-of-stream order (first token first).
 *
 * Controls sit just to the right of the visible answer(s) when that fits.
 * If not, they overlay the last visible card (or sit below) so they stay on-screen.
 * They stay vertically centered in the visible chat pane.
 */
const AdvisorCarousel = ({
  messages = [],
  onReply,
  onExpand,
  onClick,
  onSearchReferences,
  onReferenceSearchOpened,
  userQuestion = '',
  userAvatarId,
  userAvatarOptions,
}) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const [layout, setLayout] = useState({
    visible: 1,
    slideW: PREFERRED_SLIDE,
    cardsWidth: PREFERRED_SLIDE,
    controlsMode: 'none',
  });
  const shellRef = useRef(null);
  const stageRef = useRef(null);
  const controlsColRef = useRef(null);
  const controlsInnerRef = useRef(null);

  const firstMessageId = messages[0]?.id;
  const visibleCount = Math.min(layout.visible, messages.length || 1);
  const maxIndex = Math.max(0, messages.length - visibleCount);
  const showAll = visibleCount >= messages.length && messages.length > 1;
  const showControls = layout.controlsMode !== 'none' && messages.length > visibleCount;

  useEffect(() => {
    setActiveIndex(0);
  }, [firstMessageId]);

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
    const available = Math.floor(shell.clientWidth);
    if (available <= 0) return;
    const next = computeLayout(available, messages.length);
    setLayout((prev) => (
      prev.visible === next.visible
      && prev.slideW === next.slideW
      && prev.controlsMode === next.controlsMode
        ? prev
        : next
    ));
  }, [messages.length]);

  const updateControlPosition = useCallback(() => {
    const col = controlsColRef.current;
    const inner = controlsInnerRef.current;
    const stage = stageRef.current;
    const shell = shellRef.current;
    if (!col || !inner || !stage) return;

    if (layout.controlsMode === 'below') {
      inner.style.top = '';
      return;
    }

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
      let top = Math.max(0, Math.min(maxTop, mid - colRect.top - innerH / 2));

      if (shell) {
        const shellRect = shell.getBoundingClientRect();
        const innerTopAbs = colRect.top + top;
        if (innerTopAbs < shellRect.top) {
          top = Math.max(0, shellRect.top - colRect.top);
        }
        const innerBottomAbs = colRect.top + top + innerH;
        if (innerBottomAbs > shellRect.bottom) {
          top = Math.max(0, Math.min(maxTop, shellRect.bottom - colRect.top - innerH));
        }
      }

      inner.style.top = `${Math.round(top)}px`;
    }
  }, [layout.controlsMode]);

  useLayoutEffect(() => {
    measurePane();
    const shell = shellRef.current;
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measurePane) : null;
    if (shell) ro?.observe(shell);
    const scrollParent = shell ? findScrollParent(shell) : null;
    if (scrollParent) ro?.observe(scrollParent);
    const chatArea = shell?.closest('.main-chat-area, .messages-scroll');
    if (chatArea && chatArea !== scrollParent && chatArea !== shell) {
      ro?.observe(chatArea);
    }
    window.addEventListener('resize', measurePane);
    window.visualViewport?.addEventListener('resize', measurePane);
    return () => {
      window.removeEventListener('resize', measurePane);
      window.visualViewport?.removeEventListener('resize', measurePane);
      ro?.disconnect();
    };
  }, [measurePane]);

  useLayoutEffect(() => {
    if (!showControls) return undefined;

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
  }, [showControls, messages.length, activeIndex, firstMessageId, visibleCount, updateControlPosition]);

  if (messages.length === 1) {
    return (
      <div className="single-response-wide">
        <MessageBubble
          message={messages[0]}
          onReply={onReply}
          onExpand={onExpand}
          onClick={onClick}
          onSearchReferences={onSearchReferences}
          onReferenceSearchOpened={onReferenceSearchOpened}
          userQuestion={userQuestion}
          showReplyButton={true}
          userAvatarId={userAvatarId}
          userAvatarOptions={userAvatarOptions}
        />
      </div>
    );
  }

  const viewportWidth = visibleCount * layout.slideW + GAP * (visibleCount - 1);
  const offset = showAll ? 0 : activeIndex * (layout.slideW + GAP);
  const controlsMode = showControls ? layout.controlsMode : 'none';

  return (
    <div
      className={`advisor-carousel carousel-mode controls-${controlsMode}${showAll ? ' showing-all' : ''}`}
      ref={shellRef}
      data-visible={visibleCount}
      data-controls={controlsMode}
      data-slide-w={layout.slideW}
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
                  onReferenceSearchOpened={onReferenceSearchOpened}
                  userQuestion={userQuestion}
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
