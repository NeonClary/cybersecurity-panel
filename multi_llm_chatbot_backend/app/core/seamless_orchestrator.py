# app/core/seamless_orchestrator.py

import re
from typing import Dict, List, Optional
from app.llm.mistral_client import MistralClient

class SeamlessOrchestrator:
    def __init__(self):
        self.llm = MistralClient()
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
            "machine learning": ["machine learning", "ml", "ai", "artificial intelligence", "deep learning"],
            "biology": ["biology", "molecular", "genetics", "bioinformatics"],
            "chemistry": ["chemistry", "chemical", "organic chemistry"],
            "physics": ["physics", "quantum", "theoretical physics"],
            "mathematics": ["mathematics", "math", "statistics", "mathematical"],
            "psychology": ["psychology", "cognitive", "behavioral"],
            "sociology": ["sociology", "social science", "anthropology"], 
            "literature": ["literature", "english", "linguistics"],
            "history": ["history", "historical"],
            "philosophy": ["philosophy", "philosophical"],
            "economics": ["economics", "economic", "finance"],
            "political science": ["political science", "politics", "government"],
            "engineering": ["engineering", "mechanical", "electrical", "civil"],
            "medicine": ["medicine", "medical", "healthcare", "clinical"],
            "education": ["education", "teaching", "pedagogy"],
            "business": ["business", "management", "mba"],
            "data science": ["data science", "data analysis", "big data"]
        }
        
        for area, keywords in research_areas.items():
            if any(keyword in user_lower for keyword in keywords):
                info["research_area"] = area
                break
        
        # Detect academic stage
        stage_keywords = {
            "early PhD": ["first year", "1st year", "beginning", "just started", "new student"],
            "coursework phase": ["coursework", "classes", "courses", "taking classes"],
            "mid PhD": ["proposal", "qualifying", "comprehensive", "candidacy"],
            "late PhD": ["dissertation", "thesis writing", "final year", "defending", "defense"]
        }
        
        for stage, keywords in stage_keywords.items():
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
        missing = [f for f in self.required_fields if f not in self.collected_info]
        
        # Create context for the LLM
        context = f"Conversation so far: {' '.join([msg['content'] for msg in self.conversation_history])}\n"
        context += f"Information collected: {self.collected_info}\n"
        context += f"Still need to know: {missing}\n"
        
        system_prompt = """You are a PhD advisor's assistant helping to gather essential information before providing advice. 
        Based on the conversation and what information is still missing, ask ONE natural, conversational follow-up question.
        
        Missing information types:
        - research_area: What field/discipline they're studying
        - specific_question: What specific aspect they need help with
        - academic_stage: What stage of PhD they're in
        
        Ask in a friendly, conversational way as if you're part of the chat. Keep it brief and natural."""
        
        try:
            question = await self.llm.generate(system_prompt, [{"role": "user", "content": context}])
            return question.strip()
        except Exception as e:
            # Fallback to template questions
            fallback_questions = {
                "research_area": "What field are you studying in?",
                "specific_question": "What specific aspect would you like guidance on?", 
                "academic_stage": "What stage of your PhD are you currently in?"
            }
            return fallback_questions.get(missing[0], "Could you tell me more about your situation?")
    
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