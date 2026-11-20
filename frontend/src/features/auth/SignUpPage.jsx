import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth.js';
import { isLiveSupabase } from '../../services/auth.js';

export function SignUpPage({ onSignUpSuccess, onNavigateLogin }) {
  const { signUp } = useAuth();
  const [fullName, setFullName]   = useState('');
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [isConfirmationNotice, setIsConfirmationNotice] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!fullName.trim() || !email.trim() || !password) {
      setError('Please fill in all fields.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Please enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      if (!isLiveSupabase) {
        onSignUpSuccess && onSignUpSuccess();
        return;
      }
      const data = await signUp({
        email: email.trim(),
        password,
        fullName: fullName.trim(),
      });

      // Email confirmation required
      if (data?.user && !data.session) {
        setIsConfirmationNotice(true);
      } else {
        onSignUpSuccess && onSignUpSuccess();
      }
    } catch (err) {
      setError(err.message || 'Sign-up failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    width: '100%',
    padding: '11px 14px',
    boxSizing: 'border-box',
    borderRadius: '8px',
    border: '1.5px solid #d1dbd4',
    fontSize: '14px',
    background: '#fff',
  };

  /* ── Email confirmation screen ── */
  if (isConfirmationNotice) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f4f7f5', padding: '24px' }}>
        <div style={{ width: '100%', maxWidth: '440px', padding: '36px', textAlign: 'center', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7', boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
          <div style={{ fontSize: '44px', marginBottom: '14px' }}>✉️</div>
          <h2 style={{ margin: '0 0 10px 0', fontSize: '20px', color: '#1a2e28' }}>Check your inbox</h2>
          <p style={{ color: '#66776d', fontSize: '14px', lineHeight: 1.6, margin: '0 0 20px 0' }}>
            We sent a confirmation link to <strong>{email}</strong>.<br />
            Click the link to verify your email and activate your account.
          </p>
          <button
            type="button"
            onClick={onNavigateLogin}
            style={{ background: '#18352f', color: 'white', border: 'none', padding: '11px 24px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer', fontSize: '14px' }}
          >
            Back to Sign In
          </button>
        </div>
      </div>
    );
  }

  /* ── Main sign-up layout ── */
  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: '#f4f7f5' }}>

      {/* Left — Brand panel */}
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

        {/* Value props */}
        <div>
          <h2 style={{ fontSize: '30px', lineHeight: 1.25, margin: '0 0 14px 0', fontWeight: 700 }}>
            Start for free.<br />
            <span style={{ color: '#4ADE80' }}>See every rupee.</span>
          </h2>
          <p style={{ color: '#b3c2b9', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>
            Create your account and upload your first bank statement in under a minute.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '28px' }}>
            {[
              { icon: '⚡', text: 'Instant statement processing' },
              { icon: '🔐', text: 'Your data stays private & encrypted' },
              { icon: '📂', text: 'Supports PDF and CSV formats' },
            ].map(({ icon, text }) => (
              <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#d1e8db' }}>
                <span style={{ fontSize: '15px' }}>{icon}</span> {text}
              </div>
            ))}
          </div>
        </div>

        <div style={{ fontSize: '11px', color: '#6a8575' }}>
          © 2025 FinGenie · Secure sign-up
        </div>
      </div>

      {/* Right — Form panel */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 32px' }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>

          <h2 style={{ fontSize: '23px', fontWeight: 700, margin: '0 0 6px 0', color: '#1a2e28' }}>Create your account</h2>
          <p style={{ color: '#66776d', fontSize: '14px', margin: '0 0 28px 0' }}>
            It&apos;s free — no credit card required
          </p>

          {/* Error banner */}
          {error && (
            <div style={{
              background: '#FEF2F2', color: '#B91C1C',
              padding: '12px 14px', borderRadius: '8px',
              marginBottom: '18px', fontSize: '13px',
              border: '1px solid #FCA5A5',
              display: 'flex', gap: '8px', alignItems: 'flex-start',
            }}>
              <span>⚠️</span> <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: '#2d4038' }}>
                Full name
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Aditya Sharma"
                style={inputStyle}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: '#2d4038' }}>
                Email address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                style={inputStyle}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: '#2d4038' }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  style={{ ...inputStyle, paddingRight: '44px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  style={{
                    position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', fontSize: '15px', color: '#8fa297',
                  }}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? '🙈' : '👁'}
                </button>
              </div>
              {/* Strength hint */}
              {password.length > 0 && (
                <div style={{ marginTop: '5px', fontSize: '11px', color: password.length >= 8 ? '#1d8a60' : '#B91C1C' }}>
                  {password.length >= 8 ? '✓ Good length' : `${8 - password.length} more character${8 - password.length !== 1 ? 's' : ''} needed`}
                </div>
              )}
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
                marginTop: '4px',
              }}
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </button>

            <p style={{ fontSize: '11px', color: '#8fa297', textAlign: 'center', margin: '4px 0 0 0' }}>
              By creating an account you agree to our Terms of Service and Privacy Policy.
            </p>
          </form>

          {/* Sign-in link */}
          <p style={{ marginTop: '24px', textAlign: 'center', fontSize: '13px', color: '#66776d' }}>
            Already have an account?{' '}
            <span
              onClick={onNavigateLogin}
              style={{ color: '#1d8a60', fontWeight: 600, cursor: 'pointer' }}
            >
              Sign in
            </span>
          </p>

        </div>
      </div>
    </div>
  );
}

export default SignUpPage;
