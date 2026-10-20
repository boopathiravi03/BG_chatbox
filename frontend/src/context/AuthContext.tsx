import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
} from 'firebase/auth';
import { auth, googleProvider, firebaseConfig } from '../lib/firebase';
import { getApiBase, getAuthToken, setAuthToken } from '../services/api';

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

/**
 * Safe diagnostic logging for the authentication pipeline.
 * Formats stage markers, HTTP statuses, Firebase error codes, and backend categories.
 * Strictly redacts passwords, tokens, API keys, and sensitive data.
 */
function logAuthDiagnostic(stage: string, details?: Record<string, any>) {
  const sanitized: Record<string, any> = {
    stage,
    timestamp: new Date().toISOString(),
  };

  if (details) {
    for (const [k, v] of Object.entries(details)) {
      const lower = k.toLowerCase();
      if (
        lower.includes('password') ||
        lower.includes('token') ||
        lower.includes('secret') ||
        lower.includes('credential') ||
        lower.includes('apikey')
      ) {
        sanitized[k] = '[REDACTED]';
      } else {
        sanitized[k] = v;
      }
    }
  }

  console.log(`[BG AI Auth Flow] [${stage}] ${JSON.stringify(sanitized)}`);
}

/**
 * Resilient helper to communicate with the FastAPI backend.
 * Automatically injects the per-launch desktop authentication secret and Bearer token.
 */
