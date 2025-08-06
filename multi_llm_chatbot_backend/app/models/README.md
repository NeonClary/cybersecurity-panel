# `app/models` – Data Models & Persona Configuration

This module defines the **core data structures** for users, chat sessions, and AI advisor personas in the Multi-LLM Chatbot Backend.

It plays a foundational role in ensuring that:
- User data and session state are **structured, validated, and serializable**
- Persona behavior is **configurable, injectable, and extensible**

---

## Persona Model (`persona.py`)

### `class Persona`

Represents a single AI advisor with its own personality, tone, and domain of expertise.

| Attribute       | Description |
|----------------|-------------|
| `id`           | Unique identifier for the persona |
| `name`         | Human-readable display name |
| `system_prompt`| The persona’s default LLM instruction |
| `llm`          | Instance of the LLM client (Gemini/Ollama) |
| `temperature`  | Controls creativity level (0–10 scale, converted to 0.0–1.0 internally) |

### `respond()` method

This asynchronous method generates a persona-specific reply using the provided context and desired `response_length` (short, medium, long). It uses a **system prompt + user messages** + length-based instructions.

```python
await persona.respond(context=messages, response_length="medium")
```

---

## Persona Registry (`default_personas.py`)

Defines and registers **all built-in personas** using detailed `system_prompt` templates and metadata.

> These prompts define the tone, response style, formatting rules, document behavior, and epistemological approach of each advisor.

### Available Personas

- `methodologist`: Research methods and design expert  
- `theorist`: Theoretical frameworks and philosophy of science  
- `pragmatist`: Action-oriented coach with a focus on task execution  
- `socratic`: Socratic questioning mentor  
- `motivator`: Psychology-focused coach to build momentum  
- `critic`: Constructive reviewer with sharp academic critique  
- `storyteller`: Communication and storytelling specialist  
- `minimalist`: Minimal guidance, maximum clarity  
- `visionary`: Long-term strategy and innovation  
- `empathetic`: Emotionally aware advisor for mental health & motivation  

### Registry Functions

| Function | Description |
|---------|-------------|
| `get_default_personas(llm)` | Returns a list of `Persona` instances with LLM injected |
| `get_default_persona_prompt(pid)` | Returns only the `system_prompt` of a persona |
| `is_valid_persona_id(pid)` | Checks if ID exists in registry |
| `list_available_personas()` | Lists all persona IDs |

---

## User & Session Models (`user.py`)

### `UserCreate` / `UserLogin`

Pydantic models for request payloads during signup/login.

### `User`

Persistent user object, mapped to MongoDB using `_id` aliasing.

| Field | Description |
|-------|-------------|
| `id` (`_id`) | MongoDB ObjectId |
| `email`, `hashed_password` | Auth fields |
| `academicStage`, `researchArea` | Optional metadata |
| `created_at`, `last_login` | Timestamps |
| `is_active` | Soft-deletion or block flag |

### `UserResponse`

Serialized user profile returned to frontend after login/token validation.

---

### `ChatSession`

Stores a **single multi-turn conversation**. Used for RAG context, memory, and export.

| Field | Description |
|-------|-------------|
| `id` | MongoDB `_id` |
| `user_id` | Owner user’s ID |
| `title` | Human-readable title |
| `messages` | List of exchanged messages |
| `created_at`, `updated_at` | Session lifecycle tracking |
| `is_active` | Whether it is a deleted/inactive session |

### `ChatSessionResponse`

Returned when listing past sessions (lightweight response).

---

### `Token`

Used as the unified login response structure:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": { ... }
}
```

---

## Design Principles

- All models are **fully compatible with FastAPI + Pydantic**
- MongoDB integration uses `bson.ObjectId` support and aliases
- Persona logic is **decoupled** from orchestration — easy to extend
- System prompts are rich, structured, and **frontend-format aware** (markdown rules enforced)

---

## Next Steps

This module is used by:

- `core/improved_orchestrator.py` – Persona routing  
- `routes/chat.py` – Sequential chat + replies  
- `auth.py` – Token generation and validation  
- `documents.py` – Document-enhanced message generation  

> Add a new persona? Just extend `DEFAULT_PERSONAS` and restart the backend.