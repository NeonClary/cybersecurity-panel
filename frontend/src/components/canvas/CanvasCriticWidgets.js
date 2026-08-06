import React, { useState } from 'react';
import Icon from './CanvasIcon';

const fireToast = (msg, kind = 'success') =>
  window.dispatchEvent(new CustomEvent('canvas-toast', { detail: { msg, kind } }));

// Critic widgets are scripted in canvas; the *real* critique should happen in
// the main chat so message history lives in one place (per Daniel's review).
// "Open in chat" stashes a draft prompt + persona hint then asks CanvasPage to
// navigate to chat — the chat page can read `canvas-chat-handoff` from localStorage.
const handoffToChat = (persona, prompt, context = {}) => {
  try {
    localStorage.setItem('canvas-chat-handoff', JSON.stringify({
      at: Date.now(), persona, prompt, ...context,
    }));
  } catch { /* ignore */ }
  window.dispatchEvent(new CustomEvent('canvas-open-in-chat', { detail: { persona, prompt } }));
  fireToast(`Opening ${persona} in chat — full history will be there.`);
};

// ---------- Reviewer 2 widget ----------
export function Reviewer2Widget({ state, setState, openModal }) {
  return (
    <>
      <div className="critic-prompt">
        "Paste a draft paragraph, abstract, or section. I'll respond as the most uncharitable but technically competent reviewer your work will ever see."
      </div>
      {state.lastReview ? (
        <div className="review">
          <span className="review-tag">Last critique · {state.lastReview.severity}/10 severity</span>
          <div style={{ marginBottom: 6 }}><strong>Major:</strong> {state.lastReview.major}</div>
          <div style={{ color: 'var(--canvas-text-2)', fontSize: 12 }}>+{state.lastReview.minorCount} minor issues, {state.lastReview.suggestionCount} suggestions</div>
        </div>
      ) : (
        <div style={{ fontSize: 11.5, color: 'var(--canvas-text-3)', fontStyle: 'italic', padding: '4px 2px' }}>
          No drafts reviewed yet.
        </div>
      )}
      <div className="critic-meter">
        <span>tone</span>
        <div className="bar"><i style={{ width: '92%' }}/></div>
        <span style={{ color: 'var(--canvas-critic)' }}>harsh</span>
      </div>
      <div style={{ display: 'flex', gap: 6, alignSelf: 'flex-start' }}>
        <button
          className="btn btn-critic"
          onClick={() => openModal('reviewer-2', {
            initial: state.lastDraft,
            onComplete: (review) => setState({ ...state, lastDraft: review.draft, lastReview: review }),
          })}
        >
          <Icon name="gavel" size={13}/>Get critique
        </button>
        <button
          className="btn"
          title="Open Reviewer 2 in the main chat (history lives there)"
          onClick={() => handoffToChat('Reviewer 2', state.lastDraft
            ? `Critique this draft as Reviewer 2: "${state.lastDraft}"`
            : 'Open Reviewer 2 and ready a critique.')}
        >
          <Icon name="message" size={13}/>Open in chat
        </button>
      </div>
    </>
  );
}

