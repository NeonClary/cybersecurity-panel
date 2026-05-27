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
  { type: 'bibliography', name: 'Bibliography', desc: 'DOI lookup + BibTeX import; APA/MLA/Chicago/BibTeX export', icon: 'book', cat: 'research', defaultSize: 'M', enhanced: true },
  { type: 'reading-queue', name: 'Reading Queue', desc: 'CrossRef title search + DOI resolve to auto-fill papers', icon: 'list', cat: 'research', defaultSize: 'S', enhanced: true },
  { type: 'notes', name: 'Note Inbox', desc: 'Markdown rendering with full-text search', icon: 'notes', cat: 'research', defaultSize: 'S', enhanced: true },
  { type: 'concept-map', name: 'Concept Map', desc: 'Drag papers as nodes, tag themes', icon: 'network', cat: 'research', defaultSize: 'M', stub: true },
  { type: 'highlights', name: 'Highlights & Quotes', desc: 'Pulled quotes with citation key, copy-formatted', icon: 'cite', cat: 'research', defaultSize: 'M', enhanced: true },
  { type: 'paper-tldr', name: 'Paper TL;DR', desc: 'PDF → claim / method / limits / gaps', icon: 'microscope', cat: 'research', defaultSize: 'M', stub: true },

  { type: 'writing', name: 'Writing Tracker', desc: 'Inline writing pad, multi-chapter, 28-day heatmap', icon: 'pencil', cat: 'writing', defaultSize: 'M', enhanced: true },
  { type: 'outline', name: 'Outline Builder', desc: 'Collapsible tree with indent / outdent / inline editing', icon: 'list', cat: 'writing', defaultSize: 'M', enhanced: true },
  { type: 'latex', name: 'LaTeX Scratchpad', desc: 'Live KaTeX render-as-you-type with snippet chips', icon: 'flask', cat: 'writing', defaultSize: 'M', enhanced: true },
  { type: 'draft-locker', name: 'Draft Locker', desc: 'Versioned chapter drafts', icon: 'shield', cat: 'writing', defaultSize: 'S', stub: true },

  { type: 'kanban', name: 'Task Board', desc: 'Drag-to-move with priority filter chips and due-date sort', icon: 'kanban', cat: 'project', defaultSize: 'L', enhanced: true },
  { type: 'deadlines', name: 'Deadlines', desc: 'Countdown plus per-deadline .ics calendar export', icon: 'calendar', cat: 'project', defaultSize: 'S', enhanced: true },
  { type: 'pomodoro', name: 'Pomodoro', desc: 'Real timer with break cycle and session counter', icon: 'timer', cat: 'project', defaultSize: 'S', enhanced: true },
  { type: 'gantt', name: 'Milestone Timeline', desc: 'Proposal → IRB → defense', icon: 'flag', cat: 'project', defaultSize: 'L', stub: true },
  { type: 'meeting-log', name: 'Meeting Log', desc: 'Per-stakeholder, last contact, actions', icon: 'message', cat: 'project', defaultSize: 'M' },
  { type: 'goals', name: 'Goals / OKRs', desc: 'Quarterly milestones with progress sliders', icon: 'bullseye', cat: 'project', defaultSize: 'M' },
  { type: 'calendar', name: 'Calendar', desc: 'Month grid with deadlines and writing days', icon: 'calendar', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'activity', name: 'Activity Feed', desc: 'Chronological log of edits across widgets', icon: 'graph', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'documenter', name: 'Daily Documenter', desc: 'Date-stamped journal · AI weekly summary (LLM stub)', icon: 'pencil', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'phd-journey', name: 'Security Program Roadmap', desc: 'Milestones from assessment → hardening → audit → steady state', icon: 'flag', cat: 'project', defaultSize: 'M', enhanced: true },
  { type: 'phd-resources', name: 'Security Resources', desc: 'Frameworks, tools, training, and community references', icon: 'star', cat: 'research', defaultSize: 'M', enhanced: true },

  { type: 'mood', name: 'Mood / Burnout Check-in', desc: 'Daily slider, trend graph', icon: 'smile', cat: 'wellness', defaultSize: 'S', stub: true },
  { type: 'sleep', name: 'Sleep & Energy', desc: 'Correlate with productive days', icon: 'heart', cat: 'wellness', defaultSize: 'S', stub: true },
  { type: 'habits', name: 'Habit Tracker', desc: 'Daily research practices', icon: 'flame', cat: 'wellness', defaultSize: 'S' },
  { type: 'focus', name: 'Focus Playlist', desc: 'Ambient sounds & music', icon: 'music', cat: 'wellness', defaultSize: 'S', stub: true },

  { type: 'cfp', name: 'Conference / CFP Tracker', desc: 'Deadlines, fit, submission status', icon: 'send', cat: 'career', defaultSize: 'M', stub: true },
  { type: 'grants', name: 'Grant Tracker', desc: 'Applications, deadlines, awards', icon: 'award', cat: 'career', defaultSize: 'S', stub: true },
  { type: 'crm', name: 'Networking CRM', desc: 'Collaborators, last touch', icon: 'network', cat: 'career', defaultSize: 'M', stub: true },
  { type: 'cv', name: 'CV / Publications', desc: 'Track outputs, generate CV', icon: 'user', cat: 'career', defaultSize: 'S', stub: true },

  { type: 'datasets', name: 'Dataset Library', desc: 'Public datasets by domain', icon: 'database', cat: 'data', defaultSize: 'M', stub: true },
  { type: 'methods', name: 'Methods Cheat Sheet', desc: 'When to use what test', icon: 'flask', cat: 'data', defaultSize: 'M', stub: true },

  { type: 'budget', name: 'Budget Tracker', desc: 'Research spend vs. cap', icon: 'wallet', cat: 'practical', defaultSize: 'S' },
  { type: 'discounts', name: 'Student Discounts', desc: 'Software & services with edu pricing', icon: 'star', cat: 'practical', defaultSize: 'S', stub: true },

  { type: 'reviewer-2', name: 'Reviewer 2 Simulator', desc: 'Paste a draft → harsh peer-review-style critique', icon: 'gavel', cat: 'critic', defaultSize: 'M', critic: true },
  { type: 'devils-advocate', name: 'Devil\'s Advocate', desc: 'Strongest counter-arguments to your hypothesis', icon: 'scale', cat: 'critic', defaultSize: 'M', critic: true },
  { type: 'scope-realism', name: 'Scope Realism Check', desc: 'Brutal feasibility verdict given timeline', icon: 'bullseye', cat: 'critic', defaultSize: 'M', critic: true },
  { type: 'assumption', name: 'Assumption Excavator', desc: 'Names hidden assumptions, asks "what if wrong?"', icon: 'brain', cat: 'critic', defaultSize: 'M', critic: true, stub: true },
  { type: 'whats-missing', name: '"What\'s Missing"', desc: 'Gap analysis on lit review or method', icon: 'alert', cat: 'critic', defaultSize: 'S', critic: true, stub: true },
  { type: 'calibrator', name: 'Confidence Calibrator', desc: 'Challenges every "results show X" claim', icon: 'scale', cat: 'critic', defaultSize: 'S', critic: true, stub: true },
];

