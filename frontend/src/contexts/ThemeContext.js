import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const ThemeContext = createContext();
const THEME_KEY = 'theme';

const getSystemTheme = () =>
  (typeof window !== 'undefined' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches)
    ? 'dark'
    : 'light';

const readPreference = () => {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'light' || saved === 'dark' || saved === 'system') return saved;
    // Legacy values or empty → System (follow OS)
    if (saved === 'auto' || saved === 'default' || saved === '') return 'system';
  } catch {
    /* ignore */
  }
  return 'system';
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }) => {
  const [preference, setPreferenceState] = useState(readPreference);
  const [systemTheme, setSystemTheme] = useState(getSystemTheme);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e) => setSystemTheme(e.matches ? 'dark' : 'light');
    mq.addEventListener('change', onChange);
    setSystemTheme(mq.matches ? 'dark' : 'light');
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const theme = preference === 'system' ? systemTheme : preference;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem(THEME_KEY, preference);
    } catch {
      /* ignore */
    }
  }, [preference]);

  const setThemePreference = useCallback((next) => {
    if (next === 'light' || next === 'dark' || next === 'system') {
      setPreferenceState(next);
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setPreferenceState((prev) => {
      const resolved = prev === 'system' ? getSystemTheme() : prev;
      return resolved === 'light' ? 'dark' : 'light';
    });
  }, []);

  const value = {
    theme,
    preference,
    setThemePreference,
    toggleTheme,
    isLight: theme === 'light',
    isDark: theme === 'dark',
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};
