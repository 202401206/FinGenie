/**
 * FinGenie Authentication Service Interface
 * Re-exports the unified Supabase client and provides authentication actions
 * backed by Person 2's auth client service.
 */
import {
  supabase,
  isLiveSupabase,
  getAccessToken,
  getAuthSession,
} from "./supabase.js";
import {
  signInWithPassword,
  signUpWithPassword,
  signOutClient,
  sendPasswordResetEmail,
  updateUserPassword,
  updateUserProfile,
  updateUserEmail,
} from "../features/auth/services/authClient.js";

export {
  supabase,
  isLiveSupabase,
  getAccessToken,
  getAuthSession,
  signInWithPassword as signIn,
  signUpWithPassword as signUpUser,
  signOutClient as signOutUser,
  sendPasswordResetEmail,
  updateUserPassword,
  updateUserProfile,
  updateUserEmail,
};

export async function signInWithGoogle() {
  if (!supabase) {
    throw new Error("Google OAuth requires a configured Supabase environment.");
  }
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: window.location.origin },
  });
  if (error) throw error;
  return data;
}
