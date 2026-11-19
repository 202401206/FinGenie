
import { useEffect, useRef, useState } from "react";
import "./SettingsPage.css";

import { apiRequest } from "../../services/api.js";
import { supabase } from "../../services/supabase.js";
import { useAuth } from "../../hooks/useAuth.js";

const SUPPORTED_CURRENCIES = [
  "INR",
  "USD",
  "EUR",
  "GBP",
  "AED",
  "AUD",
  "CAD",
  "JPY",
];

function normalizePreferences(data) {
  if (
    !data ||
    !SUPPORTED_CURRENCIES.includes(data.default_currency) ||
    !["light", "dark"].includes(data.theme)
  ) {
    throw new Error("The server returned invalid settings preferences.");
  }

  return {
    currency: data.default_currency,
    theme: data.theme,
  };
}

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const userId = user?.id ?? null;

  // Prevent a late response from an old account from updating the current page.
  const currentUserIdRef = useRef(userId);
  currentUserIdRef.current = userId;

  const [settings, setSettings] = useState(null);
  const [preferencesStatus, setPreferencesStatus] = useState("loading");
  const [preferencesError, setPreferencesError] = useState("");
  const [preferencesRetry, setPreferencesRetry] = useState(0);
  const [savingSetting, setSavingSetting] = useState("");

  const [fullName, setFullName] = useState(
    user?.user_metadata?.full_name || ""
  );
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountError, setAccountError] = useState("");

  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [pendingDeletionKey, setPendingDeletionKey] = useState("");
  const [resumeWithoutKey, setResumeWithoutKey] = useState(false);
  const [notice, setNotice] = useState("");

  const deletionStorageKey = userId
    ? `fingenie:delete-financial-data:${userId}`
    : null;

  // Load the authenticated user's saved preferences from FastAPI.
  useEffect(() => {
    let active = true;

    if (authLoading) {
      setPreferencesStatus("loading");
      return () => {
        active = false;
      };
    }

    if (!userId) {
      setSettings(null);
      setPreferencesStatus("signed-out");
      setPreferencesError("");
      return () => {
        active = false;
      };
    }

    async function loadPreferences() {
      setSettings(null);
      setPreferencesStatus("loading");
      setPreferencesError("");
      setSavingSetting("");

      try {
        const response = await apiRequest("/me/preferences", {
          method: "GET",
        });

        if (!active || currentUserIdRef.current !== userId) return;

        setSettings(normalizePreferences(response));
        setPreferencesStatus("ready");

        // Remove old browser-only preferences, including the retired bank field.
        localStorage.removeItem("fingenie-settings");
      } catch (error) {
        if (!active || currentUserIdRef.current !== userId) return;

        setPreferencesStatus("error");
        setPreferencesError(
          error.message || "Unable to load your saved preferences."
        );
      }
    }

    loadPreferences();

    return () => {
      active = false;
    };
  }, [authLoading, userId, preferencesRetry]);

  // Keep the editable name synchronized with Supabase Auth.
  useEffect(() => {
    setFullName(user?.user_metadata?.full_name || "");
    setAccountError("");
  }, [user?.id, user?.user_metadata?.full_name]);

  // Restore an unfinished deletion operation for this signed-in account.
  useEffect(() => {
    if (!deletionStorageKey) {
      setPendingDeletionKey("");
      setResumeWithoutKey(false);
      return;
    }

    setPendingDeletionKey(
      localStorage.getItem(deletionStorageKey) || ""
    );
    setResumeWithoutKey(false);
    setDeleting(false);
    setDeleteError("");
  }, [deletionStorageKey]);

  async function updateSetting(key, value) {
    if (!settings || preferencesStatus !== "ready" || savingSetting) return;

    const accountId = userId;
    const previousSettings = settings;
    const backendField =
      key === "currency" ? "default_currency" : "theme";

    setSettings((current) => ({ ...current, [key]: value }));
    setSavingSetting(key);
    setPreferencesError("");
    setNotice("");

    try {
      const response = await apiRequest("/me/preferences", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ [backendField]: value }),
      });

      if (currentUserIdRef.current !== accountId) return;

      setSettings(normalizePreferences(response));
      setNotice(
        key === "currency"
          ? "Default currency saved to your account."
          : "Theme preference saved to your account."
      );
    } catch (error) {
      if (currentUserIdRef.current !== accountId) return;

      setSettings(previousSettings);
      setPreferencesError(
        error.message || "Unable to save your preference."
      );
    } finally {
      if (currentUserIdRef.current === accountId) {
        setSavingSetting("");
      }
    }
  }

  // Only the full name can be changed. Email is read-only.
  async function handleSaveAccount() {
    if (!supabase || !user) {
      setAccountError("Please sign in before updating your name.");
      return;
    }

    const currentName = user.user_metadata?.full_name || "";
    const newName = fullName.trim();

    if (!newName) {
      setAccountError("Please enter your full name.");
      return;
    }

    if (newName === currentName) {
      setAccountError("");
      setNotice("Your name is already up to date.");
      return;
    }

    setAccountSaving(true);
    setAccountError("");
    setNotice("");

    try {
      const { data, error } = await supabase.auth.updateUser({
        data: {
          ...(user.user_metadata || {}),
          full_name: newName,
        },
      });

      if (error) throw error;

      setFullName(data.user?.user_metadata?.full_name || newName);
      setNotice("Your name was updated successfully.");
    } catch (error) {
      setAccountError(
        error.message || "Unable to update your name."
      );
    } finally {
      setAccountSaving(false);
    }
  }

  async function performDataDeletion({ omitKey = false } = {}) {
    if (!userId || !deletionStorageKey) {
      setDeleteError("Please sign in before deleting your financial data.");
      return;
    }

    const accountId = userId;
    let deletionKey = null;

    try {
      if (!omitKey) {
        deletionKey =
          localStorage.getItem(deletionStorageKey) || pendingDeletionKey;

        // Generate one key after confirmation and reuse it for retries.
        if (!deletionKey) {
          if (!window.crypto?.randomUUID) {
            throw new Error(
              "Your browser does not support secure deletion requests."
            );
          }

          deletionKey = window.crypto.randomUUID();
          localStorage.setItem(deletionStorageKey, deletionKey);
        }

        setPendingDeletionKey(deletionKey);
      }

      setDeleting(true);
      setDeleteError("");
      setNotice("");

      const headers = deletionKey
        ? { "Idempotency-Key": deletionKey }
        : {};

      const response = await apiRequest("/me/data", {
        method: "DELETE",
        headers,
      });

      if (currentUserIdRef.current !== accountId) return;

      if (response?.status !== "deleted") {
        throw new Error(
          "The server did not confirm that your financial data was deleted."
        );
      }

      localStorage.removeItem(deletionStorageKey);
      localStorage.removeItem("fingenie-settings");

      setPendingDeletionKey("");
      setResumeWithoutKey(false);
      setShowDeleteConfirmation(false);
      setNotice("Your financial data was deleted successfully.");

      // Notify other screens after confirmed deletion.
      window.dispatchEvent(
        new CustomEvent("fingenie:financial-data-deleted", {
          detail: { userId: accountId },
        })
      );

      // Reload to discard financial data still held in mounted page state.
      window.setTimeout(() => {
        window.location.reload();
      }, 900);
    } catch (error) {
      if (currentUserIdRef.current !== accountId) return;

      const details = error.rawDetail || {};

      if (
        error.code === "data_deletion_pending" &&
        details.operation_id
      ) {
        localStorage.setItem(
          deletionStorageKey,
          details.operation_id
        );
        setPendingDeletionKey(details.operation_id);
        setResumeWithoutKey(false);
      } else if (error.code === "data_deletion_in_progress") {
        localStorage.removeItem(deletionStorageKey);
        setPendingDeletionKey("");
        setResumeWithoutKey(true);
      } else if (error.code === "deletion_request_outdated") {
        localStorage.removeItem(deletionStorageKey);
        setPendingDeletionKey("");
        setResumeWithoutKey(false);
        setShowDeleteConfirmation(true);
      }

      setDeleteError(
        error.message || "Unable to confirm data deletion. Please try again."
      );
    } finally {
      if (currentUserIdRef.current === accountId) {
        setDeleting(false);
      }
    }
  }

  function handleDeleteAllData() {
    setShowDeleteConfirmation(false);
    setDeleteError("");
    performDataDeletion();
  }

  function handleResumeDeletion() {
    setDeleteError("");
    performDataDeletion({ omitKey: resumeWithoutKey });
  }

  return (
    <main className={`settings-page theme-${settings?.theme || "light"}`}>
      <header className="settings-header">
        <div>
          <p className="settings-eyebrow">PREFERENCES</p>
          <h1>Settings</h1>
          <p className="settings-subtitle">
            Manage your account and personalize your FinGenie experience.
          </p>
        </div>

        <div className="settings-header-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"
              stroke="currentColor"
              strokeWidth="1.7"
            />
            <path
              d="m19.4 15 .1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 0 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 0 1-2.4-2.4l.1-.1a1.7 1.7 0 0 0-1.2-2.9H4a1.7 1.7 0 0 1 0-3.4h.2a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a1.7 1.7 0 0 1 2.4-2.4l.1.1a1.7 1.7 0 0 0 2.9-1.2V2a1.7 1.7 0 0 1 3.4 0v.2a1.7 1.7 0 0 0 2.9 1.2l.1-.1a1.7 1.7 0 0 1 2.4 2.4l-.1.1a1.7 1.7 0 0 0 1.2 2.9h.2a1.7 1.7 0 0 1 0 3.4h-.2a1.7 1.7 0 0 0-1.2 2.9Z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </header>

      {notice && (
        <div className="settings-notice" role="status">
          <span>{notice}</span>
          <button
            type="button"
            onClick={() => setNotice("")}
            aria-label="Dismiss message"
          >
            ×
          </button>
        </div>
      )}

      <section className="settings-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon">
            <span aria-hidden="true">◎</span>
          </div>
          <div>
            <h2>Account information</h2>
            <p>Your personal account details.</p>
          </div>
        </div>

        <div className="settings-fields">
          <label className="settings-field">
            <span>Full name</span>
            <input
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Enter your full name"
              autoComplete="name"
              disabled={authLoading || accountSaving || !user}
            />
          </label>

          <label className="settings-field">
            <span>Email address</span>
            <input
              type="email"
              value={user?.email || ""}
              readOnly
              disabled={authLoading || !user}
              autoComplete="email"
            />
          </label>
        </div>

        {accountError && (
          <p className="settings-action-error" role="alert">
            {accountError}
          </p>
        )}

        <div className="settings-actions">
          <button
            type="button"
            className="settings-save-button"
            onClick={handleSaveAccount}
            disabled={authLoading || accountSaving || !user}
          >
            {accountSaving ? "Saving..." : "Save changes"}
          </button>
        </div>

        <p className="settings-helper">
          Your name can be updated at any time. Your email address is linked
          to your account and cannot be changed from Settings.
        </p>
      </section>

      <section className="settings-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon" aria-hidden="true">
            ₹
          </div>
          <div>
            <h2>Preferences</h2>
            <p>Personalize how financial information is displayed.</p>
          </div>
        </div>

        {preferencesStatus === "loading" && (
          <p className="settings-helper">Loading your saved preferences...</p>
        )}

        {preferencesStatus === "signed-out" && (
          <p className="settings-helper">
            Please sign in to manage your preferences.
          </p>
        )}

        {preferencesStatus === "error" && (
          <div>
            <p className="settings-action-error" role="alert">
              {preferencesError}
            </p>
            <button
              type="button"
              className="cancel-button"
              onClick={() => setPreferencesRetry((value) => value + 1)}
            >
              Retry loading preferences
            </button>
          </div>
        )}

        {preferencesStatus === "ready" && settings && (
          <>
            <div className="settings-fields">
              <label className="settings-field">
                <span>Default currency</span>
                <select
                  value={settings.currency}
                  disabled={Boolean(savingSetting)}
                  onChange={(event) =>
                    updateSetting("currency", event.target.value)
                  }
                >
                  <option value="INR">INR — Indian Rupee (₹)</option>
                  <option value="USD">USD — US Dollar ($)</option>
                  <option value="EUR">EUR — Euro (€)</option>
                  <option value="GBP">GBP — British Pound (£)</option>
                  <option value="AED">AED — UAE Dirham</option>
                  <option value="AUD">AUD — Australian Dollar (A$)</option>
                  <option value="CAD">CAD — Canadian Dollar (C$)</option>
                  <option value="JPY">JPY — Japanese Yen (¥)</option>
                </select>
              </label>
            </div>

            {preferencesError && (
              <p className="settings-action-error" role="alert">
                {preferencesError}
              </p>
            )}

            {savingSetting === "currency" && (
              <p className="settings-helper">Saving currency preference...</p>
            )}
          </>
        )}

        <p className="settings-helper">
          Your default currency preference is saved to your account and will be
          used for app-wide display preferences as other screens are connected.
          It does not automatically convert or overwrite the original currency
          of uploaded statements.
        </p>
      </section>

      <section className="settings-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon" aria-hidden="true">
            ◐
          </div>
          <div>
            <h2>Appearance</h2>
            <p>Choose your preferred app theme.</p>
          </div>
        </div>

        <div className="theme-options">
          <button
            type="button"
            className={`theme-option ${settings?.theme === "light" ? "selected" : ""}`}
            aria-pressed={settings?.theme === "light"}
            disabled={preferencesStatus !== "ready" || Boolean(savingSetting)}
            onClick={() => updateSetting("theme", "light")}
          >
            <span className="theme-preview light-preview" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <span className="theme-option-label">
              <strong>Light mode</strong>
              <small>Clean and bright</small>
            </span>
            <span className="theme-radio" aria-hidden="true" />
          </button>

          <button
            type="button"
            className={`theme-option ${settings?.theme === "dark" ? "selected" : ""}`}
            aria-pressed={settings?.theme === "dark"}
            disabled={preferencesStatus !== "ready" || Boolean(savingSetting)}
            onClick={() => updateSetting("theme", "dark")}
          >
            <span className="theme-preview dark-preview" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <span className="theme-option-label">
              <strong>Dark mode</strong>
              <small>Comfortable in low light</small>
            </span>
            <span className="theme-radio" aria-hidden="true" />
          </button>
        </div>

        {savingSetting === "theme" && (
          <p className="settings-helper">Saving theme preference...</p>
        )}

        <p className="settings-helper">
          Your theme preference is saved to your account. Applying dark mode
          across the sidebar and other app screens will be connected separately.
        </p>
      </section>

      <section className="settings-card danger-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon danger-icon" aria-hidden="true">
            !
          </div>
          <div>
            <h2>Data management</h2>
            <p>Manage your uploaded documents and associated financial data.</p>
          </div>
        </div>

        <div className="danger-row">
          <div>
            <h3>Delete all my data</h3>
            <p>
              Permanently delete your uploaded financial documents, workspaces,
              transactions and associated financial data. Your FinGenie login
              account and saved preferences will remain.
            </p>
          </div>
          <button
            type="button"
            className="delete-button"
            onClick={() => {
              setDeleteError("");
              setShowDeleteConfirmation(true);
            }}
            disabled={!user || deleting}
          >
            Delete all data
          </button>
        </div>

        {deleteError && (
          <p className="settings-action-error" role="alert">
            {deleteError}
          </p>
        )}

        {(pendingDeletionKey || resumeWithoutKey) && (
          <div className="delete-confirmation">
            <h3>Deletion needs to be resumed</h3>
            <p>
              A previous deletion request has not yet been confirmed as
              complete. Resume that same operation instead of starting a new
              one.
            </p>
            <div className="confirmation-actions">
              <button
                type="button"
                className="delete-button"
                onClick={handleResumeDeletion}
                disabled={deleting}
              >
                {deleting ? "Resuming..." : "Resume deletion"}
              </button>
            </div>
          </div>
        )}

        {showDeleteConfirmation && (
          <div
            className="delete-confirmation"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h3 id="delete-title">Are you sure?</h3>
            <p>
              This action permanently deletes your financial data and cannot be
              undone. Your login account, name, email and saved preferences will
              remain unchanged.
            </p>
            <div className="confirmation-actions">
              <button
                type="button"
                className="cancel-button"
                onClick={() => setShowDeleteConfirmation(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="delete-button"
                onClick={handleDeleteAllData}
                disabled={deleting}
              >
                {deleting ? "Deleting..." : "Confirm deletion"}
              </button>
            </div>
          </div>
        )}
      </section>

      <p className="settings-footer">
        FinGenie · Your financial data deserves care.
      </p>
    </main>
  );
}
