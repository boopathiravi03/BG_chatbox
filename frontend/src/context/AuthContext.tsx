import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

interface User {
  user_id: string;
  username: string;
  email?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (username: string, password: string, email?: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Token stored in memory (not localStorage) to avoid XSS exposure.
// For persistent sessions across page refresh, we use sessionStorage
// which is cleared when the tab/browser closes.
let _memoryToken: string | null = null;

const TOKEN_KEY = 'bgai_session';

function readToken(): string | null {
  if (_memoryToken) return _memoryToken;
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(t: string | null): void {
  _memoryToken = t;
  try {
    if (t) {
      sessionStorage.setItem(TOKEN_KEY, t);
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // sessionStorage unavailable (e.g. private mode)
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: restore session from sessionStorage and validate token
  useEffect(() => {
    const stored = readToken();
    if (stored) {
      fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            setUser({ user_id: data.user_id, username: data.username, email: data.email });
            setToken(stored);
            _memoryToken = stored;
          } else {
            writeToken(null);
          }
        })
        .catch(() => writeToken(null))
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        writeToken(data.access_token);
        setToken(data.access_token);
        setUser({ user_id: data.user_id, username: data.username });
        return { success: true };
      }
      return { success: false, error: data.detail || 'Login failed.' };
    } catch {
      return { success: false, error: 'Network error. Is the backend running?' };
    }
  }, []);

  const register = useCallback(async (username: string, password: string, email = '') => {
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, email }),
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        writeToken(data.access_token);
        setToken(data.access_token);
        setUser({ user_id: data.user_id, username: data.username });
        return { success: true };
      }
      return { success: false, error: data.detail || 'Registration failed.' };
    } catch {
      return { success: false, error: 'Network error. Is the backend running?' };
    }
  }, []);

  const logout = useCallback(() => {
    writeToken(null);
    setToken(null);
    setUser(null);
    _memoryToken = null;
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, register, logout, isAuthenticated: !!user }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

/** Returns the current token for use in API calls. */
export function getAuthToken(): string | null {
  return readToken();
}
