// Demo data for a security program lead preparing for a SOC 2 audit.

export const DEMO_PROJECT = {
  title: "Zero Trust Rollout — Production SaaS",
  meta: "Security Engineer · Q2 audit prep",
};

export const INSIGHTS = [
  {
    id: 'i-progress',
    title: 'Program progress',
    icon: 'graph',
    category: 'progress',
    confidence: 82,
    summary: 'Zero Trust Phase 2 is 78% complete. MFA enforced for workforce; service accounts and legacy VPN exceptions remain the main gaps before audit sampling.',
    bullets: [
      'Identity: <strong>MFA 94%</strong> workforce · service accounts in remediation',
      'Network: micro-segmentation pilot on <strong>3 app tiers</strong>',
      '<strong>Risk:</strong> 12 VPN exceptions still lack compensating controls',
    ],
    pinned: true,
    sources: 18,
    updatedMinutesAgo: 5,
    quotes: [
      '"MFA rollout blocked on two legacy HR integrations." — IAM workstream notes',
      '"Auditors will sample VPN exception register first." — GRC advisor chat',
    ],
  },
  {
    id: 'i-method',
    title: 'Controls posture',
    icon: 'flask',
    category: 'theory',
    confidence: 71,
    summary: 'SOC 2 CC6/CC7 mappings are drafted. Detection use cases cover ransomware and cred theft; log retention and IR tabletop evidence are still thin.',
    bullets: [
      'Mapped: <strong>CC6.1–CC6.7</strong> access controls with Okta + AWS',
      'Open: centralized logging retention proof for <strong>365 days</strong>',
      'Open: tabletop scenario for <strong>ransomware + exfil</strong> not yet run',
    ],
    sources: 14,
    updatedMinutesAgo: 14,
    quotes: [
      '"Need SIEM retention screenshots before fieldwork." — compliance advisor',
      '"Tabletop scheduled but not executed." — IR lead notes',
    ],
  },
  {
    id: 'i-lit',
    title: 'Threat landscape',
    icon: 'book',
    category: 'literature',
    confidence: 76,
    summary: 'Strong coverage of identity attacks, SaaS misconfigurations, and supply-chain risks for your stack. Weaker on OT exposure and insider threat playbooks.',
    bullets: [
      '<strong>Coverage:</strong> MITRE techniques for cloud identity & SaaS',
      '<strong>Gap:</strong> limited intel on <strong>OAuth consent phishing</strong> variants',
      '<strong>Gap:</strong> no formal insider-threat escalation path documented',
    ],
    sources: 32,
    updatedMinutesAgo: 28,
    quotes: [
      '"OAuth abuse is the fastest-moving thread in your sector." — threat intel advisor',
      '"Insider playbook is a one-pager — not enough for audit." — GRC advisor',
    ],
  },
  {
    id: 'i-questions',
    title: 'Open security questions',
    icon: 'sparkles',
    category: 'theory',
    confidence: 63,
    summary: 'Three live threads. Q1 (scope of zero trust for contractors) gates architecture sign-off. Q2–Q3 affect detection engineering priorities.',
    bullets: [
      '<strong>Q1:</strong> Do contractors get full ZTNA or bastion-only access?',
      '<strong>Q2:</strong> Which SIEM detections are in-scope for SOC 2 evidence?',
      '<strong>Q3:</strong> Is customer data in EU regions in scope for DPA addendum?',
    ],
    sources: 9,
    updatedMinutesAgo: 41,
    quotes: [
      '"Contractor access model blocks network design." — architect advisor',
      '"EU data residency may expand audit scope." — privacy advisor',
    ],
  },
  {
    id: 'i-next',
    title: 'Next steps',
    icon: 'arrow',
    category: 'action',
    confidence: 85,
    summary: 'Near-term actions tied to audit date and production cutover. Two items have slipped one sprint.',
    bullets: [
      'Close <strong>12 VPN exceptions</strong> or document compensating controls',
      'Run ransomware tabletop & upload minutes to evidence locker',
      'Ship <strong>5 high-fidelity detections</strong> to production SIEM',
      'Finalize vendor SOC 2 bridge letter for subprocessors',
    ],
    sources: 7,
    updatedMinutesAgo: 9,
    quotes: [
      '"VPN exceptions are the #1 audit finding risk." — GRC advisor',
      '"Detections without tuning will false-positive in week one." — SOC advisor',
    ],
  },
  {
    id: 'i-blockers',
    title: 'Blockers & risks',
    icon: 'alert',
    category: 'risk',
    confidence: 74,
    summary: 'One technical blocker (legacy logging), one governance blocker (exception approvals). Governance is the higher audit risk.',
    bullets: [
      '<strong>Technical:</strong> legacy app logs not reaching SIEM — 18% of prod traffic',
      '<strong>Governance:</strong> exception approval SLA &gt; 10 days — auditors will flag',
    ],
    sources: 6,
    updatedMinutesAgo: 20,
    quotes: [
      '"Without those logs you cannot prove detective controls." — detection engineer',
      '"Exception backlog reads as control failure." — devil\'s advocate advisor',
    ],
  },
];

