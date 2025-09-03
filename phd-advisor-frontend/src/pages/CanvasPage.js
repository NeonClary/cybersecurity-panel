import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  RefreshCw, 
  Download, 
  Calendar,
  TrendingUp,
  Target,
  BookOpen,
  Lightbulb,
  AlertTriangle,
  Users,
  BarChart3,
  Heart,
  ArrowLeft,
  Printer
} from 'lucide-react';
import '../styles/CanvasPage.css';

// Section icons mapping
const sectionIcons = {
  research_progress: TrendingUp,
  methodology: BarChart3,
  theoretical_framework: BookOpen,
  challenges_obstacles: AlertTriangle,
  next_steps: Target,
  writing_communication: FileText,
  career_development: Users,
  literature_review: BookOpen,
  data_analysis: BarChart3,
  motivation_mindset: Heart
};

const CanvasSection = ({ section, sectionKey, isExpanded, onToggle }) => {
  const IconComponent = sectionIcons[sectionKey] || Lightbulb;
  
  return (
    <div className="canvas-section">
      <div 
        className="section-header" 
        onClick={() => onToggle(sectionKey)}
      >
        <div className="section-header-content">
          <IconComponent className="section-icon" />
          <div className="section-titles">
            <h3 className="section-title">{section.title}</h3>
            <p className="section-description">{section.description}</p>
          </div>
        </div>
        <div className="section-meta">
          <span className="insight-count">{section.insights.length} insights</span>
          <div className={`expand-arrow ${isExpanded ? 'expanded' : ''}`}>
            ▼
          </div>
        </div>
      </div>
      
      {isExpanded && (
        <div className="section-content">
          {section.insights.length === 0 ? (
            <div className="empty-section">
              <Lightbulb className="empty-icon" />
              <p>No insights yet. Keep chatting with your advisors to build this section!</p>
            </div>
          ) : (
            <div className="insights-grid">
              {section.insights.map((insight, index) => (
                <div key={index} className="insight-card">
                  <div className="insight-content">
                    {insight.content}
                  </div>
                  <div className="insight-footer">
                    <span className="insight-source">{insight.source_persona}</span>
                    <span className="insight-confidence">
                      {Math.round(insight.confidence_score * 100)}% confidence
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const CanvasPage = ({ user, authToken, onNavigateToChat, onSignOut }) => {
  const [canvasData, setCanvasData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [expandedSections, setExpandedSections] = useState({});
  const [stats, setStats] = useState({});
  const [isPrintView, setIsPrintView] = useState(false);

  useEffect(() => {
    fetchCanvas();
    fetchStats();
    triggerAutoUpdate();
  }, []);

  const fetchCanvas = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/phd-canvas`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setCanvasData(data);
        
        // Auto-expand sections with insights
        const sectionsToExpand = {};
        Object.entries(data.sections).forEach(([key, section]) => {
          if (section.insights.length > 0) {
            sectionsToExpand[key] = true;
          }
        });
        setExpandedSections(sectionsToExpand);
      } else {
        console.error('Failed to fetch canvas');
      }
    } catch (error) {
      console.error('Error fetching canvas:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/phd-canvas/stats`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const triggerAutoUpdate = async () => {
    try {
      await fetch(`${process.env.REACT_APP_API_URL}/api/phd-canvas/auto-update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });
    } catch (error) {
      console.error('Error triggering auto-update:', error);
    }
  };

  const handleRefreshCanvas = async () => {
    setIsUpdating(true);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/phd-canvas/refresh`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        // Wait a moment then refresh the canvas
        setTimeout(() => {
          fetchCanvas();
          fetchStats();
        }, 2000);
      }
    } catch (error) {
      console.error('Error refreshing canvas:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  const toggleSection = (sectionKey) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionKey]: !prev[sectionKey]
    }));
  };

  const handlePrint = () => {
    setIsPrintView(true);
    setTimeout(() => {
      window.print();
      setIsPrintView(false);
    }, 100);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="canvas-loading">
        <div className="loading-spinner"></div>
        <p>Loading your PhD Canvas...</p>
      </div>
    );
  }

  // Sort sections by priority and insights count
  const sortedSections = Object.entries(canvasData?.sections || {})
    .sort(([, a], [, b]) => {
      // First by priority (lower number = higher priority)
      if (a.priority !== b.priority) {
        return a.priority - b.priority;
      }
      // Then by insights count (more insights first)
      return b.insights.length - a.insights.length;
    });

  return (
    <div className={`canvas-page ${isPrintView ? 'print-view' : ''}`}>
      {/* Header */}
      <div className="canvas-header">
        <div className="header-left">
          <button 
            className="back-button"
            onClick={onNavigateToChat}
          >
            <ArrowLeft size={20} />
            Back to Chat
          </button>
          <div className="canvas-title-section">
            <h1 className="canvas-title">
              <FileText className="canvas-title-icon" />
              PhD Journey Canvas
            </h1>
            <p className="canvas-subtitle">Your research progress at a glance</p>
          </div>
        </div>
        
        <div className="header-actions">
          <button 
            className="action-button refresh-button"
            onClick={handleRefreshCanvas}
            disabled={isUpdating}
          >
            <RefreshCw className={`action-icon ${isUpdating ? 'spinning' : ''}`} />
            {isUpdating ? 'Updating...' : 'Refresh'}
          </button>
          
          <button 
            className="action-button print-button"
            onClick={handlePrint}
          >
            <Printer className="action-icon" />
            Print
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="canvas-stats">
        <div className="stat-item">
          <span className="stat-number">{canvasData?.total_insights || 0}</span>
          <span className="stat-label">Total Insights</span>
        </div>
        <div className="stat-item">
          <span className="stat-number">
            {Object.keys(canvasData?.sections || {}).filter(key => 
              canvasData.sections[key].insights.length > 0
            ).length}
          </span>
          <span className="stat-label">Active Sections</span>
        </div>
        <div className="stat-item">
          <span className="stat-number">
            {formatDate(canvasData?.last_updated)}
          </span>
          <span className="stat-label">Last Updated</span>
        </div>
      </div>

      {/* Canvas Content */}
      <div className="canvas-content">
        {sortedSections.length === 0 ? (
          <div className="empty-canvas">
            <FileText className="empty-canvas-icon" />
            <h2>Your Canvas is Empty</h2>
            <p>Start chatting with your AI advisors to populate your PhD Canvas with insights and guidance!</p>
            <button 
              className="start-chatting-button"
              onClick={onNavigateToChat}
            >
              Start Chatting
            </button>
          </div>
        ) : (
          <div className="sections-container">
            {sortedSections.map(([sectionKey, section]) => (
              <CanvasSection
                key={sectionKey}
                section={section}
                sectionKey={sectionKey}
                isExpanded={expandedSections[sectionKey]}
                onToggle={toggleSection}
              />
            ))}
          </div>
        )}
      </div>

      {/* Print Footer */}
      {isPrintView && (
        <div className="print-footer">
          <p>Generated by PhD Advisory Panel - {new Date().toLocaleDateString()}</p>
          <p>Student: {user?.email} | Total Insights: {canvasData?.total_insights || 0}</p>
        </div>
      )}
    </div>
  );
};

export default CanvasPage;