// ---------- Devil's Advocate widget ----------
export function DevilsAdvocateWidget({ state, setState, openModal }) {
  return (
    <>
      <div style={{ fontSize: 11, color: 'var(--canvas-text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Your claim</div>
      <div style={{ fontSize: 13, color: 'var(--canvas-text)', fontWeight: 500, lineHeight: 1.4, padding: '4px 0' }}>"{state.claim}"</div>
      <div style={{ fontSize: 11, color: 'var(--canvas-critic)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginTop: 4 }}>
        Strongest counters · {state.counters.length}
      </div>
      <div className="devil-list">
        {state.counters.slice(0, 3).map((c, i) => (
          <div key={i} className="devil-item">
            <div className="lbl">{c.lbl}</div>
            <div>{c.text}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, alignSelf: 'flex-start' }}>
        <button
          className="btn btn-critic"
          onClick={() => openModal('devils-advocate', {
            claim: state.claim,
            counters: state.counters,
            onUpdate: (next) => setState({ ...state, ...next }),
          })}
        >
          <Icon name="scale" size={13}/>Push harder
        </button>
        <button
          className="btn"
          title="Open Devil's Advocate in the main chat (history lives there)"
          onClick={() => handoffToChat("Devil's Advocate",
            `Take the position of devil's advocate on my claim: "${state.claim || 'my current security plan'}". Be ruthless.`)}
        >
          <Icon name="message" size={13}/>Open in chat
        </button>
      </div>
    </>
  );
}

// ---------- Scope realism widget ----------
export function ScopeRealismWidget({ state, openModal }) {
  return (
    <div className="realism">
      <div className="realism-verdict">
        <div className="verdict-head">
          <div className="verdict-score">{state.score.toFixed(1)}</div>
          <div>
            <div className="verdict-label">Feasibility</div>
            <div style={{ fontSize: 12, color: 'var(--canvas-text-2)', marginTop: 2 }}>{state.label}</div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--canvas-text-3)', fontFamily: 'var(--canvas-mono)' }}>
          target: {state.target}
        </div>
      </div>
      <div>
        {state.factors.map(f => (
          <div key={f.label} className="realism-row">
            <span className="label-cell">{f.label}</span>
            <span className="gauge"><i style={{ width: f.val + '%' }}/></span>
            <span className="val">{f.val}</span>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, alignSelf: 'flex-start' }}>
        <button
          className="btn btn-critic"
          onClick={() => openModal('scope-realism', { state })}
        >
          <Icon name="bullseye" size={13}/>Read full verdict
        </button>
        <button
          className="btn"
          title="Open Scope Realism in the main chat (history lives there)"
          onClick={() => handoffToChat('Scope Realism',
            `Run a brutal feasibility check on my goal: "${state.target || 'my current rollout scope'}". Be specific about what's at risk.`)}
        >
          <Icon name="message" size={13}/>Open in chat
        </button>
      </div>
    </div>
  );
}

// ===================================================================
// Critic modals
// ===================================================================

const REVIEW_TEMPLATES = [
  {
    severity: 8,
    major: 'The policy states what is required but never who enforces it or how compliance is measured. "MFA must be enabled where practical" is not a control — "where practical" is an exception process wearing a trench coat. Every attacker reads that clause the same way your least-motivated admin does.',
    minor: [
      'No owner is named for any control. Unowned controls decay within two quarters.',
      'Scope says "all systems" but the procedures only cover corporate laptops — SaaS, BYOD, and service accounts are unaddressed.',
      'Review cadence is "periodically." Auditors will read that as "never." Name a quarter.',
      'No consequence is defined for violations, which makes the whole document advisory.',
    ],
    suggestions: [
      'Rewrite each requirement as testable: who, what, by when, verified how.',
      'Add an exceptions section with an approver, an expiry date, and a register.',
      'Name a control owner per section, not one owner for the whole policy.',
    ],
  },
  {
    severity: 7,
    major: 'The plan claims the rollout will "significantly reduce risk" without a baseline or a target. Reduced from what, to what, measured how? Without numbers this is a budget request, not a security plan — and the CFO will treat it as one.',
    minor: [
      'Timeline has no dependencies: identity cleanup is scheduled after the SSO migration that depends on it.',
      'No statement of what happens to legacy systems that cannot meet the new baseline.',
      'Success criteria are activities ("deploy EDR") rather than outcomes ("alerts triaged within 30 minutes").',
    ],
    suggestions: [
      'Add a current-state metric and a 90-day target for each initiative.',
      'List the top 2 risks to the plan itself and the fallback for each.',
    ],
  },
  {
    severity: 9,
    major: 'This reads like a product brochure, not an incident report. There is no timeline, no root cause, and no number. The strongest claim is that the incident was "handled swiftly with no evidence of data exposure" — absence of evidence in an environment with 30-day log retention is not evidence of absence, and any regulator will say so.',
    minor: [
      'The word "sophisticated" appears twice describing an attack that started with a phished password.',
      '"No customer action is required" is asserted before the impact section establishes it.',
      'Lessons-learned section contains zero committed changes with owners or dates.',
    ],
    suggestions: [
      'Lead with the facts: detection time, dwell time, systems touched, records at risk.',
      'Every lesson learned gets an owner and a date, or it is a wish, not a lesson.',
    ],
  },
];

export function ReviewerModal({ data, onClose }) {
  const [draft, setDraft] = useState(data.initial || '');
  const [running, setRunning] = useState(false);
  const [review, setReview] = useState(null);

  const run = () => {
    if (!draft.trim()) return;
    setRunning(true);
    setReview(null);
    setTimeout(() => {
      const idx = (draft.length + draft.split(' ').length) % REVIEW_TEMPLATES.length;
      const r = REVIEW_TEMPLATES[idx];
      setReview(r);
      setRunning(false);
    }, 900);
  };

  const accept = () => {
    if (!review) return;
    data.onComplete({
      draft,
      severity: review.severity,
      major: review.major,
      minorCount: review.minor.length,
      suggestionCount: review.suggestions.length,
    });
    fireToast('Critique saved · severity ' + review.severity + '/10', 'critic');
    onClose();
  };

  return (
    <div className="canvas-modal huge" onClick={(e) => e.stopPropagation()}>
      <div className="modal-head">
        <div className="modal-icon critic"><Icon name="gavel" size={18}/></div>
        <div style={{ flex: 1 }}>
          <div className="modal-title">Reviewer 2 Simulator</div>
          <div className="modal-sub">Paste a draft. Get the harshest competent peer review you'll ever read — before a real reviewer does.</div>
        </div>
        <button className="icon-btn" onClick={onClose}><Icon name="x" size={16}/></button>
      </div>
      <div className="modal-body">
        <div className="form-row">
          <label className="label">Your draft</label>
          <textarea
            className="textarea"
            style={{ minHeight: 120, fontFamily: 'var(--canvas-mono)', fontSize: 12.5 }}
            value={draft}
            onChange={e => setDraft(e.target.value)}
            placeholder="Paste an abstract, a claim, a paragraph…"
          />
          <div style={{ fontSize: 11, color: 'var(--canvas-text-3)', fontFamily: 'var(--canvas-mono)', textAlign: 'right' }}>{draft.length} chars · {draft.trim().split(/\s+/).filter(Boolean).length} words</div>
        </div>

        {!review && !running && (
          <div style={{ marginTop: 16, padding: '12px 14px', background: 'var(--canvas-bg-2)', border: '1px dashed var(--canvas-border-2)', borderRadius: 8, fontSize: 12, color: 'var(--canvas-text-3)', lineHeight: 1.5 }}>
            <strong style={{ color: 'var(--canvas-text-2)' }}>What this is:</strong> a simulated peer review tuned to push back hard. It will name unstated operationalizations, rival explanations, and weak phrasings. <span style={{ color: 'var(--canvas-text-4)' }}>It will not flatter you. That's the point.</span>
          </div>
        )}

        {running && (
          <div style={{ marginTop: 20, display: 'flex', alignItems: 'center', gap: 10, color: 'var(--canvas-text-2)' }}>
            <div className="spinner critic"/>
            <span style={{ fontFamily: 'var(--canvas-mono)', fontSize: 12 }}>parsing claims · finding rival hypotheses · drafting…</span>
          </div>
        )}

        {review && (
          <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                fontFamily: 'var(--canvas-mono)', fontSize: 22, fontWeight: 600,
                color: 'var(--canvas-critic)', letterSpacing: '-0.02em',
              }}>{review.severity}/10</div>
              <div style={{ fontSize: 11, color: 'var(--canvas-text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>severity</div>
              <div style={{ flex: 1 }}/>
              <div style={{ fontSize: 11, fontFamily: 'var(--canvas-mono)', color: 'var(--canvas-text-3)' }}>{review.minor.length} minor · {review.suggestions.length} suggestions</div>
            </div>
            <div className="review">
              <span className="review-tag">Major issue</span>
              {review.major}
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--canvas-text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 6 }}>Minor issues</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: 'var(--canvas-text-2)', lineHeight: 1.55 }}>
                {review.minor.map((m, i) => <li key={i} style={{ marginBottom: 4 }}>{m}</li>)}
              </ul>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--canvas-accent)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 6 }}>Suggestions</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: 'var(--canvas-text-2)', lineHeight: 1.55 }}>
                {review.suggestions.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{s}</li>)}
              </ul>
            </div>
          </div>
        )}
      </div>
      <div className="modal-foot">
        <button className="btn btn-ghost" onClick={onClose}>Close</button>
        {review ? (
          <>
            <button className="btn" onClick={() => { setReview(null); }}>New critique</button>
            <button className="btn btn-critic" onClick={accept}><Icon name="check" size={13}/>Save to widget</button>
          </>
        ) : (
          <button className="btn btn-critic" onClick={run} disabled={!draft.trim() || running}>
            <Icon name="gavel" size={13}/>{running ? 'Reviewing…' : 'Critique my draft'}
          </button>
        )}
      </div>
    </div>
  );
}

