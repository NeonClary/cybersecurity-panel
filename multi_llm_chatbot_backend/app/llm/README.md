# `app/llm` – LLM Integration Layer

This module abstracts and implements communication with **local** and **cloud-based** large language models (LLMs) via interchangeable client wrappers.

It defines:
- A common interface for all LLM clients (`LLMClient`)
- A wrapper for Google Gemini API (`ImprovedGeminiClient`)
- A wrapper for Ollama local models (`ImprovedOllamaClient`)
- A sentence transformer embedding model (`embedding_client.py`)

---

## Abstract Base – `llm_client.py`

This file defines the **contract** that all LLM clients must follow.

### `class LLMClient (ABC)`

An abstract base class using Python’s `abc` module.

```python
@abstractmethod
async def generate(system_prompt: str, context: List[dict], temperature: float, max_tokens: int) -> str
```

Every model wrapper must implement this coroutine to generate a response given:
- A system prompt (persona instructions)
- A user/system message context (list of `{role, content}` dicts)
- A temperature (float 0.0–1.0, typically scaled from 0–10)
- A token limit (integer)

---

## Gemini Client – `improved_gemini_client.py`

### Overview

- Communicates with **Google’s Gemini API** via `httpx`
- Dynamically injects the `system_prompt` into the context using `context_manager`
- Uses environment variables for API key and model name (`GEMINI_API_KEY`, `GEMINI_MODEL`)

### Key Features

| Feature | Description |
|--------|-------------|
| Context Prep | Uses `context_manager.prepare_context_for_llm()` to optimize message length |
| Endpoint | `https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent` |
| Content Format | Gemini expects JSON-formatted `contents`, not string prompts |
| Safety Settings | Blocks harmful or explicit content categories |
| Fallback Logic | Returns user-friendly error messages on bad or empty responses |
| Token Limit | `maxOutputTokens` passed explicitly |

### SafetyConfig JSON Example

```json
"safetySettings": [
  {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
  {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
]
```

### Differences from Ollama
- Requires an API key and runs over HTTPS
- Parses deeply nested JSON structures (candidates → content → parts)
- Strict token and safety controls
- More structured response format

---

## Ollama Client – `improved_ollama_client.py`

### Overview

- Interfaces with a **local Ollama model server** (`http://localhost:11434`)
- Sends prompts as raw formatted strings (not JSON "messages")
- Uses `context_manager` to prepare prompt text

### Key Features

| Feature | Description |
|--------|-------------|
| Endpoint | `/api/generate` |
| Payload | Flat prompt string + generation config |
| Cleansing | Strips verbose, inconsistent prefixes or filler |
| Quality Filter | Removes overly verbose or vague responses |
| Robust | Recovers from connection and timeout failures |

### Prompt Payload Example

```json
{
  "model": "llama3.2:1b",
  "prompt": "System: You are a helpful advisor...\nUser: What is...",
  "stream": false,
  "options": {
    "temperature": 0.4,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 300,
    "repeat_penalty": 1.1,
    "stop": ["Student:", "User:", "Question:"]
  }
}
```

### Differences from Gemini

| Area | Gemini | Ollama |
|------|--------|--------|
| Hosting | Cloud API | Local server |
| Format | JSON "messages" | Raw string prompt |
| Safety Filters | Yes | No |
| Token Control | `maxOutputTokens` | `num_predict` |
| Output | Structured parts | Single `response` string |
| Response Cleaning | Minimal | Aggressively stripped of fluff |
| Performance | High-quality, slower | Fast & offline |

---

## Embedding Model – `embedding_client.py`

### Purpose

Provides embedding vectors (used for semantic similarity and document retrieval) using `sentence-transformers`.

### Uses:
- Model: `all-MiniLM-L6-v2` (lightweight + performant)
- Library: `sentence-transformers`
- Function: `get_embedding(text: str) -> List[float]`

```python
embedding = get_embedding("example sentence")
```

### Notes
- This module does **not** use Gemini embeddings (for cost and simplicity)
- Can be upgraded later to use Gemini’s `embedding` endpoint or Ollama-based models with vector support

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GEMINI_API_KEY` | API key for Google Gemini | `AIzz123...` |
| `GEMINI_MODEL` | Default Gemini model name | `gemini-2.0-flash` |
| `OLLAMA_BASE_URL` | Local server base URL | `http://localhost:11434` |

---

## Context Management Integration

Both clients use:

```python
context_window = context_manager.prepare_context_for_llm(...)
```

This ensures that:
- Prompt fits within model limits
- Truncation metadata is logged/debugged
- Messages are pre-formatted or optimized per provider

---

## Error Handling

All clients log internal issues and fallback to graceful responses. Each client handles:
- Timeouts (`httpx.TimeoutException`)
- API errors (`httpx.HTTPStatusError`, bad payloads)
- Unexpected failures (fallback strings are returned)

---