# Cybersecurity Advisor Panel — Overhaul Plan

**Project:** NeonClary/cybersecurity-panel (baseline copied from CCAI-Demo-Clary @ FEAT_CybersecurityCanvas, commit `e204135`)
**Collaboration:** Jerry Huaute, CISSP × Neon.ai (CCAI panel architecture, BrainForge Security model)
**Deployment target:** HuggingFace Spaces, single Docker container, port 7860, SQLite at `/data`
**Date:** August 5, 2026

---

## 1. Vision

Turn the proof-of-concept demo into a mature, engaging cybersecurity advisory app: a panel of AI experts led by AI Jerry Huaute that greets users the way a real consultant would ("You've contacted me today — what is it that I can help you with in cybersecurity?"), learns about them the way a real consultant does (from everything they say, not just form fields), adapts its depth and vocabulary to their maturity level, and gives them a visible, motivating path toward their security goals.

### The three-legged model (from Richard's framing)
Every engagement is understood along three dimensions, plus urgency:

1. **The person** — role, knowledge level, certifications, communication preferences.
2. **The organization** — size, industry, IT resources, compliance obligations, current maturity.
3. **The immediate need** — the reason they showed up today.
4. **Urgency overlay** — *triage* (incident now), *advisory* (recommendation needed), or *program* (long-term improvement). Forum research shows user questions split cleanly into these three conversation modes.

### Target user types (from forum research)
| User type | Dominant needs | Conversation mode |
|---|---|---|
| Individual | "Was I hacked?", sextortion/scam validation, phishing checks, personal digital security | Triage |
| SMB owner / solo IT | Basics ("am I a target?"), tool selection, backups/ransomware, policies | Advisory |
| Enterprise IT / practitioner | IR procedure, architecture, IAM/MFA rollout, tool comparison | Advisory + Program |
| Executive / manager | Audit prep (SOC 2 / ISO / NIST), board communication, budget justification, maturity vs peers | Program |
| Career seeker / student | Certs (Security+ vs CISSP), career paths, home labs, interviews | Advisory |

The system infers which type it's talking to from the first messages (as Jerry described: "we naturally have an idea of what someone's capable of by the question they ask") and adapts vocabulary, depth, suggested prompts, and expert selection.

---

## 2. Current state (verified in code)

**Solid, keep:**
- FastAPI backend + React SPA in one HF Spaces Docker image; SQLite (aiosqlite) persistence at `/data` behind a Mongo-API shim (`app/core/db.py`).
- LLM layer: Neon vLLM client (`BrainForge/Security@2026.03.18` at `4090-x1-3.neonaiservices2.com/vllm0`, OpenAI-compatible, Basic/Bearer auth) with resilient GPT-5.4 fallback race, plus Gemini and Ollama clients and a runtime provider switch (`/switch-provider`).
- NDJSON streaming chat with top-3 expert routing via LLM ranking, parallel persona generation.
- JWT auth (bcrypt, HS256), chat session persistence, document upload + ChromaDB RAG, export (TXT/PDF/DOCX), voice endpoints (Whisper STT / Coqui TTS).
- Backend unit/integration test suite + GitHub Actions CI.

**Broken / stubbed (must fix):**
- **Profile is dead-wired**: backend `GET/PUT /api/users/me/profile` works, but `ChatPage.js` imports `ProfileWalkthrough` / `AccountModal` / `OnboardingChat` / `ClearDataModal` and **never renders them** — sidebar clicks set state that drives no UI. The Canvas page has no profile access at all.
- Profile data model piggybacks on PhD-era fields (`academicStage` stores knowledge level, `researchArea` stores timezone).
- Canvas **Insights** = hardcoded demo data with a stubbed "refresh"; **Workspace** and **Documents** persist only to browser localStorage (lost across devices), despite a server-side canvas API existing.
- **Dockerfile COPYs `phd_config.yaml` / `undergrad_config.yaml`, which were deleted** — fresh builds fail.
- Jerry persona YAML has factual drift vs the approved bio (calls Semu his *grandfather*, wrong dates, present-tense Microsoft employment).
- Orchestrator clarification path falls back to a crude keyword list; no use of profile in routing.
- `ProviderDropdown` exists but is not mounted; account deletion doesn't remove profile/onboarding rows; README describes a MongoDB setup that no longer exists.
- Naming debt everywhere: `phd-advisor-frontend/`, `phd_canvas`, "methodologist/theorist" references in RAG instructions.

