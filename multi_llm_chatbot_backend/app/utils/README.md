# `app/utils` – Utility Modules for Summarization, Export, and Embeddings

This directory includes reusable tools that support the backend application with:

- Chat summarization for display/export
- Document extraction and cleanup
- File export to TXT, DOCX, and PDF formats
- File upload validation
- Persona-specific vector DB with ChromaDB

These modules are loosely coupled and used across core routes, RAG logic, and export endpoints.

---

## `chat_summary.py` – Conversation Summarization

This module provides summarization of past conversations using the LLM client.

### Key Functions

- `generate_summary_from_messages(messages, llm, max_tokens)` – Generates a formatted, bullet-style summary
- `format_summary_for_text_export(summary_text)` – Cleans summary for export to PDF/DOCX/TXT
- `parse_summary_to_blocks(summary_text)` – Converts summary to structured blocks (headings, lists, paragraphs)

### Format Guidelines

Summaries follow a markdown-style format with:
- `**Section Name:**` for headings
- `* Bullet Points` for insights and recommendations
- Auto-trimming and line breaks for export formatting

---

## `chroma_client.py` – Persona-Specific Knowledge Store

A minimal ChromaDB wrapper used to store and query persona-specific documents or embeddings.

### Functions

- `add_persona_doc(text, persona, doc_id)` – Add a new chunk/document for a persona
- `query_persona_knowledge(query, persona)` – Query ChromaDB for a persona-specific response

### Notes

- Uses `./chroma_storage` as the default persistent path
- Uses the local embedding model via `get_embedding()` from `embedding_client.py`

---

## `document_extractor.py` – File Text Extraction

Supports extracting raw text from uploaded documents.

### Supported Formats

| Format | Content Type |
|--------|---------------|
| PDF    | `application/pdf` |
| DOCX   | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| TXT    | `text/plain` |

### Key Function

```python
extract_text_from_file(file_bytes: bytes, content_type: str) -> str
```

Uses:
- `PyPDF2` for PDFs
- `docx2txt` for Word documents (via temp file)
- UTF-8 decoding for plain text

---

## `file_export.py` – Export Chat & Summaries

Exports content (chat logs or summaries) to the following formats:
- `.txt`
- `.docx` (Word)
- `.pdf` (ReportLab)

### Key Functions

- `export_chat_as_file(content, format)` – Unified export method (calls generate_*)  
- `prepare_export_response()` – Returns a `StreamingResponse` with correct content-disposition

### Formatting Functions

- `generate_txt_file()` – Simple UTF-8 stream
- `generate_docx_file()` – Paragraph-based Word file using `python-docx`
- `generate_pdf_file()` – Uses ReportLab’s Platypus for chat-style layout
- `generate_pdf_file_from_blocks()` – Used for structured summaries (heading, lists, etc.)

All formats apply automatic cleanup and styling via:
- `_clean_text_for_pdf()` and `_render_rich_text()`

---

## `file_limits.py` – Upload Size Checks

Used to prevent users from uploading excessively large files in a session.

### Configurable Limit

```python
MAX_TOTAL_UPLOAD_MB = 10
```

### Function

- `is_within_upload_limit(session_id, new_file_bytes, session_context)` – Returns `True` if upload is within session cap

Used by routes handling document uploads.

---

## Dependencies

These modules are used in:

| Module | Depends On |
|--------|------------|
| `rag_manager.py` | `document_extractor`, `file_limits` |
| `chat_summary.py` | `llm_client` |
| `routes/documents.py` | `document_extractor`, `file_limits` |
| `routes/export.py` | `file_export`, `chat_summary` |

---

## Example Workflow

```text
Upload File → document_extractor.py → raw text
            ↓
      file_limits.py → check quota

Chat History → chat_summary.py → formatted summary
                          ↓
                  file_export.py → TXT, DOCX, PDF

Persona Notes → chroma_client.py → embedded in ChromaDB
```