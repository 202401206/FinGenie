import { createClient } from '@supabase/supabase-js';

const getEnv = (key) => {
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env[key]) {
    return import.meta.env[key];
  }
  return '';
};

const supabaseUrl = getEnv('VITE_SUPABASE_URL');
const supabaseAnonKey = getEnv('VITE_SUPABASE_ANON_KEY');

export const isLiveSupabase = Boolean(
  supabaseUrl && 
  supabaseAnonKey && 
  !supabaseUrl.includes('your-project-ref')
);

export const supabase = isLiveSupabase ? createClient(supabaseUrl, supabaseAnonKey) : null;

export async function signIn({ email, password }) {
  if (!supabase) {
    throw new Error('Supabase is not configured. Enable Demo Mode to preview.');
  }
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

export async function signUpUser({ email, password, fullName }) {
  if (!supabase) {
    throw new Error('Supabase is not configured. Enable Demo Mode to preview.');
  }
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: fullName }
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
