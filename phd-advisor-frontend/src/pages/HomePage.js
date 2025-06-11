import React from 'react';
import { MessageCircle, Users, Target, Brain, ArrowRight } from 'lucide-react';
import AdvisorCard from '../components/AdvisorCard';
import { advisors } from '../data/advisors';

const HomePage = ({ onNavigateToChat }) => {
  return (
    <div className="homepage">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <div className="logo-container">
              <Users className="logo-icon" />
            </div>
            <div>
              <h1 className="logo-title">PhD Advisory Panel</h1>
              <p className="logo-subtitle">Your AI-powered academic advisors</p>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="main">
        <div className="hero-section">
          <h2 className="hero-title">
            Get Guidance from <span className="hero-highlight">Three Expert Advisors</span>
          </h2>
          <p className="hero-subtitle">
            Receive diverse perspectives on your PhD journey from our specialized AI advisors, 
            each bringing unique insights to help you succeed.
          </p>
          <button
            onClick={onNavigateToChat}
            className="cta-button"
          >
            <MessageCircle className="cta-icon" />
            <span>Start Conversation</span>
            <ArrowRight className="cta-arrow" />
          </button>
        </div>

        {/* Advisors Grid */}
        <div className="advisors-grid">
          {Object.entries(advisors).map(([id, advisor]) => (
            <AdvisorCard key={id} advisor={advisor} />
          ))}
        </div>

        {/* Features Section */}
        <div className="features-section">
          <h3 className="features-title">Why Choose Our Advisory Panel?</h3>
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">
                <Users />
              </div>
              <h4 className="feature-title">Multiple Perspectives</h4>
              <p className="feature-description">
                Get varied viewpoints from different advisory styles
              </p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <Brain />
              </div>
              <h4 className="feature-title">AI-Powered Insights</h4>
              <p className="feature-description">
                Leverage advanced AI for comprehensive guidance
              </p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <Target />
              </div>
              <h4 className="feature-title">Focused Advice</h4>
              <p className="feature-description">
                Receive targeted recommendations for your specific needs
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default HomePage;