const HARDER_COUNTERS = [
  { lbl: 'Compliance ≠ security', text: 'Your plan optimizes for passing the audit, not stopping the attacker. Every control maps to a framework line item; none map to the actual intrusion paths in your last three incidents.' },
  { lbl: 'Insider blind spot', text: 'Everything here assumes the threat is outside the perimeter. A disgruntled admin with legitimate credentials defeats every control on this list without triggering one alert.' },
  { lbl: 'Operational decay', text: 'Day-one coverage is not the question. Who tunes these detections in month six, when the person who built them has left and the alert queue is 400 deep?' },
  { lbl: 'Vendor dependency', text: 'Your resilience story depends on three SaaS vendors staying up and honest. Their breach is your breach, and your plan has no section for it.' },
];

export function DevilsModal({ data, onClose }) {
  const [counters, setCounters] = useState(data.counters);
  const [pushing, setPushing] = useState(false);

  const pushHarder = () => {
    setPushing(true);
    setTimeout(() => {
      const next = HARDER_COUNTERS.find(c => !counters.find(x => x.lbl === c.lbl));
      if (next) {
        const nc = [...counters, next];
        setCounters(nc);
        data.onUpdate({ counters: nc });
        fireToast('Stronger counter added: "' + next.lbl + '"', 'critic');
      } else {
        fireToast('No more counters — your plan is more robust than I thought.');
      }
      setPushing(false);
    }, 800);
  };

  return (
    <div className="canvas-modal wide" onClick={(e) => e.stopPropagation()}>
      <div className="modal-head">
        <div className="modal-icon critic"><Icon name="scale" size={18}/></div>
        <div style={{ flex: 1 }}>
          <div className="modal-title">Devil's Advocate</div>
          <div className="modal-sub">The strongest counter-arguments to your plan, ranked by how much they should worry you.</div>
        </div>
        <button className="icon-btn" onClick={onClose}><Icon name="x" size={16}/></button>
      </div>
      <div className="modal-body">
        <div style={{ background: 'var(--canvas-bg-2)', border: '1px solid var(--canvas-border-2)', borderRadius: 9, padding: '12px 14px', marginBottom: 16 }}>
          <div style={{ fontSize: 10.5, color: 'var(--canvas-text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 4 }}>Your claim</div>
          <div style={{ fontSize: 14, color: 'var(--canvas-text)', fontWeight: 500 }}>"{data.claim}"</div>
        </div>
        <div className="devil-list">
          {counters.map((c, i) => (
            <div key={i} className="devil-item" style={{ padding: '12px 14px 12px 36px' }}>
              <div className="lbl">{c.lbl}</div>
              <div style={{ fontSize: 13, lineHeight: 1.55 }}>{c.text}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="modal-foot">
        <button className="btn btn-ghost" onClick={onClose}>Close</button>
        <button className="btn btn-critic" onClick={pushHarder} disabled={pushing}>
          {pushing ? <><div className="spinner critic"/>Thinking…</> : <><Icon name="zap" size={13}/>Push harder</>}
        </button>
      </div>
    </div>
  );
}

export function ScopeModal({ data, onClose }) {
  const s = data.state;
  return (
    <div className="canvas-modal wide" onClick={(e) => e.stopPropagation()}>
      <div className="modal-head">
        <div className="modal-icon critic"><Icon name="bullseye" size={18}/></div>
        <div style={{ flex: 1 }}>
          <div className="modal-title">Scope Realism Check</div>
          <div className="modal-sub">A brutal feasibility verdict on "{s.target}" given your current pace.</div>
        </div>
        <button className="icon-btn" onClick={onClose}><Icon name="x" size={16}/></button>
      </div>
      <div className="modal-body">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 16px', background: 'var(--canvas-bg-2)', border: '1px solid rgba(232,100,184,0.3)', borderRadius: 10, marginBottom: 18 }}>
          <div style={{ fontFamily: 'var(--canvas-mono)', fontSize: 36, fontWeight: 600, color: 'var(--canvas-critic)', letterSpacing: '-0.02em', lineHeight: 1 }}>{s.score.toFixed(1)}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10.5, color: 'var(--canvas-text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Verdict</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--canvas-text)', marginTop: 2 }}>{s.label}</div>
            <div style={{ fontSize: 12, color: 'var(--canvas-text-3)', marginTop: 4 }}>5.0 = neither feasible nor infeasible · &lt;3 = unrealistic · &gt;7 = comfortable</div>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div className="label" style={{ marginBottom: 8 }}>Factor breakdown</div>
          {s.factors.map(f => (
            <div key={f.label} className="realism-row" style={{ padding: '7px 0' }}>
              <span className="label-cell" style={{ width: 140, fontSize: 12.5 }}>{f.label}</span>
              <span className="gauge" style={{ height: 6 }}><i style={{ width: f.val + '%' }}/></span>
              <span className="val" style={{ width: 36 }}>{f.val}</span>
            </div>
          ))}
        </div>

        <div className="review">
          <span className="review-tag">The actual problem</span>
          {s.notes}
        </div>

        <div style={{ marginTop: 16 }}>
          <div className="label" style={{ marginBottom: 8 }}>Recommended actions</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--canvas-text-2)', lineHeight: 1.6 }}>
            <li><strong style={{ color: 'var(--canvas-text)' }}>Lock the scope in writing.</strong> Scope creep — not effort — is what sinks security rollouts.</li>
            <li>Build slack into the timeline. Vendor delays, change freezes, and on-call weeks will eat 20–30% of it.</li>
            <li>Cut a phase. A rollout that ships MFA and backups this quarter beats one that promises everything next year.</li>
            <li>Assign a single owner per milestone; shared ownership reads as no ownership in the post-mortem.</li>
          </ul>
        </div>
      </div>
      <div className="modal-foot">
        <button className="btn btn-ghost" onClick={onClose}>Close</button>
        <button className="btn btn-critic"><Icon name="zap" size={13}/>Re-run with new estimates</button>
      </div>
    </div>
  );
}
