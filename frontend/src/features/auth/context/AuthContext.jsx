import React, { useState, useEffect, useCallback, useRef } from "react";
import { isLiveSupabase } from "../../../services/supabase.js";
import { AuthContext } from "./authContextDefinition.js";
import {
  signInWithPassword,
  signUpWithPassword,
  resendConfirmationEmail as clientResendConfirmationEmail,
  signOutClient,
  sendPasswordResetEmail,
  updateUserPassword,
  updateUserProfile,
  updateUserEmail,
  getCurrentSession,
  onAuthStateChange,
} from "../services/authClient.js";
import { getMe, setUnauthorizedHandler } from "../../../services/api.js";

export function AuthProvider({ children }) {
  // Status: 'initializing' | 'authenticated' | 'unauthenticated' | 'unavailable'
  const [status, setStatus] = useState("initializing");
  const [session, setSession] = useState(null);
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);

  // Track active verification attempts to prevent out-of-order race conditions
  const verificationGenRef = useRef(0);
  const activeTokenRef = useRef(null);
  const currentSessionRef = useRef(null);
  const currentUserIdRef = useRef(null);

  // Keep refs synchronized with state
  useEffect(() => {
    currentSessionRef.current = session;
    currentUserIdRef.current = user?.id || null;
    activeTokenRef.current = session?.access_token || null;
  }, [session, user]);

  // Register unauthorized (401) signal handler with the API transport.
  // CRITICAL FIX: Only invalidate the session if the failed token matches the current active token!
  // This prevents an in-flight request from an old/different account from clearing a newly established session.
  useEffect(() => {
    setUnauthorizedHandler((_err, failedToken) => {
      if (
        failedToken &&
        activeTokenRef.current &&
        failedToken === activeTokenRef.current
      ) {
        // Invalidate any pending verification immediately
        verificationGenRef.current += 1;
        setSession(null);
        setUser(null);
        setStatus("unauthenticated");
        setError("Your session has expired. Please sign in again.");
      }
    });

    return () => {
      setUnauthorizedHandler(null);
    };
  }, []);

  /**
   * Verifies the Supabase session with FastAPI GET /me.
   * Ensures that the backend validates the token and the returned UUID agrees
   * with the Supabase authenticated user ID before declaring 'authenticated'.
   */
  const verifySessionWithBackend = useCallback(async (activeSession) => {
    if (!activeSession?.access_token || !activeSession?.user?.id) {
      verificationGenRef.current += 1;
      setSession(null);
      setUser(null);
      setStatus("unauthenticated");
      setError(null);
      return;
    }

    const gen = ++verificationGenRef.current;
    const targetUserId = activeSession.user.id;
    const targetToken = activeSession.access_token;

    try {
      const meData = await getMe(targetToken);

      // Drop response if a newer verification, account change, or logout occurred in the interim
      if (verificationGenRef.current !== gen) return;

      if (!meData?.id || meData.id !== targetUserId) {
        // Identity mismatch between Supabase token and backend verification
        setSession(null);
        setUser(null);
        setStatus("unauthenticated");
        setError("Session identity could not be verified by the backend.");
        return;
      }

      // Successfully verified with FastAPI
      setSession(activeSession);
      setUser(activeSession.user);
      setStatus("authenticated");
      setError(null);
    } catch (err) {
      // Drop if cancelled/invalidated
      if (verificationGenRef.current !== gen) return;

      if (err.status === 503) {
        // Backend auth service temporary outage
        // Retain SDK session, mark status 'unavailable' so user can retry without loss of session
        setSession(activeSession);
        setUser(activeSession.user);
        setStatus("unavailable");
        setError(
          "Authentication service is temporarily unavailable. Please retry.",
        );
      } else if (err.status === 401) {
        // Token was rejected by backend
        setSession(null);
        setUser(null);
        setStatus("unauthenticated");
        setError("Your session has expired. Please sign in again.");
      } else {
        // Network or unexpected failure
        setSession(activeSession);
        setUser(activeSession.user);
        setStatus("unavailable");
        setError(
          err.message || "Unable to verify session with authentication server.",
        );
      }
    }
  }, []);

  // Initialize session on mount and subscribe to auth changes
  useEffect(() => {
    if (!isLiveSupabase) {
      setStatus("unavailable");
      setError(
        "Supabase credentials are not configured. Check your frontend environment settings.",
      );
      return;
    }

    let isMounted = true;

    // 1. Initial session restoration
    getCurrentSession()
      .then((initialSession) => {
        if (!isMounted) return;
        if (initialSession) {
          verifySessionWithBackend(initialSession);
        } else {
          setSession(null);
          setUser(null);
          setStatus("unauthenticated");
          setError(null);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.warn("Initial session check failed:", err);
        setStatus("unavailable");
        setError(err.message || "Failed to initialize authentication session.");
      });

    // 2. Auth state subscription (handles SIGNED_IN, SIGNED_OUT, TOKEN_REFRESHED, USER_UPDATED)
    const {
      data: { subscription },
    } = onAuthStateChange((event, newSession) => {
      if (!isMounted) return;

      if (event === "SIGNED_OUT" || !newSession) {
        // Immediately invalidate any in-flight /me verification
        verificationGenRef.current += 1;
        setSession(null);
        setUser(null);
        setStatus("unauthenticated");
        setError(null);
        return;
      }

      if (event === "TOKEN_REFRESHED") {
        // Same-user token refresh: update session without wiping verified readiness
        if (newSession.user?.id === currentUserIdRef.current) {
          setSession(newSession);
          setUser(newSession.user);
          return;
        }
      }

      if (event === "USER_UPDATED") {
        setUser(newSession.user);
        setSession(newSession);
        return;
      }

      // SIGNED_IN or account change: verify with backend
      verifySessionWithBackend(newSession);
    });

    return () => {
      isMounted = false;
      verificationGenRef.current += 1;
      subscription?.unsubscribe();
    };
  }, [verifySessionWithBackend]);

  /**
   * Action methods
   */
  const signIn = useCallback(
    async ({ email, password }) => {
      setError(null);
      const data = await signInWithPassword({ email, password });
      if (data?.session) {
        await verifySessionWithBackend(data.session);
      }
      return data;
    },
    [verifySessionWithBackend],
  );

  const signUp = useCallback(
    async ({ email, password, fullName }) => {
      setError(null);
      const data = await signUpWithPassword({ email, password, fullName });
      if (data?.session) {
        await verifySessionWithBackend(data.session);
      }
      return data;
    },
    [verifySessionWithBackend],
  );

  const resendConfirmationEmail = useCallback(async ({ email, redirectTo }) => {
    setError(null);
    return clientResendConfirmationEmail({ email, redirectTo });
  }, []);

  const signOut = useCallback(async () => {
    // 1. Immediately invalidate any pending verification so slow /me calls cannot restore identity
    verificationGenRef.current += 1;

    // 2. Clear local identity state promptly
    setSession(null);
    setUser(null);
    setStatus("unauthenticated");
    setError(null);

    if (typeof localStorage !== "undefined") {
      localStorage.removeItem("fingenie_demo_session");
    }

    // 3. Perform reliable client logout (local fallback if remote revocation errors)
    const result = await signOutClient();
    return result;
  }, []);

  const sendPasswordReset = useCallback(async ({ email, redirectTo }) => {
    setError(null);
    return sendPasswordResetEmail({ email, redirectTo });
  }, []);

  const completePasswordReset = useCallback(async ({ password }) => {
    setError(null);
    const result = await updateUserPassword({ password });
    if (result?.user) {
      setUser(result.user);
    }
    return result;
  }, []);

  const updateProfile = useCallback(async ({ fullName }) => {
    setError(null);
    const result = await updateUserProfile({ fullName });
    if (result?.user) {
      setUser(result.user);
    }
    return result;
  }, []);

  const updateEmail = useCallback(async ({ email }) => {
    setError(null);
    const result = await updateUserEmail({ email });
    return {
      user: result.user,
      pendingConfirmation: Boolean(result?.user?.new_email),
    };
  }, []);

  const updatePassword = useCallback(async ({ password }) => {
    setError(null);
    return updateUserPassword({ password });
  }, []);

  const retrySessionVerification = useCallback(async () => {
    const current = await getCurrentSession();
    if (current) {
      await verifySessionWithBackend(current);
    } else {
      setStatus("unauthenticated");
      setError(null);
    }
  }, [verifySessionWithBackend]);

  const value = {
    // Identity fields
    user,
    session,
    status,
    error,
    // Backward compatibility for existing components expecting `loading`
    loading: status === "initializing",
    // Auth operations
    signIn,
    signUp,
    resendConfirmationEmail,
    signOut,
    sendPasswordReset,
    completePasswordReset,
    updateProfile,
    updateEmail,
    updatePassword,
    retrySessionVerification,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
