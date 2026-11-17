import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth.js';
import { isLiveSupabase } from '../../services/auth.js';

export function SignUpPage({ onSignUpSuccess, onNavigateLogin }) {
  const { signUp } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
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
        fullName: fullName.trim()
      });

      // If Supabase project requires email confirmation
      if (data?.user && !data.session) {
        setIsConfirmationNotice(true);
      } else {
        onSignUpSuccess && onSignUpSuccess();
      }
    } catch (err) {
      setError(err.message || 'Signup failed.');
    } finally {
      setLoading(false);
    }
  };

  if (isConfirmationNotice) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--fg-warm-white, #f4f7f5)', padding: '24px' }}>
        <div className="fg-card" style={{ width: '100%', maxWidth: '440px', padding: '36px', textAlign: 'center', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
          <div style={{ fontSize: '36px', marginBottom: '12px' }}>✉️</div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '20px' }}>Confirm your email</h2>
          <p style={{ color: 'var(--fg-muted-grey, #66776d)', fontSize: '14px', lineHeight: 1.5 }}>
            A confirmation link has been sent to <strong>{email}</strong>. Please check your inbox and verify your email to log in.
          </p>
          <button
            type="button"
            onClick={onNavigateLogin}
            style={{ marginTop: '16px', background: 'var(--fg-emerald-green, #1d8a60)', color: 'white', border: 'none', padding: '10px 20px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--fg-warm-white, #f4f7f5)', padding: '24px' }}>
      <div className="fg-card" style={{ width: '100%', maxWidth: '440px', padding: '36px', background: 'white', borderRadius: '12px', border: '1px solid #e5ebe7' }}>
        <h2 style={{ margin: '0 0 6px 0', fontSize: '22px' }}>Create your account</h2>
        <p style={{ color: 'var(--fg-muted-grey, #66776d)', fontSize: '14px', margin: '0 0 24px 0' }}>Sign up to access your financial workspace</p>

        {error && (
          <div style={{ background: '#FEE2E2', color: '#DC2626', padding: '12px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Full Name</label>
            <input
              type="text"
              required
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              placeholder="Aditya Sharma"
              style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid #d1dbd4' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="aditya@example.com"
              style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid #d1dbd4' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid #d1dbd4' }}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            style={{ background: 'var(--fg-forest-green, #18352f)', color: 'white', border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer', marginTop: '8px' }}
          >
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--fg-muted-grey, #66776d)' }}>
          Already have an account? <span onClick={onNavigateLogin} style={{ color: 'var(--fg-emerald-green, #1d8a60)', fontWeight: 600, cursor: 'pointer' }}>Sign in</span>
        </div>
      </div>
    </div>
  );
}

export default SignUpPage;
