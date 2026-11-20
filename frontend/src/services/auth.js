/**
 * FinGenie Authentication Helpers
 * Re-exports the unified Supabase client and provides authentication actions
 */
import { supabase, isLiveSupabase } from './supabase.js';

export { supabase, isLiveSupabase };

export async function signIn({ email, password }) {
  if (!supabase) {
    throw new Error('Supabase is not configured. Check your frontend/.env file.');
  }
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

export async function signUpUser({ email, password, fullName, ...extraMetadata }) {
  if (!supabase) {
    throw new Error('Supabase is not configured. Check your frontend/.env file.');
  }
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        full_name: fullName,
        ...extraMetadata
      }
    }
  });
  if (error) throw error;
  return data;
}

export async function signInWithGoogle() {
  if (!supabase) {
    throw new Error('Google OAuth requires a configured Supabase environment.');
  }
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin }
  });
  if (error) throw error;
  return data;
}

export async function signOutUser() {
  if (supabase) {
    await supabase.auth.signOut();
  }
  localStorage.removeItem('fingenie_demo_session');
}
