// src/components/ProviderDropdown.js
import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, Cpu, Cloud, Server, Loader2 } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const ALL_PROVIDERS = [
  {
    id: 'gemini',
    name: 'Gemini',
    description: 'Google\'s Gemini AI',
    icon: Cloud,
    badge: 'Cloud'
  },
  {
    id: 'ollama',
    name: 'Ollama',
    description: 'Local LLM via Ollama',
    icon: Cpu,
    badge: 'Local'
  },
  {
    id: 'vllm',
    name: 'vLLM',
    description: 'vLLM inference endpoint',
    icon: Server,
    badge: 'API'
  }
];

/**
 * @param {string} currentProvider
 * @param {(id: string) => void} onProviderChange
 * @param {boolean} [isLoading]
 * @param {string[]|null} [onlineProviders] - when loaded and not fail-open, only these ids are selectable.
 *   Pass `null` / omit to fail open (show all). Empty array means none online.
 * @param {boolean} [statusCheckFailed] - explicit fail-open when the entire status request failed
 */
const ProviderDropdown = ({
  currentProvider,
  onProviderChange,
  isLoading = false,
  onlineProviders = null,
  statusCheckFailed = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const { isDark } = useTheme();

  const providers = useMemo(() => {
    // Fail open: show full list if status check failed or status not yet applied as a filter.
    if (statusCheckFailed || onlineProviders == null) {
      return ALL_PROVIDERS;
    }
    // Fail closed per model: drop anything not online.
    return ALL_PROVIDERS.filter((p) => onlineProviders.includes(p.id));
  }, [onlineProviders, statusCheckFailed]);

  const currentProviderInfo =
    providers.find((p) => p.id === currentProvider) ||
    ALL_PROVIDERS.find((p) => p.id === currentProvider);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleProviderSelect = (providerId) => {
    if (providerId !== currentProvider && !isLoading) {
      onProviderChange(providerId);
      setIsOpen(false);
    }
  };

  const toggleDropdown = () => {
    if (!isLoading) {
      setIsOpen(!isOpen);
    }
  };

  const Icon = currentProviderInfo?.icon || Server;

  return (
    <div className="provider-dropdown" ref={dropdownRef} data-theme-dark={isDark || undefined}>
      <button
        className={`provider-button ${isOpen ? 'open' : ''} ${isLoading ? 'loading' : ''}`}
        onClick={toggleDropdown}
        disabled={isLoading || providers.length === 0}
        title={providers.length === 0 ? 'No online providers' : undefined}
      >
        <div className="provider-button-content">
          {isLoading ? (
            <Loader2 className="provider-icon spinning" size={16} />
          ) : (
            <Icon className="provider-icon" size={16} />
          )}
          <div className="provider-info">
            <span className="provider-name">{currentProviderInfo?.name || 'No provider'}</span>
            {currentProviderInfo?.badge && (
              <span className={`provider-badge ${currentProvider}`}>{currentProviderInfo.badge}</span>
            )}
          </div>
        </div>
        <ChevronDown
          className={`dropdown-arrow ${isOpen ? 'rotated' : ''}`}
          size={16}
        />
      </button>

      {isOpen && (
        <div className="provider-dropdown-menu">
          {providers.length === 0 ? (
            <div className="provider-option" style={{ cursor: 'default', opacity: 0.7 }}>
              <div className="provider-option-info">
                <span className="provider-option-name">No online models</span>
                <span className="provider-option-description">Check Model Status in Settings</span>
              </div>
            </div>
          ) : (
            providers.map((provider) => {
              const OptionIcon = provider.icon;
              const isSelected = provider.id === currentProvider;

              return (
                <button
                  key={provider.id}
                  className={`provider-option ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleProviderSelect(provider.id)}
                  disabled={isSelected}
                >
                  <OptionIcon className="provider-option-icon" size={16} />
                  <div className="provider-option-info">
                    <div className="provider-option-header">
                      <span className="provider-option-name">{provider.name}</span>
                      <span className={`provider-option-badge ${provider.id}`}>
                        {provider.badge}
                      </span>
                    </div>
                    <span className="provider-option-description">{provider.description}</span>
                  </div>
                  {isSelected && (
                    <div className="provider-option-checkmark">✓</div>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};

export default ProviderDropdown;
