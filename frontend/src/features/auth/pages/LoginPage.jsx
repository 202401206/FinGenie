import React, { useState } from "react";
import { useAuth } from "../hooks/useAuth.js";
import { sanitizeReturnPath } from "../utils/urlSecurity.js";
import "./Auth.css";

export function LoginPage({
  onLoginSuccess,
  onEnableDemoMode,
  onNavigateSignUp,
  onNavigateForgotPassword,
}) {
  const { signIn, status, error: authError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Extract return path from query string or default to /documents
  const getReturnPath = () => {
    if (typeof window === "undefined") return "/documents";
    const params = new URLSearchParams(window.location.search);
    const returnTo = params.get("returnTo");
    return sanitizeReturnPath(returnTo);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (status === "unavailable") {
        throw new Error(
          authError ||
            "Authentication service is unavailable. Please check your connection.",
        );
      }

      await signIn({ email: email.trim(), password });

      if (onLoginSuccess) {
        onLoginSuccess();
      } else if (typeof window !== "undefined") {
        window.location.assign(getReturnPath());
      }
    } catch (err) {
      setError(
        err.message ||
          "Login failed. Please check your credentials and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleNavigateForgot = (e) => {
    e.preventDefault();
    if (onNavigateForgotPassword) {
      onNavigateForgotPassword();
    } else if (typeof window !== "undefined") {
      window.location.assign("/forgot-password");
    }
  };

  const handleNavigateSign = (e) => {
    e.preventDefault();
    if (onNavigateSignUp) {
      onNavigateSignUp();
    } else if (typeof window !== "undefined") {
      window.location.assign("/signup");
    }
  };

  return (
    <div className="fg-auth-page">
      {/* Brand Hero */}
      <div className="fg-auth-hero">
        <div className="fg-auth-brand">
          <div className="fg-auth-brand-icon" aria-hidden="true">
            💰
          </div>
          <span className="fg-auth-brand-name">FinGenie</span>
        </div>

        <div className="fg-auth-hero-content">
          <h2>
            Your finances,
            <br />
            <span className="fg-auth-hero-accent">finally in focus.</span>
          </h2>
          <p>
            Upload bank statements and balance sheets. Instantly see verified
            financial ledgers, balances, and statements in one secure workspace.
          </p>

          <div className="fg-auth-feature-list">
            <div className="fg-auth-feature-item">
              <span aria-hidden="true">🔒</span>
              <span>End-to-end encrypted storage & transport</span>
            </div>
            <div className="fg-auth-feature-item">
              <span aria-hidden="true">📊</span>
              <span>Automated transaction & ledger provenance</span>
            </div>
            <div className="fg-auth-feature-item">
              <span aria-hidden="true">🌐</span>
              <span>Personal and business statement support</span>
            </div>
          </div>
        </div>

        <div className="fg-auth-hero-footer">
          © 2026 FinGenie · Secure session verification
        </div>
      </div>

      {/* Login Form Main Panel */}
      <div className="fg-auth-main">
        <div className="fg-auth-card">
          <h2 className="fg-auth-title">Welcome back</h2>
          <p className="fg-auth-subtitle">
            Sign in to your financial workspace
          </p>

          {error && (
            <div className="fg-auth-alert fg-auth-alert-error" role="alert">
              <span aria-hidden="true">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="fg-auth-form" noValidate>
            <div className="fg-auth-field">
              <label htmlFor="login-email" className="fg-auth-label">
                Email address
              </label>
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="fg-auth-input"
                disabled={loading}
              />
            </div>

            <div className="fg-auth-field">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <label htmlFor="login-password" className="fg-auth-label">
                  Password
                </label>
                <a
                  href="/forgot-password"
                  onClick={handleNavigateForgot}
                  className="fg-auth-link"
                  style={{ fontSize: "12px" }}
                >
                  Forgot password?
                </a>
              </div>
              <div className="fg-auth-input-wrapper">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="fg-auth-input"
                  style={{ paddingRight: "44px" }}
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="fg-auth-toggle-pwd"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={0}
                >
                  {showPassword ? "🙈" : "👁"}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="fg-auth-submit-btn"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>

            {onEnableDemoMode && (
              <button
                type="button"
                onClick={onEnableDemoMode}
                style={{
                  background: "rgba(29, 138, 96, 0.08)",
                  color: "#1D8A60",
                  border: "1.5px dashed rgba(29, 138, 96, 0.35)",
                  padding: "10px 16px",
                  borderRadius: "8px",
                  fontWeight: 600,
                  fontSize: "13px",
                  cursor: "pointer",
                  marginTop: "6px",
                }}
              >
                ✨ Explore in UI Demo Mode
              </button>
            )}
          </form>

          <div className="fg-auth-links">
            Don&apos;t have an account?{" "}
            <a
              href="/signup"
              onClick={handleNavigateSign}
              className="fg-auth-link"
            >
              Create one
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
