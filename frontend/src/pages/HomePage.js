import React, { useState } from 'react';
import { MessageCircle, ArrowRight, Sparkles } from 'lucide-react';
import AdvisorCard from '../components/AdvisorCard';
import AppHeader from '../components/AppHeader';
import CopyrightNotice from '../components/CopyrightNotice';
import GuestIntakeModal from '../components/GuestIntakeModal';
import { useAppConfig } from '../contexts/AppConfigContext';

const HomePage = ({
  onNavigateToChat,
  isAuthenticated,
  onNavigateToHome,
  onNavigateToCanvas,
  onExploreAsGuest,
}) => {
  const { config, advisors, resolveIcon } = useAppConfig();
  const [showGuestIntake, setShowGuestIntake] = useState(false);

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
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center', alignItems: 'center' }}>
            <button
              onClick={onNavigateToChat}
              className="cta-button"
            >
              <MessageCircle className="cta-icon" />
              <span>{isAuthenticated ? 'Continue Conversation' : 'Sign in / Start'}</span>
              <ArrowRight className="cta-arrow" />
            </button>
            {!isAuthenticated && (
              <button
                type="button"
                className="cta-button"
                onClick={() => setShowGuestIntake(true)}
                style={{
                  background: 'transparent',
                  color: 'var(--accent-primary, #0B7A8A)',
                  border: '2px solid var(--accent-primary, #0B7A8A)',
                  boxShadow: 'none',
                }}
              >
                <Sparkles className="cta-icon" />
                <span>Explore as guest</span>
              </button>
            )}
          </div>
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

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center', alignItems: 'center', margin: '2.5rem 0 0.5rem' }}>
          <button
            type="button"
            onClick={onNavigateToChat}
            className="cta-button"
          >
            <MessageCircle className="cta-icon" />
            <span>{isAuthenticated ? 'Continue Conversation' : 'Sign in / Start'}</span>
            <ArrowRight className="cta-arrow" />
          </button>
        </div>
      </main>
      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <CopyrightNotice />
        </div>
      </footer>
      {showGuestIntake && (
        <GuestIntakeModal
          onClose={() => setShowGuestIntake(false)}
          onSuccess={(user, token) => {
            setShowGuestIntake(false);
            onExploreAsGuest?.(user, token);
          }}
        />
      )}
    </div>
  );
};

export default HomePage;