async function authBackendFetch(
  endpoint: string,
  options: { method?: string; body?: any; token?: string | null } = {}
): Promise<Response> {
  const base = getApiBase();
  const url = `${base}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  if (typeof window !== 'undefined' && window.electronAPI?.getDesktopSecret) {
    try {
      const secret = window.electronAPI.getDesktopSecret();
      if (secret) headers['X-BGAI-Desktop-Secret'] = secret;
    } catch {
      // ignore
    }
  }

  const activeToken = options.token !== undefined ? options.token : getAuthToken();
  if (activeToken) {
    headers['Authorization'] = `Bearer ${activeToken}`;
  }

  return fetch(url, {
    method: options.method || (options.body !== undefined ? 'POST' : 'GET'),
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

/**
 * Translates Firebase / backend error codes into clear, actionable messages.
 * Redacts any sensitive credentials before logging.
 */
function formatAuthError(err: any): string {
  if (!err) return 'Invalid username/email or password.';
  const code = err.code || '';
  const msg = err.message || '';

  // Redact any query param keys or tokens from message
  const safeMsg = msg.replace(/key=[A-Za-z0-9_-]+/g, 'key=[REDACTED]');
  logAuthDiagnostic('ERROR_FORMATTED', { code, safeMessage: safeMsg });

  switch (code) {
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
      return 'Invalid username/email or password.';
    case 'auth/invalid-email':
      return 'Please enter a valid email address.';
    case 'auth/email-already-in-use':
      return 'An account with this email address already exists. Please sign in instead.';
    case 'auth/weak-password':
      return 'Password must be at least 6 characters long.';
    case 'auth/operation-not-allowed':
      return 'Sign-in provider is not enabled in Firebase Console. Please verify Authentication > Sign-in method settings.';
    case 'auth/too-many-requests':
      return 'Too many failed sign-in attempts. Please wait a few moments and try again.';
    case 'auth/network-request-failed':
      return 'Unable to reach cloud authentication servers. Please verify your internet connection or use local credentials.';
    case 'auth/popup-closed-by-user':
      return 'Sign-in window was closed before completion.';
    case 'auth/popup-blocked':
      return 'Sign-in window was blocked. Please permit popups or use email/password sign-in.';
    case 'auth/unauthorized-domain': {
      const currentHost = typeof window !== 'undefined' ? window.location.hostname : 'thebg.co.in';
      return `Domain not authorized in Firebase: "${currentHost}". Please add "${currentHost}" (and "thebg.co.in") to Firebase Console > Authentication > Settings > Authorized domains.`;
    }
    case 'auth/internal-error':
      return 'Authentication could not be completed. Please verify your credentials and try again.';
    default:
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        return 'Network connection error. Please verify your internet connection and local backend status.';
      }
      return safeMsg || 'Authentication failed. Please verify your credentials and try again.';
  }
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    logAuthDiagnostic('USER_LOGOUT');
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
      logAuthDiagnostic('SESSION_EXPIRED');
      logout();
    };
    window.addEventListener('bgai:auth-expired', handleAuthExpired);
    return () => window.removeEventListener('bgai:auth-expired', handleAuthExpired);
  }, [logout]);

  // On mount: verify config and restore session from storage
  useEffect(() => {
    logAuthDiagnostic('CONFIG_VERIFIED', {
      projectId: firebaseConfig.projectId,
      authDomain: firebaseConfig.authDomain,
      hasApiKey: Boolean(firebaseConfig.apiKey),
      isDesktop: typeof window !== 'undefined' && Boolean(window.electronAPI?.isDesktop?.()),
    });

    const stored = getAuthToken();
    if (stored) {
      logAuthDiagnostic('SESSION_RESTORE_START');
      authBackendFetch('/auth/me', { token: stored })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            setUser({ user_id: data.user_id, username: data.username, email: data.email });
            setToken(stored);
            logAuthDiagnostic('SESSION_RESTORE_SUCCESS', { username: data.username });
          } else {
            logAuthDiagnostic('SESSION_RESTORE_FAILED', { status: res.status });
            logout();
          }
        })
        .catch((err) => {
          logAuthDiagnostic('SESSION_RESTORE_NETWORK_ERROR', { error: err?.message });
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

    const isEmailInput = cleanIdent.includes('@');
    logAuthDiagnostic('SIGN_IN_START', { isEmail: isEmailInput, identifierLength: cleanIdent.length });

    // Helper: exchange Firebase token with backend
    const exchangeFirebaseToken = async (cred: any, displayUsername: string) => {
      logAuthDiagnostic('FIREBASE_TOKEN_RETRIEVAL_START');
      const idToken = await cred.user.getIdToken();
      logAuthDiagnostic('FIREBASE_TOKEN_RETRIEVAL_SUCCESS');

      logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_START');
      const res = await authBackendFetch('/auth/firebase', {
        body: {
          id_token: idToken,
          email: cred.user.email,
          username: displayUsername,
        },
      });

      logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_STATUS', { status: res.status });
      if (res.ok) {
        const data = await res.json();
        if (data.access_token) {
          setAuthToken(data.access_token);
          setToken(data.access_token);
          setUser({ user_id: data.user_id, username: data.username, email: data.email });
          logAuthDiagnostic('SIGN_IN_COMPLETE', { method: 'firebase' });
          return { success: true };
        }
      }
      const errData = await res.json().catch(() => ({}));
      return { success: false, error: errData.detail || 'Backend sync failed' };
    };

    // Helper: try local SQLite login
    const tryLocalLogin = async () => {
      try {
        logAuthDiagnostic('LOCAL_SQLITE_AUTH_START', { identifier: cleanIdent });
        const localRes = await authBackendFetch('/auth/login', {
          body: { username: cleanIdent, password },
        });
        logAuthDiagnostic('LOCAL_SQLITE_AUTH_STATUS', { status: localRes.status });

        if (localRes.ok) {
          const localData = await localRes.json();
          if (localData.access_token) {
            setAuthToken(localData.access_token);
            setToken(localData.access_token);
            setUser({
              user_id: localData.user_id,
              username: localData.username,
              email: localData.email,
            });
            logAuthDiagnostic('SIGN_IN_COMPLETE', { method: 'local_sqlite' });
            return { success: true };
          }
        } else if (localRes.status === 403) {
          return {
            success: false,
            error: 'Desktop security verification failed. Please restart BG AI.',
          };
        } else {
          const localErr = await localRes.json().catch(() => ({}));
          return {
            success: false,
            error: localErr.detail || 'Invalid username or password.',
          };
        }
      } catch (locErr: any) {
        logAuthDiagnostic('LOCAL_SQLITE_AUTH_ERROR', { error: locErr?.message });
        return {
          success: false,
          error: 'Cannot connect to local BG AI backend. Please verify the application service is running.',
        };
      }
      return { success: false, error: 'Invalid username/email or password.' };
    };

    const isDesktop = typeof window !== 'undefined' && Boolean(window.electronAPI?.isDesktop?.());

    // In desktop mode: always try local SQLite first for instantaneous, reliable sign-in
    if (isDesktop) {
      const localResult = await tryLocalLogin();
      if (localResult.success) return localResult;
      // If local returned an explicit instruction (like Google Auth Required), return immediately
      if (localResult.error && localResult.error.includes("Google Sign-In")) {
        return localResult;
      }
      if (localResult.error && localResult.error.includes("Incorrect password")) {
        return localResult;
      }
    }

    // If an email is supplied (or local user not found on desktop): try Firebase Authentication
    if (isEmailInput) {
      logAuthDiagnostic('FIREBASE_SIGN_IN_START', { email: cleanIdent });
      try {
        const cred = await signInWithEmailAndPassword(auth, cleanIdent, password);
        logAuthDiagnostic('FIREBASE_SIGN_IN_SUCCESS');
        const exchange = await exchangeFirebaseToken(cred, cleanIdent.split('@')[0]);
        if (exchange.success) return exchange;
      } catch (fbErr: any) {
        logAuthDiagnostic('FIREBASE_SIGN_IN_FAILED', { code: fbErr?.code, message: fbErr?.message });
        if (fbErr?.code === 'auth/too-many-requests' || fbErr?.code === 'auth/user-disabled') {
          return { success: false, error: formatAuthError(fbErr) };
        }
      }

      if (!isDesktop) {
        const localResult = await tryLocalLogin();
        return localResult;
      }
    }

    // Try local SQLite for web / non-email inputs
    const localResult = await tryLocalLogin();
    if (localResult.success) return localResult;

    // If local failed with invalid credentials, check if username maps to a Firebase account via email lookup
    try {
      const lookupRes = await authBackendFetch('/auth/lookup-email', {
        body: { username: cleanIdent },
      });
      if (lookupRes.ok) {
        const lookupData = await lookupRes.json();
        if (lookupData.found && lookupData.email) {
          logAuthDiagnostic('RESOLVE_USERNAME_SUCCESS', { hasEmail: true });
          const cred = await signInWithEmailAndPassword(auth, lookupData.email, password);
          logAuthDiagnostic('FIREBASE_SIGN_IN_SUCCESS');
          const exchange = await exchangeFirebaseToken(cred, cleanIdent);
          if (exchange.success) return exchange;
        }
      }
    } catch (e: any) {
      logAuthDiagnostic('RESOLVE_USERNAME_NETWORK_ERROR', { error: e?.message });
    }

    return localResult;
  }, []);

  const register = useCallback(async (username: string, password: string, email = '') => {
    const cleanUser = username.trim();
    if (!cleanUser || !password) {
      return { success: false, error: 'Username and password are required.' };
    }
    if (password.length < 6) {
      return { success: false, error: 'Password must be at least 6 characters long.' };
    }

    const regEmail = email && email.trim() ? email.trim() : `${cleanUser.toLowerCase()}@bgai.app`;
    logAuthDiagnostic('REGISTER_START', {
      username: cleanUser,
      hasCustomEmail: Boolean(email && email.trim()),
    });

    let firebaseError: any = null;

    // 1. Try Firebase Authentication user creation
    try {
      logAuthDiagnostic('FIREBASE_CREATE_USER_START');
      const cred = await createUserWithEmailAndPassword(auth, regEmail, password);
      logAuthDiagnostic('FIREBASE_CREATE_USER_SUCCESS');

      if (cleanUser) {
        try {
          await updateProfile(cred.user, { displayName: cleanUser });
        } catch {
          // ignore
        }
      }

      logAuthDiagnostic('FIREBASE_TOKEN_RETRIEVAL_START');
      const idToken = await cred.user.getIdToken();

      logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_START');
      const res = await authBackendFetch('/auth/firebase', {
        body: {
          id_token: idToken,
          email: cred.user.email,
          username: cleanUser,
        },
      });

      logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_STATUS', { status: res.status });

      if (res.ok) {
        const data = await res.json();
        if (data.access_token) {
          setAuthToken(data.access_token);
          setToken(data.access_token);
          setUser({ user_id: data.user_id, username: data.username, email: data.email });
          logAuthDiagnostic('REGISTER_COMPLETE', { method: 'firebase' });
          return { success: true };
        }
      } else {
        const data = await res.json().catch(() => ({}));
        logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_REJECTED', { detail: data.detail });
      }
    } catch (err: any) {
      firebaseError = err;
      logAuthDiagnostic('FIREBASE_CREATE_USER_FAILED', {
        code: err?.code,
        category: 'firebase_register_error',
      });
    }

    // If Firebase specifically returned an account validation error (email taken, weak password, invalid email),
    // immediately return that clear error instead of falling back to SQLite!
    if (
      firebaseError &&
      ['auth/email-already-in-use', 'auth/weak-password', 'auth/invalid-email'].includes(firebaseError.code)
    ) {
      return { success: false, error: formatAuthError(firebaseError) };
    }

    // 2. Fallback: If Firebase failed due to offline network, register locally in backend
    logAuthDiagnostic('LOCAL_SQLITE_REGISTER_START');
    try {
      const localRes = await authBackendFetch('/auth/register', {
        body: {
          username: cleanUser,
          password: password,
          email: regEmail,
        },
      });

      logAuthDiagnostic('LOCAL_SQLITE_REGISTER_STATUS', { status: localRes.status });

      if (localRes.ok) {
        const localData = await localRes.json();
        if (localData.access_token) {
          setAuthToken(localData.access_token);
          setToken(localData.access_token);
          setUser({ user_id: localData.user_id, username: localData.username, email: regEmail });
          logAuthDiagnostic('REGISTER_COMPLETE', { method: 'local_sqlite' });
          return { success: true };
        }
      } else {
        const localErr = await localRes.json().catch(() => ({}));
        logAuthDiagnostic('LOCAL_SQLITE_REGISTER_REJECTED', { detail: localErr.detail });
        if (localErr.detail) {
          return { success: false, error: localErr.detail };
        }
      }
    } catch (locErr: any) {
      logAuthDiagnostic('LOCAL_SQLITE_REGISTER_ERROR', { error: locErr?.message });
    }

    return { success: false, error: formatAuthError(firebaseError) };
  }, []);

  const loginWithGoogle = useCallback(async () => {
    logAuthDiagnostic('GOOGLE_SIGN_IN_START');

    // 1. Desktop Flow: Native System Browser + Loopback Server (RFC 8252)
    if (typeof window !== 'undefined' && window.electronAPI?.isDesktop?.()) {
      try {
        logAuthDiagnostic('DESKTOP_GOOGLE_AUTH_START');
        const desktopResult = await window.electronAPI.startGoogleAuth?.();
        if (!desktopResult || !desktopResult.success) {
          logAuthDiagnostic('DESKTOP_GOOGLE_AUTH_FAILED', { error: desktopResult?.error });
          return {
            success: false,
            error: desktopResult?.error || 'Google sign-in was cancelled.',
          };
        }

        logAuthDiagnostic('DESKTOP_GOOGLE_AUTH_SUCCESS', { email: desktopResult.email });
        logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_START');

        // Exchange Google OAuth token with backend dedicated /auth/google endpoint (with fallback to /auth/firebase)
        let res = await authBackendFetch('/auth/google', {
          body: {
            id_token: desktopResult.idToken,
            access_token: desktopResult.accessToken,
          },
        });

        if (!res.ok && res.status === 404) {
          res = await authBackendFetch('/auth/firebase', {
            body: {
              id_token: desktopResult.idToken,
            },
          });
        }

        logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_STATUS', { status: res.status });
        if (res.ok) {
          const data = await res.json();
          if (data.access_token) {
            setAuthToken(data.access_token);
            setToken(data.access_token);
            setUser({ user_id: data.user_id, username: data.username, email: data.email });
            logAuthDiagnostic('SIGN_IN_COMPLETE', { method: 'google_oauth_desktop' });
            return { success: true };
          }
        }

        const data = await res.json().catch(() => ({}));
        logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_REJECTED', { detail: data.detail });
        return { success: false, error: data.detail || 'Backend session creation failed.' };
      } catch (err: any) {
        logAuthDiagnostic('DESKTOP_GOOGLE_AUTH_ERROR', { error: err?.message });
        return { success: false, error: err?.message || 'Google sign-in encountered an error.' };
      }
    }

    // 2. Web Browser Flow: standard signInWithPopup
    let firebaseError: any = null;
    logAuthDiagnostic('GOOGLE_POPUP_SIGN_IN_START');
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      logAuthDiagnostic('GOOGLE_POPUP_SIGN_IN_SUCCESS', { email: cred.user.email });

      logAuthDiagnostic('FIREBASE_TOKEN_RETRIEVAL_START');
      const idToken = await cred.user.getIdToken();

      logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_START');
      const res = await authBackendFetch('/auth/firebase', {
        body: {
          id_token: idToken,
          email: cred.user.email,
          username: cred.user.displayName || cred.user.email?.split('@')[0] || 'google_user',
        },
      });

      logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_STATUS', { status: res.status });

      if (res.ok) {
        const data = await res.json();
        if (data.access_token) {
          setAuthToken(data.access_token);
          setToken(data.access_token);
          setUser({ user_id: data.user_id, username: data.username, email: data.email });
          logAuthDiagnostic('SIGN_IN_COMPLETE', { method: 'google_oauth_web' });
          return { success: true };
        }
      } else {
        const data = await res.json().catch(() => ({}));
        logAuthDiagnostic('BACKEND_FIREBASE_EXCHANGE_REJECTED', { detail: data.detail });
        return { success: false, error: data.detail || 'Google sign-in exchange with backend failed.' };
      }
      return { success: false, error: 'Google sign-in failed.' };
    } catch (err: any) {
      firebaseError = err;
      logAuthDiagnostic('GOOGLE_POPUP_SIGN_IN_FAILED', {
        code: err?.code,
        message: err?.message,
      });
    }

    return { success: false, error: formatAuthError(firebaseError) };
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
