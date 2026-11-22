import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth.js';
import { signInWithGoogle, isLiveSupabase } from '../../services/auth.js';

export function LoginPage({ onLoginSuccess, onEnableDemoMode, onNavigateSignUp }) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (!isLiveSupabase) {
        throw new Error('Sign-in is not available right now. Try "Explore Demo" below, or contact your administrator.');
      }
      await signIn({ email, password });
      onLoginSuccess && onLoginSuccess();
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError('');
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(err.message || 'Google sign-in failed. Please try again.');
    }
  };

  const inputStyle = {
    width: '100%',
    padding: '11px 14px',
    boxSizing: 'border-box',
    borderRadius: '8px',
    border: '1.5px solid #d1dbd4',
    fontSize: '14px',
    outline: 'none',
    transition: 'border-color 0.15s',
    background: '#fff',
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: '#f4f7f5' }}>

      {/* Left — Brand Hero (hidden on small screens via inline — acceptable for MVP) */}
      <div style={{
        flex: '0 0 42%',
        background: 'linear-gradient(150deg, #18352f 0%, #0B1B15 100%)',
        color: 'white',
        padding: '56px 48px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: 36, height: 36, borderRadius: '10px',
            background: 'rgba(74,222,128,0.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '18px'
          }}>💰</div>
          <span style={{ fontSize: '20px', fontWeight: 700, letterSpacing: '-0.3px' }}>FinGenie</span>
        </div>

        {/* Tagline */}
        <div>
          <h2 style={{ fontSize: '30px', lineHeight: 1.25, margin: '0 0 14px 0', fontWeight: 700 }}>
            Your finances,<br />
            <span style={{ color: '#4ADE80' }}>finally in focus.</span>
          </h2>
          <p style={{ color: '#b3c2b9', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>
            Upload bank statements. Instantly see categorised transactions,
            balances, and insights — all in one secure workspace.
          </p>

          {/* Feature pills */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '28px' }}>
            {[
              { icon: '🔒', text: 'End-to-end encrypted storage' },
              { icon: '📊', text: 'Automatic transaction categorisation' },
              { icon: '🌐', text: 'Multi-currency statement support' },
            ].map(({ icon, text }) => (
              <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#d1e8db' }}>
                <span style={{ fontSize: '15px' }}>{icon}</span> {text}
              </div>
            ))}
          </div>
        </div>

        <div style={{ fontSize: '11px', color: '#6a8575' }}>
          © 2025 FinGenie · Secure sign-in
        </div>
      </div>

      {/* Right — Form panel */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 32px' }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>

          <h2 style={{ fontSize: '23px', fontWeight: 700, margin: '0 0 6px 0', color: '#1a2e28' }}>Welcome back</h2>
          <p style={{ color: '#66776d', fontSize: '14px', margin: '0 0 28px 0' }}>
            Sign in to your account to continue
          </p>

          {/* Error banner */}
          {error && (
            <div style={{
              background: '#FEF2F2', color: '#B91C1C',
              padding: '12px 14px', borderRadius: '8px',
              marginBottom: '18px', fontSize: '13px',
              border: '1px solid #FCA5A5',
              display: 'flex', gap: '8px', alignItems: 'flex-start'
            }}>
              <span>⚠️</span> <span>{error}</span>
            </div>
          )}

          {/* Google SSO */}
          <button
            type="button"
            onClick={handleGoogle}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: '10px', background: 'white', color: '#1a2e28',
              border: '1.5px solid #d1dbd4', padding: '11px', borderRadius: '8px',
              fontWeight: 600, fontSize: '14px', cursor: 'pointer', marginBottom: '20px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.2l6.7-6.7C35.8 2.5 30.3 0 24 0 14.7 0 6.7 5.4 2.9 13.3l7.8 6C12.4 13 17.8 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17z"/>
              <path fill="#FBBC05" d="M10.7 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.8-6A23.9 23.9 0 0 0 0 24c0 3.9.9 7.5 2.5 10.7l8.2-6z"/>
              <path fill="#34A853" d="M24 48c6.5 0 12-2.1 16-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.2-13.4-9.9l-8.2 6C6.5 42.5 14.6 48 24 48z"/>
            </svg>
            Continue with Google
          </button>

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
            <div style={{ flex: 1, height: '1px', background: '#e2e8e4' }} />
            <span style={{ fontSize: '12px', color: '#8fa297', fontWeight: 500 }}>or sign in with email</span>
            <div style={{ flex: 1, height: '1px', background: '#e2e8e4' }} />
          </div>

          {/* Email + Password form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: '#2d4038' }}>
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                style={inputStyle}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label style={{ fontSize: '13px', fontWeight: 600, color: '#2d4038' }}>Password</label>
                <span style={{ fontSize: '12px', color: '#1d8a60', fontWeight: 500, cursor: 'pointer' }}>
                  Forgot password?
                </span>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{ ...inputStyle, paddingRight: '44px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  style={{
                    position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', fontSize: '15px', color: '#8fa297'
                  }}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                background: loading ? '#a0bfb4' : '#18352f',
                color: 'white', border: 'none',
                padding: '12px', borderRadius: '8px',
                fontWeight: 600, fontSize: '15px',
                cursor: loading ? 'not-allowed' : 'pointer',
                marginTop: '4px', letterSpacing: '0.01em',
              }}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          {/* Demo Mode */}
          <div style={{ marginTop: '14px' }}>
            <button
              type="button"
              onClick={onEnableDemoMode}
              style={{
                width: '100%',
                background: 'rgba(29,138,96,0.07)',
                color: '#1d8a60',
                border: '1.5px dashed rgba(29,138,96,0.35)',
                padding: '10px 16px', borderRadius: '8px',
                fontWeight: 600, fontSize: '13px', cursor: 'pointer',
              }}
            >
              ✨ Explore Demo — no account needed
            </button>
          </div>

          {/* Sign-up link */}
          <p style={{ marginTop: '24px', textAlign: 'center', fontSize: '13px', color: '#66776d' }}>
            Don&apos;t have an account?{' '}
            <span
              onClick={onNavigateSignUp}
              style={{ color: '#1d8a60', fontWeight: 600, cursor: 'pointer' }}
            >
              Create one
            </span>
          </p>

        </div>
      </div>
    </div>
  );
}
