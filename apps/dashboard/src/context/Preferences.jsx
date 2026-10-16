import { createContext, useContext, useState } from 'react';
import { DEFAULT_PREFERENCES, PREFERENCES_KEY, validatePreferences } from '../lib/preferences';

const PreferencesContext = createContext(null);

export function PreferencesProvider({ children }) {
  const [preferences, setPreferences] = useState(() => {
    try {
      const stored = localStorage.getItem(PREFERENCES_KEY);
      return stored ? validatePreferences(JSON.parse(stored)) : DEFAULT_PREFERENCES;
    } catch { return DEFAULT_PREFERENCES; }
  });
  function savePreferences(value) {
    const next = validatePreferences(value);
    // Persist before updating the UI so a storage failure is never reported as success.
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
    setPreferences(next);
  }
  return <PreferencesContext.Provider value={{ preferences, savePreferences }}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() { return useContext(PreferencesContext); }
