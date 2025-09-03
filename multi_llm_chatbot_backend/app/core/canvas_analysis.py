import re
import json
import logging
from typing import Dict, List, Tuple, Set
from datetime import datetime
from collections import defaultdict

from app.models.phd_canvas import CanvasInsight, CanvasSection
from app.llm.improved_gemini_client import ImprovedGeminiClient
from app.llm.improved_ollama_client import ImprovedOllamaClient

logger = logging.getLogger(__name__)

class CanvasAnalysisService:
    """Service for extracting and categorizing insights from chat messages"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        
        # Predefined section mappings for semantic analysis
        self.section_keywords = {
            "research_progress": [
                "progress", "milestone", "completed", "finished", "accomplished", 
                "achieved", "timeline", "deadline", "chapter", "draft", "version"
            ],
            "methodology": [
                "method", "methodology", "approach", "design", "data collection",
                "survey", "interview", "experiment", "analysis", "statistical", 
                "qualitative", "quantitative", "mixed methods"
            ],
            "theoretical_framework": [
                "theory", "theoretical", "framework", "concept", "model",
                "literature", "author", "philosophy", "paradigm", "assumption"
            ],
            "challenges_obstacles": [
                "challenge", "problem", "difficulty", "obstacle", "stuck",
                "confused", "frustrated", "struggle", "barrier", "issue"
            ],
            "next_steps": [
                "next", "plan", "should", "will", "going to", "need to",
                "action", "step", "priority", "focus", "goal", "objective"
            ],
            "writing_communication": [
                "write", "writing", "paper", "thesis", "dissertation", "publication",
                "communication", "presentation", "defense", "draft", "revision"
            ],
            "career_development": [
                "career", "job", "position", "networking", "conference",
                "skills", "CV", "resume", "application", "fellowship", "grant"
            ],
            "literature_review": [
                "literature", "sources", "papers", "articles", "bibliography",
                "citation", "author", "study", "research", "gap", "review"
            ],
            "data_analysis": [
                "data", "analysis", "results", "findings", "statistics",
                "coding", "software", "tool", "visualization", "pattern"
            ],
            "motivation_mindset": [
                "motivation", "confidence", "stress", "anxiety", "balance",
                "mental health", "mindset", "support", "overwhelmed", "burnout"
            ]
        }
    
    async def extract_insights_from_messages(self, messages: List[Dict], chat_session_id: str) -> List[CanvasInsight]:
        """Extract actionable insights from chat messages using semantic analysis"""
        try:
            insights = []
            
            for message in messages:
                if message.get("type") == "assistant" and "responses" in message:
                    # Handle multi-persona responses
                    for response in message.get("responses", []):
                        persona_insights = await self._extract_insights_from_persona_response(
                            response, message.get("id"), chat_session_id
                        )
                        insights.extend(persona_insights)
                elif message.get("role") == "assistant" and message.get("content"):
                    # Handle single response format
                    persona_insights = await self._extract_insights_from_content(
                        message.get("content", ""), "assistant", 
                        message.get("id"), chat_session_id
                    )
                    insights.extend(persona_insights)
            
            # Remove duplicates and low-confidence insights
            unique_insights = self._deduplicate_insights(insights)
            high_confidence_insights = [i for i in unique_insights if i.confidence_score >= 0.6]
            
            logger.info(f"Extracted {len(high_confidence_insights)} insights from {len(messages)} messages")
            return high_confidence_insights
            
        except Exception as e:
            logger.error(f"Error extracting insights from messages: {e}")
            return []
    
    async def _extract_insights_from_persona_response(self, response: Dict, message_id: str, chat_session_id: str) -> List[CanvasInsight]:
        """Extract insights from a single persona response"""
        persona_id = response.get("persona_id", "unknown")
        content = response.get("content", "")
        
        return await self._extract_insights_from_content(content, persona_id, message_id, chat_session_id)
    
    async def _extract_insights_from_content(self, content: str, persona_id: str, message_id: str, chat_session_id: str) -> List[CanvasInsight]:
        """Extract actionable insights from content using LLM analysis"""
        if not content or len(content.strip()) < 50:
            return []
        
        try:
            # Use LLM to extract key insights
            extraction_prompt = f"""
            Extract actionable insights from this PhD advisor response that would be valuable for a student's progress summary:

            PERSONA: {persona_id}
            CONTENT: {content}

            Return a JSON list of insights. Each insight should be:
            - Actionable and specific to PhD progress
            - 1-2 sentences long
            - Valuable for advisor meetings
            - Not generic advice

            Format: [{{"insight": "specific actionable insight here", "keywords": ["keyword1", "keyword2"]}}]
            
            Return ONLY the JSON array, no other text.
            """
            
            if self.llm_client:
                llm_response = await self.llm_client.generate(
                    system_prompt="You are an expert at extracting actionable PhD guidance from advisor responses.",
                    context=[{"role": "user", "content": extraction_prompt}],
                    temperature=0.3,
                    max_tokens=500
                )
                
                try:
                    insights_data = json.loads(llm_response.strip())
                    insights = []
                    
                    for item in insights_data:
                        if isinstance(item, dict) and "insight" in item:
                            insight = CanvasInsight(
                                content=item["insight"],
                                source_persona=persona_id,
                                source_message_id=message_id,
                                source_chat_session=chat_session_id,
                                confidence_score=0.8,  # High confidence from LLM extraction
                                keywords=item.get("keywords", [])
                            )
                            insights.append(insight)
                    
                    return insights
                    
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM insights response for {persona_id}")
                    # Fallback to rule-based extraction
                    return self._extract_insights_rule_based(content, persona_id, message_id, chat_session_id)
            
            # Fallback if no LLM available
            return self._extract_insights_rule_based(content, persona_id, message_id, chat_session_id)
            
        except Exception as e:
            logger.error(f"Error extracting insights from {persona_id} content: {e}")
            return []
    
    def _extract_insights_rule_based(self, content: str, persona_id: str, message_id: str, chat_session_id: str) -> List[CanvasInsight]:
        """Fallback rule-based insight extraction"""
        insights = []
        
        # Extract actionable sentences
        sentences = re.split(r'[.!?]+', content)
        actionable_patterns = [
            r"(?:you should|consider|try|focus on|prioritize|next step|recommended?|suggest)",
            r"(?:action item|goal|objective|plan|strategy)",
            r"(?:deadline|timeline|schedule|by \w+)",
            r"(?:complete|finish|work on|tackle|address)"
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
                
            # Check if sentence contains actionable language
            is_actionable = any(re.search(pattern, sentence, re.IGNORECASE) for pattern in actionable_patterns)
            
            if is_actionable:
                # Extract keywords
                keywords = self._extract_keywords_from_sentence(sentence)
                
                insight = CanvasInsight(
                    content=sentence,
                    source_persona=persona_id,
                    source_message_id=message_id,
                    source_chat_session=chat_session_id,
                    confidence_score=0.6,  # Lower confidence for rule-based
                    keywords=keywords
                )
                insights.append(insight)
        
        return insights[:3]  # Limit to 3 insights per message to avoid noise
    
    def _extract_keywords_from_sentence(self, sentence: str) -> List[str]:
        """Extract relevant keywords from a sentence"""
        # Simple keyword extraction
        words = re.findall(r'\b\w{4,}\b', sentence.lower())  # Words with 4+ chars
        
        # Filter out common words
        stop_words = {
            "should", "could", "would", "your", "research", "work", "study", 
            "consider", "think", "important", "also", "really", "maybe",
            "probably", "definitely", "certainly", "particular", "specific"
        }
        
        keywords = [word for word in words if word not in stop_words]
        return keywords[:5]  # Limit to 5 keywords
    
    def categorize_insights(self, insights: List[CanvasInsight]) -> Dict[str, List[CanvasInsight]]:
        """Categorize insights into canvas sections using semantic analysis"""
        categorized = defaultdict(list)
        
        for insight in insights:
            section = self._determine_section(insight)
            categorized[section].append(insight)
        
        return dict(categorized)
    
    def _determine_section(self, insight: CanvasInsight) -> str:
        """Determine which canvas section an insight belongs to"""
        content_lower = insight.content.lower()
        keywords_lower = [kw.lower() for kw in insight.keywords]
        all_text = content_lower + " " + " ".join(keywords_lower)
        
        # Score each section based on keyword matches
        section_scores = {}
        
        for section_key, section_keywords in self.section_keywords.items():
            score = 0
            for keyword in section_keywords:
                if keyword in all_text:
                    score += 1
            
            # Bonus for persona-specific insights
            persona_bonuses = {
                "methodologist": {"methodology": 2, "data_analysis": 1},
                "theorist": {"theoretical_framework": 2, "literature_review": 1},
                "pragmatist": {"next_steps": 2, "research_progress": 1},
                "socratic": {"theoretical_framework": 1, "challenges_obstacles": 1},
                "motivator": {"motivation_mindset": 2, "career_development": 1},
                "critic": {"challenges_obstacles": 1, "writing_communication": 1},
                "empathetic": {"motivation_mindset": 2},
                "visionary": {"career_development": 1, "research_progress": 1}
            }
            
            if insight.source_persona in persona_bonuses:
                score += persona_bonuses[insight.source_persona].get(section_key, 0)
            
            section_scores[section_key] = score
        
        # Return section with highest score, default to general category
        best_section = max(section_scores, key=section_scores.get) if section_scores else "research_progress"
        
        # If no keywords matched, categorize by persona type
        if section_scores[best_section] == 0:
            persona_defaults = {
                "methodologist": "methodology",
                "theorist": "theoretical_framework", 
                "pragmatist": "next_steps",
                "socratic": "theoretical_framework",
                "motivator": "motivation_mindset",
                "critic": "challenges_obstacles",
                "empathetic": "motivation_mindset",
                "visionary": "career_development",
                "storyteller": "writing_communication",
                "minimalist": "next_steps"
            }
            best_section = persona_defaults.get(insight.source_persona, "research_progress")
        
        return best_section
    
    def _deduplicate_insights(self, insights: List[CanvasInsight]) -> List[CanvasInsight]:
        """Remove duplicate insights based on semantic similarity"""
        if not insights:
            return []
        
        unique_insights = []
        seen_contents = set()
        
        for insight in insights:
            # Simple deduplication based on content similarity
            content_normalized = re.sub(r'\s+', ' ', insight.content.lower().strip())
            
            # Check for substantial overlap with existing insights
            is_duplicate = False
            for seen_content in seen_contents:
                if self._calculate_similarity(content_normalized, seen_content) > 0.8:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_insights.append(insight)
                seen_contents.add(content_normalized)
        
        return unique_insights
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity between two texts"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0

    def prioritize_insights(self, insights: List[CanvasInsight]) -> List[CanvasInsight]:
        """Prioritize insights based on relevance and actionability"""
        
        def calculate_priority_score(insight: CanvasInsight) -> float:
            score = insight.confidence_score
            
            # Boost score for actionable language
            actionable_terms = ["should", "need to", "must", "plan", "goal", "deadline", "complete"]
            content_lower = insight.content.lower()
            for term in actionable_terms:
                if term in content_lower:
                    score += 0.1
            
            # Boost score for specific vs generic advice
            specific_terms = ["chapter", "data", "analysis", "method", "theory", "timeline"]
            for term in specific_terms:
                if term in content_lower:
                    score += 0.05
            
            # Boost score for certain personas
            persona_boosts = {
                "pragmatist": 0.1,    # Action-oriented insights are valuable
                "methodologist": 0.08, # Methodological insights are important
                "critic": 0.06        # Critical feedback is valuable
            }
            score += persona_boosts.get(insight.source_persona, 0)
            
            return min(score, 1.0)  # Cap at 1.0
        
        # Calculate scores and sort
        for insight in insights:
            insight.confidence_score = calculate_priority_score(insight)
        
        return sorted(insights, key=lambda x: x.confidence_score, reverse=True)

    async def generate_section_summary(self, section: CanvasSection) -> str:
        """Generate a summary for a canvas section using LLM"""
        if not section.insights or not self.llm_client:
            return f"Key insights for {section.title}"
        
        try:
            insights_text = "\n".join([f"- {insight.content}" for insight in section.insights])
            
            prompt = f"""
            Create a 1-2 sentence summary of these PhD insights for the section "{section.title}":
            
            {insights_text}
            
            The summary should be concise, professional, and suitable for sharing with an advisor.
            Return only the summary text, no other content.
            """
            
            summary = await self.llm_client.generate(
                system_prompt="You create concise summaries of academic insights.",
                context=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=100
            )
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error generating section summary: {e}")
            return f"Key insights and guidance for {section.title}"