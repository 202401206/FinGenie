import React, { useState, useEffect, useCallback, useRef } from "react";
import { isLiveSupabase } from "../../../services/supabase.js";
import { AuthContext } from "./authContextDefinition.js";
import {
  signInWithPassword,
  signUpWithPassword,
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

  // Register unauthorized (401) signal handler with the API transport
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setSession(null);
      setUser(null);
      setStatus("unauthenticated");
      setError("Your session has expired. Please sign in again.");
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
      setSession(null);
      setUser(null);
      setStatus("unauthenticated");
      setError(null);
      return;
    }

    const gen = ++verificationGenRef.current;

    try {
      const meData = await getMe(activeSession.access_token);

      if (verificationGenRef.current !== gen) return;

      if (!meData?.id || meData.id !== activeSession.user.id) {
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
      if (verificationGenRef.current !== gen) return;

      if (err.status === 503) {
        // Backend auth service temporary outage (e.g. Supabase unavailable from backend)
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
        setSession(null);
        setUser(null);
        setStatus("unauthenticated");
        setError(null);
        return;
      }

      if (event === "TOKEN_REFRESHED") {
        // Same-user token refresh: update session and token without triggering full re-verification
        setSession(newSession);
        setUser(newSession.user);
        return;
      }

      if (event === "USER_UPDATED") {
        setUser(newSession.user);
        setSession(newSession);
        return;
      }

      // SIGNED_IN or initial detection
      verifySessionWithBackend(newSession);
    });

    return () => {
      isMounted = false;
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

  const signOut = useCallback(async () => {
    await signOutClient();
    setSession(null);
    setUser(null);
    setStatus("unauthenticated");
    setError(null);
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem("fingenie_demo_session");
    }
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
    // If confirmation is required, Supabase returns the user with new_email pending
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
