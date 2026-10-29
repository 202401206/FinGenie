import React, { useState } from 'react';
import { signIn, signInWithGoogle, isLiveSupabase } from '../../services/auth.js';

export function LoginPage({ onLoginSuccess, onEnableDemoMode, onNavigateSignUp }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (!isLiveSupabase) {
        throw new Error('Supabase URL/Key is not set. Please click "Explore in Demo Mode" below.');
      }
      const data = await signIn({ email, password });
      onLoginSuccess && onLoginSuccess(data.session);
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>
      {/* Brand Hero */}
      <div style={{
        flex: 1, background: 'linear-gradient(145deg, var(--fg-forest-green) 0%, #0B1B15 100%)',
        color: 'white', padding: '56px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
      }}>
        <div style={{ fontSize: '22px', fontWeight: 700 }}>FinGenie</div>
        <div>
          <h2 style={{ fontSize: '32px', lineHeight: 1.2, margin: '0 0 16px 0' }}>
            Your finances,<br /><span style={{ color: '#4ADE80' }}>finally in focus.</span>
          </h2>
          <p style={{ color: '#B3C2B9', fontSize: '15px', lineHeight: 1.6 }}>
            Intelligent statement analysis with verified data provenance and natural language conversational answers.
          </p>
        </div>
        <div style={{ fontSize: '12px', color: '#8FA297' }}>Bank-grade encryption. Real Supabase Authentication.</div>
      </div>

      {/* Form */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '48px' }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: '0 0 8px 0' }}>Welcome back</h2>
          <p style={{ color: 'var(--fg-muted-grey)', fontSize: '14px', margin: '0 0 24px 0' }}>Log in to access your financial workspace</p>

          {error && (
            <div style={{ background: 'var(--fg-soft-red-light)', color: 'var(--fg-soft-red)', padding: '12px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid var(--fg-light-grey-green)' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid var(--fg-light-grey-green)' }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                background: 'var(--fg-forest-green)', color: 'white', border: 'none',
                padding: '12px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer'
              }}
            >
              {loading ? 'Authenticating...' : 'Sign In with Supabase'}
            </button>

            <button
              type="button"
              onClick={handleGoogle}
              style={{
                background: 'white', color: 'var(--fg-charcoal)', border: '1px solid var(--fg-light-grey-green)',
                padding: '10px', borderRadius: '8px', fontWeight: 500, cursor: 'pointer'
              }}
            >
              Continue with Google
            </button>

            {/* Explicit Demo Mode Choice */}
            <div style={{ textAlign: 'center', marginTop: '8px' }}>
              <button
                type="button"
                onClick={onEnableDemoMode}
                style={{
                  background: 'var(--fg-pale-mint)', color: 'var(--fg-emerald-green)', border: '1px solid rgba(29, 138, 96, 0.3)',
                  padding: '10px 16px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer', width: '100%'
                }}
              >
                ✨ Explore in UI Demo Mode
              </button>
            </div>
          </form>

          <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--fg-muted-grey)' }}>
            Need an account? <span onClick={onNavigateSignUp} style={{ color: 'var(--fg-emerald-green)', fontWeight: 600, cursor: 'pointer' }}>Sign up</span>
          </div>
        </div>
      </div>
    </div>
  );
}
