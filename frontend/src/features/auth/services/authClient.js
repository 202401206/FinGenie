/**
 * Low-level Supabase Auth SDK client operations.
 * Wraps official Supabase JS v2 auth methods with safe parameter validation and errors.
 */
import { supabase, isLiveSupabase } from "../../../services/supabase.js";

function ensureSupabase() {
  if (!supabase || !isLiveSupabase) {
    const error = new Error(
      "Supabase authentication is not configured. Check your frontend environment settings.",
    );
    error.code = "auth_unconfigured";
    throw error;
  }
  return supabase;
}

/**
 * Sign in with email and password.
 */
export async function signInWithPassword({ email, password }) {
  const client = ensureSupabase();
  const trimmedEmail = (email || "").trim();

  if (!trimmedEmail || !password) {
    throw new Error("Please enter both your email address and password.");
  }

  const { data, error } = await client.auth.signInWithPassword({
    email: trimmedEmail,
    password,
  });

  if (error) throw error;
  return data;
}

/**
 * Sign up with email, password, and optional full_name in user_metadata.
 */
export async function signUpWithPassword({ email, password, fullName }) {
  const client = ensureSupabase();
  const trimmedEmail = (email || "").trim();
  const trimmedName = (fullName || "").trim();

  if (!trimmedEmail || !password) {
    throw new Error("Please enter an email address and password.");
  }

  const { data, error } = await client.auth.signUp({
    email: trimmedEmail,
    password,
    options: {
      data: trimmedName ? { full_name: trimmedName } : {},
    },
  });

  if (error) throw error;
  return data;
}

/**
 * Sign out of the active Supabase session.
 */
export async function signOutClient() {
  if (!supabase) return;
  try {
    const { error } = await supabase.auth.signOut();
    if (error) {
      console.warn("Supabase remote sign-out returned error:", error.message);
    }
  } catch (err) {
    console.warn("Supabase sign-out threw exception:", err);
  }
}

/**
 * Send password reset link to user's email.
 */
export async function sendPasswordResetEmail({ email, redirectTo }) {
  const client = ensureSupabase();
  const trimmedEmail = (email || "").trim();

  if (!trimmedEmail) {
    throw new Error("Please enter your email address to reset your password.");
  }

  const fallbackRedirect =
    typeof window !== "undefined"
      ? `${window.location.origin}/reset-password`
      : undefined;

  const { data, error } = await client.auth.resetPasswordForEmail(
    trimmedEmail,
    {
      redirectTo: redirectTo || fallbackRedirect,
    },
  );

  if (error) throw error;
  return data;
}

/**
 * Complete password reset for a recovered session.
 */
export async function updateUserPassword({ password }) {
  const client = ensureSupabase();

  if (!password || password.length < 8) {
    throw new Error("Password must be at least 8 characters long.");
  }

  const { data, error } = await client.auth.updateUser({
    password,
  });

  if (error) throw error;
  return data;
}

/**
 * Update user's profile metadata (e.g. full_name).
 */
export async function updateUserProfile({ fullName }) {
  const client = ensureSupabase();
  const trimmedName = (fullName || "").trim();

  const { data, error } = await client.auth.updateUser({
    data: {
      full_name: trimmedName,
    },
  });

  if (error) throw error;
  return data;
}

/**
 * Update user's email address (triggers verification if configured).
 */
export async function updateUserEmail({ email }) {
  const client = ensureSupabase();
  const trimmedEmail = (email || "").trim();

  if (!trimmedEmail) {
    throw new Error("Please enter a valid email address.");
  }

  const { data, error } = await client.auth.updateUser({
    email: trimmedEmail,
  });

  if (error) throw error;
  return data;
}

/**
 * Retrieve the current session.
 */
export async function getCurrentSession() {
  if (!supabase) return null;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session;
}

/**
 * Listen to auth state transitions.
 */
export function onAuthStateChange(callback) {
  if (!supabase) {
    return { data: { subscription: { unsubscribe: () => {} } } };
  }
  return supabase.auth.onAuthStateChange(callback);
}
