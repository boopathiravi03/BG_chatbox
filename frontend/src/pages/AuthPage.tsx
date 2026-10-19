import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface AuthPageProps {
  onSuccess?: () => void;
}

export default function AuthPage({ onSuccess }: AuthPageProps) {
  const { login, register, loginWithGoogle } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let result;
      if (mode === 'login') {
        result = await login(username, password);
      } else {
        if (password.length < 6) {
          setError('Password must be at least 6 characters.');
          setLoading(false);
          return;
        }
        result = await register(username, password, email);
      }

      if (result.success) {
        onSuccess?.();
      } else {
        setError(result.error || 'Authentication failed.');
      }
    } catch {
      setError('Unexpected error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError('');
    setGoogleLoading(true);
    try {
      const result = await loginWithGoogle();
      if (result.success) {
        onSuccess?.();
      } else {
        setError(result.error || 'Google sign-in failed.');
      }
    } catch {
      setError('Google sign-in encountered an unexpected error.');
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a]">
      <div className="w-full max-w-md px-8 py-10 rounded-2xl border border-white/10 bg-[#111] shadow-2xl">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="text-3xl font-bold text-white tracking-tight mb-1">
            <span className="text-[#7c6bff]">BG</span> AI
          </div>
          <p className="text-zinc-400 text-sm">AI Data Intelligence Platform</p>
        </div>

        {/* Tab switcher */}
        <div className="flex bg-white/5 rounded-lg p-1 mb-6">
          <button
            className={`flex-1 py-2 text-sm rounded-md font-medium transition-all ${
              mode === 'login'
                ? 'bg-[#7c6bff] text-white shadow'
                : 'text-zinc-400 hover:text-white'
            }`}
            onClick={() => { setMode('login'); setError(''); }}
          >
            Sign In
          </button>
          <button
            className={`flex-1 py-2 text-sm rounded-md font-medium transition-all ${
              mode === 'register'
                ? 'bg-[#7c6bff] text-white shadow'
                : 'text-zinc-400 hover:text-white'
            }`}
            onClick={() => { setMode('register'); setError(''); }}
          >
            Create Account
          </button>
        </div>

        {/* 1-Click Google Sign-in */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={googleLoading || loading}
          className="w-full py-2.5 px-4 rounded-lg bg-white/10 hover:bg-white/15 border border-white/15 text-white font-medium text-sm transition flex items-center justify-center gap-3 mb-4 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="#EA4335"
              d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"
            />
            <path
              fill="#4285F4"
              d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
            />
            <path
              fill="#FBBC05"
              d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12 0 14.5s.7 4.8 1.9 7.2l3.7-2.9z"
            />
            <path
              fill="#34A853"
              d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16.5C3.7 20.2 7.5 23.5 12 23.5z"
            />
          </svg>
          {googleLoading ? 'Signing in with Google...' : 'Continue with Google'}
        </button>

        <div className="flex items-center gap-3 my-4">
          <div className="flex-1 h-px bg-white/10"></div>
          <span className="text-xs text-zinc-500 uppercase tracking-wider">or</span>
          <div className="flex-1 h-px bg-white/10"></div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-zinc-400 mb-1 font-medium uppercase tracking-wider">
              {mode === 'login' ? 'Email or Username' : 'Username'}
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={mode === 'login' ? 'you@example.com or username' : 'your_username'}
              required
              autoComplete="username"
              className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none focus:border-[#7c6bff] focus:ring-1 focus:ring-[#7c6bff] text-sm transition"
            />
          </div>

          {mode === 'register' && (
            <div>
              <label className="block text-xs text-zinc-400 mb-1 font-medium uppercase tracking-wider">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none focus:border-[#7c6bff] focus:ring-1 focus:ring-[#7c6bff] text-sm transition"
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-zinc-400 mb-1 font-medium uppercase tracking-wider">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'register' ? 'Min 6 characters' : '••••••••'}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none focus:border-[#7c6bff] focus:ring-1 focus:ring-[#7c6bff] text-sm transition"
            />
          </div>

          {error && (
            <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || googleLoading}
            className="w-full py-3 rounded-lg bg-[#7c6bff] hover:bg-[#6d5ce6] text-white font-semibold text-sm transition disabled:opacity-50 disabled:cursor-not-allowed mt-2"
          >
            {loading
              ? (mode === 'login' ? 'Signing in...' : 'Creating account...')
              : (mode === 'login' ? 'Sign In' : 'Create Account')
            }
          </button>
        </form>

        <p className="text-center text-zinc-600 text-xs mt-6">
          By using BG AI you agree to our{' '}
          <a href="https://thebg.co.in" className="text-zinc-500 hover:text-zinc-400 underline">
            Terms of Service
          </a>
        </p>
      </div>
    </div>
  );
}
