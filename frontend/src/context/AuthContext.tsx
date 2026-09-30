import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { API_BASE, getAuthToken, setAuthToken } from '../services/api';

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  // Listen for 401 session expiration event
  useEffect(() => {
    const handleAuthExpired = () => {
      logout();
    };
    window.addEventListener('bgai:auth-expired', handleAuthExpired);
    return () => window.removeEventListener('bgai:auth-expired', handleAuthExpired);
  }, [logout]);

  // On mount: restore session from sessionStorage and validate token
  useEffect(() => {
    const stored = getAuthToken();
    if (stored) {
      fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${stored}` },
      })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            setUser({ user_id: data.user_id, username: data.username, email: data.email });
            setToken(stored);
          } else {
            logout();
          }
        })
        .catch(() => logout())
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        setAuthToken(data.access_token);
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
        setAuthToken(data.access_token);
        setToken(data.access_token);
        setUser({ user_id: data.user_id, username: data.username });
        return { success: true };
      }
      return { success: false, error: data.detail || 'Registration failed.' };
    } catch {
      return { success: false, error: 'Network error. Is the backend running?' };
    }
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

export { getAuthToken } from '../services/api';