export const WIDGET_CATALOG = [
  { type: 'reading-queue', name: 'Reading Queue', desc: 'Advisories, breach write-ups, and reports to work through', icon: 'list', cat: 'research', defaultSize: 'S', enhanced: true },
  { type: 'notes', name: 'Note Inbox', desc: 'Markdown security notes with full-text search', icon: 'notes', cat: 'research', defaultSize: 'S', enhanced: true },
  { type: 'highlights', name: 'Highlights & Quotes', desc: 'Key excerpts from reports and advisories, with source', icon: 'cite', cat: 'research', defaultSize: 'M', enhanced: true },
  { type: 'phd-resources', name: 'Security Resources', desc: 'Frameworks, tools, training, and community references', icon: 'star', cat: 'research', defaultSize: 'M', enhanced: true },

  { type: 'writing', name: 'Doc Drafting', desc: 'Draft policies, runbooks, and reports; 28-day writing heatmap', icon: 'pencil', cat: 'writing', defaultSize: 'M', enhanced: true },
  { type: 'outline', name: 'Outline Builder', desc: 'Structure a policy, report, or runbook before drafting', icon: 'list', cat: 'writing', defaultSize: 'M', enhanced: true },

  { type: 'kanban', name: 'Task Board', desc: 'Remediation and project tasks with priority filters', icon: 'kanban', cat: 'project', defaultSize: 'L', enhanced: true },
  { type: 'deadlines', name: 'Deadlines', desc: 'Audit dates, cert renewals, patch windows — with .ics export', icon: 'calendar', cat: 'project', defaultSize: 'S', enhanced: true },
  { type: 'pomodoro', name: 'Pomodoro', desc: 'Real timer with break cycle and session counter', icon: 'timer', cat: 'project', defaultSize: 'S', enhanced: true },
  { type: 'meeting-log', name: 'Meeting Log', desc: 'Per-stakeholder contact history and action items', icon: 'message', cat: 'project', defaultSize: 'M' },
  { type: 'goals', name: 'Goals / OKRs', desc: 'Quarterly security milestones with progress sliders', icon: 'bullseye', cat: 'project', defaultSize: 'M' },
  { type: 'calendar', name: 'Calendar', desc: 'Month grid with deadlines and work days', icon: 'calendar', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'activity', name: 'Activity Feed', desc: 'Chronological log of edits across widgets', icon: 'graph', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'documenter', name: 'Daily Documenter', desc: 'Date-stamped work journal with weekly summary', icon: 'pencil', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'phd-journey', name: 'Security Program Roadmap', desc: 'Milestones from assessment → hardening → audit → steady state', icon: 'flag', cat: 'project', defaultSize: 'M', enhanced: true },

  { type: 'habits', name: 'Habit Tracker', desc: 'Daily security practices — reviews, backups, alert triage', icon: 'flame', cat: 'wellness', defaultSize: 'S' },

  { type: 'budget', name: 'Budget Tracker', desc: 'Security spend vs. cap — tools, training, services', icon: 'wallet', cat: 'practical', defaultSize: 'S' },

  { type: 'reviewer-2', name: 'Red Team Reviewer', desc: 'Paste a draft policy or plan → adversarial critique', icon: 'gavel', cat: 'critic', defaultSize: 'M', critic: true },
  { type: 'devils-advocate', name: 'Devil\'s Advocate', desc: 'Strongest counter-arguments to your security plan', icon: 'scale', cat: 'critic', defaultSize: 'M', critic: true },
  { type: 'scope-realism', name: 'Scope Realism Check', desc: 'Blunt feasibility verdict for your rollout timeline', icon: 'bullseye', cat: 'critic', defaultSize: 'M', critic: true },
];

