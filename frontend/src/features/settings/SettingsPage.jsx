import { useEffect, useState } from "react";
import "./SettingsPage.css";

const DEFAULT_SETTINGS = {
  bankName: "",
  currency: "INR",
  theme: "light",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem("fingenie-settings");
      return saved
        ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) }
        : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  const [fullName, setFullName] = useState("Your name");
  const [email, setEmail] = useState("your.email@example.com");
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    localStorage.setItem("fingenie-settings", JSON.stringify(settings));
  }, [settings]);

  function updateSetting(key, value) {
    setSettings((current) => ({ ...current, [key]: value }));
    setNotice("Preference saved on this device.");
  }

  function handleDeleteAllData() {
    // Real account deletion must be connected to the backend.
    setShowDeleteConfirmation(false);
    setNotice(
      "Demo only: no account data has been deleted. Data deletion will be connected when the API is ready.",
    );
  }

  return (
    <main className={`settings-page theme-${settings.theme}`}>
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
            />
          </label>

          <label className="settings-field">
            <span>Email address</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Enter your email"
            />
          </label>
        </div>

        <p className="settings-helper">
          Demo account fields for now. They will use authenticated account data
          when login is integrated.
        </p>
      </section>

      <section className="settings-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon" aria-hidden="true">
            ⌂
          </div>
          <div>
            <h2>Bank preferences</h2>
            <p>Choose your default bank and currency.</p>
          </div>
        </div>

        <div className="settings-fields">
          <label className="settings-field">
            <span>Default bank name</span>
            <input
              type="text"
              value={settings.bankName}
              onChange={(event) =>
                updateSetting("bankName", event.target.value)
              }
              placeholder="e.g. HDFC Bank"
            />
          </label>

          <label className="settings-field">
            <span>Default currency</span>
            <select
              value={settings.currency}
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

        <p className="settings-helper">
          These preferences are currently saved in this browser only.
        </p>
      </section>

      <section className="settings-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon" aria-hidden="true">
            ◐
          </div>
          <div>
            <h2>Appearance</h2>
            <p>Choose the theme used on this settings page.</p>
          </div>
        </div>

        <div className="theme-options">
          <button
            type="button"
            className={`theme-option ${settings.theme === "light" ? "selected" : ""}`}
            aria-pressed={settings.theme === "light"}
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
            className={`theme-option ${settings.theme === "dark" ? "selected" : ""}`}
            aria-pressed={settings.theme === "dark"}
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

        <p className="settings-helper">
          App-wide theme support can be connected after the main layout is
          agreed upon with your teammates.
        </p>
      </section>

      <section className="settings-card danger-card">
        <div className="settings-card-heading">
          <div className="settings-section-icon danger-icon" aria-hidden="true">
            !
          </div>
          <div>
            <h2>Data management</h2>
            <p>Manage your uploaded documents and associated analysis.</p>
          </div>
        </div>

        <div className="danger-row">
          <div>
            <h3>Delete all my data</h3>
            <p>
              This action is intended to permanently delete your uploaded
              documents and related analysis.
            </p>
          </div>
          <button
            type="button"
            className="delete-button"
            onClick={() => setShowDeleteConfirmation(true)}
          >
            Delete all data
          </button>
        </div>

        {showDeleteConfirmation && (
          <div
            className="delete-confirmation"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <h3 id="delete-title">Are you sure?</h3>
            <p>
              Real data deletion is not connected yet. No data will be deleted
              from this demo.
            </p>
            <div className="confirmation-actions">
              <button
                type="button"
                className="cancel-button"
                onClick={() => setShowDeleteConfirmation(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="delete-button"
                onClick={handleDeleteAllData}
              >
                Confirm
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
