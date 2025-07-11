from typing import Dict, List, Optional, Any
from app.models.persona import Persona
from app.core.session_manager import ConversationContext, get_session_manager
from app.core.context_manager import get_context_manager
from app.core.rag_manager import get_rag_manager
from app.llm.llm_client import LLMClient
import logging
import re

logger = logging.getLogger(__name__)

class ImprovedChatOrchestrator:
    """
    Improved orchestrator with proper session management and context handling
    """
    
    def __init__(self):
        self.personas: Dict[str, Persona] = {}
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
    
    async def process_message(self, 
                            user_input: str, 
                            session_id: Optional[str] = None,
                            response_length: str = "medium") -> Dict[str, Any]:
        """
        Process a user message through the orchestration pipeline
        """
        try:
            # Get or create session
            session = self.session_manager.get_session(session_id)
            
            # Add user message to session
            session.append_message("user", user_input)
            
            # Determine if we need clarification
            needs_clarification = self._needs_clarification(session, user_input)
            
            if needs_clarification:
                # Generate clarification question
                clarification = await self._generate_clarification_question(session)
                session.append_message("orchestrator", clarification)
                
                return {
                    "type": "clarification",
                    "session_id": session.session_id,
                    "message": clarification,
                    "context_summary": self.context_manager.get_context_summary(session.messages)
                }
            
            # Generate responses from all personas
            responses = await self._generate_persona_responses(session, response_length)
            
            return {
                "type": "persona_responses",
                "session_id": session.session_id,
                "responses": responses,
                "context_summary": self.context_manager.get_context_summary(session.messages)
            }
            
        except Exception as e:
            logger.error(f"Error in process_message: {str(e)}")
            return {
                "type": "error",
                "session_id": session_id,
                "message": "I encountered an error processing your request. Please try again.",
                "error": str(e)
            }
    
    async def chat_with_persona(self, 
                               user_input: str, 
                               persona_id: str,
                               session_id: Optional[str] = None,
                               response_length: str = "medium") -> Dict[str, Any]:
        """
        Chat with a specific persona - ENHANCED WITH RAG
        """
        try:
            if persona_id not in self.personas:
                return {
                    "type": "error",
                    "message": f"Persona '{persona_id}' not found"
                }
            
            # Get or create session
            session = self.session_manager.get_session(session_id)
            
            # Add user message
            session.append_message("user", user_input)
            
            # Generate response from specific persona with RAG
            persona = self.personas[persona_id]
            response = await self._generate_single_persona_response(session, persona, response_length)
            
            # Add persona response to session
            session.append_message(persona_id, response['response'])
            
            return {
                "type": "single_persona_response",
                "session_id": session.session_id,
                "persona": response,
                "context_summary": self.context_manager.get_context_summary(session.messages),
                "rag_info": {
                    "used_documents": response.get("used_documents", False),
                    "document_chunks_used": response.get("document_chunks_used", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in chat_with_persona: {str(e)}")
            return {
                "type": "error",
                "session_id": session_id,
                "message": "I encountered an error generating a response. Please try again.",
                "error": str(e)
            }
    
    def _needs_clarification(self, session, user_input: str) -> bool:
        """
        Determine if we need clarification - SIMPLIFIED VERSION
        """
        try:
            # Simple heuristics for clarification
            if len(user_input.strip()) < 10:
                return True
            
            # Check if it's a greeting or very general question
            greeting_words = ['hi', 'hello', 'hey', 'good morning', 'good afternoon']
            if any(word in user_input.lower() for word in greeting_words):
                return True
            
            # Very vague questions
            vague_words = ['help', 'advice', 'what should i do', 'i need help']
            if len([word for word in vague_words if word in user_input.lower()]) > 0 and len(user_input.split()) < 8:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in clarification check: {str(e)}")
            return False  # Default to no clarification needed
    
    async def _generate_clarification_question(self, session: ConversationContext) -> str:
        """
        Generate a clarification question based on context
        """
        user_messages = session.get_messages_by_role("user")
        if not user_messages:
            return "What specific aspect of your PhD journey would you like guidance on?"
        
        latest_message = user_messages[-1]['content']
        
        # Extract what information we might be missing
        missing_info = []
        
        # Check for research area
        research_keywords = ["computer science", "biology", "psychology", "physics", "chemistry", 
                           "engineering", "literature", "history", "mathematics", "sociology"]
        if not any(keyword in latest_message.lower() for keyword in research_keywords):
            missing_info.append("research area")
        
        # Check for specific question type
        question_keywords = ["methodology", "theory", "writing", "analysis", "data", "literature review"]
        if not any(keyword in latest_message.lower() for keyword in question_keywords):
            missing_info.append("specific aspect")
        
        # Check for academic stage
        stage_keywords = ["first year", "second year", "third year", "qualifying", "dissertation", 
                         "defense", "proposal", "coursework"]
        if not any(keyword in latest_message.lower() for keyword in stage_keywords):
            missing_info.append("PhD stage")
        
        # Generate appropriate clarification question
        if "research area" in missing_info:
            return "What field or discipline are you studying in?"
        elif "specific aspect" in missing_info:
            return "What specific aspect of your research would you like guidance on?"
        elif "PhD stage" in missing_info:
            return "What stage of your PhD program are you currently in?"
        else:
            return "Could you provide more details about your specific situation or question?"
    
    async def _generate_persona_responses(self, session, response_length: str = "medium"):
        """
        Generate responses from all personas with RAG integration
        
        Each persona gets persona-specific document retrieval for more targeted responses
        """
        responses = []
        
        for persona_id, persona in self.personas.items():
            logger.info(f"Generating response for {persona_id} with RAG")
            
            # Generate persona response with RAG
            response_data = await self._generate_single_persona_response(session, persona, response_length)
            
            # Add persona response to session context
            session.append_message(persona_id, response_data["response"])
            
            responses.append(response_data)
        
        return responses
    
    async def _generate_single_persona_response(self, session, persona, response_length: str = "medium"):
        """
        Generate response from a single persona with RAG-enhanced context - FIXED VERSION
        """
        try:
            # Get conversation context (recent messages only for efficiency)
            recent_messages = session.messages[-5:] if len(session.messages) > 5 else session.messages
            
            # Get the user's latest message for document retrieval
            user_message = ""
            try:
                # Use the new method to get latest user message
                user_message = session.get_latest_user_message() or ""
            except AttributeError:
                # Fallback: manually find latest user message
                for msg in reversed(recent_messages):
                    if msg.get('role') == 'user':
                        user_message = msg.get('content', '')
                        break
            
            # Retrieve relevant document context using RAG
            document_context = ""
            if user_message:
                document_context = await self._retrieve_relevant_documents(
                    user_input=user_message,
                    session_id=session.session_id,
                    persona_id=persona.id
                )
            
            # Build enhanced context for the LLM
            enhanced_context = []
            
            # Add document context at the beginning if available
            if document_context:
                enhanced_context.append({
                    "role": "system",
                    "content": f"{document_context}Based on the above document context and conversation history, please respond as {persona.name}."
                })
            
            # Add recent conversation messages
            enhanced_context.extend(recent_messages)
            
            # Generate response with enhanced context
            response = await persona.respond(enhanced_context, response_length)
            
            # Validate response
            if not self._is_valid_response(response, persona.id):
                logger.warning(f"Invalid response from {persona.id}, using fallback")
                response = self._get_fallback_response(persona.id)
            
            return {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": response,
                "error": False,
                "used_documents": bool(document_context),
                "document_chunks_used": document_context.count("[Document") if document_context else 0
            }
            
        except Exception as e:
            logger.error(f"Error in _generate_single_persona_response for {persona.id}: {str(e)}")
            return {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": self._get_fallback_response(persona.id),
                "error": True,
                "used_documents": False,
                "document_chunks_used": 0
            }
    
    def _is_valid_response(self, response: str, persona_id: str) -> bool:
        """Validate response quality"""
        if not response or len(response.strip()) < 10:
            return False
        
        if len(response) > 2000:  # Too long
            return False
        
        # Check for AI confusion indicators
        confusion_indicators = [
            f"Thank you, Dr. {persona_id.title()}",
            "Assistant:",
            f"Dr. {persona_id.title()}:",
            "excellent discussion, Assistant"
        ]
        
        return not any(indicator in response for indicator in confusion_indicators)
    
    def _get_fallback_response(self, persona_id: str) -> str:
        """Get persona-specific fallback response"""
        fallbacks = {
            "methodologist": "Let's focus on your research methodology. What specific methodological approach are you considering?",
            "theorist": "I'd like to explore the theoretical foundation of your work. What conceptual framework guides your research?",
            "pragmatist": "Let's take a practical approach. What's the most pressing decision you need to make about your research right now?"
        }
        return fallbacks.get(persona_id, "I'd be happy to help. Could you provide more specific details about your question?")
    
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
    
    def _get_persona_context_keywords(self, persona_id: str) -> str:
        """
        Get persona-specific keywords for enhanced document retrieval
        
        This ensures each advisor gets the most relevant document chunks
        based on their specialization
        """
        persona_keywords = {
            "methodologist": "methodology research design analysis methods data collection sampling validity reliability statistical approach quantitative qualitative",
            "theorist": "theory theoretical framework conceptual model literature review philosophy epistemology ontology paradigm abstract concepts",
            "pragmatist": "practical application implementation action steps next steps recommendation solution strategy timeline concrete advice"
        }
        return persona_keywords.get(persona_id, "")
    
    async def _retrieve_relevant_documents(self, user_input: str, session_id: str, persona_id: str = "") -> str:
        """
        Retrieve relevant document chunks using RAG - FIXED VERSION
        """
        try:
            rag_manager = get_rag_manager()
            
            # Get persona-specific context for better retrieval
            persona_context = self._get_persona_context_keywords(persona_id)
            
            # Search for relevant chunks
            relevant_chunks = rag_manager.search_documents(
                query=user_input,
                session_id=session_id,
                persona_context=persona_context,
                n_results=3  # Limit to top 3 most relevant chunks
            )
            
            logger.info(f"Retrieved {len(relevant_chunks)} total chunks for {persona_id}")
            
            if not relevant_chunks:
                logger.info(f"No relevant documents found for query: {user_input[:50]}...")
                return ""
            
            # Format retrieved content - LOWERED THRESHOLD
            context_parts = []
            for i, chunk in enumerate(relevant_chunks, 1):
                filename = chunk["metadata"].get("filename", "Unknown")
                relevance = chunk["relevance_score"]
                distance = chunk.get("distance", "unknown")
                text = chunk["text"]
                
                logger.info(f"Chunk {i} for {persona_id}: relevance={relevance:.3f}, distance={distance}")
                
                # LOWERED threshold from 0.3 to 0.1 to allow more chunks through
                if relevance > 0.1:
                    context_parts.append(
                        f"[Document {i}: {filename} (relevance: {relevance:.3f})]\n{text[:500]}..."  # Limit text length
                    )
                    logger.info(f"Including chunk {i} for {persona_id} (relevance: {relevance:.3f})")
                else:
                    logger.info(f"Excluding chunk {i} for {persona_id} (relevance too low: {relevance:.3f})")
            
            if context_parts:
                retrieved_context = "\n\n".join(context_parts)
                logger.info(f"Using {len(context_parts)} relevant chunks for {persona_id}")
                return f"RELEVANT DOCUMENT CONTEXT:\n{retrieved_context}\n\n"
            
            logger.info(f"No chunks met relevance threshold for {persona_id}")
            return ""
            
        except Exception as e:
            logger.error(f"Error retrieving documents for {persona_id}: {str(e)}")
            return ""