import React, { useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth.js";
import { getAuthSession } from "../../../services/supabase.js";
import "./Auth.css";

export function ResetPasswordPage() {
  const { completePasswordReset, status } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [hasValidSession, setHasValidSession] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    // Verify whether an active recovery session exists
    getAuthSession()
      .then((session) => {
        setHasValidSession(Boolean(session));
        setCheckingSession(false);
      })
      .catch(() => {
        setHasValidSession(false);
        setCheckingSession(false);
      });
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password || password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (status === "unavailable") {
        throw new Error(
          "Authentication service is currently unavailable. Please check your connection.",
        );
      }

      await completePasswordReset({ password });
      setSuccess(true);
    } catch (err) {
      setError(
        err.message ||
          "Unable to update password. Your reset link may have expired.",
      );
    } finally {
      setLoading(false);
    }
  };

  if (checkingSession) {
    return (
      <div
        className="fg-auth-page"
        style={{ alignItems: "center", justifyContent: "center" }}
      >
        <div
          className="fg-auth-card"
          style={{ textAlign: "center", margin: "auto" }}
        >
          <p style={{ color: "#66776D", fontSize: "15px" }}>
            Verifying reset authorization...
          </p>
        </div>
      </div>
    );
  }

  if (!hasValidSession && !success) {
    return (
      <div
        className="fg-auth-page"
        style={{ alignItems: "center", justifyContent: "center" }}
      >
        <div
          className="fg-auth-card"
          style={{ textAlign: "center", margin: "auto" }}
        >
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>⚠️</div>
          <h2
            className="fg-auth-title"
            style={{ fontSize: "20px", color: "#B91C1C" }}
          >
            Invalid or Expired Link
          </h2>
          <p className="fg-auth-subtitle" style={{ lineHeight: 1.6 }}>
            This password reset link is invalid, has expired, or has already
            been used. Please request a new reset link.
          </p>
          <a
            href="/forgot-password"
            className="fg-auth-submit-btn"
            style={{
              display: "inline-block",
              width: "100%",
              boxSizing: "border-box",
              textAlign: "center",
              textDecoration: "none",
            }}
          >
            Request New Reset Link
          </a>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fg-auth-page"
      style={{ alignItems: "center", justifyContent: "center" }}
    >
      <div className="fg-auth-card" style={{ margin: "auto" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "16px",
          }}
        >
          <div
            className="fg-auth-brand-icon"
            style={{ width: "30px", height: "30px", fontSize: "15px" }}
          >
            🔐
          </div>
          <span style={{ fontWeight: 700, fontSize: "16px", color: "#18352F" }}>
            FinGenie Security
          </span>
        </div>

        <h2 className="fg-auth-title" style={{ fontSize: "22px" }}>
          Set new password
        </h2>
        <p className="fg-auth-subtitle">
          Please choose a strong password with at least 8 characters.
        </p>

        {success ? (
          <div style={{ textAlign: "center" }}>
            <div className="fg-auth-alert fg-auth-alert-success" role="status">
              <span aria-hidden="true">✓</span>
              <span>
                Your password has been successfully updated! You can now log in
                with your new credentials.
              </span>
            </div>
            <a
              href="/login"
              className="fg-auth-submit-btn"
              style={{
                display: "inline-block",
                width: "100%",
                boxSizing: "border-box",
                textAlign: "center",
                textDecoration: "none",
                marginTop: "14px",
              }}
            >
              Sign In with New Password
            </a>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="fg-auth-form" noValidate>
            {error && (
              <div className="fg-auth-alert fg-auth-alert-error" role="alert">
                <span aria-hidden="true">⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <div className="fg-auth-field">
              <label htmlFor="reset-password" className="fg-auth-label">
                New password
              </label>
              <div className="fg-auth-input-wrapper">
                <input
                  id="reset-password"
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
            </div>

            <div className="fg-auth-field">
              <label htmlFor="reset-password-confirm" className="fg-auth-label">
                Confirm new password
              </label>
              <input
                id="reset-password-confirm"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your new password"
                className="fg-auth-input"
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={
                loading || password.length < 8 || password !== confirmPassword
              }
              className="fg-auth-submit-btn"
            >
              {loading ? "Updating password..." : "Update Password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default ResetPasswordPage;
