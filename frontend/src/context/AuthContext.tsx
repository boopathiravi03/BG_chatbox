import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
} from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';
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
  login: (usernameOrEmail: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (username: string, password: string, email?: string) => Promise<{ success: boolean; error?: string }>;
  loginWithGoogle: () => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    try {
      signOut(auth);
    } catch {
      // ignore
    }
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
        .catch(() => {
          // If backend was not reached on mount, don't crash
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [logout]);

  const login = useCallback(async (usernameOrEmail: string, password: string) => {
    const cleanIdent = usernameOrEmail.trim();
    if (!cleanIdent || !password) {
      return { success: false, error: 'Please enter both username/email and password.' };
    }

    const email = cleanIdent.includes('@') ? cleanIdent : `${cleanIdent.toLowerCase()}@bgai.app`;

    // 1. Try Firebase Authentication
    try {
      const cred = await signInWithEmailAndPassword(auth, email, password);
      const idToken = await cred.user.getIdToken();

      const res = await fetch(`${API_BASE}/auth/firebase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_token: idToken,
          email: cred.user.email,
          username: cleanIdent.includes('@') ? cred.user.email?.split('@')[0] : cleanIdent,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        return { success: false, error: data.detail || 'Authentication exchange with backend failed.' };
      }

      const data = await res.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        setToken(data.access_token);
        setUser({ user_id: data.user_id, username: data.username, email: data.email });
        return { success: true };
      }
    } catch (fbErr: any) {
      // 2. Fallback to local auth for legacy accounts (e.g. created directly in SQLite)
      try {
        const localRes = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: cleanIdent, password }),
        });
        if (localRes.ok) {
          const localData = await localRes.json();
          if (localData.access_token) {
            setAuthToken(localData.access_token);
            setToken(localData.access_token);
            setUser({ user_id: localData.user_id, username: localData.username });
            return { success: true };
          }
        }
      } catch (localErr: any) {
        if (localErr?.message?.includes('fetch') || fbErr?.message?.includes('fetch')) {
          return {
            success: false,
            error: 'Backend unreachable. Make sure FastAPI backend is running on http://127.0.0.1:8001',
          };
        }
      }

      // Friendly Firebase errors
      if (
        fbErr.code === 'auth/invalid-credential' ||
        fbErr.code === 'auth/wrong-password' ||
        fbErr.code === 'auth/user-not-found'
      ) {
        return { success: false, error: 'Invalid username/email or password.' };
      }
      if (fbErr.code === 'auth/operation-not-allowed') {
        return {
          success: false,
          error: 'Email/Password sign-in is not enabled in Firebase Console. Go to Authentication > Sign-in method and enable it.',
        };
      }
      if (fbErr.code === 'auth/too-many-requests') {
        return { success: false, error: 'Too many failed login attempts. Please wait a moment and try again.' };
      }
      if (fbErr.message === 'Failed to fetch' || fbErr.code === 'auth/network-request-failed') {
        return {
          success: false,
          error: 'Network error. Please verify backend is running on http://127.0.0.1:8001 and internet is connected.',
        };
      }
      return { success: false, error: fbErr.message || 'Login failed.' };
    }

    return { success: false, error: 'Login failed.' };
  }, []);

  const register = useCallback(async (username: string, password: string, email = '') => {
    try {
      const cleanUser = username.trim();
      const regEmail = (email && email.trim()) ? email.trim() : `${cleanUser.toLowerCase()}@bgai.app`;

      const cred = await createUserWithEmailAndPassword(auth, regEmail, password);
      if (cleanUser) {
        try {
          await updateProfile(cred.user, { displayName: cleanUser });
        } catch {
          // ignore
        }
      }

      const idToken = await cred.user.getIdToken();

      const res = await fetch(`${API_BASE}/auth/firebase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_token: idToken,
          email: cred.user.email,
          username: cleanUser,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        return { success: false, error: data.detail || 'Registration exchange with backend failed.' };
      }

      const data = await res.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        setToken(data.access_token);
        setUser({ user_id: data.user_id, username: data.username, email: data.email });
        return { success: true };
      }
      return { success: false, error: 'Registration failed.' };
    } catch (err: any) {
      if (err.code === 'auth/email-already-in-use') {
        return { success: false, error: 'This email or username already exists. Please sign in.' };
      }
      if (err.code === 'auth/weak-password') {
        return { success: false, error: 'Password must be at least 6 characters.' };
      }
      if (err.code === 'auth/operation-not-allowed') {
        return {
          success: false,
          error: 'Email/Password is not enabled in your Firebase Console. Please enable it in Authentication > Sign-in method.',
        };
      }
      if (err.message === 'Failed to fetch' || err.code === 'auth/network-request-failed') {
        return {
          success: false,
          error: 'Network error. Please verify backend is running on http://127.0.0.1:8001 and internet is connected.',
        };
      }
      return { success: false, error: err.message || 'Registration failed.' };
    }
  }, []);

  const loginWithGoogle = useCallback(async () => {
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      const idToken = await cred.user.getIdToken();

      const res = await fetch(`${API_BASE}/auth/firebase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_token: idToken,
          email: cred.user.email,
          username: cred.user.displayName || cred.user.email?.split('@')[0],
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        return { success: false, error: data.detail || 'Google sign-in exchange with backend failed.' };
      }

      const data = await res.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        setToken(data.access_token);
        setUser({ user_id: data.user_id, username: data.username, email: data.email });
        return { success: true };
      }
      return { success: false, error: 'Google sign-in failed.' };
    } catch (err: any) {
      if (err.code === 'auth/popup-closed-by-user') {
        return { success: false, error: 'Sign-in cancelled.' };
      }
      if (err.code === 'auth/operation-not-allowed') {
        return {
          success: false,
          error: 'Google Sign-In is not enabled in Firebase Console. Go to Authentication > Sign-in method and enable Google.',
        };
      }
      if (err.message === 'Failed to fetch' || err.code === 'auth/network-request-failed') {
        return {
          success: false,
          error: 'Network error. Please verify backend is running on http://127.0.0.1:8001 and internet is connected.',
        };
      }
      return { success: false, error: err.message || 'Google sign-in failed.' };
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        loginWithGoogle,
        logout,
        isAuthenticated: !!user,
      }}
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
