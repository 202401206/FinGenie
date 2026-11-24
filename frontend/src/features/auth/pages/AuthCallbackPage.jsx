import React, { useEffect, useState } from "react";
import { supabase } from "../../../services/supabase.js";
import { sanitizeReturnPath } from "../utils/urlSecurity.js";
import "./Auth.css";

export function AuthCallbackPage() {
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(true);

  useEffect(() => {
    let active = true;

    async function processCallback() {
      if (typeof window === "undefined") return;

      const url = new URL(window.location.href);
      const params = new URLSearchParams(url.search);
      const hashParams = new URLSearchParams(url.hash.replace(/^#/, ""));

      // Check for errors returned in query or hash by the provider
      const errorMsg =
        params.get("error_description") || hashParams.get("error_description");
      if (errorMsg) {
        if (active) {
          setError(decodeURIComponent(errorMsg));
          setProcessing(false);
        }
        return;
      }

      const type = params.get("type") || hashParams.get("type");
      const isRecovery = type === "recovery";

      // Clean up sensitive tokens from address bar without reloading
      const cleanUrl = `${window.location.origin}${window.location.pathname}`;
      window.history.replaceState({}, document.title, cleanUrl);

      if (!supabase) {
        if (active) {
          setError("Authentication client is not configured.");
          setProcessing(false);
        }
        return;
      }

      try {
        // Retrieve the established session after Supabase client consumed URL parameters
        const {
          data: { session },
          error: sessionError,
        } = await supabase.auth.getSession();

        if (sessionError) throw sessionError;

        if (active) {
          if (isRecovery) {
            // Forward user to password reset screen
            window.location.assign("/reset-password");
          } else if (session) {
            // Successful confirmation / login
            const returnTo = sanitizeReturnPath(params.get("returnTo"));
            window.location.assign(returnTo);
          } else {
            // No session detected
            setError(
              "Unable to verify callback authorization link. It may have expired or been used already.",
            );
            setProcessing(false);
          }
        }
      } catch (err) {
        if (active) {
          setError(
            err.message ||
              "Error occurred while verifying your authentication link.",
          );
          setProcessing(false);
        }
      }
    }

    processCallback();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div
      className="fg-auth-page"
      style={{ alignItems: "center", justifyContent: "center" }}
    >
      <div
        className="fg-auth-card"
        style={{ textAlign: "center", margin: "auto" }}
      >
        {processing ? (
          <div>
            <div style={{ fontSize: "36px", marginBottom: "14px" }}>🔄</div>
            <h2 className="fg-auth-title" style={{ fontSize: "20px" }}>
              Verifying your session
            </h2>
            <p className="fg-auth-subtitle" style={{ margin: 0 }}>
              Completing secure authentication. You will be redirected
              momentarily...
            </p>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: "36px", marginBottom: "14px" }}>⚠️</div>
            <h2
              className="fg-auth-title"
              style={{ fontSize: "20px", color: "#B91C1C" }}
            >
              Authentication Link Issue
            </h2>
            <p className="fg-auth-subtitle" style={{ lineHeight: 1.6 }}>
              {error ||
                "The authentication verification link could not be verified."}
            </p>
            <a
              href="/login"
              className="fg-auth-submit-btn"
              style={{
                display: "inline-block",
                width: "100%",
                boxSizing: "border-box",
                textAlign: "center",
                textDecoration: "none",
              }}
            >
              Return to Sign In
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuthCallbackPage;
