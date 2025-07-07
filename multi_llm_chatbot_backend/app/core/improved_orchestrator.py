from typing import Dict, List, Optional, Any
from app.models.persona import Persona
from app.core.session_manager import ConversationContext, get_session_manager
from app.core.context_manager import get_context_manager
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
        Chat with a specific persona
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
            
            # Generate response from specific persona
            persona = self.personas[persona_id]
            response = await self._generate_single_persona_response(session, persona, response_length)
            
            # Add persona response to session
            session.append_message(persona_id, response['response'])
            
            return {
                "type": "single_persona_response",
                "session_id": session.session_id,
                "persona": response,
                "context_summary": self.context_manager.get_context_summary(session.messages)
            }
            
        except Exception as e:
            logger.error(f"Error in chat_with_persona: {str(e)}")
            return {
                "type": "error",
                "session_id": session_id,
                "message": "I encountered an error generating a response. Please try again.",
                "error": str(e)
            }
    
    def _needs_clarification(self, session: ConversationContext, user_input: str) -> bool:
        """
        Determine if user input needs clarification
        """
        # Don't ask for clarification if this is a follow-up message
        user_messages = session.get_messages_by_role("user")
        if len(user_messages) > 1:
            return False
        
        # Check if input is vague
        vague_patterns = [
            r"i'm (not sure|unsure|confused|lost)",
            r"i (don't know|dunno) (what|how|where)",
            r"help me with (my|the|a) (thesis|research|phd)",
            r"(what should i|how do i|where do i start)",
            r"i need (help|advice|guidance)$",
            r"(stuck|struggling) with",
            r"(any|some) (advice|suggestions|ideas)$",
            r"^(help|advice|guidance)$",
        ]
        
        user_lower = user_input.lower().strip()
        
        for pattern in vague_patterns:
            if re.search(pattern, user_lower):
                return True
        
        # Check if input is too short (likely vague)
        if len(user_input.split()) < 8:
            return True
        
        return False
    
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
    
    async def _generate_persona_responses(self, 
                                        session: ConversationContext, 
                                        response_length: str) -> List[Dict[str, Any]]:
        """
        Generate responses from all personas
        """
        responses = []
        
        # Get the conversation context for personas
        context_messages = session.get_recent_messages(limit=20)
        
        for persona_id, persona in self.personas.items():
            try:
                response_data = await self._generate_single_persona_response(
                    session, persona, response_length
                )
                responses.append(response_data)
                
                # Add persona response to session
                session.append_message(persona_id, response_data['response'])
                
            except Exception as e:
                logger.error(f"Error generating response for persona {persona_id}: {str(e)}")
                # Add fallback response
                responses.append({
                    "persona_id": persona_id,
                    "persona_name": persona.name,
                    "response": self._get_fallback_response(persona_id),
                    "error": True
                })
        
        return responses
    
    async def _generate_single_persona_response(self, 
                                              session: ConversationContext,
                                              persona: Persona, 
                                              response_length: str) -> Dict[str, Any]:
        """
        Generate response from a single persona
        """
        try:
            # Get conversation context
            context_messages = session.get_recent_messages(limit=20)
            
            # Generate response using persona
            response = await persona.respond(context_messages, response_length)
            
            # Validate response
            if not self._is_valid_response(response, persona.id):
                response = self._get_fallback_response(persona.id)
            
            return {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": response,
                "error": False
            }
            
        except Exception as e:
            logger.error(f"Error in _generate_single_persona_response for {persona.id}: {str(e)}")
            return {
                "persona_id": persona.id,
                "persona_name": persona.name,
                "response": self._get_fallback_response(persona.id),
                "error": True
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
            "methodist": "Let's focus on your research methodology. What specific methodological approach are you considering?",
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