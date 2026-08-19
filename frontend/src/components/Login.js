import React, { useState } from 'react';
import { Eye, EyeOff, Mail, Lock, ArrowRight } from 'lucide-react';
import { useAppConfig } from '../contexts/AppConfigContext';
import CopyrightNotice from './CopyrightNotice';
import '../styles/Login.css';

const Login = ({ onNavigateToSignup, onNavigateToHome, onExploreAsGuest }) => {
  const { config } = useAppConfig();
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }
    
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    setIsLoading(true);
    
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password
        }),
      });

      const data = await response.json();

      if (response.ok) {
        // Store the token and user info
        localStorage.setItem('authToken', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        onNavigateToHome?.(data.user, data.access_token);
      } else {
        setErrors({ submit: data.detail || 'Login failed. Please try again.' });
      }
      
    } catch (error) {
      console.error('Login error:', error);
      setErrors({ submit: 'Login failed. Please try again.' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-content">
        <div className="login-container">
        {/* Header */}
        <div className="login-header">
          <div className="logo-container">
            <img
              src="/brand/cybersecurity-advisor-mark.png"
              alt=""
              className="logo-icon"
            />
          </div>
          <h1 className="login-title">Welcome Back</h1>
          <p className="login-subtitle">
            {config?.login?.subtitle || 'Sign in to continue'}
          </p>
        </div>

        {/* Main Login Form */}
        <div className="login-form-container">
          <form onSubmit={handleSubmit} className="login-form">
            
            {/* Email Field */}
            <div className="form-group">
              <label htmlFor="email" className="form-label">
                Email Address
              </label>
              <div className="input-container">
                <Mail className="input-icon" />
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  className={`form-input ${errors.email ? 'error' : ''}`}
                  placeholder="Enter your email"
                  disabled={isLoading}
                />
              </div>
              {errors.email && (
                <span className="error-message">{errors.email}</span>
              )}
            </div>

            {/* Password Field */}
            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password
              </label>
              <div className="input-container">
                <Lock className="input-icon" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  className={`form-input ${errors.password ? 'error' : ''}`}
                  placeholder="Enter your password"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="password-toggle"
                  disabled={isLoading}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && (
                <span className="error-message">{errors.password}</span>
              )}
            </div>

            {/* Forgot Password */}
            <div className="form-actions">
              <button type="button" className="forgot-password">
                Forgot your password?
              </button>
            </div>

            {/* Submit Error */}
            {errors.submit && (
              <div className="submit-error">
                {errors.submit}
              </div>
            )}

            {/* Submit Button */}
            <button 
              type="submit" 
              className={`submit-btn ${isLoading ? 'loading' : ''}`}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="loading-spinner"></div>
                  Signing In...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <div className="divider">
            <span>or</span>
          </div>

          <div className="social-login">
            <button
              type="button"
              className="guest-explore-btn"
              onClick={onExploreAsGuest}
              disabled={isLoading || !onExploreAsGuest}
            >
              Explore as Guest
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="login-footer">
          <p className="login-signup-prompt">
            Don't have an account?{' '}
            <button 
              type="button" 
              className="link-btn"
              onClick={onNavigateToSignup}
            >
              Sign up here
            </button>
          </p>
          <div className="login-powered-by">
            <a href="https://neon.ai" target="_blank" rel="noopener noreferrer" className="footer-neon-link">
              <img src="/neon-logo.png" alt="" className="footer-neon-logo" />
              Powered by Neon.ai
            </a>
          </div>
        </div>
      </div>
      </div>
      <footer className="login-page-footer">
        <CopyrightNotice className="login-page-copyright" />
      </footer>
    </div>
  );
};

export default Login;
