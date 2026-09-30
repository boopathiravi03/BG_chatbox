import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface AuthPageProps {
  onSuccess?: () => void;
}

export default function AuthPage({ onSuccess }: AuthPageProps) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-zinc-400 mb-1 font-medium uppercase tracking-wider">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="your_username"
              required
              autoComplete="username"
              className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:outline-none focus:border-[#7c6bff] focus:ring-1 focus:ring-[#7c6bff] text-sm transition"
            />
          </div>

          {mode === 'register' && (
            <div>
              <label className="block text-xs text-zinc-400 mb-1 font-medium uppercase tracking-wider">
                Email <span className="text-zinc-600">(optional)</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
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
            disabled={loading}
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