export const CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'research', label: 'Threat Intel' },
  { id: 'writing', label: 'Writing' },
  { id: 'project', label: 'Project' },
  { id: 'wellness', label: 'Wellness' },
  { id: 'career', label: 'Career' },
  { id: 'data', label: 'Data' },
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
      { type: 'bibliography', size: 'M' },
      { type: 'notes', size: 'M' },
      { type: 'deadlines', size: 'S' },
      { type: 'pomodoro', size: 'S' },
      { type: 'kanban', size: 'L' },
    ]),
  },
  {
    id: 'writing-sprint',
    name: 'Writing Sprint',
    desc: 'Focus mode for drafting: writing pad, outline, LaTeX, highlights, pomodoro.',
    icon: 'pencil',
    layout: presetIds([
      { type: 'writing', size: 'M' },
      { type: 'outline', size: 'M' },
      { type: 'pomodoro', size: 'S' },
      { type: 'latex', size: 'M' },
      { type: 'highlights', size: 'M' },
      { type: 'bibliography', size: 'M' },
    ]),
  },
  {
    id: 'audit-prep',
    name: 'Audit Prep',
    desc: 'Evidence-heavy: bibliography, reading queue, notes, highlights, kanban.',
    icon: 'book',
    layout: presetIds([
      { type: 'bibliography', size: 'L' },
      { type: 'reading-queue', size: 'M' },
      { type: 'notes', size: 'M' },
      { type: 'highlights', size: 'M' },
      { type: 'kanban', size: 'M' },
    ]),
  },
  {
    id: 'incident-mode',
    name: 'Incident Mode',
    desc: 'Active response: kanban, deadlines, challenge widgets, meeting log.',
    icon: 'gavel',
    layout: presetIds([
      { type: 'writing', size: 'M' },
      { type: 'outline', size: 'M' },
      { type: 'reviewer-2', size: 'M', critic: true },
      { type: 'devils-advocate', size: 'M', critic: true },
      { type: 'scope-realism', size: 'M', critic: true },
      { type: 'deadlines', size: 'S' },
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
    // Milestones come from the standard PhD journey (course selection → ProQuest)
    statuses: {},
    notes: {},
  },
  'phd-resources': {
    customLinks: [],
  },
};

