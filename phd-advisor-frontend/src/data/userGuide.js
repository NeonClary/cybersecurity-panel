// User Guide content for Cybersecurity Advisor.
// Use {{appName}} as a placeholder — replaced at render time.

export const userGuideTopics = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: 'Sparkles',
    content: `# Welcome to {{appName}}

{{appName}} is your AI-powered cybersecurity guidance system. A panel of specialized advisors gives you diverse perspectives on threats, controls, incidents, compliance, architecture, and career growth.

## Your first steps
1. **Start a new chat** using the pencil icon next to the search bar
2. **Type a question** about security risks, tools, policies, incidents, or your career path
3. **Read multiple advisor responses** — each persona brings a different lens
4. **Reply to a specific advisor** to go deeper on their angle

## Need help?
Return to this guide anytime via the **?** icon in the header.`,
  },
  {
    id: 'advisors',
    title: 'Your Advisors',
    icon: 'Shield',
    content: `# Your Advisors

{{appName}} includes {{advisorCount}} specialized cybersecurity personas, powered by Neon BrainForge Security (4090 x1-3) with GPT-5.4 fallback when needed.

## Available advisors
{{advisorList}}

## Seeing who's available
Click the **advisors** dropdown in the top right of the chat to see the full panel.`,
  },
  {
    id: 'conversations',
    title: 'Conversations & Replies',
    icon: 'MessageCircle',
    content: `# Conversations & Replies

## Asking a question
Type into the chat box at the bottom. All advisors respond with their unique perspective.

## Replying to a specific advisor
Click an advisor's response to **reply directly to them** and continue one-on-one.

## Tips
- Include environment context (cloud, on-prem, SaaS, regulated industry)
- Paste log snippets, policy excerpts, or architecture notes for sharper advice
- Different advisors may disagree — use that tension to stress-test decisions`,
  },
  {
    id: 'documents',
    title: 'Uploading Documents',
    icon: 'Paperclip',
    content: `# Uploading Documents

Attach **PDFs, Word documents, and text files** so advisors can reference your materials.

## How it works
1. Click the paperclip icon in the chat input
2. Select your file
3. Wait for processing
4. Ask a question — advisors use **RAG** to pull relevant sections

## Good uploads
- Incident reports and postmortems
- Architecture diagrams (exported as PDF)
- Policy drafts, audit findings, pen-test summaries`,
  },
  {
    id: 'sessions',
    title: 'Sessions & History',
    icon: 'MessagesSquare',
    content: `# Sessions & History

Every conversation is saved as a session. Use the sidebar search to find past chats, switch sessions, or start a new chat with the pencil icon.`,
  },
  {
    id: 'canvas',
    title: 'Security Canvas',
    icon: 'BarChart3',
    content: `# {{appName}} Canvas

The Canvas is a **structured workspace** for your security program. Insights from chats can inform widgets such as:

- Threat landscape
- Controls posture
- Open incidents & IR actions
- Compliance gaps
- Architecture decisions
- Skill development & certifications

Open Canvas from the sidebar. Layout and widgets auto-save in your browser.`,
  },
  {
    id: 'tips',
    title: 'Tips & Shortcuts',
    icon: 'Sparkles',
    content: `# Tips & Shortcuts

## Useful workflows
- **Incident triage:** Incident Response Lead + Threat Modeling Analyst
- **Audit prep:** Compliance Advisor + Security Architect
- **Career planning:** Jerry Huaute Advisor + Security Career Mentor
- **Red-team mindset:** Use anti-yes-man Canvas widgets for challenge and scope checks

## Theme
Switch light/dark mode from the toggle in the header.`,
  },
];
