# `app/core` – Application Core Logic

Central logic of the cybersecurity advisor panel: orchestration, personas,
context management, document RAG, sessions, user knowledge, and startup.

## Modules

| Module | Responsibility |
|--------|----------------|
| `auth.py` | Authentication (JWT, password hashing, user resolution) |
| `bootstrap.py` | Startup: provider selection, LLM clients, persona registration |
| `context_manager.py` | Token estimation and context windowing |
| `db.py` | SQLite persistence behind a Mongo-shaped async shim |
| `improved_orchestrator.py` | Routing engine: urgency + advisor ranking, persona responses, RAG context, follow-ups |
| `rag_manager.py` | ChromaDB document RAG: chunking, storage, semantic search |
| `session_manager.py` | In-memory chat session lifecycle with RAG hooks |
| `user_knowledge.py` | Stated/inferred fact store, dual user summaries, regeneration triggers |
| `model_status.py` | Provider health probes for Model Status |
| `tracks_loader.py` | Security Journey track definitions from `tracks/*.yaml` |
| `guest_demo.py` | Guest sample data seeding and cleanup |

## `improved_orchestrator.py`

The main message routing engine, used by `/chat-stream` and `/reply-to-advisor`.

- `route_message()` – one LLM call classifying urgency (`triage` / `advisory`
  / `program`) and ranking advisors with the user profile in the prompt.
  Post-processing guarantees the required lead advisor (config
  `orchestrator.required_advisor`, Jerry) is on the panel and pulls the
  triage advisor (`orchestrator.triage_advisor`) to the front on incidents.
- `generate_single_persona_response()` – persona response with document-aware
  context.
- `_build_enhanced_context_for_persona()` – system prompt + user summary +
  urgency note + conversation history. Small-context providers (vLLM/Ollama)
  are capped by `user_knowledge.small_model_context_budget` (4096 by
  default); long conversations are summarized with the recent turns kept
  verbatim.
- `generate_followups()` – 3 generated follow-up chips after each panel
  response.
- `needs_clarification_improved()` / `generate_contextual_clarification()` –
  LLM-driven clarification with config fallback.

## Flow

```text
User input → route_message (urgency + advisors)
           → per advisor: RAG retrieval → context build → persona.respond
           → follow-up chips → user-summary regeneration (background)
```
