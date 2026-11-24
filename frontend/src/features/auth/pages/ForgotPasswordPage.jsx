import React, { useState } from "react";
import { useAuth } from "../hooks/useAuth.js";
import "./Auth.css";

export function ForgotPasswordPage() {
  const { sendPasswordReset, status } = useAuth();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Please enter your email address.");
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

      await sendPasswordReset({ email: email.trim() });
      // Always show success to prevent account enumeration
      setSubmitted(true);
    } catch (err) {
      setError(
        err.message ||
          "Unable to process password reset request. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

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
            🔑
          </div>
          <span style={{ fontWeight: 700, fontSize: "16px", color: "#18352F" }}>
            FinGenie Security
          </span>
        </div>

        <h2 className="fg-auth-title" style={{ fontSize: "22px" }}>
          Reset your password
        </h2>
        <p className="fg-auth-subtitle">
          Enter your registered email address and we will send you a link to
          reset your password.
        </p>

        {submitted ? (
          <div style={{ textAlign: "center" }}>
            <div className="fg-auth-alert fg-auth-alert-success" role="status">
              <span aria-hidden="true">✉️</span>
              <span>
                If an account exists for <strong>{email}</strong>, a password
                reset link has been dispatched. Please check your inbox.
              </span>
            </div>
            <p
              style={{ fontSize: "13px", color: "#66776D", marginTop: "16px" }}
            >
              Didn&apos;t receive an email? Check your spam folder or try again
              in a few minutes.
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
                marginTop: "12px",
              }}
            >
              Back to Sign In
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
              <label htmlFor="forgot-email" className="fg-auth-label">
                Email address
              </label>
              <input
                id="forgot-email"
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

            <button
              type="submit"
              disabled={loading || !email.trim()}
              className="fg-auth-submit-btn"
            >
              {loading ? "Sending link..." : "Send Reset Link"}
            </button>

            <div className="fg-auth-links">
              Remember your password?{" "}
              <a href="/login" className="fg-auth-link">
                Sign in
              </a>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default ForgotPasswordPage;