---

## 3. Architecture decisions

1. **Keep the stack** (FastAPI + React + SQLite + single Docker image). It's proven on HF Spaces and the persistence/LLM layers are sound. No framework migration.
2. **Retire PhD naming debt early**: rename `phd-advisor-frontend/` → `frontend/`, `phd_canvas` → `canvas`/`workspace`, purge PhD references from prompts, README, and RAG instructions. Done first so all new work lands on clean names.
3. **New data model for user knowledge** (new SQLite tables via the existing shim):
   - `user_facts` — one row per fact: `category` (person / organization / needs / preferences), `key`, `value`, `source` (**stated** | **inferred**), `confidence`, `evidence` (message reference), timestamps. Stated and inferred facts are stored separately as required, and both are user-visible and editable.
   - `user_summaries` — the two generated summaries (`short` for ≤25B Neon models, `long` for large models) + generation metadata.
   - `goal_tracks`, `track_items`, `assessments` — the progress-path engine (§7).
4. **Config-driven everything** (per reuse guidelines): summaries' token budgets, model context limits, persona roster, track definitions, and intake chips all live in `cybersecurity_config.yaml` / persona YAMLs / new `tracks/*.yaml` — no hard-coded values.
5. **Dev experience**: docker-compose `dev` profile with `uvicorn --reload` + CRA dev server (hot reload both sides); container naming `cybersecurity-panel-dev-cursor-<date>`; BuildKit cache mounts already present, keep them. Secrets from `C:\Users\dream\.secrets\shared.env` (loader already supports `SHARED_ENV`).

---

## 4. User knowledge system (the core new capability)

### 4.1 Two-source profile
- **Stated profile**: what the user explicitly provides — via the profile editor, onboarding chat, or direct statements ("I'm the IT manager at a 200-person clinic"). Direct statements in chat are extracted and saved as `source=stated`.
- **Inferred profile**: after **every user message**, a background extraction pass (small/cheap model — Neon vLLM) infers facts: knowledge level from vocabulary, role, org type, urgency, tools mentioned, emotional state, goals. Saved as `source=inferred` with confidence + the message it came from. Never blocks the chat response (fire-and-forget task).
- **User visibility & control**: a "What we know about you" view with two clearly labeled sections (Things you told us / Things we noticed), each fact editable, confirmable (promotes inferred → stated), or deletable. This is both the trust feature Clary raised ("people don't want to give away their profile") and a differentiator.

### 4.2 Dual user summaries
- `short` summary (~150 tokens): for the Neon ~25B models — the essentials: who they are, org, maturity level, current goal, communication preference.
- `long` summary (~600 tokens): for large models (GPT-5.4, Gemini) — everything relevant including history highlights and open threads.
- **Regeneration triggers** (exactly as specified): at the start of each new user session, and after each completed chat **except the first one in a session**.
- **Routing rule**: the LLM client layer picks the summary by provider — vLLM/Ollama get `short`, OpenAI/Gemini get `long`. Implemented at the prompt-assembly boundary so it's automatic for any future provider (flagged `small_context: true/false` in config).

### 4.3 Context budgeting
- **Small models** (Neon vLLM, Ollama): total prompt budget **~4096 tokens** (configurable) = persona prompt + short summary + rolling conversation summary + most recent turns + current message. The existing `chat_summary.py` summarizer is upgraded to maintain a rolling summary that compresses older turns as the budget tightens.
- **Large models**: full conversation history + long summary, no summarization.

---

## 5. Orchestrator & conversation intelligence

