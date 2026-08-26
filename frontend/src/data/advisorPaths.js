/**
 * Non-linear onboarding paths for the chat welcome screen.
 * Only root nodes (tier 0) show initially; deeper steps unlock as prerequisites complete.
 */

export const PATH_SECTION_TITLE = 'Find your way';

/** @typedef {'scroll_suggestions'|'open_profile'|'navigate_journey'|'navigate_canvas'|'open_user_guide'|'open_model_status'|'navigate_signup'|'none'} PathActionType */

/**
 * @typedef {Object} PathNode
 * @property {string} id
 * @property {number} tier
 * @property {string} title
 * @property {string} tagline
 * @property {string} guide
 * @property {{ type: PathActionType, label?: string }} action
 * @property {string[]} [requires] - all must be completed
 * @property {string[]} [requiresAny] - at least one must be completed
 * @property {string} icon - Lucide icon name
 * @property {boolean} [guestOnly]
 * @property {boolean} [signedInOnly]
 */

/** @type {PathNode[]} */
export const PATH_NODES = [
  {
    id: 'first-question',
    tier: 0,
    title: 'Ask your first question',
    tagline: 'Start with a suggested prompt',
    guide:
      'Scroll to “Practical Next Steps” and tap any chip. Your panel answers in the carousel — no need to pick a topic up here.',
    action: { type: 'scroll_suggestions', label: 'Show suggestions' },
    icon: 'MessageCircle',
  },
  {
    id: 'your-profile',
    tier: 0,
    title: 'Build your profile',
    tagline: 'Role, org & context',
    guide:
      'Open About You and add a few facts — who you are, what you protect, and what you’re worried about. Advisors use this in every reply.',
    action: { type: 'open_profile', label: 'Open About You' },
    icon: 'UserCircle',
  },
  {
    id: 'your-journey',
    tier: 0,
    title: 'Set your journey',
    tagline: 'Goal → milestones',
    guide:
      'The Journey page turns a security goal into trackable steps — baseline hardening, audit prep, IR readiness, or career growth.',
    action: { type: 'navigate_journey', label: 'Open Journey' },
    icon: 'Map',
  },
  {
    id: 'your-workspace',
    tier: 0,
    title: 'Open workspace',
    tagline: 'Drafts & references',
    guide:
      'Workspace is where you pin sources, build checklists, and draft policies. Search arXiv, NIST, NVD, and CISA without leaving the app.',
    action: { type: 'navigate_canvas', label: 'Open workspace' },
    icon: 'FileText',
  },
  {
    id: 'stated-goal',
    tier: 1,
    title: 'Name your priority',
    tagline: 'One line advisors remember',
    guide:
      'Add a stated goal in About You — e.g. “SOC 2 for a 50-person SaaS” or “home network hardening.” Starters and follow-ups adapt to it.',
    action: { type: 'open_profile', label: 'Set your goal' },
    requiresAny: ['your-profile', 'your-journey'],
    icon: 'Target',
  },
  {
    id: 'add-references',
    tier: 1,
    title: 'Add reference material',
    tagline: 'Upload or paste sources',
    guide:
      'Attach PDFs in chat, paste from your clipboard into context, or pull citations from workspace search. Ground advice in your policies and standards.',
    action: { type: 'open_user_guide', label: 'See how' },
    requiresAny: ['your-workspace', 'first-question'],
    icon: 'BookmarkPlus',
  },
  {
    id: 'pick-advisors',
    tier: 1,
    title: 'Shape your panel',
    tagline: 'Turn specialists on/off',
    guide:
      'Use the advisor menu in the header to add or remove experts. Jerry stays as lead; invite compliance, IR, or career mentors when the topic fits.',
    action: { type: 'none', label: 'Got it' },
    requires: ['first-question'],
    icon: 'Users',
  },
  {
    id: 'explore-guide',
    tier: 1,
    title: 'Skim the user guide',
    tagline: '2-minute feature map',
    guide:
      'The guide covers chat, workspace widgets, Journey tracks, and profile memory — useful when you want the full layout before diving in.',
    action: { type: 'open_user_guide', label: 'Open guide' },
    requiresAny: ['first-question', 'your-workspace'],
    icon: 'BookOpen',
  },
  {
    id: 'model-status',
    tier: 2,
    title: 'Check advisor availability',
    tagline: 'See who’s online',
    guide:
      'Settings → Model Status probes each advisor endpoint. Unavailable models are hidden from the panel so you’re not waiting on a dead API.',
    action: { type: 'open_model_status', label: 'Open model status' },
    requires: ['first-question'],
    signedInOnly: true,
    icon: 'Activity',
  },
  {
    id: 'save-progress',
    tier: 2,
    title: 'Create an account',
    tagline: 'Keep chats & progress',
    guide:
      'Guest mode is temporary. Sign up to save profile, Journey, workspace layout, and chat history across devices.',
    action: { type: 'navigate_signup', label: 'Create account' },
    requiresAny: ['your-profile', 'your-journey', 'first-question'],
    guestOnly: true,
    icon: 'KeyRound',
  },
];

export const ROOT_NODE_IDS = PATH_NODES.filter((n) => n.tier === 0).map((n) => n.id);

export function getPathNode(id) {
  return PATH_NODES.find((n) => n.id === id) || null;
}
