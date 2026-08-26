from typing import Dict, List, Optional, Any
from app.models.persona import Persona, _finalize_compact, panel_lens_reminder
from app.core.session_manager import ConversationContext, get_session_manager
from app.core.context_manager import get_context_manager
from app.core.rag_manager import get_rag_manager
from app.config import get_settings
from app.core.user_context import (
    RECENCY_OVER_GOAL_RULE,
    conversation_first_clarification_fallback,
    count_user_messages,
    format_latest_topic,
    format_recent_conversation,
    goal_aware_clarification_fallback,
    has_stated_goal_or_summary,
    history_disambiguates,
    is_truly_ambiguous_followup,
    looks_like_anaphora,
    recent_topic_competes_with_goal,
    refers_to_known_goal,
)
from app.llm.llm_client import LLMClient, ToolCallResult
from app.tools import get_tool_definitions, get_tool_executor
from app.utils.chat_summary import generate_conversation_context_summary

import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

# Cheap fallback signal for active-incident (triage) messages, used only when
# the LLM routing call fails or returns garbage.
_TRIAGE_FALLBACK = re.compile(
    r"(hacked|hack into|compromis\w*|breach\w*|ransomware|ransom note|"
    r"malware|infected|virus on|stolen|sextortion|extort\w*|scammed|"
    r"locked out|unauthorized (access|login|charge)|suspicious (login|activity)|"
    r"data leak|account.{0,20}taken over)",
    re.IGNORECASE,
)

VALID_URGENCIES = ("triage", "advisory", "program")

# YAML tool keys → registered function names (see app.tools).
_YAML_TOOL_NAME_MAP = {
    "current_datetime": "get_current_datetime",
}


