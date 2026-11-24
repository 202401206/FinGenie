import { createClient } from "@supabase/supabase-js";

const getEnv = (key) => {
  if (
    typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env[key]
  ) {
    return import.meta.env[key];
  }
  return "";
};

const supabaseUrl = getEnv("VITE_SUPABASE_URL");
const supabaseKey =
  getEnv("VITE_SUPABASE_PUBLISHABLE_KEY") || getEnv("VITE_SUPABASE_ANON_KEY");

export const isLiveSupabase = Boolean(
  supabaseUrl && supabaseKey && !supabaseUrl.includes("YOUR_PROJECT_REF"),
);

export const supabase = isLiveSupabase
  ? createClient(supabaseUrl, supabaseKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        flowType: "pkce",
      },
    })
  : null;

/**
 * Non-React access token getter for the shared API transport.
 * Reads the latest valid token directly from the Supabase client.
 */
export async function getAccessToken() {
  if (!supabase) return null;
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token || null;
  } catch (err) {
    console.warn("Unable to retrieve access token:", err);
    return null;
  }
}

/**
 * Non-React session getter for initialization and recovery helpers.
 */
export async function getAuthSession() {
  if (!supabase) return null;
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session || null;
  } catch (err) {
    console.warn("Unable to retrieve auth session:", err);
    return null;
  }
}
