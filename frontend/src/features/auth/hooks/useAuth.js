import { useContext } from "react";
import { AuthContext } from "../context/authContextDefinition.js";

/**
 * Main authentication hook for Person 2 feature and cross-feature consumers.
 * Exposes identity state: { user, session, status, error, loading }
 * and operations: { signIn, signUp, signOut, sendPasswordReset, completePasswordReset,
 *                   updateProfile, updateEmail, updatePassword, retrySessionVerification }
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}

export default useAuth;
