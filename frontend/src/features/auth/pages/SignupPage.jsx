import React, { useState } from "react";
import { useAuth } from "../hooks/useAuth.js";
import "./Auth.css";

export function SignupPage({ onSignUpSuccess, onNavigateLogin }) {
  const { signUp, status, error: authError } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isConfirmationNotice, setIsConfirmationNotice] = useState(false);

  const handleNavigateSignIn = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (onNavigateLogin) {
      onNavigateLogin();
    } else if (typeof window !== "undefined") {
      window.location.assign("/login");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!fullName.trim() || !email.trim() || !password) {
      setError("Please fill in all required fields.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Please enter a valid email address.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (status === "unavailable") {
        throw new Error(
          authError ||
            "Authentication service is unavailable. Please check your connection.",
        );
      }

      const data = await signUp({
        email: email.trim(),
        password,
        fullName: fullName.trim(),
      });

      // If email confirmation is required by Supabase project
      if (data?.user && !data?.session) {
        setIsConfirmationNotice(true);
      } else {
        if (onSignUpSuccess) {
          onSignUpSuccess();
        } else if (typeof window !== "undefined") {
          window.location.assign("/documents");
        }
      }
    } catch (err) {
      setError(err.message || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Screen shown when user was created but needs to confirm email before signing in
  if (isConfirmationNotice) {
    return (
      <div
        className="fg-auth-page"
        style={{ alignItems: "center", justifyContent: "center" }}
      >
        <div
          className="fg-auth-card"
          style={{ textAlign: "center", margin: "auto" }}
        >
          <div style={{ fontSize: "44px", marginBottom: "14px" }}>✉️</div>
          <h2 className="fg-auth-title" style={{ fontSize: "20px" }}>
            Check your inbox
          </h2>
          <p className="fg-auth-subtitle" style={{ lineHeight: 1.6 }}>
            We sent a verification link to <strong>{email}</strong>.<br />
            Click the link in your email to activate your account and start
            using FinGenie.
          </p>
          <button
            type="button"
            onClick={handleNavigateSignIn}
            className="fg-auth-submit-btn"
            style={{ width: "100%" }}
          >
            Back to Sign In
          </button>
        </div>
      </div>
    );
  }

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
            Start for free.
            <br />
            <span className="fg-auth-hero-accent">See every rupee.</span>
          </h2>
          <p>
            Create your account and upload your first bank statement or balance
            sheet in under a minute.
          </p>

          <div className="fg-auth-feature-list">
            <div className="fg-auth-feature-item">
              <span aria-hidden="true">⚡</span>
              <span>Instant statement parsing & provenance</span>
            </div>
            <div className="fg-auth-feature-item">
              <span aria-hidden="true">🔐</span>
              <span>Your financial data stays private & isolated</span>
            </div>
            <div className="fg-auth-feature-item">
              <span aria-hidden="true">📂</span>
              <span>Supports CSV and XLSX formats</span>
            </div>
          </div>
        </div>

        <div className="fg-auth-hero-footer">
          © 2026 FinGenie · Secure registration
        </div>
      </div>

      {/* Main Signup Form */}
      <div className="fg-auth-main">
        <div className="fg-auth-card">
          <h2 className="fg-auth-title">Create your account</h2>
          <p className="fg-auth-subtitle">
            Get started with your personal or business workspace
          </p>

          {error && (
            <div className="fg-auth-alert fg-auth-alert-error" role="alert">
              <span aria-hidden="true">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="fg-auth-form" noValidate>
            <div className="fg-auth-field">
              <label htmlFor="signup-name" className="fg-auth-label">
                Full name
              </label>
              <input
                id="signup-name"
                type="text"
                required
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Aditya Sharma"
                className="fg-auth-input"
                disabled={loading}
              />
            </div>

            <div className="fg-auth-field">
              <label htmlFor="signup-email" className="fg-auth-label">
                Email address
              </label>
              <input
                id="signup-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="aditya@example.com"
                className="fg-auth-input"
                disabled={loading}
              />
            </div>

            <div className="fg-auth-field">
              <label htmlFor="signup-password" className="fg-auth-label">
                Password
              </label>
              <div className="fg-auth-input-wrapper">
                <input
                  id="signup-password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
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
              {password.length > 0 && (
                <span
                  className="fg-auth-help-text"
                  style={{
                    color: password.length >= 8 ? "#1D8A60" : "#B91C1C",
                  }}
                >
                  {password.length >= 8
                    ? "✓ Good length"
                    : `${8 - password.length} more character${8 - password.length !== 1 ? "s" : ""} needed`}
                </span>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || !fullName || !email || password.length < 8}
              className="fg-auth-submit-btn"
            >
              {loading ? "Creating account..." : "Create Account"}
            </button>

            <p
              style={{
                fontSize: "11px",
                color: "#8FA297",
                textAlign: "center",
                margin: "4px 0 0 0",
                lineHeight: 1.4,
              }}
            >
              By creating an account, you agree to our Terms of Service and
              Privacy Policy.
            </p>
          </form>

          <div className="fg-auth-links">
            Already have an account?{" "}
            <a
              href="/login"
              onClick={handleNavigateSignIn}
              className="fg-auth-link"
            >
              Sign in
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SignupPage;
