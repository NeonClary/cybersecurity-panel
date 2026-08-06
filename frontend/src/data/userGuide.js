// User Guide content for Cybersecurity Advisor.
// Placeholders {{appName}}, {{advisorCount}}, {{advisorList}} are replaced at render time.

export const userGuideTopics = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: 'Sparkles',
    content: `# Welcome to {{appName}}

{{appName}} is your AI cybersecurity advisory panel. AI Jerry Huaute greets you like a real consultant, learns from what you say, and brings in specialized experts when needed.

## Opening a conversation
When you start a new chat, Jerry greets you with something like:

> **"You've contacted me today — what is it that I can help you with in cybersecurity?"**

## Intake chips
Tap a starter chip to jump straight in, or choose **Something else…** to type free text:

- **I think I've been hacked** — urgent personal or account compromise
- **Prepare for an audit or review** — compliance, evidence, readiness
- **Secure my business** — practical SMB priorities
- **Grow my security career** — paths, certs, skills
- **Something else…** — describe your need in your own words

You don't need a long intake form. The panel learns as you talk.

## First steps
1. Open **Chat** (or start a new session from the sidebar pencil icon)
2. Pick a chip or type your question
3. Read Jerry's and the panel's replies
4. Reply to a specific advisor when you want to go deeper

## Need this guide again?
Open it anytime via the **?** icon in the header.`,
  },
  {
    id: 'advisors',
    title: 'Your Advisors',
    icon: 'Shield',
    content: `# Your Advisors

{{appName}} includes **{{advisorCount}}** specialized cybersecurity personas. **AI Jerry Huaute** is the lead advisor: he opens conversations, owns intake, and stays in the loop by default. Other experts join when your question needs their lens.

## Available advisors
{{advisorList}}

## How the panel works
- Jerry leads with practical, consultant-style guidance
- The orchestrator ranks which experts should answer based on your question and profile
- You may see multiple perspectives in one turn — use disagreement to stress-test decisions

## Seeing who's available
Use the **advisors** control in the chat header to review the full panel.`,
  },
  {
    id: 'conversations',
    title: 'Conversations & Replies',
    icon: 'MessageCircle',
    content: `# Conversations & Replies

## Asking a question
Type in the chat box at the bottom. Advisors respond with their unique angles. Sessions are saved automatically — find them in the sidebar search.

## Replying to a specific advisor
Click an advisor's response to **reply directly to them** and continue one-on-one.

## Getting sharper answers
- Name your role and environment (home user, SMB, cloud, regulated industry)
- Paste logs, policy excerpts, or architecture notes when relevant
- Say whether this is urgent (incident now) or planning (audit, program, career)

## Sessions
Every conversation is a session. Switch or start new chats with the sidebar pencil icon.`,
  },
  {
    id: 'profile',
    title: 'Your Profile',
    icon: 'User',
    content: `# Your Profile

Open **Profile** from the user menu to see and edit what the app knows about you. Facts come from two sources and stay visible and editable.

## Things you told us (stated)
Information you provide explicitly — profile fields, onboarding choices, or clear statements in chat (for example, "I'm the IT manager at a 200-person clinic").

## Things we noticed (inferred)
After you message, the app may infer role, knowledge level, org type, urgency, tools, or goals. Inferred facts are labeled separately so you can trust and correct them.

## What you can do
- **Edit** any fact that looks wrong
- **Confirm** an inferred fact to promote it to stated
- **Delete** facts you don't want kept

## Summaries
The app builds short and long **user summaries** from your facts and recent chats. Advisors use these so guidance matches your maturity and context. Summaries refresh as conversations progress (and at the start of a new session).

You don't have to fill a long form up front — talk normally, then refine Profile when you want.`,
  },
  {
    id: 'journey',
    title: 'Security Journey',
    icon: 'Map',
    content: `# Security Journey

**Security Journey** is your progress path toward cybersecurity goals. Open it from the header or sidebar.

## Pick a track
Choose (or change) an active track:

| Track | Best for |
|---|---|
| **ITIL Maturity Model** | Organizations maturing processes (Initial → Optimizing) |
| **NIST CSF 2.0** | Govern / Identify / Protect / Detect / Respond / Recover |
| **CIS Controls** | Concrete checklists (IG1 → IG3), especially SMB |
| **Certification paths** | Security+, CySA+, CISSP, and similar milestones |
| **Personal Digital Security** | Passwords, MFA, backups, devices, monitoring for individuals |
| **Custom goal** | A goal you map with the panel (e.g. pass a review in Q4) |

## Tracking progress
- Headline progress shows your current level and overall %
- Check items off as you complete them
- Advisors may propose a check-off when a chat demonstrates readiness — you confirm

Revisit Journey anytime to see how far you've come and what's next.`,
  },
  {
    id: 'workspace-documents',
    title: 'Workspace & Documents',
    icon: 'LayoutDashboard',
    content: `# Workspace & Documents

Use the header tabs to move between Chat, Journey, **Workspace**, and **Documents**.

## Workspace
Your security operations dashboard. Add widgets for things like:

- Incident checklists and IR actions
- Risk register notes
- Controls and deadlines
- Policy drafts and reading queues

Start empty or from a preset. Layout and widget state persist with your account. Open Workspace from the header **Workspace** tab.

## Documents
A place for deliverables and artifacts you create or keep — policies, evidence lists, board summaries, and related drafts. Export when you need a copy outside the app.

Workspace is for interactive widgets; Documents is for lasting artifacts and drafts.`,
  },
  {
    id: 'uploads-rag',
    title: 'Uploads & RAG',
    icon: 'Paperclip',
    content: `# Uploads & RAG

Attach reference files so advisors can cite **your** materials, not just general knowledge.

## How to upload
1. Click the paperclip in the chat input
2. Select a PDF, Word, or text file
3. Wait for processing
4. Ask a question — relevant sections are retrieved via **RAG** (retrieval-augmented generation)

## Good uploads
- Incident reports and postmortems
- Architecture notes (PDF export works well)
- Policy drafts, audit findings, pen-test summaries
- Security questionnaires you're answering

View already-uploaded files from the documents control next to the input when files are attached to the session.`,
  },
  {
    id: 'model-status',
    title: 'Model Status',
    icon: 'Activity',
    content: `# Model Status

Check which LLM providers and models are reachable right now.

## Where to find it
**Settings → Model Status** (also available from the user / provider menus).

## What you'll see
- Online, unavailable, or error status per model/provider
- A **Refresh** control to re-probe without leaving the modal

Secrets stay on the server — the status view only reports reachability. If a primary model is down, the app may use a fallback provider when configured.`,
  },
  {
    id: 'tips',
    title: 'Tips: Triage vs Advisory',
    icon: 'Lightbulb',
    content: `# Tips: Triage vs Advisory

Match how you ask to what you need. The panel adapts urgency, depth, and which experts speak.

## Triage (something is wrong *now*)
Use when accounts, devices, or business systems may be compromised.

- Lead with impact: "I think I've been hacked" / "ransomware on a file server"
- Share what you already did (password changes, disconnecting, screenshots)
- Expect first-steps checklists before deep profiling questions
- Prefer **Incident Responder** replies; follow Jerry's immediate guidance

## Advisory (you need a recommendation)
Use for tools, architecture, policy, career, or "what should we do next?"

- State goal and constraints (budget, timeline, skill level)
- Mention org size and industry if relevant
- Ask for options ranked by priority, not just a single answer

## Program / Journey (long-term improvement)
- Open **Security Journey** and pick ITIL, NIST, CIS, certs, Personal Digital Security, or a custom goal
- Bring audit dates, current maturity, and target state into chat
- Use Workspace widgets to keep checklists and registers visible between sessions

## Theme
Switch light/dark mode from the header toggle.`,
  },
];
