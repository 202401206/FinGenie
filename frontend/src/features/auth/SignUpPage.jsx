import React, { useState } from 'react';
import { signUpUser, isLiveSupabase } from '../../services/auth.js';

export const INDIAN_BANKS = [
  { id: 'sbi', name: 'State Bank of India', code: 'SBI' },
  { id: 'hdfc', name: 'HDFC Bank', code: 'HDFC' },
  { id: 'icici', name: 'ICICI Bank', code: 'ICICI' },
  { id: 'axis', name: 'Axis Bank', code: 'AXIS' },
  { id: 'kotak', name: 'Kotak Mahindra Bank', code: 'KOTAK' },
  { id: 'bob', name: 'Bank of Baroda', code: 'BOB' },
  { id: 'other', name: 'Other Bank', code: 'OTHER' }
];

export function SignUpPage({ onSignUpSuccess, onNavigateLogin }) {
  const [step, setStep] = useState(1);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [accountType, setAccountType] = useState('personal');
  const [selectedBank, setSelectedBank] = useState('hdfc');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    setError('');
    setLoading(true);

    try {
      if (!isLiveSupabase) {
        // Fallback demo signup
        onSignUpSuccess && onSignUpSuccess({ user: { email, full_name: fullName } });
        return;
      }
      const data = await signUpUser({ email, password, fullName });
      onSignUpSuccess && onSignUpSuccess(data.session);
    } catch (err) {
      setError(err.message || 'Signup failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--fg-warm-white)', padding: '24px' }}>
      <div className="fg-card" style={{ width: '100%', maxWidth: '500px', padding: '36px' }}>
        <h2 style={{ margin: '0 0 6px 0', fontSize: '22px' }}>FinGenie Onboarding</h2>
        <p style={{ color: 'var(--fg-muted-grey)', fontSize: '14px', margin: '0 0 24px 0' }}>Step {step} of 3</p>

        {error && (
          <div style={{ background: 'var(--fg-soft-red-light)', color: 'var(--fg-soft-red)', padding: '12px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px' }}>
            {error}
          </div>
        )}

        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Aditya Sharma"
                style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid var(--fg-light-grey-green)' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="aditya@example.com"
                style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid var(--fg-light-grey-green)' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                style={{ width: '100%', padding: '10px 12px', boxSizing: 'border-box', borderRadius: '8px', border: '1px solid var(--fg-light-grey-green)' }}
              />
            </div>
            <button
              onClick={() => { if (email && password) setStep(2); else setError('Please fill all fields'); }}
              style={{ background: 'var(--fg-forest-green)', color: 'white', border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}
            >
              Next: Account Type →
            </button>
          </div>
        )}

        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div 
              onClick={() => setAccountType('personal')}
              style={{
                border: `2px solid ${accountType === 'personal' ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'}`,
                background: accountType === 'personal' ? 'var(--fg-pale-mint)' : 'white',
                padding: '16px', borderRadius: '12px', cursor: 'pointer'
              }}
            >
              <strong>Personal Account</strong>
              <div style={{ fontSize: '13px', color: 'var(--fg-muted-grey)', marginTop: '4px' }}>For personal cash flow tracking and bank statement analysis.</div>
            </div>

            <div 
              onClick={() => setAccountType('business')}
              style={{
                border: `2px solid ${accountType === 'business' ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'}`,
                background: accountType === 'business' ? 'var(--fg-pale-mint)' : 'white',
                padding: '16px', borderRadius: '12px', cursor: 'pointer'
              }}
            >
              <strong>Small Business Account</strong>
              <div style={{ fontSize: '13px', color: 'var(--fg-muted-grey)', marginTop: '4px' }}>For businesses and freelancers with statements and balance sheets.</div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button onClick={() => setStep(1)} style={{ flex: 1, padding: '12px', borderRadius: '8px' }}>← Back</button>
              <button onClick={() => setStep(3)} style={{ flex: 2, background: 'var(--fg-forest-green)', color: 'white', border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 600 }}>Next: Bank Selection →</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ background: '#F8FAF9', padding: '10px 14px', borderRadius: '8px', fontSize: '12px', color: 'var(--fg-muted-grey)' }}>
              ℹ Selecting a bank identifies your statement file format. FinGenie does not connect to live banking accounts.
            </div>

            <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {INDIAN_BANKS.map(b => (
                <div
                  key={b.id}
                  onClick={() => setSelectedBank(b.id)}
                  style={{
                    padding: '12px', borderRadius: '8px', cursor: 'pointer',
                    border: `1px solid ${selectedBank === b.id ? 'var(--fg-emerald-green)' : 'var(--fg-light-grey-green)'}`,
                    background: selectedBank === b.id ? 'var(--fg-pale-mint)' : 'white',
                    display: 'flex', justifyContent: 'space-between'
                  }}
                >
                  <span>{b.name}</span>
                  {selectedBank === b.id && <span style={{ color: 'var(--fg-emerald-green)', fontWeight: 'bold' }}>✓</span>}
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button onClick={() => setStep(2)} style={{ flex: 1, padding: '12px', borderRadius: '8px' }}>← Back</button>
              <button
                disabled={loading}
                onClick={handleCreate}
                style={{ flex: 2, background: 'var(--fg-emerald-green)', color: 'white', border: 'none', padding: '12px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}
              >
                {loading ? 'Creating Account...' : 'Complete Onboarding'}
              </button>
            </div>
          </div>
        )}

        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--fg-muted-grey)' }}>
          Already have an account? <span onClick={onNavigateLogin} style={{ color: 'var(--fg-emerald-green)', fontWeight: 600, cursor: 'pointer' }}>Sign in</span>
        </div>
      </div>
    </div>
  );
}