export const CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'research', label: 'Threat Intel' },
  { id: 'writing', label: 'Docs & Policies' },
  { id: 'project', label: 'Project' },
  { id: 'wellness', label: 'Practice' },
  { id: 'practical', label: 'Practical' },
  { id: 'critic', label: 'Anti-yes-man', critic: true },
];

// Workspace starts empty — users add widgets from the palette or pick a preset.
export const DEFAULT_LAYOUT = [];

// Curated starter layouts. Each preset assigns its own widget IDs so reseeding
// won't collide with manually-added widgets.
const presetIds = (types) => types.map((t, i) => ({ id: `pre-${t.type}-${i}`, ...t }));
export const WORKSPACE_PRESETS = [
  {
    id: 'day1-soc',
    name: 'SOC Starter',
    desc: 'Get oriented: reading queue, notes, deadlines, kanban, pomodoro.',
    icon: 'sparkles',
    layout: presetIds([
      { type: 'reading-queue', size: 'M' },
      { type: 'notes', size: 'M' },
      { type: 'deadlines', size: 'S' },
      { type: 'pomodoro', size: 'S' },
      { type: 'kanban', size: 'L' },
      { type: 'activity', size: 'M' },
    ]),
  },
  {
    id: 'writing-sprint',
    name: 'Policy Sprint',
    desc: 'Focus mode for drafting: doc pad, outline, highlights, pomodoro, red-team review.',
    icon: 'pencil',
    layout: presetIds([
      { type: 'writing', size: 'M' },
      { type: 'outline', size: 'M' },
      { type: 'pomodoro', size: 'S' },
      { type: 'highlights', size: 'M' },
      { type: 'reviewer-2', size: 'M', critic: true },
    ]),
  },
  {
    id: 'audit-prep',
    name: 'Audit Prep',
    desc: 'Evidence-heavy: reading queue, notes, highlights, kanban, deadlines, goals.',
    icon: 'book',
    layout: presetIds([
      { type: 'reading-queue', size: 'M' },
      { type: 'notes', size: 'M' },
      { type: 'highlights', size: 'M' },
      { type: 'kanban', size: 'L' },
      { type: 'deadlines', size: 'S' },
      { type: 'goals', size: 'M' },
    ]),
  },
  {
    id: 'incident-mode',
    name: 'Incident Mode',
    desc: 'Active response: kanban, deadlines, meeting log, doc pad, challenge widgets.',
    icon: 'gavel',
    layout: presetIds([
      { type: 'kanban', size: 'L' },
      { type: 'deadlines', size: 'S' },
      { type: 'meeting-log', size: 'M' },
      { type: 'writing', size: 'M' },
      { type: 'devils-advocate', size: 'M', critic: true },
      { type: 'scope-realism', size: 'M', critic: true },
    ]),
  },
];

// Initial state when a widget is first added — minimal scaffolding, no demo content.
export const EMPTY_STATE = {
  bibliography: { format: 'APA', entries: [] },
  kanban: {
    cols: [
      { id: 'todo', label: 'To Do' },
      { id: 'doing', label: 'Doing' },
      { id: 'stuck', label: 'Stuck' },
      { id: 'done', label: 'Done' },
    ],
    cards: [],
  },
  pomodoro: { focus: 25, brk: 5, sessionsToday: 0 },
  writing: {
    chapters: [{ id: 'c-default', name: 'Untitled chapter', target: 500, draft: '' }],
    activeChapterId: 'c-default',
    dailyTotals: {},
    target: 500,
  },
  deadlines: [],
  budget: { cap: 1000, items: [] },
  notes: { items: [] },
  habits: { items: [] },
  goals: { items: [] },
  'meeting-log': { items: [] },
  'reading-queue': [],
  'reviewer-2': { lastDraft: '', lastReview: null },
  'devils-advocate': { claim: '', counters: [] },
  'scope-realism': {
    target: '',
    score: 0,
    label: 'Set a target',
    factors: [],
    notes: '',
  },
  outline: { items: [], expanded: {} },
  highlights: { items: [] },
  latex: { source: '', displayMode: true },
  calendar: { viewMonth: new Date().toISOString().slice(0, 7) },
  activity: {},
  documenter: { entries: [], lastSummary: null },
  'phd-journey': {
    // Status per milestone: 'open' | 'in-progress' | 'completed'
    // Milestones come from the security program roadmap (assessment → steady state)
    statuses: {},
    notes: {},
  },
  'phd-resources': {
    customLinks: [],
  },
};

