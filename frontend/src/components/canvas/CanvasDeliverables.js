// Documents view — multi-project security deliverable center.
// Each "project" is a draft of a template (assessment report, IR plan, policy,
// briefing slides, etc.). You can keep many projects in flight, switch between
// them, version-rollback, embed images, and export to Markdown / HTML / Print.
import React, { useState, useMemo, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import Icon from './CanvasIcon';
import { MOD } from './platform';
import LatexEditor from './CanvasLatexEditor';
import { fetchCanvas, saveDeliverables, debounce } from '../../utils/canvasApi';

// Markdown plugins shared across all rendered blocks. remark-math + rehype-katex
// give us real LaTeX math (`$...$` inline, `$$...$$` block) inside any preview.
const REMARK_PLUGINS = [remarkGfm, remarkMath];
const REHYPE_PLUGINS = [rehypeKatex];

const fireToast = (msg, kind = 'success') =>
  window.dispatchEvent(new CustomEvent('canvas-toast', { detail: { msg, kind } }));

const STORE_KEY = 'canvas-deliverables-v2';
const MAX_VERSIONS = 10;
const newId = (p) => p + Math.random().toString(36).slice(2, 8);

// ============================================================================
// Templates
// ============================================================================
export const TEMPLATES = [
  {
    id: 'research-paper',
    name: 'Security Assessment Report',
    desc: 'Executive summary → Scope → Findings → Risk ratings → Remediation → Appendix',
    icon: 'book',
    mode: 'paper',
    sections: [
      { id: 'abstract', name: 'Executive summary', target: 250, hint: 'One paragraph for leadership: what was assessed, top risks, headline recommendation.', checks: ['hasNumber', 'hasFinding'] },
      { id: 'intro', name: 'Scope & methodology', target: 600, hint: 'Systems in scope, testing window, methodology and tools, rules of engagement.', checks: ['hasNumber'] },
      { id: 'results', name: 'Findings', target: 1000, hint: 'One finding per block: description, evidence, affected assets. Reference screenshots/tables.', checks: ['hasNumber', 'hasFigure'] },
      { id: 'methods', name: 'Risk ratings', target: 400, hint: 'Severity × likelihood per finding. Say which rating scale you used.', checks: ['hasRisk', 'hasNumber'] },
      { id: 'discussion', name: 'Remediation plan', target: 800, hint: 'Prioritized fixes with owner and target date per item.', checks: ['hasOwner', 'hasDate'] },
      { id: 'refs', name: 'Appendix', target: 0, hint: 'Raw output, full host lists, references (@key).', checks: [] },
    ],
  },
  {
    id: 'thesis-chapter',
    name: 'Incident Report',
    desc: 'Overview → Timeline → Impact → Root cause → Containment → Lessons learned',
    icon: 'book',
    mode: 'paper',
    sections: [
      { id: 'overview', name: 'Overview', target: 200, hint: 'What happened, when detected, current status — in plain language.', checks: [] },
      { id: 'background', name: 'Timeline', target: 600, hint: 'Timestamped sequence: initial access → detection → escalation → containment.', checks: ['hasNumber'] },
      { id: 'methods', name: 'Impact', target: 400, hint: 'Systems, data, users, and money affected. Numbers over adjectives.', checks: ['hasNumber'] },
      { id: 'results', name: 'Root cause', target: 500, hint: 'Technical root cause and the control gaps that let it happen.', checks: ['hasGap'] },
      { id: 'discussion', name: 'Containment & lessons learned', target: 600, hint: 'What stopped it, what changes now, with owners and dates.', checks: ['hasOwner', 'hasDate'] },
    ],
  },
  {
    id: 'nsf-grfp',
    name: 'Security Policy',
    desc: 'Purpose → Scope → Policy statements → Roles → Exceptions → Enforcement.',
    icon: 'award',
    mode: 'document',
    sections: [
      { id: 'personal', name: 'Purpose & scope', target: 250, hint: 'Why this policy exists, who and what it covers. Short beats thorough.', checks: [] },
      { id: 'research', name: 'Policy statements', target: 800, hint: 'Numbered, testable statements ("MFA is required for…"). Include roles, exceptions process, enforcement.', checks: ['hasNumber', 'hasOwner'] },
    ],
  },
  {
    id: 'conference-abstract',
    name: 'Executive Briefing',
    desc: 'Single section, 250 words. Lead with the risk and the ask.',
    icon: 'send',
    mode: 'document',
    sections: [
      { id: 'abs', name: 'Briefing', target: 250, hint: 'One paragraph for the board: risk, business impact, what you need approved.', checks: ['hasFinding', 'hasNumber'] },
    ],
  },
  {
    id: 'defense-slides',
    name: 'Security Briefing Slides',
    desc: 'Title → Agenda → Threat landscape → Posture → Gaps → Plan → Budget → Q&A',
    icon: 'kanban',
    mode: 'slides',
    sections: [
      { id: 'title', name: 'Title slide', target: 30, hint: 'Topic, your name, audience, date.', checks: [] },
      { id: 'outline', name: 'Agenda', target: 60, hint: '5–7 bullets covering the talk arc.', checks: [] },
      { id: 'background', name: 'Threat landscape', target: 200, hint: 'What is targeting orgs like yours right now. Cite sources.', checks: ['hasRisk'] },
      { id: 'question', name: 'Current posture', target: 120, hint: 'Where you stand today — one honest slide.', checks: ['hasNumber'] },
      { id: 'methods', name: 'Gaps & risks', target: 200, hint: 'Top gaps ranked by business impact.', checks: ['hasRisk'] },
      { id: 'results', name: 'Plan', target: 300, hint: 'One slide per initiative. Lead with the outcome.', checks: ['hasDate', 'hasNumber'] },
      { id: 'discussion', name: 'Budget & asks', target: 200, hint: 'What you need: money, headcount, decisions.', checks: ['hasNumber'] },
      { id: 'qa', name: 'Anticipated Q&A', target: 300, hint: 'Hardest 5 questions and your answers.', checks: [] },
    ],
  },
  {
    id: 'poster',
    name: 'Risk Snapshot (1-pager)',
    desc: '4-quadrant one-pager: Context · Top risks · Mitigations · Next steps.',
    icon: 'layout',
    mode: 'poster',
    sections: [
      { id: 'title', name: 'Title & owner', target: 30, hint: 'System or program name, owner, date.', checks: [] },
      { id: 'intro', name: 'Context', target: 200, hint: 'What this system does and why it matters to the business.', checks: [] },
      { id: 'methods', name: 'Top risks', target: 200, hint: '3–5 risks ranked by impact × likelihood.', checks: ['hasRisk'] },
      { id: 'results', name: 'Mitigations', target: 250, hint: 'Current and planned controls per risk.', checks: ['hasNumber'] },
      { id: 'discussion', name: 'Next steps', target: 200, hint: 'Decisions needed, owners, dates.', checks: ['hasOwner', 'hasDate'] },
      { id: 'refs', name: 'References', target: 80, hint: 'Framework mappings, related reports (@key).', checks: [] },
    ],
  },
  {
    id: 'cv',
    name: 'Security Résumé',
    desc: 'Standard sections: Summary · Experience · Certs · Projects · Skills.',
    icon: 'user',
    mode: 'document',
    sections: [
      { id: 'header', name: 'Header', target: 40, hint: 'Name, target role, location, contact.', checks: [] },
      { id: 'education', name: 'Summary', target: 100, hint: '2–3 sentences: who you are, your specialty, one quantified win.', checks: ['hasNumber'] },
      { id: 'publications', name: 'Experience', target: 300, hint: 'Most recent first. Lead each bullet with impact + numbers.', checks: ['hasNumber'] },
      { id: 'talks', name: 'Certifications & training', target: 150, hint: 'Cert · Issuer · Year. In-progress ones count — say so.', checks: [] },
      { id: 'awards', name: 'Projects & home lab', target: 100, hint: 'CTFs, detections you wrote, lab builds — with links.', checks: [] },
      { id: 'service', name: 'Community & service', target: 100, hint: 'Meetups, open source, mentoring, writing.', checks: [] },
      { id: 'skills', name: 'Skills', target: 60, hint: 'Tools, platforms, languages — grouped, not a wall.', checks: [] },
    ],
  },
  {
    id: 'cover-letter',
    name: 'Cover Letter',
    desc: 'For security job applications — specific, quantified, short.',
    icon: 'send',
    mode: 'document',
    sections: [
      { id: 'header', name: 'Header', target: 40, hint: 'Date, recipient, salutation.', checks: [] },
      { id: 'opener', name: 'Opening paragraph', target: 100, hint: 'Why you\'re writing + the role.', checks: [] },
      { id: 'body', name: 'Why me', target: 250, hint: 'Specific achievements that match the posting. Numbers > adjectives.', checks: ['hasNumber'] },
      { id: 'fit', name: 'Why this team', target: 150, hint: 'What about this company / security team makes it the right fit.', checks: [] },
      { id: 'close', name: 'Close', target: 60, hint: 'Thanks + next step + signature.', checks: [] },
    ],
  },
  {
    id: 'irb-protocol',
    name: 'Incident Response Plan',
    desc: 'Roles → Severity levels → Playbooks → Communications → Evidence → Recovery.',
    icon: 'shield',
    mode: 'document',
    sections: [
      { id: 'overview', name: 'Purpose & scope', target: 200, hint: 'What counts as an incident here, and who this plan is for.', checks: [] },
      { id: 'background', name: 'Roles & contacts', target: 300, hint: 'Incident commander, deputies, legal, PR, on-call tree — with phone numbers.', checks: ['hasOwner'] },
      { id: 'aims', name: 'Severity levels', target: 250, hint: 'SEV1–SEV3 definitions with example scenarios and response SLAs.', checks: ['hasNumber'] },
      { id: 'procedures', name: 'Response playbooks', target: 500, hint: 'Step-by-step for your top scenarios: ransomware, BEC, account takeover, data exposure.', checks: ['hasNumber'] },
      { id: 'consent', name: 'Communications plan', target: 200, hint: 'Who is notified when — internal, customers, regulators, law enforcement.', checks: ['hasDate'] },
      { id: 'risks', name: 'Evidence handling', target: 200, hint: 'What to preserve, what never to wipe, chain of custody.', checks: ['hasLimit'] },
      { id: 'data', name: 'Recovery & post-incident', target: 200, hint: 'Restore order, validation steps, blameless review within N days.', checks: ['hasNumber'] },
    ],
  },
  {
    id: 'meeting-prep',
    name: 'Stakeholder Meeting Prep',
    desc: 'Bring this to your 1:1 or steering meeting — agenda, updates, decisions, follow-ups.',
    icon: 'message',
    mode: 'document',
    sections: [
      { id: 'agenda', name: 'Agenda', target: 80, hint: '3–5 bullets ranked by priority.', checks: [] },
      { id: 'progress', name: 'Progress since last meeting', target: 200, hint: 'What you actually did, with numbers when possible.', checks: ['hasNumber'] },
      { id: 'blockers', name: 'Blockers', target: 150, hint: 'What you need from them to move forward.', checks: ['hasLimit'] },
      { id: 'decisions', name: 'Decisions needed', target: 200, hint: 'Frame as A/B options with your recommendation.', checks: [] },
      { id: 'questions', name: 'Questions', target: 150, hint: 'Open questions you genuinely want their take on.', checks: [] },
      { id: 'followup', name: 'Action items (post-meeting)', target: 100, hint: 'Fill in during/after. Owner + due date for each.', checks: ['hasOwner'] },
    ],
  },
  {
    id: 'dissertation-formatting',
    name: 'Audit Evidence Checklist',
    desc: 'Catch-everything pass before the auditors arrive.',
    icon: 'shield',
    mode: 'document',
    sections: [
      { id: 'frontmatter', name: 'Policies & procedures', target: 0, hint: 'Current versions, approval signatures, review dates within the last year.', checks: ['hasDate'] },
      { id: 'margins', name: 'Access reviews', target: 0, hint: 'Quarterly review exports, sign-offs, revocation tickets for leavers.', checks: ['hasDate'] },
      { id: 'fonts', name: 'Change management', target: 0, hint: 'Sampled changes with approvals; emergency-change log.', checks: ['hasNumber'] },
      { id: 'pagenumbers', name: 'Vulnerability management', target: 0, hint: 'Scan reports, remediation SLAs, exception approvals.', checks: ['hasNumber'] },
      { id: 'figures', name: 'Backup & recovery', target: 0, hint: 'Backup job logs and the last successful restore test.', checks: ['hasDate'] },
      { id: 'citations', name: 'Security awareness', target: 0, hint: 'Training completion rates, phishing simulation results.', checks: ['hasNumber'] },
      { id: 'appendices', name: 'Incident records', target: 0, hint: 'Incident log, post-mortems, evidence that lessons were applied.', checks: [] },
      { id: 'proquest', name: 'Vendor / third-party', target: 0, hint: 'Vendor list, SOC 2 / ISO reports collected, contract security clauses.', checks: [] },
    ],
  },
  {
    id: 'faculty-hunt',
    name: 'Vendor / MSP Evaluation',
    desc: 'Choosing a security vendor or managed provider — research before you sign.',
    icon: 'user',
    mode: 'document',
    sections: [
      { id: 'criteria', name: 'Requirements', target: 150, hint: 'What you actually need: coverage hours, response SLA, compliance support, budget band.', checks: ['hasNumber'] },
      { id: 'shortlist', name: 'Shortlist (3–5 vendors)', target: 400, hint: 'For each: name, offering, pricing model, why they fit.', checks: ['hasNumber'] },
      { id: 'pubs', name: 'Diligence', target: 300, hint: 'SOC 2 / ISO status, breach history, references from similar-size customers.', checks: [] },
      { id: 'students', name: 'Trial / PoC notes', target: 200, hint: 'What you tested, response times observed, gaps found.', checks: ['hasNumber'] },
      { id: 'reachout', name: 'Negotiation plan', target: 200, hint: 'Contract terms to push on: exit clause, data ownership, SLA credits.', checks: [] },
      { id: 'notes', name: 'Decision log', target: 0, hint: 'Final choice and why — future-you will want this.', checks: [] },
    ],
  },
  {
    id: 'research-statement',
    name: 'Security Program Strategy',
    desc: 'Annual strategy: where you are, where you\'re going, what it costs.',
    icon: 'sparkles',
    mode: 'document',
    sections: [
      { id: 'overview', name: 'Overview', target: 200, hint: 'One paragraph: program mission and this year\'s theme.', checks: [] },
      { id: 'past', name: 'Current state', target: 600, hint: 'Honest posture assessment: what works, key metrics, incidents handled.', checks: ['hasNumber', 'hasFinding'] },
      { id: 'current', name: 'Gaps & risks', target: 400, hint: 'Top gaps ranked by business risk.', checks: ['hasGap', 'hasRisk'] },
      { id: 'future', name: 'Roadmap', target: 600, hint: '12–18 month arc: initiatives with quarters, owners, and outcomes.', checks: ['hasDate', 'hasOwner'] },
      { id: 'broader', name: 'Budget & resourcing', target: 200, hint: 'Headcount, tooling, training — and what happens if it is not funded.', checks: ['hasNumber'] },
    ],
  },
];

// ============================================================================
// Slash command catalog — typed at the start of a line in any section editor.
// ============================================================================
const SLASH_COMMANDS = [
  { id: 'h2', label: 'Heading', kind: 'block', icon: 'list', insert: () => '## Heading\n' },
  { id: 'h3', label: 'Subheading', kind: 'block', icon: 'list', insert: () => '### Subheading\n' },
  { id: 'list', label: 'Bullet list', kind: 'block', icon: 'list', insert: () => '- ' },
  { id: 'todo', label: 'To-do', kind: 'block', icon: 'task', insert: () => '- [ ] ' },
  { id: 'numbered', label: 'Numbered list', kind: 'block', icon: 'list', insert: () => '1. ' },
  { id: 'quote', label: 'Quote', kind: 'block', icon: 'cite', insert: () => '> ' },
  { id: 'callout', label: 'Callout', kind: 'block', icon: 'sparkles', insert: () => '> [!note]\n> ' },
  { id: 'divider', label: 'Divider', kind: 'block', icon: 'list', insert: () => '\n---\n\n' },
  { id: 'code', label: 'Code block', kind: 'block', icon: 'flask', insert: () => '```\n\n```\n' },
  { id: 'math', label: 'Equation', kind: 'block', icon: 'flask', insert: () => '$$\nE = mc^2\n$$\n' },
  { id: 'inline-math', label: 'Inline equation', kind: 'inline', icon: 'flask', insert: () => '$x^2$' },
  { id: 'image', label: 'Image (paste URL)', kind: 'block', icon: 'download', insert: () => '![caption](https://)' },
  { id: 'cite', label: 'Citation @key', kind: 'inline', icon: 'book', insert: () => '(@key)' },
  { id: 'bold', label: 'Bold', kind: 'inline', icon: 'pencil', insert: () => '**bold**' },
  { id: 'italic', label: 'Italic', kind: 'inline', icon: 'pencil', insert: () => '*italic*' },
];

// ============================================================================
// Static "missing" checks
// ============================================================================
const CHECKS = {
  hasNumber: { test: (s) => /\d/.test(s), label: 'Mentions at least one number' },
  hasCitation: { test: (s) => /@\w+/.test(s), label: 'Cites at least one source (@key)' },
  hasFinding: { test: (s) => /\b(we (find|found|identified|observed)|finding|result|observed)/i.test(s), label: 'States a finding' },
  hasGap: { test: (s) => /\b(gap|lack|missing|unknown|unclear|despite)/i.test(s), label: 'Names a gap' },
  hasFigure: { test: (s) => /\b(fig(ure)?|table|screenshot)\.?\s*\d/i.test(s), label: 'References a figure, table, or screenshot' },
  hasLimit: { test: (s) => /\b(limit|caveat|however|future work|did not|cannot)/i.test(s), label: 'Acknowledges a limit' },
  hasRisk: { test: (s) => /\b(risk|threat|likelihood|impact|severity|critical|high|medium|low)/i.test(s), label: 'Names a risk or severity' },
  hasOwner: { test: (s) => /\b(owner|responsible|accountable|assigned|@\w+)/i.test(s), label: 'Assigns an owner' },
  hasDate: { test: (s) => /\b(by|due|deadline|q[1-4]|week|month|\d{4}-\d{2}|\d{1,2}\/\d{1,2})/i.test(s), label: 'Sets a date or deadline' },
};

const wordCount = (s) => (s || '').trim().split(/\s+/).filter(Boolean).length;
const readingMinutes = (n) => Math.max(1, Math.round(n / 220));

// ============================================================================
// Exporters
// ============================================================================
const exportMarkdown = (template, sections) => [
  `# ${template.name}\n`,
  ...template.sections.map(s => `## ${s.name}\n\n${sections[s.id] || ''}\n`),
].join('\n');
const exportLatex = (template, sections) => [
  '\\documentclass{article}',
  `\\title{${template.name}}`,
  '\\begin{document}',
  '\\maketitle',
  ...template.sections.map(s => `\n\\section{${s.name}}\n${sections[s.id] || ''}\n`),
  '\\end{document}',
].join('\n');
const exportHtml = (template, sections) => [
  '<!doctype html>',
  `<html><head><title>${template.name}</title></head><body>`,
  `<h1>${template.name}</h1>`,
  ...template.sections.map(s => `<section><h2>${s.name}</h2><p>${(sections[s.id] || '').replace(/\n/g, '<br>')}</p></section>`),
  '</body></html>',
].join('\n');
const downloadFile = (filename, mime, contents) => {
  const blob = new Blob([contents], { type: mime });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
};

// ============================================================================
// Project store — multi-project (was: single-template). Migrates v1 if found.
// ============================================================================
const loadStore = () => {
  try {
    const v2 = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    if (v2) return v2;
    // Migrate v1: turn each templateId entry into a project.
    const v1 = JSON.parse(localStorage.getItem('canvas-deliverables-v1') || '{}');
    if (v1 && v1.templates) {
      const projects = {};
      let activeId;
      Object.entries(v1.templates).forEach(([tid, sec]) => {
        const id = newId('p-');
        const { _aiNotes, ...rest } = sec;
        projects[id] = {
          id,
          name: TEMPLATES.find(t => t.id === tid)?.name || tid,
          templateId: tid,
          sections: rest,
          versions: [],
          aiNotes: _aiNotes || null,
          createdAt: Date.now(),
        };
        if (tid === v1.activeTemplateId) activeId = id;
      });
      return { activeProjectId: activeId, projects };
    }
  } catch { /* fallthrough */ }
  return { activeProjectId: null, projects: {} };
};

// ============================================================================
// Main view
// ============================================================================
const DeliverablesView = ({ allStates, authToken }) => {
  const [store, setStore] = useState(loadStore);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const hydratedRef = useRef(false);
  const [serverHydrated, setServerHydrated] = useState(false);

  // Prefer server store when available; keep localStorage as cache.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authToken) {
        hydratedRef.current = true;
        setServerHydrated(true);
        return;
      }
      const remote = await fetchCanvas(authToken);
      if (cancelled) return;
      const d = remote?.deliverables;
      if (d?.projects && Object.keys(d.projects).length) {
        setStore(d);
        localStorage.setItem(STORE_KEY, JSON.stringify(d));
      } else if (Object.keys(store.projects || {}).length) {
        await saveDeliverables(authToken, store);
      }
      hydratedRef.current = true;
      setServerHydrated(true);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  useEffect(() => { localStorage.setItem(STORE_KEY, JSON.stringify(store)); }, [store]);

  // Uploaded RAG documents (from chat uploads) — shown alongside drafted
  // artifacts so Documents is the single place to see what the panel knows.
  useEffect(() => {
    if (!authToken) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(`${process.env.REACT_APP_API_URL || ''}/my-documents`, {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (!resp.ok || cancelled) return;
        const data = await resp.json();
        if (!cancelled) setUploadedDocs(Array.isArray(data.documents) ? data.documents : []);
      } catch { /* non-fatal — panel just stays hidden */ }
    })();
    return () => { cancelled = true; };
  }, [authToken]);

  useEffect(() => {
    if (!serverHydrated || !authToken || !hydratedRef.current) return undefined;
    const persist = debounce(async () => {
      const ok = await saveDeliverables(authToken, store);
      if (!ok) {
        fireToast('Documents saved locally (server sync failed)', 'danger');
      }
    }, 900);
    persist();
    return () => persist.cancel();
  }, [store, authToken, serverHydrated]);

  // Refresh when CanvasPage seeds localStorage from server before this mounts
  useEffect(() => {
    const onStorage = () => {
      try {
        const next = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
        if (next?.projects) setStore(next);
      } catch { /* ignore */ }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const project = store.projects[store.activeProjectId] || null;
  const template = project ? TEMPLATES.find(t => t.id === project.templateId) : null;
  const sections = project?.sections || {};
  const [activeSectionId, setActiveSectionId] = useState(template?.sections[0]?.id);
  const [generatingAi, setGeneratingAi] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  // Normalize active section when project/template changes
  useEffect(() => {
    if (!template) return;
    const valid = template.sections.some(s => s.id === activeSectionId);
    if (!valid) setActiveSectionId(template.sections[0].id);
  }, [project?.id, template, activeSectionId]);

  // ---------- Project ops ----------
  const createProject = (templateId, name) => {
    const id = newId('p-');
    const t = TEMPLATES.find(x => x.id === templateId);
    setStore(s => ({
      activeProjectId: id,
      projects: {
        ...s.projects,
        [id]: { id, name: name || `${t.name} draft`, templateId, sections: {}, versions: [], aiNotes: null, createdAt: Date.now() },
      },
    }));
    fireToast(`New ${t.name} draft created`);
  };
  const switchProject = (id) => setStore(s => ({ ...s, activeProjectId: id }));
  const renameProject = (name) => {
    if (!project) return;
    setStore(s => ({ ...s, projects: { ...s.projects, [project.id]: { ...s.projects[project.id], name } } }));
  };
  const deleteProject = () => {
    if (!project) return;
    if (!window.confirm(`Delete "${project.name}"? This can't be undone.`)) return;
    setStore(s => {
      const { [project.id]: _, ...rest } = s.projects;
      const nextActive = Object.keys(rest)[0] || null;
      return { activeProjectId: nextActive, projects: rest };
    });
  };
  const closeProject = () => setStore(s => ({ ...s, activeProjectId: null }));

  // ---------- Section ops + auto-versioning ----------
  const updateSection = (id, value) => {
    setStore(s => {
      const proj = s.projects[project.id];
      const oldText = proj.sections[id] || '';
      // Snapshot a version every time a section gains/loses ≥80 chars (rough save cadence)
      const shouldSnap = Math.abs(value.length - oldText.length) >= 80;
      const newVersions = shouldSnap
        ? [{ at: Date.now(), sectionId: id, snapshot: { ...proj.sections } }, ...proj.versions].slice(0, MAX_VERSIONS)
        : proj.versions;
      return {
        ...s,
        projects: {
          ...s.projects,
          [project.id]: { ...proj, sections: { ...proj.sections, [id]: value }, versions: newVersions },
        },
      };
    });
  };

  const restoreVersion = (v) => {
    if (!window.confirm('Restore this version? Current text will be replaced.')) return;
    setStore(s => ({
      ...s,
      projects: { ...s.projects, [project.id]: { ...s.projects[project.id], sections: v.snapshot } },
    }));
    fireToast('Restored');
  };

  // ---------- AI pass (stub) ----------
  // TODO(LLM): POST {project, sections, canvas} → {notes:[{sectionId,msg}]}
  const runAiPass = () => {
    setGeneratingAi(true);
    setTimeout(() => {
      const notes = template.sections.map(s => {
        const text = sections[s.id] || '';
        const wc = wordCount(text);
        if (wc === 0) return { sectionId: s.id, msg: `Empty — start with: "${s.hint}"` };
        if (wc < s.target * 0.3) return { sectionId: s.id, msg: `Thin (${wc} words). Target ${s.target}.` };
        return { sectionId: s.id, msg: `Looks reasonable for length (${wc} words). LLM-pass would suggest specifics here.` };
      });
      setStore(s => ({ ...s, projects: { ...s.projects, [project.id]: { ...s.projects[project.id], aiNotes: notes } } }));
      setGeneratingAi(false);
      fireToast('AI pass complete (stub)');
    }, 700);
  };

  // ---------- Insertables: Bibliography + Highlights + Outline + Drafts + arXiv search ----------
  const localInsertables = useMemo(() => {
    const items = [];
    (allStates?.bibliography?.entries || []).forEach(e =>
      items.push({ kind: 'cite', label: e.title, snippet: ` (${e.authors}, ${e.year}; @${e.key})` }));
    (allStates?.highlights?.items || []).forEach(h =>
      items.push({ kind: 'quote', label: h.text.slice(0, 60), snippet: `"${h.text}"${h.citeKey ? ` (@${h.citeKey})` : ''}` }));
    (allStates?.outline?.items || []).forEach(o =>
      items.push({ kind: 'outline', label: o.text || '(empty)', snippet: '\n' + '  '.repeat(o.depth) + '- ' + (o.text || '') }));
    (allStates?.writing?.chapters || []).forEach(c =>
      items.push({ kind: 'draft', label: c.name, snippet: c.draft || '' }));
    return items;
  }, [allStates]);

  const insertIntoActive = (snippet) => {
    if (!activeSectionId) return;
    const cur = sections[activeSectionId] || '';
    updateSection(activeSectionId, cur + (cur && !cur.endsWith('\n') ? ' ' : '') + snippet);
    fireToast('Inserted into ' + template.sections.find(s => s.id === activeSectionId)?.name);
  };

  // ---------- Export ----------
  const exportAs = (format) => {
    const filename = `${project.name.replace(/\s+/g, '_')}.${format === 'latex' ? 'tex' : format === 'markdown' ? 'md' : 'html'}`;
    const mime = format === 'html' ? 'text/html' : 'text/plain';
    const contents = format === 'markdown' ? exportMarkdown(template, sections)
      : format === 'latex' ? exportLatex(template, sections)
      : exportHtml(template, sections);
    downloadFile(filename, mime, contents);
    fireToast(`Exported ${filename}`);
  };

  // ---------- Aggregates ----------
  const totalWords = template ? template.sections.reduce((sum, s) => sum + wordCount(sections[s.id]), 0) : 0;
  const totalTarget = template ? template.sections.reduce((sum, s) => sum + s.target, 0) : 0;
  const projectList = Object.values(store.projects).sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));

  // ---------- Empty state: project picker / template picker ----------
  if (!project) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1 className="page-title">Documents</h1>
            <div className="page-sub">
              Security deliverables hub — policies, IR reports, audit evidence, and architecture briefs. Drafts auto-save. Versions kept for rollback.
              {projectList.length > 0 && ` · ${projectList.length} draft${projectList.length === 1 ? '' : 's'} in flight.`}
            </div>
          </div>
        </div>

        {/* Existing projects, if any */}
        {projectList.length > 0 && (
          <div className="canvas-presets" style={{ marginBottom: 24 }}>
            <div className="canvas-presets-head">
              <div className="canvas-presets-title">Continue working</div>
              <div className="canvas-presets-sub">Drafts you've started.</div>
            </div>
            <div className="canvas-presets-grid">
              {projectList.map(p => {
                const t = TEMPLATES.find(t => t.id === p.templateId);
                if (!t) return null;
                const wc = t.sections.reduce((sum, s) => sum + wordCount(p.sections[s.id]), 0);
                const target = t.sections.reduce((sum, s) => sum + s.target, 0);
                return (
                  <button key={p.id} className="canvas-preset-card" onClick={() => switchProject(p.id)}>
                    <div className="canvas-preset-icon"><Icon name={t.icon} size={18}/></div>
                    <div className="canvas-preset-content">
                      <div className="canvas-preset-name">{p.name}</div>
                      <div className="canvas-preset-desc">{t.name} · {wc}/{target} words</div>
                      <div className="canvas-preset-meta">opened {new Date(p.createdAt).toLocaleDateString()}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Templates */}
        <div className="canvas-presets">
          <div className="canvas-presets-head">
            <div className="canvas-presets-title">{projectList.length > 0 ? 'Or start a new draft' : 'Pick a template'}</div>
            <div className="canvas-presets-sub">{TEMPLATES.length} templates · assessment report, IR plan, policy, briefing slides, and more.</div>
          </div>
          <div className="canvas-presets-grid">
            {TEMPLATES.map(t => (
              <button key={t.id} className="canvas-preset-card" onClick={() => createProject(t.id)}>
                <div className="canvas-preset-icon"><Icon name={t.icon} size={18}/></div>
                <div className="canvas-preset-content">
                  <div className="canvas-preset-name">{t.name}</div>
                  <div className="canvas-preset-desc">{t.desc}</div>
                  <div className="canvas-preset-meta">{t.sections.length} sections · {t.mode}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Uploaded RAG documents from chat sessions */}
        {uploadedDocs.length > 0 && (
          <div className="canvas-presets" style={{ marginTop: 18 }}>
            <div className="canvas-presets-head">
              <div className="canvas-presets-title">Uploaded documents</div>
              <div className="canvas-presets-sub">
                Files you uploaded in chat — the advisors can reference these by name.
              </div>
            </div>
            <div className="canvas-presets-grid">
              {uploadedDocs.map((d, i) => (
                <div key={`${d.chat_session_id}-${d.filename}-${i}`} className="canvas-preset-card" style={{ cursor: 'default' }}>
                  <div className="canvas-preset-icon"><Icon name="book" size={18}/></div>
                  <div className="canvas-preset-content">
                    <div className="canvas-preset-name">{d.title || d.filename}</div>
                    <div className="canvas-preset-desc">{d.file_type?.toUpperCase()} · {d.chunks} section{d.chunks === 1 ? '' : 's'} indexed</div>
                    <div className="canvas-preset-meta">from chat: {d.chat_title}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </>
    );
  }

  // ============================================================================
  // Editor: project tabs + header + per-mode editor
  // ============================================================================
  const aiNotes = project.aiNotes;

  const ProjectTabs = (
    <div className="deliverable-projects">
      {projectList.map(p => {
        const t = TEMPLATES.find(x => x.id === p.templateId);
        return (
          <button
            key={p.id}
            className={`deliverable-project-tab ${p.id === project.id ? 'active' : ''}`}
            onClick={() => switchProject(p.id)}
            title={`${t?.name || ''} · ${wordCount(Object.values(p.sections || {}).join(' '))} words`}
          >
            <Icon name={t?.icon || 'book'} size={12}/>
            <span>{p.name}</span>
          </button>
        );
      })}
      <details className="canvas-export-menu deliverable-new-project">
        <summary className="deliverable-project-tab"><Icon name="plus" size={12}/>New</summary>
        <div className="canvas-export-menu-list">
          {TEMPLATES.map(t => (
            <button key={t.id} onClick={() => createProject(t.id)}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Icon name={t.icon} size={12}/>{t.name}
              </span>
            </button>
          ))}
        </div>
      </details>
    </div>
  );

  const Header = (
    <div className="page-header">
      <div>
        <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 12, marginBottom: 4, color: 'var(--canvas-text-3)' }} onClick={closeProject}>
          <Icon name="back" size={12}/>All drafts
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            className="page-title page-title-editable"
            value={project.name}
            onChange={(e) => renameProject(e.target.value)}
          />
          <SaveIndicator project={project}/>
        </div>
        <div className="page-sub">
          {template.name} · {totalWords} / {totalTarget} words · ~{readingMinutes(totalWords)} min read · {template.sections.length} {template.mode === 'slides' ? 'slides' : 'sections'}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <button className="btn btn-ghost" onClick={() => setHistoryOpen(o => !o)} title="Version history">
          <Icon name="reset" size={13}/>History · {project.versions.length}
        </button>
        <button className="btn btn-ghost" onClick={runAiPass} disabled={generatingAi} title="AI check (stub)">
          {generatingAi ? <><div className="spinner"/></> : <Icon name="sparkles" size={13}/>}
          AI check
        </button>
        <details className="canvas-export-menu">
          <summary className="btn btn-primary"><Icon name="download" size={13}/>Export</summary>
          <div className="canvas-export-menu-list">
            <button onClick={() => exportAs('markdown')}>Markdown (.md)</button>
            <button onClick={() => exportAs('latex')}>LaTeX (.tex)</button>
            <button onClick={() => exportAs('html')}>HTML (.html)</button>
            <button onClick={() => window.print()}>Print / Save as PDF</button>
          </div>
        </details>
        <button className="btn btn-ghost" onClick={deleteProject} title="Delete this draft" style={{ color: 'var(--canvas-danger)' }}>
          <Icon name="trash" size={13}/>
        </button>
      </div>
    </div>
  );

  const HistoryPanel = historyOpen && (
    <div className="deliverable-history">
      <div className="deliverable-history-head">
        <span>Version history · {project.versions.length}</span>
        <button className="icon-btn" onClick={() => setHistoryOpen(false)}><Icon name="x" size={13}/></button>
      </div>
      {project.versions.length === 0 ? (
        <div style={{ padding: 14, color: 'var(--canvas-text-3)', fontSize: 12 }}>
          Snapshots auto-save every ~80 characters of edits.
        </div>
      ) : (
        project.versions.map((v, i) => {
          const sec = template.sections.find(s => s.id === v.sectionId);
          return (
            <button key={i} className="deliverable-history-row" onClick={() => restoreVersion(v)}>
              <span className="tag-pill">{sec?.name || v.sectionId}</span>
              <span style={{ flex: 1 }}>{new Date(v.at).toLocaleString()}</span>
              <Icon name="reset" size={11} style={{ color: 'var(--canvas-text-3)' }}/>
            </button>
          );
        })
      )}
    </div>
  );

  const InsertPanel = (
    <div className="deliverable-insertables">
      <ArxivSearch onPick={insertIntoActive}/>
      <div style={{ fontSize: 11, color: 'var(--canvas-text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginTop: 14, marginBottom: 6 }}>
        From canvas · {localInsertables.length}
      </div>
      {localInsertables.length === 0 && (
        <div style={{ padding: 12, fontSize: 11.5, color: 'var(--canvas-text-3)', background: 'var(--canvas-surface)', border: '1px dashed var(--canvas-border-2)', borderRadius: 7 }}>
          Add a Bibliography, Highlights, Outline, or Writing widget to your canvas to surface its content here.
        </div>
      )}
      {localInsertables.map((it, i) => (
        <button key={i} onClick={() => insertIntoActive(it.snippet)} className="canvas-insert-row">
          <span className="tag-pill">{it.kind}</span>
          <span style={{ flex: 1, fontSize: 11.5, color: 'var(--canvas-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.label}</span>
          <Icon name="plus" size={12} style={{ color: 'var(--canvas-text-3)' }}/>
        </button>
      ))}
    </div>
  );

  // ---------- POSTER MODE — 4-quadrant + 2 banner sections ----------
  if (template.mode === 'poster') {
    const layout = template.sections;
    return (
      <>
        {ProjectTabs}
        {Header}
        {HistoryPanel}
        <div className="poster-grid">
          <div className="poster-banner">
            <PosterPanel section={layout[0]} sections={sections} updateSection={updateSection}/>
          </div>
          <PosterPanel section={layout[1]} sections={sections} updateSection={updateSection}/>
          <PosterPanel section={layout[2]} sections={sections} updateSection={updateSection}/>
          <PosterPanel section={layout[3]} sections={sections} updateSection={updateSection}/>
          <PosterPanel section={layout[4]} sections={sections} updateSection={updateSection}/>
          <div className="poster-banner">
            <PosterPanel section={layout[5]} sections={sections} updateSection={updateSection}/>
          </div>
        </div>
        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
          {InsertPanel}
        </div>
      </>
    );
  }

  // ---------- SLIDES MODE — Google Slides feel ----------
  if (template.mode === 'slides') {
    const activeIdx = template.sections.findIndex(s => s.id === activeSectionId);
    const active = template.sections[activeIdx] || template.sections[0];
    const text = sections[active.id] || '';
    const aiForSlide = aiNotes && aiNotes.find(n => n.sectionId === active.id);
    const lines = text.split(/\n+/).map(l => l.trim()).filter(Boolean);

    return (
      <>
        {ProjectTabs}
        {Header}
        {HistoryPanel}
        <div className="deliverable-slides-grid">
          <div className="slide-thumbs">
            <div style={{ fontSize: 10, color: 'var(--canvas-text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, padding: '0 4px 6px' }}>
              {template.sections.length} slides
            </div>
            {template.sections.map((s, i) => {
              const t = sections[s.id] || '';
              const tLines = t.split(/\n+/).map(l => l.trim()).filter(Boolean);
              return (
                <button key={s.id}
                  className={`slide-thumb ${s.id === active.id ? 'active' : ''}`}
                  onClick={() => setActiveSectionId(s.id)}
                  title={s.name}>
                  <div className="slide-thumb-num">{i + 1}</div>
                  <div className="slide-thumb-canvas">
                    <div className="slide-thumb-title">{s.name}</div>
                    <div className="slide-thumb-body">
                      {tLines.slice(0, 3).map((l, j) => <div key={j}>• {l.slice(0, 30)}</div>)}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <div>
            <div className="slide-canvas-wrap">
              <div className="slide-canvas">
                <div className="slide-canvas-title">{active.name}</div>
                <div className="slide-canvas-body">
                  {lines.length === 0 ? (
                    <div className="slide-placeholder">{active.hint}</div>
                  ) : lines.length === 1 ? (
                    <div className="slide-paragraph">{lines[0]}</div>
                  ) : (
                    <ul>{lines.map((l, j) => <li key={j}>{l}</li>)}</ul>
                  )}
                </div>
                <div className="slide-canvas-footer">{activeIdx + 1} / {template.sections.length}</div>
              </div>
            </div>
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--canvas-text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
                  Slide content
                </span>
                <span style={{ fontSize: 11, color: 'var(--canvas-text-3)' }}>· One bullet per line</span>
                <span style={{ flex: 1 }}/>
                <span style={{ fontFamily: 'var(--canvas-mono)', fontSize: 10, color: 'var(--canvas-text-3)' }}>
                  {wordCount(text)}{active.target ? `/${active.target}` : ''} words
                </span>
              </div>
              <SlashTextarea
                value={text}
                onChange={(v) => updateSection(active.id, v)}
                placeholder={active.hint}
                rows={6}
              />
              {(active.checks || []).length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {active.checks.map(c => {
                    const check = CHECKS[c];
                    if (!check) return null;
                    const passed = check.test(text);
                    return (
                      <span key={c} className="check-pill" data-passed={passed}>
                        {passed ? <Icon name="check" size={10}/> : <span style={{ width: 10, height: 10, borderRadius: 2, border: '1px solid currentColor' }}/>}
                        {check.label}
                      </span>
                    );
                  })}
                </div>
              )}
              {aiForSlide && (
                <div className="notion-callout">
                  <Icon name="sparkles" size={14}/>
                  <div>
                    <div className="notion-callout-label">AI suggestion · stub</div>
                    <div>{aiForSlide.msg}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
          {InsertPanel}
        </div>
      </>
    );
  }

  // ---------- PAPER / DOCUMENT MODE — Notion single-surface page ----------
  const paperLike = template.mode === 'paper';

  // For paper-mode projects: optional LaTeX editor (CodeMirror + LaTeX.js preview).
  // Source stored as a single string at project.latexSource.
  const editorMode = (paperLike && project.editorMode) || 'rich';
  const setEditorMode = (next) => {
    setStore(s => {
      const proj = s.projects[project.id];
      // First time switching to LaTeX, seed the source from current sections.
      let nextLatex = proj.latexSource;
      if (next === 'latex' && (!nextLatex || nextLatex.trim() === '')) {
        nextLatex = template.sections.map(sec =>
          `\\section{${sec.name}}\n${proj.sections[sec.id] || ''}\n`
        ).join('\n');
      }
      return {
        ...s,
        projects: {
          ...s.projects,
          [project.id]: { ...proj, editorMode: next, latexSource: nextLatex },
        },
      };
    });
  };
  const updateLatexSource = (src) => {
    setStore(s => ({
      ...s,
      projects: { ...s.projects, [project.id]: { ...s.projects[project.id], latexSource: src } },
    }));
  };

  if (paperLike && editorMode === 'latex') {
    return (
      <>
        {ProjectTabs}
        {Header}
        {HistoryPanel}
        <div className="paper-editor-toggle">
          <span className="paper-editor-toggle-label">Editor</span>
          <button className="active" onClick={() => setEditorMode('rich')} title="Switch to Notion-style rich editor">
            LaTeX
          </button>
          <button onClick={() => setEditorMode('rich')}>Rich</button>
        </div>
        <LatexEditor
          value={project.latexSource || ''}
          onChange={updateLatexSource}
          title={project.name}
        />
      </>
    );
  }

  return (
    <>
      {ProjectTabs}
      {Header}
      {HistoryPanel}
      {paperLike && (
        <div className="paper-editor-toggle">
          <span className="paper-editor-toggle-label">Editor</span>
          <button onClick={() => setEditorMode('latex')}>LaTeX</button>
          <button className="active" onClick={() => setEditorMode('rich')}>Rich</button>
        </div>
      )}
      <div className="notion-deliverable-grid">
        <div className="notion-toc">
          <div className="notion-toc-label">On this page</div>
          {template.sections.map(s => {
            const wc = wordCount(sections[s.id]);
            return (
              <button key={s.id}
                className={`notion-toc-link ${activeSectionId === s.id ? 'active' : ''}`}
                onClick={() => {
                  setActiveSectionId(s.id);
                  const el = document.getElementById(`notion-section-${s.id}`);
                  if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' });
                }}>
                <span className="notion-toc-link-text">{s.name}</span>
                {wc > 0 && <span className="notion-toc-link-count">{wc}</span>}
              </button>
            );
          })}
        </div>

        <div className={`notion-page-wrap ${paperLike ? 'paper' : ''}`}>
          <div className={`notion-page ${paperLike ? 'serif' : ''}`}>
            <h1 className="notion-page-title">{project.name}</h1>
            <div className="notion-page-meta">
              {totalWords} words · ~{readingMinutes(totalWords)} min read · {template.sections.length} sections{paperLike ? ' · formal report' : ''}
            </div>
            {template.sections.map(s => {
              const text = sections[s.id] || '';
              const aiForSection = aiNotes ? aiNotes.find(n => n.sectionId === s.id) : null;
              return (
                <div key={s.id} id={`notion-section-${s.id}`} className="notion-block">
                  <h2 className={`notion-h2 ${paperLike ? 'serif' : ''}`}>{s.name}</h2>
                  <RichBlock
                    value={text}
                    onChange={(v) => updateSection(s.id, v)}
                    placeholder={`Start writing ${s.name.toLowerCase()}…`}
                    hint={s.hint}
                    serif={paperLike}
                  />
                  {(s.checks || []).length > 0 && (
                    <div className="notion-block-meta">
                      {s.checks.map(c => {
                        const check = CHECKS[c];
                        if (!check) return null;
                        const passed = check.test(text);
                        return (
                          <span key={c} className="check-pill" data-passed={passed}>
                            {passed ? <Icon name="check" size={10}/> : <span style={{ width: 10, height: 10, borderRadius: 2, border: '1px solid currentColor' }}/>}
                            {check.label}
                          </span>
                        );
                      })}
                      {s.target > 0 && (
                        <span className="check-pill" data-passed={wordCount(text) >= s.target * 0.7}>
                          {wordCount(text)} / {s.target} words
                        </span>
                      )}
                    </div>
                  )}
                  {aiForSection && (
                    <div className="notion-callout">
                      <Icon name="sparkles" size={14}/>
                      <div>
                        <div className="notion-callout-label">AI suggestion · stub</div>
                        <div>{aiForSection.msg}</div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {InsertPanel}
      </div>
    </>
  );
};

// ============================================================================
// Auto-save indicator. Drafts persist to localStorage on every keystroke,
// so we show a transient "Saving…" pill when the project changes, settling
// to "Saved · Xs ago" while idle.
// ============================================================================
function SaveIndicator({ project }) {
  const [savedAt, setSavedAt] = useState(Date.now());
  const [pulse, setPulse] = useState(false);
  const sectionsKey = JSON.stringify(project?.sections || {});
  useEffect(() => {
    setPulse(true);
    const t1 = setTimeout(() => setPulse(false), 300);
    const t2 = setTimeout(() => setSavedAt(Date.now()), 350);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [sectionsKey]);

  // Tick the relative-time string
  const [, force] = useState(0);
  useEffect(() => {
    const i = setInterval(() => force(n => n + 1), 5000);
    return () => clearInterval(i);
  }, []);

  const ago = (() => {
    const d = Math.floor((Date.now() - savedAt) / 1000);
    if (d < 5) return 'just now';
    if (d < 60) return `${d}s ago`;
    if (d < 3600) return `${Math.floor(d / 60)}m ago`;
    return `${Math.floor(d / 3600)}h ago`;
  })();

  return (
    <span className={`save-indicator ${pulse ? 'saving' : ''}`}>
      <span className="save-indicator-dot"/>
      {pulse ? 'Saving…' : `Saved · ${ago}`}
    </span>
  );
}

// ============================================================================
// RichBlock — Notion-style click-to-edit + Docs-style floating toolbar.
//   • Idle: shows rendered markdown (with KaTeX math) — looks like a real doc
//   • Click: switches to a textarea source view
//   • While editing: floating toolbar above with Bold / Italic / H2 / list / link / cite / math
//   • Slash commands still work via the underlying textarea
// ============================================================================
const wrap = (text, l, r = l) => `${l}${text || 'text'}${r}`;
const lineWrap = (text, prefix) =>
  (text ? text.split('\n').map(line => line ? `${prefix}${line}` : line).join('\n') : `${prefix}`);

const TOOLBAR = [
  { id: 'bold',     icon: 'pencil', label: `Bold (${MOD}+B)`,   run: (sel) => wrap(sel, '**') },
  { id: 'italic',   icon: 'pencil', label: `Italic (${MOD}+I)`, run: (sel) => wrap(sel, '*') },
  { id: 'code',     icon: 'flask',  label: 'Inline code',      run: (sel) => wrap(sel, '`') },
  { id: 'h2',       icon: 'list',   label: 'Heading',          run: (sel) => `## ${sel || 'Heading'}` },
  { id: 'h3',       icon: 'list',   label: 'Subheading',       run: (sel) => `### ${sel || 'Subheading'}` },
  { id: 'list',     icon: 'list',   label: 'Bullet list',      run: (sel) => lineWrap(sel, '- ') },
  { id: 'numbered', icon: 'list',   label: 'Numbered list',    run: (sel) => lineWrap(sel, '1. ') },
  { id: 'quote',    icon: 'cite',   label: 'Block quote',      run: (sel) => lineWrap(sel, '> ') },
  { id: 'link',     icon: 'link',   label: 'Link',             run: (sel) => `[${sel || 'link text'}](https://)` },
  { id: 'cite',     icon: 'book',   label: 'Citation @key',    run: (sel) => `(@${sel || 'key'})` },
  { id: 'math',     icon: 'flask',  label: 'Inline math (LaTeX)', run: (sel) => `$${sel || 'x^2'}$` },
  { id: 'math-block', icon: 'flask', label: 'Math block',       run: (sel) => `\n$$\n${sel || 'E = mc^2'}\n$$\n` },
];

function RichBlock({ value, onChange, placeholder, serif, hint }) {
  const [editing, setEditing] = useState(false);
  const [slash, setSlash] = useState(null);
  const taRef = useRef(null);
  const containerRef = useRef(null);

  // Auto-grow when editing
  useEffect(() => {
    if (!editing || !taRef.current) return;
    taRef.current.style.height = 'auto';
    taRef.current.style.height = taRef.current.scrollHeight + 'px';
  }, [value, editing]);

  // Click outside to leave edit mode
  useEffect(() => {
    if (!editing) return;
    const onDocClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setEditing(false);
        setSlash(null);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [editing]);

  const applyToolbar = (cmd) => {
    const ta = taRef.current;
    if (!ta) return;
    const { selectionStart: s, selectionEnd: e } = ta;
    const before = value.slice(0, s);
    const sel = value.slice(s, e);
    const after = value.slice(e);
    const replacement = cmd.run(sel);
    const next = before + replacement + after;
    onChange(next);
    // Reposition cursor at end of inserted text
    setTimeout(() => {
      if (taRef.current) {
        const pos = before.length + replacement.length;
        taRef.current.setSelectionRange(pos, pos);
        taRef.current.focus();
      }
    }, 0);
  };

  const onTextChange = (e) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart;
    onChange(val);
    const before = val.slice(0, cursor);
    const m = before.match(/(?:^|\n)(\/[\w-]*)$/);
    if (m) {
      const q = m[1].slice(1).toLowerCase();
      const choices = SLASH_COMMANDS.filter(c => c.label.toLowerCase().includes(q) || c.id.includes(q)).slice(0, 8);
      setSlash({ start: cursor - m[1].length, query: q, choices, idx: 0 });
    } else {
      setSlash(null);
    }
  };

  const insertSlash = (cmd) => {
    if (!slash) return;
    const before = value.slice(0, slash.start);
    const after = value.slice(slash.start + 1 + slash.query.length);
    const inserted = cmd.insert();
    onChange(before + inserted + after);
    setSlash(null);
    setTimeout(() => {
      if (taRef.current) {
        const pos = before.length + inserted.length;
        taRef.current.setSelectionRange(pos, pos);
        taRef.current.focus();
      }
    }, 0);
  };

  const onKeyDown = (e) => {
    // ⌘B / ⌘I keyboard shortcuts (Word/Docs convention)
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey) {
      if (e.key.toLowerCase() === 'b') { e.preventDefault(); applyToolbar(TOOLBAR.find(t => t.id === 'bold')); return; }
      if (e.key.toLowerCase() === 'i') { e.preventDefault(); applyToolbar(TOOLBAR.find(t => t.id === 'italic')); return; }
    }
    if (slash && slash.choices.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSlash(s => ({ ...s, idx: Math.min(s.choices.length - 1, s.idx + 1) })); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setSlash(s => ({ ...s, idx: Math.max(0, s.idx - 1) })); }
      else if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); insertSlash(slash.choices[slash.idx]); }
      else if (e.key === 'Escape') setSlash(null);
    }
  };

  return (
    <div ref={containerRef} className="rich-block">
      {/* Floating toolbar — only when actively editing */}
      {editing && (
        <div className="rich-toolbar" onMouseDown={(e) => e.preventDefault() /* keep textarea focused */}>
          {TOOLBAR.map(t => (
            <button key={t.id} title={t.label} onClick={() => applyToolbar(t)}>
              {t.id === 'bold' && <strong>B</strong>}
              {t.id === 'italic' && <em>I</em>}
              {t.id === 'code' && <span style={{ fontFamily: 'var(--canvas-mono)', fontSize: 11 }}>{'<>'}</span>}
              {t.id === 'h2' && <span style={{ fontWeight: 700 }}>H2</span>}
              {t.id === 'h3' && <span style={{ fontWeight: 700, fontSize: 11 }}>H3</span>}
              {t.id === 'list' && '•'}
              {t.id === 'numbered' && <span style={{ fontFamily: 'var(--canvas-mono)', fontSize: 11 }}>1.</span>}
              {t.id === 'quote' && '"'}
              {t.id === 'link' && <Icon name="link" size={12}/>}
              {t.id === 'cite' && '@'}
              {t.id === 'math' && <span style={{ fontFamily: 'serif', fontStyle: 'italic' }}>x</span>}
              {t.id === 'math-block' && <span style={{ fontFamily: 'serif' }}>∑</span>}
            </button>
          ))}
        </div>
      )}

      {editing ? (
        <div style={{ position: 'relative' }}>
          <textarea
            ref={taRef}
            className={`notion-text ${serif ? 'serif' : ''}`}
            value={value}
            onChange={onTextChange}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            autoFocus
            rows={1}
          />
          {slash && slash.choices.length > 0 && (
            <div className="slash-menu">
              <div className="slash-menu-head">Insert block</div>
              {slash.choices.map((c, i) => (
                <button key={c.id}
                  onMouseEnter={() => setSlash(s => ({ ...s, idx: i }))}
                  onClick={() => insertSlash(c)}
                  className={i === slash.idx ? 'active' : ''}>
                  <Icon name={c.icon} size={13}/>
                  <span style={{ flex: 1 }}>{c.label}</span>
                  <span className="slash-menu-kind">{c.kind}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div
          className={`rich-rendered ${serif ? 'serif' : ''}`}
          onClick={() => setEditing(true)}
          onFocus={() => setEditing(true)}
          tabIndex={0}
        >
          {value ? (
            <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS}>{value}</ReactMarkdown>
          ) : (
            <span className="rich-placeholder">{hint || placeholder || 'Click to edit'}</span>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// SlashTextarea — auto-grows; `/` opens a block-insert popover.
// ============================================================================
function SlashTextarea({ value, onChange, placeholder, serif, notion, rows = 1 }) {
  const ref = useRef(null);
  const [slash, setSlash] = useState(null); // { start, query, choices, idx }

  useEffect(() => {
    if (!ref.current || !notion) return;
    ref.current.style.height = 'auto';
    ref.current.style.height = ref.current.scrollHeight + 'px';
  }, [value, notion]);

  const onTextChange = (e) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart;
    onChange(val);
    const before = val.slice(0, cursor);
    const m = before.match(/(?:^|\n)(\/[\w-]*)$/);
    if (m) {
      const q = m[1].slice(1).toLowerCase();
      const choices = SLASH_COMMANDS.filter(c => c.label.toLowerCase().includes(q) || c.id.includes(q)).slice(0, 8);
      setSlash({ start: cursor - m[1].length, query: q, choices, idx: 0 });
    } else {
      setSlash(null);
    }
  };

  const insertCmd = (cmd) => {
    if (!slash) return;
    const before = value.slice(0, slash.start);
    const after = value.slice(slash.start + 1 + slash.query.length);
    const inserted = cmd.insert();
    onChange(before + inserted + after);
    setSlash(null);
    setTimeout(() => {
      if (ref.current) {
        const pos = before.length + inserted.length;
        ref.current.setSelectionRange(pos, pos);
        ref.current.focus();
      }
    }, 0);
  };

  const onKeyDown = (e) => {
    if (!slash || slash.choices.length === 0) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setSlash(s => ({ ...s, idx: Math.min(s.choices.length - 1, s.idx + 1) })); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSlash(s => ({ ...s, idx: Math.max(0, s.idx - 1) })); }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); insertCmd(slash.choices[slash.idx]); }
    if (e.key === 'Escape') setSlash(null);
  };

  return (
    <div style={{ position: 'relative' }}>
      <textarea
        ref={ref}
        className={notion ? `notion-text ${serif ? 'serif' : ''}` : 'textarea'}
        value={value}
        onChange={onTextChange}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        rows={rows}
        style={notion ? undefined : { minHeight: 110, fontFamily: 'var(--canvas-sans)', fontSize: 13, lineHeight: 1.6 }}
      />
      {slash && slash.choices.length > 0 && (
        <div className="slash-menu">
          <div className="slash-menu-head">Insert block</div>
          {slash.choices.map((c, i) => (
            <button key={c.id}
              onMouseEnter={() => setSlash(s => ({ ...s, idx: i }))}
              onClick={() => insertCmd(c)}
              className={i === slash.idx ? 'active' : ''}>
              <Icon name={c.icon} size={13}/>
              <span style={{ flex: 1 }}>{c.label}</span>
              <span className="slash-menu-kind">{c.kind}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Poster panel — single-section block in the poster layout
// ============================================================================
function PosterPanel({ section, sections, updateSection }) {
  if (!section) return null;
  const text = sections[section.id] || '';
  return (
    <div className="poster-panel">
      <div className="poster-panel-head">{section.name}</div>
      <RichBlock
        value={text}
        onChange={(v) => updateSection(section.id, v)}
        placeholder={section.hint}
        hint={section.hint}
      />
    </div>
  );
}

// ============================================================================
// arXiv search — public ATOM API, CORS-enabled.
// ============================================================================
function ArxivSearch({ onPick }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState([]);

  const search = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try {
      const url = `https://export.arxiv.org/api/query?search_query=all:${encodeURIComponent(q)}&max_results=5`;
      const res = await fetch(url);
      const xml = await res.text();
      const doc = new DOMParser().parseFromString(xml, 'text/xml');
      const entries = Array.from(doc.getElementsByTagName('entry')).map(e => {
        const id = e.getElementsByTagName('id')[0]?.textContent?.split('/').pop() || '';
        const title = e.getElementsByTagName('title')[0]?.textContent?.trim() || '';
        const authors = Array.from(e.getElementsByTagName('author')).map(a => a.getElementsByTagName('name')[0]?.textContent?.trim()).filter(Boolean);
        const year = (e.getElementsByTagName('published')[0]?.textContent || '').slice(0, 4);
        return { id, title, authors, year };
      });
      setResults(entries);
    } catch (e) {
      fireToast('arXiv search failed', 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--canvas-text-4)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 6 }}>
        Search arXiv
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        <input className="input" placeholder="Predictive coding…" value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') search(); }}
          style={{ fontSize: 12, padding: '5px 8px' }}/>
        <button className="icon-btn" onClick={search} disabled={!q.trim() || busy} title="Search arXiv">
          {busy ? <div className="spinner"/> : <Icon name="search" size={13}/>}
        </button>
      </div>
      {results.length > 0 && (
        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {results.map(r => {
            const a = r.authors[0] ? r.authors[0].split(' ').pop() : 'Unknown';
            const snippet = ` (${a}, ${r.year}; arXiv:${r.id})`;
            return (
              <button key={r.id} className="canvas-insert-row" onClick={() => onPick(snippet)}>
                <span className="tag-pill">arXiv</span>
                <span style={{ flex: 1, fontSize: 11.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.title}>{r.title}</span>
                <Icon name="plus" size={12} style={{ color: 'var(--canvas-text-3)' }}/>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default DeliverablesView;
