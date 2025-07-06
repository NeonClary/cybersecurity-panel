# app/core/seamless_orchestrator.py

import re
from typing import Dict, List, Optional
from app.llm.llm_client import LLMClient

class SeamlessOrchestrator:
    def __init__(self, llm: LLMClient = None):
        self.llm = llm
        self.required_fields = ["research_area", "specific_question", "academic_stage"]
        self.collected_info = {}
        self.conversation_history = []
        self.orchestrator_active = False
        
    def is_input_complete(self) -> bool:
        """Check if we have enough information to proceed to advisors"""
        return all(field in self.collected_info for field in self.required_fields)
    
    def is_input_vague(self, user_input: str) -> bool:
        """Determine if the input is too vague and needs clarification"""
        vague_patterns = [
            r"i'm (not sure|unsure|confused|lost)",
            r"i (don't know|dunno) (what|how|where)",
            r"help me with (my|the|a) (thesis|research|phd)",
            r"(what should i|how do i|where do i start)",
            r"i need (help|advice|guidance)",
            r"(stuck|struggling) with",
            r"(any|some) (advice|suggestions|ideas)",
            r"^(help|advice|guidance)$",
        ]
        
        user_lower = user_input.lower().strip()
        
        # Check for vague patterns
        for pattern in vague_patterns:
            if re.search(pattern, user_lower):
                return True
        
        # Check if input is too short (likely vague)
        if len(user_input.split()) < 8:
            return True
            
        return False
    
    def extract_info(self, user_input: str) -> Dict[str, str]:
        """Extract information from user input"""
        info = {}
        user_lower = user_input.lower()
        
        # Detect research area
        research_areas = {
            "computer science": ["computer science", "cs", "software", "programming", "algorithms"],
            "machine learning": ["machine learning", "ml", "ai", "artificial intelligence", "neural networks"],
            "biology": ["biology", "bio", "genetics", "molecular", "cell"],
            "physics": ["physics", "quantum", "mechanics", "particle"],
            "psychology": ["psychology", "psych", "cognitive", "behavioral"],
            "chemistry": ["chemistry", "chemical", "organic", "inorganic"],
            "mathematics": ["mathematics", "math", "statistics", "calculus"],
            "engineering": ["engineering", "mechanical", "electrical", "civil"],
            "economics": ["economics", "finance", "business", "market"],
            "literature": ["literature", "english", "writing", "poetry"],
            "history": ["history", "historical", "ancient", "medieval"],
            "sociology": ["sociology", "social", "society", "culture"]
        }
        
        for area, keywords in research_areas.items():
            if any(keyword in user_lower for keyword in keywords):
                info["research_area"] = area
                break
        
        # Detect academic stage
        stage_patterns = {
            "first year": ["first year", "1st year", "beginning", "just started", "new"],
            "second year": ["second year", "2nd year", "coursework", "classes"],
            "third year": ["third year", "3rd year", "qualifying", "comprehensive"],
            "dissertation": ["dissertation", "thesis", "writing", "final year", "defense"],
            "postdoc": ["postdoc", "post-doctoral", "finished", "graduated"]
        }
        
        for stage, keywords in stage_patterns.items():
            if any(keyword in user_lower for keyword in keywords):
                info["academic_stage"] = stage
                break
        
        # Detect specific question types
        question_keywords = {
            "topic selection": ["topic", "research question", "focus", "direction", "what to study"],
            "methodology": ["method", "approach", "design", "analysis", "how to research"],
            "literature review": ["literature", "sources", "papers", "reading", "references"],
            "time management": ["time", "schedule", "deadline", "planning", "organizing"],
            "advisor relationship": ["advisor", "supervisor", "mentor", "committee", "meeting"],
            "career planning": ["career", "job", "postdoc", "industry", "academic job"],
            "writing": ["writing", "paper", "manuscript", "publication"],
            "funding": ["funding", "grant", "scholarship", "money", "financial"]
        }
        
        for q_type, keywords in question_keywords.items():
            if any(keyword in user_lower for keyword in keywords):
                info["specific_question"] = q_type
                break
        
        return info
    
    def analyze_input(self, user_input: str):
        """Analyze and store information from user input"""
        self.conversation_history.append({"role": "user", "content": user_input})
        extracted = self.extract_info(user_input)
        self.collected_info.update(extracted)
    
    async def generate_orchestrator_question(self) -> str:
        """Generate a contextual follow-up question using the LLM"""
        if not self.llm:
            return self._get_fallback_question()
            
        missing = [f for f in self.required_fields if f not in self.collected_info]
        
        # Create context for the LLM
        context = f"Conversation so far: {' '.join([msg['content'] for msg in self.conversation_history])}\n"
        context += f"Information collected: {self.collected_info}\n"
        context += f"Still need to know: {missing}\n"
        
        system_prompt = """You are a PhD advisor's assistant. Ask ONE brief follow-up question (under 15 words) to gather missing info.
        
        Missing info types:
        - research_area: What field/discipline they study
        - specific_question: What specific aspect they need help with
        - academic_stage: What stage of PhD they're in
        
        Ask briefly and naturally."""
        
        try:
            question = await self.llm.generate(system_prompt, [{"role": "user", "content": context}], temperature=0.5, max_tokens=50)
            return question.strip()
        except Exception as e:
            print(f"Error generating orchestrator question: {e}")
            return self._get_fallback_question()
    
    def _get_fallback_question(self) -> str:
        """Fallback questions when LLM fails"""
        missing = [f for f in self.required_fields if f not in self.collected_info]
        fallback_questions = {
            "research_area": "What field are you studying in?",
            "specific_question": "What specific aspect would you like guidance on?", 
            "academic_stage": "What stage of your PhD are you currently in?"
        }
        return fallback_questions.get(missing[0] if missing else "research_area", "Could you tell me more about your situation?")
    
    async def process_message(self, user_input: str) -> Dict:
        """Process user message and determine next action"""
        
        # If this is the first message and it's vague, activate orchestrator
        if not self.conversation_history and self.is_input_vague(user_input):
            self.orchestrator_active = True
        
        # Analyze the input
        self.analyze_input(user_input)
        
        # If orchestrator is active and we don't have complete info
        if self.orchestrator_active and not self.is_input_complete():
            question = await self.generate_orchestrator_question()
            return {
                "status": "orchestrator_asking",
                "orchestrator_question": question,
                "collected_info": self.collected_info.copy()
            }
        
        # If we have complete information or orchestrator was never activated
        if self.is_input_complete() or not self.orchestrator_active:
            self.orchestrator_active = False
            return {
                "status": "ready_for_advisors",
                "collected_info": self.collected_info.copy(),
                "enhanced_context": self._create_enhanced_context(user_input)
            }
        
        # Default case - proceed without orchestrator
        return {
            "status": "ready_for_advisors", 
            "collected_info": {},
            "enhanced_context": user_input
        }
    
    def _create_enhanced_context(self, original_query: str) -> str:
        """Create enhanced context for advisors"""
        if not self.collected_info:
            return original_query
            
        context_parts = []
        if "research_area" in self.collected_info:
            context_parts.append(f"Research area: {self.collected_info['research_area']}")
        if "academic_stage" in self.collected_info:
            context_parts.append(f"Academic stage: {self.collected_info['academic_stage']}")
        if "specific_question" in self.collected_info:
            context_parts.append(f"Focus area: {self.collected_info['specific_question']}")
            
        if context_parts:
            return f"[Context: {', '.join(context_parts)}] {original_query}"
        return original_query
    
    def reset(self):
        """Reset for new conversation"""
        self.collected_info = {}
        self.conversation_history = []
        self.orchestrator_active = False