import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import MessageBubble from './MessageBubble';

/**
 * Always show one advisor answer at a time with prev/next + dots.
 * Messages should already be ordered most-relevant-first (orchestrator rank).
 */
const AdvisorCarousel = ({ messages = [], onReply, onExpand, onClick, onSearchReferences, userAvatarId, userAvatarOptions }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef(null);

  useEffect(() => {
    setActiveIndex(0);
  }, [messages.map((m) => m.id).join('|')]);

  const goPrev = useCallback(() => {
    setActiveIndex(i => Math.max(0, i - 1));
  }, []);

  const goNext = useCallback(() => {
    setActiveIndex(i => Math.min(messages.length - 1, i + 1));
  }, [messages.length]);

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

  return (
    <div className="advisor-carousel carousel-mode" ref={containerRef}>
      <button
        className="carousel-arrow carousel-prev"
        onClick={goPrev}
        disabled={activeIndex === 0}
        aria-label="Previous advisor"
      >
        <ChevronLeft size={20} />
      </button>

      <div className="carousel-viewport">
        <div
          className="carousel-track"
          style={{
            width: `${messages.length * 100}%`,
            transform: `translateX(-${activeIndex * (100 / messages.length)}%)`,
          }}
        >
          {messages.map(message => (
            <div
              key={message.id}
              className="carousel-slide"
              style={{ width: `${100 / messages.length}%` }}
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

      <button
        className="carousel-arrow carousel-next"
        onClick={goNext}
        disabled={activeIndex === messages.length - 1}
        aria-label="Next advisor"
      >
        <ChevronRight size={20} />
      </button>

      <div className="carousel-dots" role="tablist" aria-label="Advisor answers">
        {messages.map((m, i) => (
          <button
            key={m.id}
            type="button"
            className={`carousel-dot ${i === activeIndex ? 'active' : ''}`}
            onClick={() => setActiveIndex(i)}
            aria-label={m.advisorName ? `Show ${m.advisorName}` : `Go to advisor ${i + 1}`}
            aria-selected={i === activeIndex}
            role="tab"
          />
        ))}
      </div>
    </div>
  );
};

export default AdvisorCarousel;
