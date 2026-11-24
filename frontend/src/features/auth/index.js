/**
 * Person 2: FinGenie Authentication & Authenticated Transport Feature Surface
 * Exports AuthProvider, useAuth hook, RequireAuth route guard, and auth pages.
 */

// Context and hooks
export { AuthProvider } from "./context/AuthContext.jsx";
export { AuthContext } from "./context/authContextDefinition.js";
export { useAuth } from "./hooks/useAuth.js";
export { RequireAuth } from "./components/RequireAuth.jsx";
export { sanitizeReturnPath } from "./utils/urlSecurity.js";

// Pages
export { default as LoginPage } from "./pages/LoginPage.jsx";
export { default as SignupPage } from "./pages/SignupPage.jsx";
export { default as ForgotPasswordPage } from "./pages/ForgotPasswordPage.jsx";
export { default as ResetPasswordPage } from "./pages/ResetPasswordPage.jsx";
export { default as AuthCallbackPage } from "./pages/AuthCallbackPage.jsx";

// Client operations and Supabase instance
export {
  signInWithPassword,
  signUpWithPassword,
  signOutClient,
  sendPasswordResetEmail,
  updateUserPassword,
  updateUserProfile,
  updateUserEmail,
  getCurrentSession,
  onAuthStateChange,
} from "./services/authClient.js";

export {
  supabase,
  isLiveSupabase,
  getAccessToken,
  getAuthSession,
} from "../../services/supabase.js";
