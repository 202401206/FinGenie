import React, { useEffect } from "react";
import { useAuth } from "../hooks/useAuth.js";
import { sanitizeReturnPath } from "../utils/urlSecurity.js";

/**
 * Route guard component.
 * Protects private application routes by verifying authenticated state.
 * Handles:
 * - initializing: displays accessible loading indicator
 * - unavailable: displays retryable outage notice with retrySessionVerification
 * - unauthenticated: safely preserves return path and prompts/redirects to login
 * - authenticated: renders children
 */
export function RequireAuth({
  children,
  fallback = null,
  onRedirectToLogin = null,
}) {
  const { status, error, retrySessionVerification } = useAuth();

  // Move navigation side effects out of render into useEffect to prevent React render warnings and loops
  useEffect(() => {
    if (status === "unauthenticated" && onRedirectToLogin) {
      onRedirectToLogin();
    }
  }, [status, onRedirectToLogin]);

  if (status === "initializing") {
    return (
      <div
        className="fg-auth-guard-loading"
        role="status"
        aria-live="polite"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          padding: "32px",
          fontFamily: "sans-serif",
          color: "#18352F",
        }}
      >
        <div style={{ fontSize: "28px", marginBottom: "12px" }}>🔒</div>
        <p style={{ margin: 0, fontSize: "15px", fontWeight: 500 }}>
          Verifying your financial workspace session...
        </p>
      </div>
    );
  }

  if (status === "unavailable") {
    return (
      <div
        className="fg-auth-guard-unavailable"
        role="alert"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          padding: "32px",
          textAlign: "center",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: "32px", marginBottom: "12px" }}>⚠️</div>
        <h3 style={{ margin: "0 0 8px 0", fontSize: "18px", color: "#B91C1C" }}>
          Authentication Service Unavailable
        </h3>
        <p
          style={{
            margin: "0 0 20px 0",
            maxWidth: "440px",
            fontSize: "14px",
            color: "#66776D",
            lineHeight: 1.5,
          }}
        >
          {error ||
            "Unable to connect to the authentication server. Please check your connection and try again."}
        </p>
        <button
          type="button"
          onClick={retrySessionVerification}
          style={{
            background: "#18352F",
            color: "white",
            border: "none",
            padding: "10px 20px",
            borderRadius: "8px",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Retry Connection
        </button>
      </div>
    );
  }

  if (status === "unauthenticated") {
    if (onRedirectToLogin) {
      return fallback;
    }

    // Determine current safe return path
    const currentPath =
      typeof window !== "undefined"
        ? sanitizeReturnPath(window.location.pathname + window.location.search)
        : "/documents";

    return (
      <div
        className="fg-auth-guard-unauthenticated"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          padding: "32px",
          textAlign: "center",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: "32px", marginBottom: "12px" }}>🔑</div>
        <h3 style={{ margin: "0 0 8px 0", fontSize: "18px", color: "#18352F" }}>
          Sign In Required
        </h3>
        <p
          style={{
            margin: "0 0 20px 0",
            maxWidth: "440px",
            fontSize: "14px",
            color: "#66776D",
            lineHeight: 1.5,
          }}
        >
          Please sign in to access your financial documents and workspaces.
        </p>
        <a
          href={`/login?returnTo=${encodeURIComponent(currentPath)}`}
          style={{
            background: "#1D8A60",
            color: "white",
            textDecoration: "none",
            padding: "10px 22px",
            borderRadius: "8px",
            fontWeight: 600,
            display: "inline-block",
          }}
        >
          Go to Sign In →
        </a>
      </div>
    );
  }

  // status === 'authenticated'
  return children;
}

export default RequireAuth;