class ImprovedChatOrchestrator:
    """
    Enhanced orchestrator with document awareness and improved context handling
    """
    
    def __init__(self, llm_client: LLMClient = None):
        self.personas: Dict[str, Persona] = {}
        self.llm_client = llm_client
        self.session_manager = get_session_manager()
        self.context_manager = get_context_manager()
    
    def register_persona(self, persona: Persona):
        """Register a persona with the orchestrator"""
        self.personas[persona.id] = persona
        logger.info(f"Registered persona: {persona.id} ({persona.name})")
    
    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """Get a specific persona"""
        return self.personas.get(persona_id)
    
    def list_personas(self) -> List[str]:
        """List all available persona IDs"""
        return list(self.personas.keys())

    async def get_tool_response(self, user_message: str) -> ToolCallResult:
        """Check whether a tool can handle *user_message*.

        If tools are disabled in config, no LLM client is available, or the
        model decides no tool is needed, returns
        ``ToolCallResult(used_tool=False)``.  Otherwise executes the tool and
        returns the grounded response with ``used_tool=True``.
        """
        if self.llm_client is None:
            return ToolCallResult(text="", used_tool=False)

        tools_enabled = self._resolve_enabled_tool_names()

        if not tools_enabled:
            return ToolCallResult(text="", used_tool=False)

        # Datetime is injected locally; do not spend an LLM round-trip on it.
        if set(tools_enabled) <= {"get_current_datetime"}:
            return ToolCallResult(text="", used_tool=False)

        tool_definitions = get_tool_definitions(enabled=tools_enabled)
        tool_executor = get_tool_executor(enabled=tools_enabled)

        if not tool_definitions:
            return ToolCallResult(text="", used_tool=False)

        system_prompt = (
            "You are a helpful cybersecurity assistant with access to external tools. "
            "Use the available tools when the user's question can be answered by one of them. "
            "Call get_current_datetime when the user asks about today, deadlines, timelines, "
            "schedules, incident timing, or when accurate date/time context would improve "
            "your guidance — then weave the result into your answer. "
            "If no tool is relevant, respond with a brief text answer. "
            "Format your responses using markdown."
        )

        return await self.llm_client.generate_with_tools(
            system_prompt=system_prompt,
            user_message=user_message,
            tool_definitions=tool_definitions,
            tool_executor=tool_executor,
        )

    def _resolve_enabled_tool_names(self) -> List[str]:
        """Map config YAML keys to registered tool function names."""
        from app.tools import list_registered_tools

        registered = set(list_registered_tools())
        resolved: List[str] = []
        for raw in get_settings().tools.get_enabled_names():
            mapped = _YAML_TOOL_NAME_MAP.get(raw, raw)
            if mapped in registered and mapped not in resolved:
                resolved.append(mapped)
        return resolved

    async def attach_datetime_context(self, session: ConversationContext) -> None:
        """Stamp current date/time onto the session without an LLM call."""
        if "get_current_datetime" not in self._resolve_enabled_tool_names():
            return
        try:
            from app.tools.current_datetime import execute

            info = await execute()
            session.datetime_context = (
                f"CURRENT DATETIME: {info.get('local_weekday')} {info.get('local_date')} "
                f"{info.get('local_time')} {info.get('local_timezone')} "
                f"(UTC {info.get('utc_iso')})"
            )
        except Exception as exc:
            logger.warning("Could not attach datetime context: %s", exc)

    def needs_clarification(self, session: ConversationContext, user_input: str) -> bool:
        """Public alias for the rule-based clarification heuristic."""
        return self._heuristic_needs_clarification(session, user_input)

    def _heuristic_needs_clarification(self, session: ConversationContext, user_input: str) -> bool:
        """
        Determine if the user input needs clarification.
        Patterns and keywords are driven by config.yaml → orchestrator section.
        """
        # TODO: This method should be refactored to be more generic instead of
        # relying on hard-coded regex and keywords.

        # If this is not the first message, probably don't need clarification
        user_messages = [msg for msg in session.messages if msg.get('role') == 'user']
        if len(user_messages) > 1:
            logger.info(f"Skipping clarification: session already has {len(user_messages)} user message(s)")
            return False

        # Check for vague patterns - FIXED to handle "I am" vs "I'm"
        vague_patterns = [
            r"^(help|advice|guidance|assistance)$",
            r"i'?m (stuck|lost|confused|not sure)",  # matches "I'm confused"
            r"i am (stuck|lost|confused|not sure)",  # matches "I am confused" 
            r"(what should i|how do i|where do i start)",
            r"i need (help|advice|guidance)",
            r"(any|some) (advice|suggestions|ideas)",
            r"don'?t know (what|how|where)",
            r"(stuck|struggling) with",
            r"unsure about"
        ]

        orch_cfg = get_settings().orchestrator
        user_lower = user_input.lower().strip()
        word_count = len(user_input.split())

        logger.info(f"Checking clarification for: {user_input} ({word_count} words)")

        has_specific_keywords = any(
            keyword in user_lower for keyword in orch_cfg.specific_keywords
        )
        if has_specific_keywords:
            logger.info("NO CLARIFICATION: input contains specific keywords")
            return False

        if word_count >= orch_cfg.min_words_without_keywords:
            logger.info(
                    f"NO CLARIFICATION: input has {word_count} words "
                    f"(>= {orch_cfg.min_words_without_keywords} threshold)")
            return False

        for pattern in vague_patterns:
            if re.search(pattern, user_lower):
                logger.info(f"CLARIFICATION TRIGGERED: pattern `{pattern}` matched `{user_input}`")
                return True

        logger.info("CLARIFICATION TRIGGERED: short input (%d words) without specific keywords", word_count)
        return True

    async def needs_clarification_improved(
        self,
        session: ConversationContext,
        user_input: str,
        user_context: str = "",
    ) -> bool:
        """
        Use an LLM call to determine whether the user's input is too vague
        to route to the advisor panel.  Falls back to the legacy rule-based
        method if the LLM call fails.
        """
        session_messages = getattr(session, "messages", None) or []
        user_msg_count = count_user_messages(session_messages)
        is_first_user_message = user_msg_count <= 1
        recent_block = format_recent_conversation(session_messages, current_input=user_input)

        session_ctx = getattr(session, "user_profile_context", "")
        if not isinstance(session_ctx, str):
            session_ctx = ""
        known_context = (user_context if isinstance(user_context, str) else "").strip() or session_ctx.strip()

        # Follow-ups are not first-message-vague. Default to no clarification
        # unless the text is empty/generic AND recent history does not already
        # name a topic the advisors can continue.
        if not is_first_user_message:
            if history_disambiguates(session_messages, user_input):
                logger.info(
                    "Skipping clarification: later-turn history already names a topic (%d user messages)",
                    user_msg_count,
                )
                return False
            if not is_truly_ambiguous_followup(user_input):
                logger.info("Skipping clarification: follow-up is not empty/generic")
                return False
            logger.info(
                "Follow-up is generic and history does not disambiguate; continuing clarification check"
            )

        if looks_like_anaphora(user_input) and history_disambiguates(session_messages, user_input):
            logger.info(
                "Skipping clarification: anaphora resolves against recent conversation (%r)",
                user_input[:120],
            )
            return False

        if has_stated_goal_or_summary(known_context) and refers_to_known_goal(user_input):
            logger.info(
                "Skipping clarification: message refers to a known goal/profile (%r)",
                user_input[:120],
            )
            return False

        # Cheap rule-based gate for first messages. Later-turn generic follow-ups
        # with no usable history skip this so the LLM can still ask a question.
        if is_first_user_message and not self._heuristic_needs_clarification(session, user_input):
            logger.info("Skipping clarification LLM: heuristic says input is specific enough")
            return False

        app_cfg = get_settings().app
        orch_cfg = get_settings().orchestrator
        advisor_descriptions = ", ".join(
            f"{p.name} ({p.id})" for p in self.personas.values()
        )
        domain_keywords = ", ".join(orch_cfg.specific_keywords)

        recency_rules = (
            f"{RECENCY_OVER_GOAL_RULE}\n"
            "- If recent turns already named a specific incident or topic, a "
            "follow-up that refers to \"the incident\" / \"that\" / a year range "
            "is CLEAR ENOUGH — do not ask whether they meant an older goal.\n"
        )

        profile_rules = ""
        if has_stated_goal_or_summary(known_context):
            profile_rules = (
                "The application already knows this user's profile, stated goal, "
                "and/or knowledge summary. Treat that as durable BACKGROUND, not "
                "as the current question when recent chat has moved on.\n"
                "- Messages that refer to \"my goal\", \"the situation I described\", "
                "\"what I shared\", \"my custom security goal\", or similar are "
                "CLEAR ENOUGH — do not ask them to restate the goal.\n"
                "- Do not treat a first message as vague merely because it omits "
                "details that are already in the profile.\n"
                "- Do not ask them to pick generic enterprise domains (GDPR, HIPAA, "
                "org architecture) when a specific goal is already known AND there "
                "is no competing recent topic.\n"
            )
        else:
            profile_rules = (
                "No usable goal or profile is on file. Truly empty/generic messages "
                "like \"help\" or \"advice\" NEED CLARIFICATION when this is the "
                "first user message and history does not already name a topic.\n"
            )

        turn_scope = (
            "latest message (this may be a follow-up, not the first message)"
            if not is_first_user_message
            else "FIRST message"
        )

        system_prompt = (
            "You are a routing classifier for an AI advisory application.\n\n"
            f"Application: {app_cfg.title} — {app_cfg.subtitle}\n"
            f"Available advisors: {advisor_descriptions}\n"
            f"Domain-relevant topics: {domain_keywords}\n\n"
            f"Your task: decide whether the user's {turn_scope} contains enough "
            "substance to send to the advisors, or whether it is too vague and "
            "requires a clarifying follow-up before the advisors can help.\n\n"
            f"{recency_rules}\n"
            f"{profile_rules}\n"
            "A message NEEDS CLARIFICATION when it:\n"
            "- Expresses confusion or uncertainty without a concrete topic "
            "(and neither recent chat nor a usable goal/profile can fill it in)\n"
            "- Is a single generic request like 'help' or 'advice' AND there is "
            "no usable goal/profile on file AND no recent topic to continue\n"
            "- Contains no identifiable subject the advisors could address, even "
            "after considering recent conversation and the known profile\n\n"
            "A message is CLEAR ENOUGH when it:\n"
            "- Mentions a specific topic, question, or problem area\n"
            "- Continues a topic the last assistant/user turns already named\n"
            "- Provides enough context for at least one advisor to respond usefully "
            "when combined with recent conversation and/or the known profile/goal\n"
            "- Even a short message is fine if the intent is unambiguous "
            "(e.g. 'explain transformers' is clear)\n"
            "- Messages mentioning domain-relevant topics are likely clear enough "
            "to route directly, even if brief\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"needs_clarification": true or false, "reason": "one sentence explanation"}'
        )

        user_prompt = f'User message: "{user_input}"'
        if recent_block:
            user_prompt += (
                "\n\n--- Recent conversation (latest last; current message omitted) ---\n"
                f"{recent_block}"
            )
        if known_context:
            user_prompt += (
                "\n\n--- Already-known user profile / goals (background only) ---\n"
                f"{known_context}"
            )

        raw = None

        try:
            llm = next(iter(self.personas.values())).llm
            raw = await llm.generate(
                system_prompt=system_prompt,
                context=[{"role": "user", "content": user_prompt}],
                temperature=0.0,
                max_tokens=128,
                response_mime_type="application/json",
            )

            parsed = json.loads(raw.strip())
            value = parsed.get("needs_clarification")
            if not isinstance(value, bool):
                raise TypeError(
                    f"needs_clarification must be a boolean, got {type(value).__name__}: {value!r}"
                )
            result = value
            reason = parsed.get("reason", "")

            logger.info(
                "LLM clarification classification: needs_clarification=%s, reason=%r, input=%r",
                result, reason, user_input,
            )
            return result

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to parse LLM classification response: %s (raw=%r)", exc, raw)
        except Exception as exc:
            logger.error("LLM classification call failed: %s", exc)

        # TODO: Evaluate if this fallback is still needed and remove if not.
        logger.warning("Falling back to rule-based clarification check")
        return self.needs_clarification(session, user_input)

    async def generate_contextual_clarification(
        self,
        user_input: str,
        user_context: str = "",
        session=None,
    ) -> Dict[str, Any]:
        """
        Use the LLM to produce a clarification question and clickable
        suggestions that are tailored to what the user actually typed.
        Falls back to the static values in config.yaml if the LLM call fails.
        """
        orch_cfg = get_settings().orchestrator
        known_context = (user_context or "").strip()
        session_messages = getattr(session, "messages", None) if session is not None else None
        recent_block = format_recent_conversation(session_messages, current_input=user_input)
        latest_topic = format_latest_topic(session_messages, current_input=user_input)
        prefer_recent = bool(recent_block) and (
            looks_like_anaphora(user_input)
            or recent_topic_competes_with_goal(session_messages, user_input, known_context)
        )

        advisor_list = ", ".join(
            f"{p.name} ({p.id})" for p in self.personas.values()
        )

        profile_instruction = ""
        if prefer_recent:
            profile_instruction = (
                f"{RECENCY_OVER_GOAL_RULE}\n"
                "The question and all 4 suggestions MUST stay on the current "
                "conversation topic (the most recent named incident/event). Do "
                "not mix in the user's original goal (e.g. account recovery) "
                "unless they are still talking about that goal.\n\n"
            )
        elif has_stated_goal_or_summary(known_context):
            profile_instruction = (
                "The user already has a stated goal and/or profile. The question "
                "and all 4 suggestions MUST be specific to that goal. Never offer "
                "generic enterprise domains (GDPR, HIPAA, SOC 2, org architecture) "
                "unless that is actually their goal.\n\n"
            )

        system_prompt = (
            "You are a helpful routing assistant. The user's message is too "
            "vague to send to the advisors. Produce a short clarifying question "
            "and exactly 4 clickable suggestion buttons the user could press.\n\n"
            f"{profile_instruction}"
            "Reply ONLY with valid JSON — no markdown, no extra text:\n"
            '{"question": "...", "suggestions": ["...", "...", "...", "..."]}\n\n'
            "Keep the question to one sentence. Each suggestion should be a "
            "complete sentence the user could send as their next message."
        )

        user_prompt = (
            f"User said: \"{user_input}\"\n"
            f"Available advisors: {advisor_list}\n"
        )
        if recent_block:
            user_prompt += (
                "\n--- Recent conversation (latest last; current message omitted) ---\n"
                f"{recent_block}\n"
            )
        if latest_topic:
            user_prompt += (
                "\n--- Current topic (resolve references against this first) ---\n"
                f"{latest_topic}\n"
            )
        if known_context:
            label = (
                "Known user profile / goals (background only; do not hijack "
                "the current topic)"
                if prefer_recent
                else "Known user profile / goals"
            )
            user_prompt += f"\n--- {label} ---\n{known_context}\n"
        user_prompt += (
            "\nGenerate a clarifying question and 4 suggestion buttons that "
            "relate to what the user said"
        )
        if prefer_recent:
            user_prompt += (
                " and the recent conversation topic — not an older stated goal "
                "they have moved on from"
            )
        elif known_context:
            user_prompt += " and their known goal/profile — not generic compliance topics"
        user_prompt += " and steer toward the advisors above."

        try:
            llm = next(iter(self.personas.values())).llm
            raw = await llm.generate(
                system_prompt=system_prompt,
                context=[{"role": "user", "content": user_prompt}],
                temperature=0.4,
                max_tokens=1024,
                response_mime_type="application/json"
            )

            cleaned = raw.strip()
            cleaned = re.sub(r"```(?:json)?", "", cleaned).strip()

            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            parsed = json.loads(cleaned)
            question = parsed.get("question", "").strip()
            suggestions = parsed.get("suggestions", [])

            if question and isinstance(suggestions, list) and len(suggestions) >= 2:
                logger.info(f"LLM clarification generated for: {user_input}")
                return {"question": question, "suggestions": suggestions[:4]}

        except Exception as e:
            logger.error(f"LLM clarification failed, using config fallback: {e}")

        if prefer_recent:
            recency_fallback = conversation_first_clarification_fallback(
                user_input, latest_topic or recent_block, known_context
            )
            if recency_fallback:
                return recency_fallback

        goal_fallback = goal_aware_clarification_fallback(known_context)
        if goal_fallback and not prefer_recent:
            return goal_fallback

        fallback_questions = orch_cfg.clarification_questions
        fallback_suggestions = orch_cfg.clarification_suggestions
        return {
            "question": fallback_questions[0],
            "suggestions": fallback_suggestions,
        }
    
    async def generate_single_persona_response(self, session, persona, response_length: str = "medium"):
        """
        Enhanced version - Generate response from a single persona with enhanced RAG integration
        """
        try:
            # Get the user's latest message for document retrieval
            user_message = ""
            try:
                user_message = session.get_latest_user_message() or ""
            except AttributeError:
                # Fallback: manually find latest user message
                for msg in reversed(session.messages):
                    if msg.get('role') == 'user':
                        user_message = msg.get('content', '')
                        break
            
            # Retrieve relevant document context using enhanced RAG
            document_context = ""
            if user_message:
                document_context = await self._retrieve_relevant_documents(
                    user_input=user_message,
                    session_id=session.session_id,
                    persona_id=persona.id,
                    session=session,
                )
            
            # Build enhanced context for the LLM
            enhanced_context = await self._build_enhanced_context_for_persona(
                session, persona, user_message, document_context
            )
            
            # Generate response with enhanced context
            response = await persona.respond(enhanced_context, response_length)
            
            # Validate and improve response quality
            if not self._is_valid_response(response, persona.id):
                logger.warning(f"Invalid response from {persona.id}, using fallback")
                response = self._get_persona_fallback(persona.id)
            
            # Track document usage for debugging
            used_documents = bool(document_context and len(document_context.strip()) > 100)
            document_chunks_used = document_context.count("[Source:") if document_context else 0
            
            return {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": response,
                "used_documents": used_documents,
                "document_chunks_used": document_chunks_used,
                "response_length": response_length,
                "context_quality": "high" if document_context else "conversation_only"
            }
            
        except Exception as e:
            logger.error(f"Error generating response for {persona.id}: {str(e)}")
            return {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": f"I apologize, but I'm having technical difficulties. {self._get_persona_fallback(persona.id)}",
                "used_documents": False,
                "document_chunks_used": 0,
                "response_length": response_length,
                "context_quality": "error"
            }

    async def iter_persona_response_stream(self, session, persona, response_length: str = "medium"):
        """Yield ``delta`` text chunks then a final ``done`` dict with metadata."""
        user_message = ""
        try:
            user_message = session.get_latest_user_message() or ""
        except AttributeError:
            for msg in reversed(session.messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

        document_context = ""
        if user_message:
            document_context = await self._retrieve_relevant_documents(
                user_input=user_message,
                session_id=session.session_id,
                persona_id=persona.id,
                session=session,
            )

        enhanced_context = await self._build_enhanced_context_for_persona(
            session, persona, user_message, document_context
        )
        used_documents = bool(document_context and len(document_context.strip()) > 100)
        document_chunks_used = document_context.count("[Source:") if document_context else 0

        pieces: List[str] = []
        try:
            async for chunk in persona.respond_stream(enhanced_context, response_length):
                if not chunk:
                    continue
                pieces.append(chunk)
                yield {"event": "delta", "text": chunk}
        except Exception as e:
            logger.error(f"Error streaming response for {persona.id}: {str(e)}")
            response = (
                f"I apologize, but I'm having technical difficulties. "
                f"{self._get_persona_fallback(persona.id)}"
            )
            yield {
                "event": "done",
                "result": {
                    "persona_id": persona.id,
                    "persona_name": persona.name,
                    "response": response,
                    "used_documents": used_documents,
                    "document_chunks_used": document_chunks_used,
                    "response_length": response_length,
                    "context_quality": "error",
                },
            }
            return

        raw = "".join(pieces)
        response = _finalize_compact(raw, response_length)
        if not self._is_valid_response(response, persona.id):
            logger.warning(f"Invalid response from {persona.id}, using fallback")
            response = self._get_persona_fallback(persona.id)

        yield {
            "event": "done",
            "result": {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": response,
                "used_documents": used_documents,
                "document_chunks_used": document_chunks_used,
                "response_length": response_length,
                "context_quality": "high" if document_context else "conversation_only",
            },
        }

    async def _retrieve_relevant_documents(
        self,
        user_input: str,
        session_id: str,
        persona_id: str = "",
        session=None,
    ) -> str:
        """
        Enhanced document retrieval with document awareness and better attribution
        """
        try:
            if session is not None and getattr(session, "_rag_empty", False):
                return ""

            # Add comprehensive logging to track session ID usage
            logger.info(f"Retrieving documents for session_id: {session_id}")
            logger.info(f"User input: {user_input[:100]}...")
            
            rag_manager = get_rag_manager()
            
            # Check what documents are available for this session with detailed logging
            doc_stats = rag_manager.get_document_stats(session_id)
            logger.info(f"Available documents for {session_id}: {doc_stats.get('total_documents', 0)} documents, {doc_stats.get('total_chunks', 0)} chunks")
            
            # Log document details for debugging
            if doc_stats.get('documents'):
                for doc in doc_stats['documents']:
                    logger.info(f"  - Document: {doc.get('filename', 'unknown')} ({doc.get('chunks', 0)} chunks)")
            
            # If no documents found and this looks like a chat session, log warning
            if doc_stats.get('total_documents', 0) == 0:
                if session_id.startswith('chat_'):
                    logger.warning(f"No documents found for chat session {session_id} - this may indicate session ID mismatch during upload")
                    
                    # Try alternative session ID formats for debugging
                    alternative_formats = [
                        session_id.replace('chat_', ''),  # Remove chat_ prefix
                        session_id,  # Keep as is
                    ]
                    
                    for alt_session_id in alternative_formats:
                        if alt_session_id != session_id:
                            alt_stats = rag_manager.get_document_stats(alt_session_id)
                            if alt_stats.get('total_documents', 0) > 0:
                                logger.warning(f"Found documents under alternative session ID {alt_session_id}: {alt_stats}")
                else:
                    logger.info(f"No documents found for new session {session_id} - this is normal for new chats")

                if session is not None:
                    session._rag_empty = True
                return ""  # No documents available
            
            # Extract document hints from user query
            document_hint = self._extract_document_hint_from_query(user_input)
            logger.info(f"Document hint extracted from query: {document_hint}")
            
            # Get persona-specific context for better retrieval
            persona_context = self._get_enhanced_persona_context_keywords(persona_id)
            
            # Search for relevant chunks with document awareness
            logger.info(f"Searching with persona context: {persona_context[:100]}...")
            relevant_chunks = rag_manager.search_documents_with_context(
                query=user_input,
                session_id=session_id,
                persona_context=persona_context,
                n_results=6,  # Increased for better context
                document_hint=document_hint
            )
            
            logger.info(f"Retrieved {len(relevant_chunks)} chunks for {persona_id}")
            
            # Log relevance scores for debugging
            if relevant_chunks:
                for i, chunk in enumerate(relevant_chunks):
                    relevance = chunk.get("relevance_score", 0)
                    doc_source = chunk.get("document_source", {})
                    filename = doc_source.get("filename", "unknown")
                    logger.info(f"  Chunk {i+1}: {filename} (relevance: {relevance:.3f})")
            
            if not relevant_chunks:
                logger.info(f"No relevant document chunks found for query: {user_input[:50]}...")
                return ""
            
            # Format retrieved content with enhanced attribution
            formatted_context = self._format_document_context_with_attribution(relevant_chunks, persona_id)
            
            # Log final context length
            logger.info(f"Final document context length: {len(formatted_context)} characters")
            
            return formatted_context
            
        except Exception as e:
            logger.error(f"Error retrieving documents for {persona_id} in session {session_id}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return ""

    def _extract_document_hint_from_query(self, query: str) -> Optional[str]:
        """
        Extract document name hints from user queries
        """
        query_lower = query.lower()
        
        # Common patterns for document references
        document_indicators = [
            r"(?:my|the|in|from)\s+([a-zA-Z_\-]+\.(?:pdf|docx|txt|doc))",  # specific files
            r"(?:my|the|our)\s+(policy|policies|plan|playbook|runbook|report|assessment|architecture|diagram|questionnaire|contract|audit)",  # document types
            r"(?:in|from)\s+(?:my\s+)?([a-zA-Z_\-\s]+(?:section|appendix|policy|plan))",  # sections
            r"(?:the|my|our)\s+([a-zA-Z_\-\s]+(?:document|file))",  # generic documents
        ]
        
        for pattern in document_indicators:
            matches = re.findall(pattern, query_lower)
            if matches:
                return matches[0].strip().replace(" ", "_")
        
        return None

    def _get_enhanced_persona_context_keywords(self, persona_id: str) -> str:
        """Retrieval keywords derived from the persona's own descriptors."""
        persona = self.personas.get(persona_id)
        if not persona:
            return ""
        return " ".join(part for part in (persona.role, persona.summary) if part)

    def _format_document_context_with_attribution(self, chunks: List[Dict], persona_id: str) -> str:
        """
        Format document context with clear attribution and source information
        """
        if not chunks:
            return ""
        
        # Filter chunks by relevance (increased threshold for quality)
        high_quality_chunks = [
            chunk for chunk in chunks 
            if chunk.get("relevance_score", 0) > 0.4  # Increased from 0.3
        ]
        
        if not high_quality_chunks:
            # If no high-quality chunks, take top 2 anyway but with lower confidence
            high_quality_chunks = chunks[:2]
        
        formatted_sections = []
        
        # Group chunks by document for better organization
        documents = {}
        for chunk in high_quality_chunks:
            doc_source = chunk.get("document_source", {})
            filename = doc_source.get("filename", "unknown")
            
            if filename not in documents:
                documents[filename] = {
                    "title": doc_source.get("document_title", filename),
                    "chunks": []
                }
            documents[filename]["chunks"].append(chunk)
        
        # Format each document's content
        for filename, doc_data in documents.items():
            doc_title = doc_data["title"]
            doc_chunks = doc_data["chunks"]
            
            formatted_sections.append(f"=== FROM DOCUMENT: {doc_title} ===")
            
            for i, chunk in enumerate(doc_chunks):
                doc_source = chunk.get("document_source", {})
                section = doc_source.get("section", "unknown section")
                position = doc_source.get("chunk_position", "unknown position")
                relevance = chunk.get("relevance_score", 0)
                
                chunk_intro = f"[Source: {section}, Part {position}, Relevance: {relevance:.2f}]"
                formatted_sections.append(f"{chunk_intro}\n{chunk['text']}\n")
        
        # Add context summary
        total_docs = len(documents)
        total_chunks = len(high_quality_chunks)
        
        context_header = f"""
DOCUMENT CONTEXT FOR {persona_id.upper()} ANALYSIS:
Found {total_chunks} relevant passages from {total_docs} document(s).
Use this context to inform your response, and cite specific documents when referencing information.

"""
        
        formatted_context = context_header + "\n".join(formatted_sections)
        
        # Add instructions specific to persona
        persona_instructions = self._get_persona_document_instructions(persona_id)
        formatted_context += f"\n\nSPECIAL INSTRUCTIONS FOR {persona_id.upper()}:\n{persona_instructions}"
        
        return formatted_context

    def _get_persona_document_instructions(self, persona_id: str) -> str:
        """
        Get persona-specific instructions for handling document context
        """
        persona = self.personas.get(persona_id)
        lens = f" through your {persona.role} lens" if persona and persona.role else ""
        return (
            "When analyzing the document context:\n"
            f"- Evaluate the material{lens} and cite the document by name.\n"
            "- Point out concrete gaps, risks, or missing controls you can see in the text.\n"
            "- Tie recommendations to specific passages rather than generic advice."
        )

    async def _build_enhanced_context_for_persona(self, session, persona, user_message: str, document_context: str) -> List[Dict[str, str]]:
        """
        Build enhanced context that properly integrates document information with conversation history
        FIXED VERSION - Ensures document context is properly preserved for both providers
        """
        enhanced_context = []

        conversation_messages = [
            m for m in session.messages if m.get("role") != "system"
        ]
        history_tokens = self.context_manager._estimate_tokens_for_messages(
            conversation_messages
        )
        settings = get_settings()
        threshold = settings.orchestrator.conversation_history_token_threshold
        try:
            from app.core import user_knowledge as uk
            from app.core.bootstrap import current_provider as active_provider

            if uk.is_small_context_provider(active_provider):
                # Cap total history used for Neon/~25B-class models (~4096 default).
                threshold = min(
                    threshold,
                    int(settings.user_knowledge.small_model_context_budget),
                )
                self.context_manager.max_context_tokens = int(
                    settings.user_knowledge.small_model_context_budget
                )
            else:
                # Large models: allow the full conversation; keep a high ceiling.
                self.context_manager.max_context_tokens = max(
                    self.context_manager.max_context_tokens, 32000
                )
        except Exception:
            pass

        # Check if we actually have meaningful document content
        has_documents = bool(document_context and document_context.strip() and len(document_context.strip()) > 50)
        
        # Build the system message with proper document awareness
        if has_documents:
            # Get list of uploaded documents
            uploaded_docs = session.uploaded_files if hasattr(session, 'uploaded_files') else []
            doc_list = ", ".join(uploaded_docs) if uploaded_docs else "uploaded documents"
            
            # NOTE: persona.system_prompt is intentionally NOT included here —
            # Persona.respond() already sends it as the LLM system prompt.
            # Including it again doubled the prompt and wasted context budget
            # on small models.
            system_message = f"""CURRENT SESSION CONTEXT:
    The user has uploaded the following documents: {doc_list}

    DOCUMENT CONTENT:
    {document_context}

    IMPORTANT: When the user refers to "my document," "my policy," "my architecture," etc., they are referring to one of their uploaded documents. Use the document context above and reference it by name in your response.

    Always cite your sources when referencing information from their documents using the format: "According to your [document_name]..." or "In your [section_name] from [document_name]..."
    """
        else:
            # NO DOCUMENTS - Explicitly tell persona not to reference documents
            system_message = """IMPORTANT: The user has NOT uploaded any documents yet. Do not reference specific documents, files, or assume you have access to their materials.

    If they mention "my document," "my policy," "my architecture," etc., you should:
    1. Acknowledge that you don't have access to those files yet
    2. Ask them to upload the relevant files for more targeted advice
    3. Provide general guidance based on best practices in your area of expertise

    Do NOT make up document names or pretend to have access to files that don't exist."""

        if hasattr(session, "user_profile_context") and session.user_profile_context:
            system_message += (
                f"\n\n{session.user_profile_context}\n"
                "Use this background to calibrate technical depth, examples, and priorities. "
                f"{RECENCY_OVER_GOAL_RULE}"
            )

        if getattr(session, "urgency_context", ""):
            system_message += f"\n\n{session.urgency_context}"

        if getattr(session, "datetime_context", ""):
            system_message += f"\n\n{session.datetime_context}"

        lens = panel_lens_reminder(
            getattr(persona, "name", ""),
            getattr(persona, "role", ""),
        )
        if lens:
            system_message += f"\n\n{lens}"

        enhanced_context.append({
            "role": "system",
            "content": system_message,
        })

        if history_tokens < threshold:
            for message in conversation_messages:
                enhanced_context.append({
                    "role": message["role"],
                    "content": message["content"],
                })
        else:
            msg_count = len(conversation_messages)
            summary_lock = getattr(session, "_summary_lock", None)

            async def _load_or_build_summary() -> str:
                if (
                    session.conversation_summary
                    and session.conversation_summary_message_count == msg_count
                ):
                    return session.conversation_summary
                llm = self.llm_client
                if llm is None and self.personas:
                    llm = next(iter(self.personas.values())).llm
                persona_names = {p.id: p.name for p in self.personas.values()}
                built = ""
                if llm is not None:
                    built = await generate_conversation_context_summary(
                        conversation_messages,
                        llm,
                        persona_names=persona_names,
                    )
                if built:
                    session.conversation_summary = built
                    session.conversation_summary_message_count = msg_count
                return built

            if isinstance(summary_lock, asyncio.Lock):
                async with summary_lock:
                    summary = await _load_or_build_summary()
            else:
                summary = await _load_or_build_summary()

            if summary:
                system_message += f"\n\nSummary of earlier conversation:\n{summary}"
                enhanced_context[0]["content"] = system_message
                # Keep the most recent turns verbatim so anaphora ("the
                # incident") still binds to the last named topic, not a
                # summarized original goal. Always retain at least the current
                # user turn plus the previous user turn and intervening replies.
                recent_budget = max(1536, threshold // 2)
                min_user_turns = 2
                tail = []
                used = 0
                user_turns = 0
                for message in reversed(conversation_messages):
                    tokens = self.context_manager._estimate_tokens_for_messages(
                        [message]
                    )
                    is_user = str(message.get("role") or "").lower() == "user"
                    if tail and used + tokens > recent_budget and user_turns >= min_user_turns:
                        break
                    tail.insert(0, {
                        "role": message["role"],
                        "content": message["content"],
                    })
                    used += tokens
                    if is_user:
                        user_turns += 1
                enhanced_context.extend(tail)
            else:
                logger.warning(
                    "Summary generation failed; including full history (%d tokens)",
                    history_tokens,
                )
                for message in conversation_messages:
                    enhanced_context.append({
                        "role": message["role"],
                        "content": message["content"],
                    })

        return enhanced_context
    
    def _is_valid_response(self, response: str, persona_id: str) -> bool:
        """Validate response quality"""
        if len(response) < 10 or len(response) > 8000:
            return False

        # Check for AI confusion indicators (model talking to itself)
        confusion_indicators = [
            "Assistant:",
            "excellent discussion, Assistant",
        ]

        return not any(indicator in response for indicator in confusion_indicators)

    def _get_persona_fallback(self, persona_id: str) -> str:
        """Get persona-specific fallback responses"""
        persona = self.personas.get(persona_id)
        focus = persona.role if persona and persona.role else "cybersecurity"
        return (
            f"I'd be happy to help with {focus.lower()}. "
            "Could you share a little more about your situation so I can give specific guidance?"
        )
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session"""
        session = self.session_manager.get_session(session_id)
        if session:
            return {
                "session_id": session.session_id,
                "message_count": len(session.messages),
                "uploaded_files": session.uploaded_files,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "context_summary": self.context_manager.get_context_summary(session.messages)
            }
        return None
    
    def reset_session(self, session_id: str) -> bool:
        """Reset a session (clear messages but keep metadata)"""
        session = self.session_manager.get_session(session_id)
        if session:
            session.clear_messages()
            return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session completely"""
        return self.session_manager.delete_session(session_id)
    
    # Legacy method for backward compatibility
    def _get_persona_context_keywords(self, persona_id: str) -> str:
        """
        Legacy method - use _get_enhanced_persona_context_keywords instead
        """
        return self._get_enhanced_persona_context_keywords(persona_id)
    
    async def chat_with_persona(self, user_input: str, persona_id: str, session_id: str, response_length: str = "medium") -> Dict[str, Any]:
        """
        Chat with a specific persona directly - FIXED for consistent document access
        """
        try:
            persona = self.get_persona(persona_id)
            if not persona:
                return {
                    "error": f"Persona {persona_id} not found",
                    "available_personas": list(self.personas.keys()),
                    "persona_id": persona_id,
                    "persona_name": "Unknown"
                }
            
            # Ensure session exists and log session info
            session = self.session_manager.get_session(session_id)
            logger.info(f"Chat with {persona_id} using session {session_id}")
            
            # Add user message to session
            session.append_message("user", user_input)
            
            # Use the same session_id for document retrieval
            logger.info(f"Generating response for {persona_id} with session {session_id}")
            
            # Generate response from single persona using consistent session ID
            response_data = await self.generate_single_persona_response(session, persona, response_length)
            
            # Add response to session
            session.append_message(persona_id, response_data["response"])
            
            # Ensure response data includes all necessary fields
            return {
                "persona_id": persona_id,
                "persona_name": persona.name,
                "response": response_data.get("response", "I'm having trouble generating a response."),
                "used_documents": response_data.get("used_documents", False),
                "document_chunks_used": response_data.get("document_chunks_used", 0),
                "response_length": response_length,
                "context_quality": response_data.get("context_quality", "unknown"),
                "session_id": session_id,
                "type": "single_persona_response",
                "persona": {
                    "persona_id": persona_id,
                    "persona_name": persona.name,
                    "response": response_data.get("response", "I'm having trouble generating a response."),
                    "used_documents": response_data.get("used_documents", False),
                    "document_chunks_used": response_data.get("document_chunks_used", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in chat_with_persona for {persona_id}: {str(e)}")
            logger.error(f"Session ID: {session_id}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            return {
                "error": f"Error processing request: {str(e)}",
                "persona_id": persona_id,
                "persona_name": self.personas.get(persona_id, {}).name if persona_id in self.personas else "Unknown",
                "response": "I encountered an error while processing your request. Please try again.",
                "used_documents": False,
                "document_chunks_used": 0,
                "response_length": response_length,
                "context_quality": "error",
                "session_id": session_id,
                "type": "error"
            }
        

    def _candidate_pool(self, candidate_ids: Optional[List[str]]) -> Dict[str, Persona]:
        """Resolve the advisor pool, respecting the user's active selection."""
        if candidate_ids:
            pool = {
                pid: self.personas[pid]
                for pid in candidate_ids
                if pid in self.personas
            }
            if pool:
                return pool
        return dict(self.personas)

    @staticmethod
    def _heuristic_urgency(user_input: str) -> str:
        return "triage" if _TRIAGE_FALLBACK.search(user_input or "") else "advisory"

    def _apply_routing_rules(
        self,
        ranked: List[str],
        pool: Dict[str, Persona],
        k: int,
        urgency: str,
    ) -> List[str]:
        """Enforce panel rules on the LLM ranking.

        - The required lead advisor (Jerry) always responds when he is in
          the user's active pool.
        - In triage mode the incident expert responds first.
        - The list is always exactly ``k`` valid, unique advisor IDs.
        """
        cfg = get_settings().orchestrator

        order: List[str] = []
        for pid in ranked:
            if pid in pool and pid not in order:
                order.append(pid)
        for pid in pool:
            if pid not in order:
                order.append(pid)

        top = order[:k]

        required = cfg.required_advisor
        if required in pool and required not in top and top:
            top[-1] = required

        if urgency == "triage":
            triage = cfg.triage_advisor
            if triage in pool:
                if triage not in top and top:
                    for i in range(len(top) - 1, -1, -1):
                        if top[i] != required:
                            top[i] = triage
                            break
                if triage in top:
                    top.remove(triage)
                    top.insert(0, triage)

        # De-duplicate while preserving order, then refill to k if needed.
        seen: List[str] = []
        for pid in top:
            if pid not in seen:
                seen.append(pid)
        for pid in order:
            if len(seen) >= k:
                break
            if pid not in seen:
                seen.append(pid)
        return seen[:k]

    async def route_message(
        self,
        session_id: str,
        user_input: str,
        k: int = 3,
        candidate_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Classify urgency and pick the responding advisors in one LLM call.

        The routing prompt is profile-aware: it includes the user knowledge
        summary loaded onto the session, so an executive asking about "risk"
        is routed differently than a student. Falls back to a keyword urgency
        heuristic plus registry order if the LLM call fails.
        """
        if not self.personas:
            logger.warning("No personas registered.")
            return {"advisors": [], "urgency": "advisory"}

        pool = self._candidate_pool(candidate_ids)
        k = min(k, len(pool))

        ranked: List[str] = []
        urgency = self._heuristic_urgency(user_input)

        try:
            session = self.session_manager.get_session(session_id)
            llm = self.llm_client or next(iter(pool.values())).llm

            profile_block = (
                getattr(session, "user_profile_context", "") or "(nothing known yet)"
            )
            convo = format_recent_conversation(
                getattr(session, "messages", None),
                current_input="",
                max_turns=8,
            )
            advisor_cards = "\n".join(
                f"- {p.id}: {p.name} — {p.role}. {p.summary}"
                for p in pool.values()
            )

            system_prompt = (
                "You route messages for a cybersecurity advisor panel.\n"
                "Given the user context and conversation, do two things:\n"
                "1. Classify urgency: 'triage' (active incident happening now, e.g. "
                "\"I think I've been hacked\"), 'advisory' (needs a recommendation), "
                "or 'program' (long-term improvement, audits, maturity).\n"
                f"2. Choose the {k} most relevant advisors for the LATEST message, "
                "in order of relevance, considering who the user is (role, "
                "knowledge level, organization) — not just the original goal.\n"
                f"{RECENCY_OVER_GOAL_RULE}\n"
                "Do not route as if they were still asking about the stated goal "
                "when recent turns named a different topic.\n\n"
                "Respond ONLY with valid JSON:\n"
                '{"urgency": "triage|advisory|program", "advisors": ["id1", "id2", ...]}'
            )
            user_prompt = (
                f"--- User context (background) ---\n{profile_block}\n\n"
                f"--- Conversation (latest last) ---\n{convo}\n\n"
                f"--- Advisors ---\n{advisor_cards}"
            )

            raw = await llm.generate(
                system_prompt=system_prompt,
                context=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
                max_tokens=150,
                response_mime_type="application/json",
            )

            parsed: Any
            try:
                parsed = json.loads(raw.strip())
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", raw or "", re.DOTALL)
                parsed = json.loads(match.group(0)) if match else {}

            if isinstance(parsed, list):
                parsed = {"advisors": parsed}
            if isinstance(parsed, dict):
                llm_urgency = str(parsed.get("urgency", "")).strip().lower()
                if llm_urgency in VALID_URGENCIES:
                    urgency = llm_urgency
                raw_ids = parsed.get("advisors")
                if isinstance(raw_ids, list):
                    ranked = [str(pid) for pid in raw_ids]

        except Exception as e:
            logger.error(f"Routing LLM call failed, using fallbacks: {e}")

        advisors = self._apply_routing_rules(ranked, pool, k, urgency)
        logger.info(
            "Routing result: urgency=%s advisors=%s (llm_ranked=%s)",
            urgency, advisors, ranked,
        )
        return {"advisors": advisors, "urgency": urgency}

    async def generate_followups(
        self,
        session_id: str,
        count: Optional[int] = None,
    ) -> List[str]:
        """Generate short follow-up suggestions the user could send next.

        Uses conversation context plus the user knowledge summary (plan §5.2).
        Returns an empty list on any failure — the UI simply shows no chips.
        """
        cfg = get_settings().orchestrator
        n = cfg.followup_count if count is None else count
        if n <= 0:
            return []

        try:
            session = self.session_manager.get_session(session_id)
            llm = self.llm_client
            if llm is None and self.personas:
                llm = next(iter(self.personas.values())).llm
            if llm is None:
                return []

            profile_block = getattr(session, "user_profile_context", "") or ""
            convo = format_recent_conversation(
                getattr(session, "messages", None),
                current_input="",
                max_turns=8,
            )

            system_prompt = (
                "You suggest the user's next message to a cybersecurity advisor "
                "panel. Write in the user's voice (first person), specific to "
                "the most recent topic in this conversation — natural next "
                "questions or actions, never generic, and not a snap-back to an "
                "older stated goal unless that is still the current topic. "
                "Each suggestion is one sentence, at most 12 words.\n"
                f"Respond ONLY with valid JSON: {{\"followups\": [{n} strings]}}"
            )
            user_prompt = (
                (f"--- User context ---\n{profile_block}\n\n" if profile_block else "")
                + f"--- Conversation (latest last) ---\n{convo}"
            )

            raw = await llm.generate(
                system_prompt=system_prompt,
                context=[{"role": "user", "content": user_prompt}],
                temperature=0.5,
                max_tokens=200,
                response_mime_type="application/json",
            )

            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            parsed = json.loads(match.group(0)) if match else {}
            items = parsed.get("followups")
            if not isinstance(items, list):
                return []
            cleaned = [
                str(s).strip() for s in items
                if isinstance(s, str) and str(s).strip()
            ]
            return cleaned[:n]

        except Exception as e:
            logger.warning(f"Follow-up generation failed: {e}")
            return []
