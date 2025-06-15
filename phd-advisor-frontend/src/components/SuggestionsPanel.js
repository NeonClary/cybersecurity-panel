import React from 'react';
import { BookOpen, FlaskConical, PenTool, Heart } from 'lucide-react';

const SuggestionsPanel = ({ onSuggestionClick }) => {
  const suggestionCategories = [
    {
      title: "Orientation & Guidance",
      icon: BookOpen,
      color: "#3B82F6",
      bgColor: "#EFF6FF",
      suggestions: [
        "How do I choose a research topic that's interesting and doable?",
        "Meeting and Presentation Prep",
        "What should I be doing my first semester?"
      ]
    },
    {
      title: "Research Design & Academic Skills",
      icon: FlaskConical,
      color: "#8B5CF6", 
      bgColor: "#F3E8FF",
      suggestions: [
        "Should I use qualitative, quantitative, or mixed methods for my research?",
        "Is my research question too broad?",
        "How do I defend a non-traditional methodology to my committee?"
      ]
    },
    {
      title: "Writing & Communication",
      icon: PenTool,
      color: "#10B981",
      bgColor: "#ECFDF5",
      suggestions: [
        "What's the right tone for an introduction? Persuasive, cautious, or bold?",
        "How should I respond when reviewers give conflicting feedback?",
        "Should I prioritize journal articles or dissertation chapters when I write?"
      ]
    },
    {
      title: "Mental Health & Hidden Curriculum",
      icon: Heart,
      color: "#F59E0B",
      bgColor: "#FFFBEB",
      suggestions: [
        "How do I cope when I feel behind compared to others in my cohort?",
        "Should I speak up about unclear expectations or just try to figure it out quietly?",
        "What are the unspoken expectations no one tells you about?"
      ]
    }
  ];

  return (
    <div className="suggestions-panel">
      <div className="suggestions-header">
        <h2 className="suggestions-title">Getting Started</h2>
        <p className="suggestions-subtitle">
          Choose a topic to get advice from all personas
        </p>
      </div>
      
      <div className="suggestions-grid">
        {suggestionCategories.map((category, categoryIndex) => {
          const Icon = category.icon;
          return (
            <div key={categoryIndex} className="suggestion-category">
              <div className="category-header">
                <div 
                  className="category-icon"
                  style={{ 
                    backgroundColor: category.bgColor,
                    color: category.color 
                  }}
                >
                  <Icon size={20} />
                </div>
                <h3 
                  className="category-title"
                  style={{ color: category.color }}
                >
                  {category.title}
                </h3>
              </div>
              
              <div className="suggestion-buttons">
                {category.suggestions.map((suggestion, suggestionIndex) => (
                  <button
                    key={suggestionIndex}
                    onClick={() => onSuggestionClick(suggestion)}
                    className="suggestion-button"
                    style={{
                      borderColor: category.color + '20',
                      '--hover-bg': category.bgColor,
                      '--hover-border': category.color
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SuggestionsPanel;