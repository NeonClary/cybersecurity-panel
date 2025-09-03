from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson import ObjectId
from app.models.user import PyObjectId

class CanvasInsight(BaseModel):
    """Individual insight extracted from chat messages"""
    content: str
    source_persona: str
    source_message_id: Optional[str] = None
    source_chat_session: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.8)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    keywords: List[str] = Field(default_factory=list)

class CanvasSection(BaseModel):
    """A themed section of the PhD Canvas with related insights"""
    title: str
    description: str
    insights: List[CanvasInsight] = Field(default_factory=list)
    priority: int = Field(default=1, ge=1, le=5)  # 1=highest priority
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PhdCanvas(BaseModel):
    """Main PhD Canvas model storing all user insights organized by sections"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    
    # Canvas sections organized by theme
    sections: Dict[str, CanvasSection] = Field(default_factory=dict)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    last_chat_processed: Optional[datetime] = None
    total_insights: int = Field(default=0)
    
    # Settings
    auto_update: bool = Field(default=True)
    print_optimized: bool = Field(default=True)
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    def update_section(self, section_key: str, insights: List[CanvasInsight]):
        """Update a specific canvas section with new insights"""
        if section_key not in self.sections:
            self.sections[section_key] = CanvasSection(
                title=self._get_section_title(section_key),
                description=self._get_section_description(section_key)
            )
        
        # Add new insights and remove duplicates
        existing_contents = {insight.content for insight in self.sections[section_key].insights}
        new_insights = [insight for insight in insights if insight.content not in existing_contents]
        
        self.sections[section_key].insights.extend(new_insights)
        self.sections[section_key].updated_at = datetime.utcnow()
        self.last_updated = datetime.utcnow()
        
        # Update total insights count
        self.total_insights = sum(len(section.insights) for section in self.sections.values())
    
    def _get_section_title(self, section_key: str) -> str:
        """Get human-readable title for section"""
        titles = {
            "research_progress": "Research Progress & Milestones",
            "methodology": "Research Methods & Approach", 
            "theoretical_framework": "Theoretical Foundations",
            "challenges_obstacles": "Challenges & Solutions",
            "next_steps": "Action Items & Next Steps",
            "writing_communication": "Writing & Communication",
            "career_development": "Academic Career Planning",
            "literature_review": "Literature & Sources",
            "data_analysis": "Data & Analysis",
            "motivation_mindset": "Motivation & Mindset"
        }
        return titles.get(section_key, section_key.replace("_", " ").title())
    
    def _get_section_description(self, section_key: str) -> str:
        """Get description for each section"""
        descriptions = {
            "research_progress": "Key milestones, accomplishments, and timeline updates",
            "methodology": "Research design decisions and methodological insights",
            "theoretical_framework": "Theoretical perspectives and conceptual foundations",
            "challenges_obstacles": "Challenges faced and strategies for overcoming them",
            "next_steps": "Immediate action items and upcoming priorities",
            "writing_communication": "Writing strategies and communication insights",
            "career_development": "Professional development and career planning",
            "literature_review": "Literature gaps, sources, and review strategies",
            "data_analysis": "Data collection and analysis approaches",
            "motivation_mindset": "Motivational insights and mental health considerations"
        }
        return descriptions.get(section_key, "General insights and guidance")

class CanvasResponse(BaseModel):
    """Response model for canvas API endpoints"""
    id: str
    user_id: str
    sections: Dict[str, CanvasSection]
    created_at: datetime
    last_updated: datetime
    last_chat_processed: Optional[datetime]
    total_insights: int
    auto_update: bool
    print_optimized: bool

class UpdateCanvasRequest(BaseModel):
    """Request model for updating canvas"""
    force_full_update: bool = Field(default=False)
    include_chat_sessions: Optional[List[str]] = None  # Specific sessions to include
    exclude_sections: Optional[List[str]] = None  # Sections to skip updating