1. **Profile-aware routing**: the orchestrator's expert-ranking prompt includes the user summary, so expert selection reflects who the user is (an executive asking about "risk" gets the compliance/strategy experts; a student gets the mentor).
2. **Intelligent follow-ups**: replace the canned `clarification_questions` list with generated follow-ups that use conversation context + user summary — modeled on Jerry's intake behavior ("Is the review internal or external? What's your role in it?").
3. **Give-and-take rule** (from the notes): the panel never interrogates. Every clarifying question is preceded by useful information — "answer what you can, then ask the one most valuable follow-up." Enforced in the orchestrator/persona prompt contracts.
4. **Adaptive depth**: response register (plain-language vs technical) driven by the inferred knowledge level in the summary; beginners get no unexplained jargon, experts get full technical vocabulary (Jerry's tailoring principle).
5. **Urgency detection**: triage-mode messages ("I think I've been hacked") short-circuit to a first-steps checklist from the incident expert before any profiling questions.

---

## 6. Intake & onboarding redesign

- **Opening screen** (post-login, first session): Jerry's greeting — *"You've contacted me today — what can I help you with in cybersecurity?"* — with 3–4 tappable chips matching top question categories (research-backed: "I think I've been hacked", "Prepare for an audit/review", "Secure my business", "Grow my security career") **plus a free-text box** (the "blank fill-in" from the notes). Chips are context-aware and change with user type once known.
- **Progressive profiling, not forms**: no up-front questionnaire. Profile fills from conversation. The optional **capability check-off screen** (Jerry's maturity checklist idea) exists but is skippable — users who prefer a "situation profile" just talk, per Richard's point.
- **Give info before asking**: the first response always delivers value before the first follow-up question.
- UX patterns per current best practice: ≤4 starter chips, follow-up chips above the input bar, streaming with "what the panel is doing" indicators, progressive disclosure (summary first, expand for detail), no autoscroll-to-bottom on long streamed answers.

---

## 7. Progress path ("Security Journey")

Replaces the fake Insights page as the app's second pillar. A user picks (or is guided to) a **track**:

| Track | Engine | Audience |
|---|---|---|
| **ITIL Maturity Model** (Jerry's favorite) | 5 levels: Initial → Managed → Defined → Quantitative → Optimizing | Organizations |
| NIST CSF 2.0 | 6 functions (Govern/Identify/Protect/Detect/Respond/Recover) × 4 tiers, Current vs Target profile | Organizations |
| CIS Controls IG1→IG3 | Concrete checkable safeguards — the checklist engine | SMB especially |
| Certification paths | Security+ → CySA+ → CISSP etc., study milestones | Individuals |
| Personal Digital Security | Passwords/MFA → backups → device hygiene → monitoring | Individuals |
| **Custom goal** | Mapped out with the panel's help ("internal assessment", "pass our review in Q4") | Anyone |

Mechanics:
- Headline **progress bar** (level + % within level) on the Journey page and a compact version in the chat header.
- Per-function/domain **radar or segmented bars** (NIST-style Current vs Target).
- Items check off three ways: user checks manually, the optional assessment wizard, or **the panel proposes a check-off when a conversation demonstrates completion** (user confirms).
- **Re-assessment trend** ("you moved from Managed to Defined in Respond") mirroring ITIL's repeat-assessment reporting.
- Light gamification: easy early wins ("Enable MFA" = instant progress), milestone celebrations, a weekly security check-in cadence — no anxiety-inducing daily streaks.
- Track definitions are data (`tracks/*.yaml`), so Jerry can supply/edit checklists without code changes.

---

## 8. Pages restructure

| Current | New | Content |
|---|---|---|
| Chat | **Chat** (primary) | Redesigned panel chat: intake chips, expert cards, follow-up chips, profile-aware suggestions |
| Insights (fake) | **Journey** | Progress path above; panel-generated insights tied to the user's actual track & chats (real `/api` persistence) |
| Workspace (localStorage) | **Workspace** (server-persisted, curated) | Cyber-relevant widgets only: incident checklist, risk register, asset inventory notes, policy drafts kanban; drop PhD widgets; persist via the existing canvas API |
| Documents (localStorage drafts) | **Documents** | Unified: uploaded reference docs (RAG) + generated artifacts (policies, audit-evidence lists, board summaries) with server persistence and export |
| — | **Profile** ("About you") | Stated + inferred facts, summaries preview, edit/confirm/delete, clear-data controls |

---

## 9. Expert panel roster

**AI Jerry Huaute — lead advisor (required).** Replace the YAML prompt with the approved canonical persona prompt (father Semu, correct dates/tenses, CISSP signature, communication style, sample responses). Jerry opens conversations, owns the intake, and is always among the responders by default.

**Revised existing experts** (prompts rewritten for the three-legged model, give-and-take rule, adaptive register, and Compact-Markdown contract):
1. **Incident Responder** — expanded to cover personal triage ("was I hacked", sextortion/scam validation) *and* business IR (notification order, evidence preservation, ransom decisions). Covers the highest-volume question categories.
2. **Compliance & Audit Advisor** — SOC 2 / ISO 27001 / NIST / CMMC / HIPAA; audit evidence expectations; security-questionnaire help.
3. **Security Architect** — Zero Trust, cloud, IAM/MFA rollouts, hardening.
4. **Threat Modeler** — STRIDE/ATT&CK; also powers the role-playing/tabletop-exercise capability (from the notes: "role playing bot for situation analysis").
5. **Career Mentor** — merged with Jerry's mentoring instinct kept distinct: this persona handles cert/interview mechanics; Jerry handles wisdom/encouragement.

**New experts (proposed):**
6. **Small Business Security Advisor** — the "Geek Squad" leg: minimum viable security stack, tool selection (password managers, EDR vs AV, backups), plain language, budget-aware. Forum research shows this audience is huge and underserved.
7. **AI Security & Technology Strategist** — helps C-level users understand and safely adopt AI (per the notes: "making AI more understandable… a productivity assist rather than taking their job"); OWASP GenAI LLM Top 10, NIST Cyber AI Profile focus areas (Secure / Defend / Thwart), overcoming resistance to change.
8. *(Optional, decide later)* **Privacy & Data Protection Advisor** — GDPR/CCPA, data handling, breach disclosure duties. Could fold into Compliance initially.

Roster stays at 7–8: enough diversity without decision paralysis; orchestrator typically surfaces top 2–3 per message.

---

## 10. Tools (new capabilities)

**Required (per project guidelines):**
- **API/model health pre-check** — on app load and on demand, the backend probes every configured provider using the real request path with a tiny prompt ("Reply with the single word: OK"); classifies online / unavailable / error; non-online models are removed from the selectable list (fail closed per model; fail open only if the whole check fails); a Settings → **Model Status** modal lists statuses with first ~200 chars of errors and a refresh control. Secrets stay server-side.

**High-value additions (recommended):**
- **Curated knowledge base (RAG)** — pre-seed ChromaDB with Jerry's approved documents (NIST IR 8596 Cyber AI Profile, OWASP GenAI LLM Top 10, OWASP secure-MCP guide, CIS/NIST framework summaries) so advisors cite real sources. Extensible with Jerry's own checklists/how-tos.
- **CVE / NVD / CISA KEV lookup** — live vulnerability answers ("is CVE-2026-XXXX being exploited?").
- **Have I Been Pwned breach check** — directly serves the #1 individual question category.
- **Phishing/scam analyzer** — paste an email/text; structured verdict + recommended actions (sextortion pattern gets a canned, reassuring flow).
- **Maturity assessment wizard** — the interactive intake for the Journey tracks.
- **Document/policy generator** — templates (AUP, IR plan, access policy) filled from the user's profile; exports via existing TXT/PDF/DOCX pipeline.
- **Web search tool** for advisors (current-events questions), gated per-persona.

**Later / discuss:** IP-based org enrichment (from the transcript) — technically feasible but privacy-sensitive; if used, disclose transparently in the profile view. Jerry's data-flow/monitoring open-source tool list — integrate as a Workspace resource page when he delivers it.

---

## 11. UI/UX overhaul

- **Design system**: professional security aesthetic — deep slate + teal (Jerry's `#0F766E`), high-contrast light/dark themes, consistent card/chip/modal components, subtle motion (reduced-motion respected). Rule of 3–4 choices per screen (Jerry's "don't make it busy" principle).
- **Responsive, three layouts**: phone (<768px: full-screen chat, bottom-sheet modals, hamburger nav, composer docked above keyboard), tablet (768–1100px: collapsible rail), desktop. Tap targets ≥44px. Tested on Safari/iOS, Chrome/Android, Edge/Windows (manual matrix + responsive automated checks).
- **Chat presentation**: expert avatars/colors, one-line "Thought" summary with expandable detail, follow-up chips, copy/save/export on every artifact, streaming status ("Jerry is reviewing your question…").
- **Engagement**: Journey progress visible in header; session-start "welcome back" referencing the user's goal; suggested next actions after each chat.
- App-level security posture honors OWASP LLM Top 10: prompt-injection hardening in system prompts, output handling, no secrets client-side — credibility matters for a security product.

---

## 12. Hygiene & infrastructure fixes

- Fix Dockerfile (remove deleted-YAML COPYs) — **build is currently broken**.
- Mount `ProviderDropdown` (or fold provider choice into Settings with Model Status).
- Account deletion also purges `user_facts`, `user_profiles`, `user_summaries`, onboarding rows.
- Fix `SettingsModal` field-name mismatch vs `PATCH /auth/me`; consolidate with `AccountModal`.
- Rewrite README (SQLite not Mongo, real advisor list, HF Spaces + local dev instructions).
- Remove dead code: `seamless_orchestrator.py` (PhD-era), `OldMessageBubble.js`, stale `scripts/patch_*` files targeting other repos.
- **Update the User Guide** (`src/data/userGuide.js`) — last step, covering all new features: intake, profile & inferred info, Journey, tools, Model Status.

---

## 13. Execution phases

Executed with Cursor multitasking + subagents on cheaper/faster models where suitable; each phase tested before the next; work lands on `dev-cursor`, PRs from `FEAT_*` branches.

| Phase | Scope | Depends on |
|---|---|---|
| **0. Baseline & hygiene** | Snapshot on `origin/dev-cursor` (emails rewritten to noreply); Dockerfile fix; rename/purge PhD debt; dev hot-reload compose; README | — |
| **1. Profile foundation** | Render profile UI; new `user_facts`/`user_summaries` schema; Profile page (stated+inferred views); clean field mapping | 0 |
| **2. Knowledge engine** | Inference pass per message; dual summaries + regeneration triggers; context budgeting (4096 small / full large); summary→provider routing | 1 |
| **3. Conversation intelligence** | Orchestrator profile-aware routing; generated follow-ups; give-and-take + adaptive register prompt contracts; intake flow & chips | 2 |
| **4. Panel roster** | Canonical Jerry prompt; revise 5 experts; add SMB advisor + AI Security strategist | 0 (parallel w/ 2–3) |
| **5. Journey & pages** | Track engine + YAML tracks; Journey page w/ progress bar & trend; Workspace/Documents server persistence & curation | 1 |
| **6. Tools** | Model health pre-check + Model Status modal (early — it's required); RAG seeding; HIBP; CVE lookup; phishing analyzer; doc generator | 2 |
| **7. UI overhaul** | Design system, responsive layouts, chat presentation, engagement features | 3, 5 |
| **8. Ship** | User Guide update; full test pass (backend pytest, frontend RTL, device matrix); Docker build; HF push via `hf` CLI; CHANGELOG | all |

---

## 14. Who does what

**I can do:** everything in Phases 0–8 (code, tests, Docker, HF upload via `hf` CLI, docs), plus the snapshot push to `dev-cursor` once unblocked.

**You need to:**
1. **Now:** temporarily uncheck "Block command line pushes that expose my email" at github.com/settings/emails so I can push the pristine baseline (or approve history rewrite with your noreply email — hashes change).
2. Create/confirm the `main` branch on the new repo (I'll give you the exact command), and set HF Space secrets when we deploy (`JWT_SECRET_KEY`, `VLLM_API_KEY`/`HANA_*`, `OPENAI_API_KEY`, `GEMINI_API_KEY`).
3. **Decisions to review in this plan:** expert roster (§9 — especially the two new personas and whether Privacy gets its own advisor), track list (§7), page structure (§8), and whether IP-based org enrichment is in or out (§10).
4. From Jerry: his checklists/how-tos for the ITIL track content, his open-source data-flow tool list, and any color/branding preferences.
