import React from 'react';
import { MessageCircle, ArrowRight } from 'lucide-react';
import AdvisorCard from '../components/AdvisorCard';
import AppHeader from '../components/AppHeader';
import CopyrightNotice from '../components/CopyrightNotice';
import { useAppConfig } from '../contexts/AppConfigContext';

const HomePage = ({ onNavigateToChat, isAuthenticated, onNavigateToHome, onNavigateToCanvas }) => {
  const { config, advisors, resolveIcon } = useAppConfig();

  return (
    <div className="homepage">
      <AppHeader
        currentPage="home"
        onNavigateToHome={onNavigateToHome}
        onNavigateToChat={onNavigateToChat}
        onNavigateToCanvas={onNavigateToCanvas}
      />

      {/* Hero Section */}
      <main className="main">
        <div className="hero-section">
          <h2 className="hero-title">
            {config.homepage.headline_prefix}{' '}
            <span className="hero-highlight">{config.homepage.headline_highlight}</span>
          </h2>
          <p className="hero-subtitle">
            {config.homepage.description}
          </p>
          <button
            onClick={onNavigateToChat}
            className="cta-button"
          >
            <MessageCircle className="cta-icon" />
            <span>{isAuthenticated ? 'Continue Conversation' : 'Start Conversation'}</span>
            <ArrowRight className="cta-arrow" />
          </button>
        </div>

        {/* Advisors Grid */}
        <div className="advisors-grid">
          {Object.entries(advisors).map(([id, advisor]) => (
            <AdvisorCard key={id} advisor={advisor} advisorId={id} />
          ))}
        </div>

        {/* Features Section */}
        <div className="features-section">
          <h3 className="features-title">{config.homepage.features_title}</h3>
          <div className="features-grid">
            {(config.homepage.features || []).map((feature, index) => {
              const FeatureIcon = resolveIcon(feature.icon);
              return (
                <div key={index} className="feature-card">
                  <div className="feature-icon">
                    <FeatureIcon />
                  </div>
                  <h4 className="feature-title">{feature.title}</h4>
                  <p className="feature-description">
                    {feature.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </main>
      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <CopyrightNotice />
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
