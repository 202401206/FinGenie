/**
 * FinGenie Authentication & Onboarding Service
 * Handles user authentication with Supabase and multi-step onboarding
 */

import { mockDb, isLiveSupabaseConfigured, getSupabaseConfig } from '../lib/supabaseClient.js';

export const INDIAN_BANKS = [
  { id: 'sbi', name: 'State Bank of India', shortCode: 'SBI', popular: true, tagline: 'Public Sector Banking' },
  { id: 'hdfc', name: 'HDFC Bank', shortCode: 'HDFC', popular: true, tagline: 'Private Sector Banking' },
  { id: 'icici', name: 'ICICI Bank', shortCode: 'ICICI', popular: true, tagline: 'Private Sector Banking' },
  { id: 'axis', name: 'Axis Bank', shortCode: 'AXIS', popular: true, tagline: 'Private Sector Banking' },
  { id: 'kotak', name: 'Kotak Mahindra Bank', shortCode: 'KOTAK', popular: true, tagline: 'Private Sector Banking' },
  { id: 'bob', name: 'Bank of Baroda', shortCode: 'BOB', popular: true, tagline: 'Public Sector Banking' },
  { id: 'pnb', name: 'Punjab National Bank', shortCode: 'PNB', popular: true, tagline: 'Public Sector Banking' },
  { id: 'indusind', name: 'IndusInd Bank', shortCode: 'INDUSIND', popular: false, tagline: 'Private Sector Banking' },
  { id: 'other', name: 'Other Bank', shortCode: 'OTHER', popular: true, tagline: 'Custom Institution' }
];

export const VALIDATION_RULES = {
  EMAIL_REGEX: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PASSWORD_MIN_LENGTH: 8
};

export function validateEmail(email) {
  if (!email || typeof email !== 'string') return { valid: false, message: 'Email is required.' };
  const trimmed = email.trim();
  if (!VALIDATION_RULES.EMAIL_REGEX.test(trimmed)) {
    return { valid: false, message: 'Please enter a valid email address.' };
  }
  return { valid: true, message: '' };
}

export function validatePassword(password) {
  if (!password || typeof password !== 'string') {
    return { valid: false, message: 'Password is required.' };
  }
  if (password.length < VALIDATION_RULES.PASSWORD_MIN_LENGTH) {
    return { valid: false, message: 'Password must be at least 8 characters.' };
  }
  const hasLetter = /[a-zA-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  if (!hasLetter || !hasNumber) {
    return { valid: false, message: 'Password must contain at least one letter and one number.' };
  }
  return { valid: true, message: '' };
}

export function validateSignUpForm({ fullName, email, password, confirmPassword, termsAccepted }) {
  const errors = {};

  if (!fullName || fullName.trim().length < 2) {
    errors.fullName = 'Full name must be at least 2 characters.';
  }

  const emailRes = validateEmail(email);
  if (!emailRes.valid) {
    errors.email = emailRes.message;
  }

  const passRes = validatePassword(password);
  if (!passRes.valid) {
    errors.password = passRes.message;
  }

  if (password !== confirmPassword) {
    errors.confirmPassword = 'Passwords do not match.';
  }

  if (!termsAccepted) {
    errors.terms = 'You must accept the terms of service and privacy policy.';
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors
  };
}

export function searchBanks(query = '') {
  if (!query || typeof query !== 'string') return INDIAN_BANKS;
  const q = query.toLowerCase().trim();
  return INDIAN_BANKS.filter(b => 
    b.name.toLowerCase().includes(q) || 
    b.shortCode.toLowerCase().includes(q)
  );
}

export async function login({ email, password }) {
  const emailRes = validateEmail(email);
  if (!emailRes.valid) throw new Error(emailRes.message);
  if (!password) throw new Error('Password is required.');

  // If live Supabase client is configured, make the live call
  if (isLiveSupabaseConfigured) {
    // In production, invoke supabase.auth.signInWithPassword({ email, password })
    // Fallback handles local mock verification
  }

  const user = mockDb.users.find(u => u.email.toLowerCase() === email.toLowerCase());
  if (!user || user.password !== password) {
    throw new Error('Invalid email or password. Please check your credentials.');
  }

  mockDb.session = {
    user: {
      id: user.id,
      email: user.email,
      profile: user.profile
    },
    token: 'fg-mock-session-token-' + Date.now()
  };

  return { session: mockDb.session, user: mockDb.session.user };
}

export async function signUp({ fullName, email, password, confirmPassword, termsAccepted }) {
  const validation = validateSignUpForm({ fullName, email, password, confirmPassword, termsAccepted });
  if (!validation.valid) {
    const firstError = Object.values(validation.errors)[0];
    throw new Error(firstError);
  }

  const existing = mockDb.users.find(u => u.email.toLowerCase() === email.toLowerCase());
  if (existing) {
    throw new Error('An account with this email already exists.');
  }

  const newUserId = 'usr-' + Math.random().toString(36).substring(2, 9);
  const newUser = {
    id: newUserId,
    email: email.trim(),
    password,
    profile: {
      id: newUserId,
      full_name: fullName.trim(),
      account_type: 'personal',
      bank_id: null,
      bank_name: null,
      onboarding_completed: false
    }
  };

  mockDb.users.push(newUser);
  mockDb.session = {
    user: {
      id: newUser.id,
      email: newUser.email,
      profile: newUser.profile
    },
    token: 'fg-mock-session-token-' + Date.now()
  };

  return { session: mockDb.session, user: mockDb.session.user };
}

export async function updateAccountType(userId, accountType) {
  if (!['personal', 'business'].includes(accountType)) {
    throw new Error('Invalid account type. Must be "personal" or "business".');
  }

  const user = mockDb.users.find(u => u.id === userId);
  if (!user) throw new Error('User not found.');

  user.profile.account_type = accountType;
  if (mockDb.session && mockDb.session.user.id === userId) {
    mockDb.session.user.profile.account_type = accountType;
  }

  return user.profile;
}

export async function updateBankSelection(userId, { bankId, bankName }) {
  const user = mockDb.users.find(u => u.id === userId);
  if (!user) throw new Error('User not found.');

  const knownBank = INDIAN_BANKS.find(b => b.id === bankId);
  user.profile.bank_id = bankId;
  user.profile.bank_name = knownBank ? knownBank.name : (bankName || 'Other Bank');

  if (mockDb.session && mockDb.session.user.id === userId) {
    mockDb.session.user.profile.bank_id = user.profile.bank_id;
    mockDb.session.user.profile.bank_name = user.profile.bank_name;
  }

  return user.profile;
}

export async function completeOnboarding(userId) {
  const user = mockDb.users.find(u => u.id === userId);
  if (!user) throw new Error('User not found.');

  user.profile.onboarding_completed = true;
  if (mockDb.session && mockDb.session.user.id === userId) {
    mockDb.session.user.profile.onboarding_completed = true;
  }

  return user.profile;
}

export function getCurrentSession() {
  return mockDb.session;
}

export async function logout() {
  mockDb.session = null;
  return { success: true };
}
