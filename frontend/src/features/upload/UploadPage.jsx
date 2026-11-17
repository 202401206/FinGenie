import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../hooks/useAuth.js";
import {
  uploadBankStatement,
  getWorkspaces,
} from "./uploadService.js";
import { isRecoveryPending } from "../../services/api.js";
import "./UploadPage.css";

const ALLOWED_EXTENSIONS = [".csv", ".xlsx"];
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MiB

function validateFile(file) {
  if (!file) {
    return "Please select a bank statement first.";
  }

  const fileName = file.name.toLowerCase();

  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((extension) =>
    fileName.endsWith(extension)
  );

  if (!hasAllowedExtension) {
    return "Unsupported file type. Please choose a CSV or XLSX file.";
  }

  if (file.size === 0) {
    return "This file is empty. Please select another file.";
  }

  if (file.size > MAX_FILE_SIZE) {
    return "File size exceeds 5 MiB. Please select a smaller file.";
  }

  return "";
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatWorkspaceDate(dateValue) {
  if (!dateValue) {
    return "Date unavailable";
  }

  const date = new Date(dateValue);

  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }

  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function UploadPage({ onSelectWorkspace }) {
  const { session, loading: authLoading } = useAuth();
  const fileInputRef = useRef(null);

  // Form state.
  const [userType, setUserType] = useState("personal");
  const [file, setFile] = useState(null);

  // Status: idle | ready | uploading | success | error | uncertain
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // Recent Documents state.
  const [workspaces, setWorkspaces] = useState([]);
  const [workspaceStatus, setWorkspaceStatus] = useState("loading");
  const [workspaceError, setWorkspaceError] = useState("");
  const [workspaceRefreshKey, setWorkspaceRefreshKey] = useState(0);

  const hasSession = Boolean(session?.access_token);

  /**
   * Fetch recent workspaces whenever:
   * - Authentication finishes loading.
   * - The logged-in user/session changes.
   * - A new upload succeeds and requests a refresh.
   */
  useEffect(() => {
    let isActive = true;

    async function loadWorkspaces() {
      if (authLoading) {
        setWorkspaceStatus("loading");
        return;
      }

      if (!hasSession) {
        setWorkspaces([]);
        setWorkspaceError("");
        setWorkspaceStatus("signed-out");
        return;
      }

      setWorkspaceStatus("loading");
      setWorkspaceError("");

      try {
        const response = await getWorkspaces({
          limit: 50,
          offset: 0,
        });

        if (!isActive) return;

        const items = Array.isArray(response?.items)
          ? response.items
          : [];

        setWorkspaces(items);
        setWorkspaceStatus(items.length > 0 ? "loaded" : "empty");
      } catch (loadError) {
        if (!isActive) return;

        setWorkspaceError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load your recent documents."
        );

        setWorkspaceStatus(
          loadError.status === 401 ? "signed-out" : "error"
        );
      }
    }

    loadWorkspaces();

    return () => {
      isActive = false;
    };
  }, [
    authLoading,
    session?.access_token,
    hasSession,
    workspaceRefreshKey,
  ]);

  function resetMessages() {
    setError("");
    setResult(null);
    setStatus("idle");
  }

  function handleUserTypeChange(event) {
    setUserType(event.target.value);
    resetMessages();
  }

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] ?? null;

    setFile(selectedFile);
    resetMessages();

    // Allows the user to select the same file again.
    event.target.value = "";
  }

  function handleRemoveFile() {
    setFile(null);
    resetMessages();

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  /**
   * Continue validates the selection.
   * It does NOT upload the file yet.
   */
  function handleSubmit(event) {
    event.preventDefault();

    if (!userType) {
      setError("Please select Personal or Business account type.");
      setStatus("error");
      return;
    }

    const validationError = validateFile(file);

    if (validationError) {
      setError(validationError);
      setStatus("error");
      return;
    }

    setError("");
    setResult(null);
    setStatus("ready");
  }

  /**
   * Import Statement sends the actual upload request.
   */
  async function handleImportStatement() {
    if (status === "uploading") {
      return;
    }

    if (authLoading) {
      setError("Please wait while your sign-in status is being checked.");
      setStatus("error");
      return;
    }

    if (!hasSession) {
      setError("Please sign in before uploading your bank statement.");
      setStatus("error");
      return;
    }

    setError("");
    setResult(null);
    setStatus("uploading");

    try {
      const response = await uploadBankStatement({
        userType,
        file,
      });

      // The backend has successfully created the workspace.
      setResult(response);
      setStatus("success");

      // Refresh Recent Documents after successful upload.
      setWorkspaceRefreshKey((current) => current + 1);
    } catch (uploadError) {
      const isNetworkError =
        uploadError instanceof TypeError ||
        uploadError.code === "NETWORK_ERROR";
      const isPendingRecovery = isRecoveryPending(uploadError);

      if (isPendingRecovery) {
        setError(
          `Upload outcome could not be confirmed immediately (${uploadError.code}). The backend may still be processing or recovering this upload. Please refresh Recent Documents below to inspect your workspace details before attempting another upload. If the outcome remains unclear, contact the backend lead.`
        );
        // Refresh workspaces to check whether the backend saved the file.
        setWorkspaceRefreshKey((current) => current + 1);
        setStatus("uncertain");
      } else if (isNetworkError) {
        setError(
          "The connection was interrupted. Your upload may have reached the backend. Check Recent Documents before attempting another upload."
        );

        // Refresh workspaces to check whether the backend saved the file.
        setWorkspaceRefreshKey((current) => current + 1);
        setStatus("uncertain");
      } else {
        setError(
          uploadError instanceof Error
            ? uploadError.message
            : "Something went wrong. Please try again."
        );

        setStatus("error");
      }
    }
  }

  function handleCancelAndStartOver() {
    setFile(null);
    resetMessages();

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleRefreshWorkspaces() {
    setWorkspaceRefreshKey((current) => current + 1);
  }

  return (
    <main className="fg-page">
      {/* Main heading */}
      <section className="fg-hero">
        <div className="fg-eyebrow">
          <span className="fg-status-dot" />
          YOUR FINANCES, ORGANIZED
        </div>

        <h1>
          Understand your money.
          <br />
          <span>Start with a statement.</span>
        </h1>

        <p>
          Upload a bank statement to create your financial workspace.
          Your parsed transactions and verified records will be accessible
          in the transactions ledger.
        </p>
      </section>

      {/* Upload and Workspace section */}
      <section className="fg-workbench">
        {/* Upload form card */}
        <section className="fg-form-card">
          <div className="fg-form-header">
            <div>
              <span className="fg-step-label">STEP 1 OF 2</span>
              <h2>Add a bank statement</h2>
            </div>
          </div>

          <form onSubmit={handleSubmit} noValidate>
            {/* Account type selection */}
            <div className="fg-bank-section">
              <label className="fg-section-label" htmlFor="user-type">
                Account type
              </label>

              <select
                id="user-type"
                className="fg-bank-select"
                value={userType}
                onChange={handleUserTypeChange}
                disabled={status === "uploading"}
              >
                <option value="personal">Personal account</option>
                <option value="business">Business account</option>
              </select>

              <span className="fg-field-hint">
                Sprint 1 supports bank statements for both account types.
              </span>
            </div>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              id="statement-file-input"
              className="fg-hidden-file-input"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              disabled={status === "uploading"}
            />

            {/* Dropzone */}
            <div
              className={`fg-dropzone ${file ? "has-file" : ""}`}
              onClick={() => {
                if (status !== "uploading") {
                  fileInputRef.current?.click();
                }
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (
                  (event.key === "Enter" || event.key === " ") &&
                  status !== "uploading"
                ) {
                  event.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
            >
              <div className="fg-dropzone-icon" aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                >
                  <path d="M12 16.5V3.75m0 0L7.5 8.25m4.5-4.5 4.5 4.5" />
                  <path d="M20.25 14.25v4.5a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5v-4.5" />
                </svg>
              </div>

              <div className="fg-dropzone-copy">
                <strong>Click to choose a statement file</strong>
                <span>Supports CSV and XLSX files up to 5 MiB</span>
              </div>
            </div>

            {/* Selected file preview */}
            {file && (
              <div className="fg-file-preview">
                <div className="fg-file-pill">
                  <div className="fg-file-pill-icon" aria-hidden="true">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                      <path d="M14 2v6h6" />
                    </svg>
                  </div>

                  <div className="fg-file-pill-info">
                    <strong>{file.name}</strong>
                    <span>{formatFileSize(file.size)}</span>
                  </div>

                  <button
                    type="button"
                    className="fg-remove-file"
                    onClick={handleRemoveFile}
                    aria-label="Remove selected file"
                    disabled={status === "uploading"}
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}

            {/* Error message */}
            {error && status === "error" && (
              <div className="fg-message fg-message-error" role="alert">
                <strong>Upload issue</strong>
                <span>{error}</span>
              </div>
            )}

            {/* Uncertain network or pending-recovery state */}
            {status === "uncertain" && (
              <div className="fg-message fg-message-warning" role="status">
                <strong>Check recent documents</strong>
                <span>{error}</span>

                <button
                  type="button"
                  className="fg-cancel-button"
                  onClick={handleRefreshWorkspaces}
                >
                  Refresh Recent Documents
                </button>
              </div>
            )}

            {/* Success state */}
            {status === "success" && result && (
              <div className="fg-message fg-message-success" role="status">
                <strong>Statement uploaded successfully!</strong>

                <span>
                  {result.workspace?.name
                    ? `Your workspace "${result.workspace.name}" has been created.`
                    : "Your statement has been saved successfully."}
                </span>

                <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
                  {onSelectWorkspace && result?.workspace?.id && (
                    <button
                      type="button"
                      className="fg-import-button"
                      onClick={() => onSelectWorkspace(result.workspace.id, result.workspace)}
                    >
                      View Transactions Ledger →
                    </button>
                  )}
                  <button
                    type="button"
                    className="fg-cancel-button"
                    onClick={handleCancelAndStartOver}
                  >
                    Upload another statement
                  </button>
                </div>
              </div>
            )}

            {/* Initial form submit button */}
            {status === "idle" && (
              <div className="fg-form-actions">
                <button
                  type="submit"
                  className="fg-submit-button"
                  disabled={!file}
                >
                  Continue to Confirmation →
                </button>
              </div>
            )}
          </form>

          {/* Step 2: Upload confirmation modal / drawer */}
          {(status === "ready" || status === "uploading") && (
            <div className="fg-confirm-overlay">
              <div
                className="fg-confirm-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="confirm-modal-title"
              >
                <div className="fg-confirm-header">
                  <span className="fg-step-label">STEP 2 OF 2</span>
                  <h3 id="confirm-modal-title">Confirm upload</h3>
                  <p>
                    Your selected statement will be uploaded and saved
                    to your financial workspace.
                  </p>
                </div>

                <div className="fg-confirm-details">
                  <div className="fg-confirm-row">
                    <span>Account type</span>
                    <strong>
                      {userType === "business"
                        ? "Business account"
                        : "Personal account"}
                    </strong>
                  </div>

                  <div className="fg-confirm-row">
                    <span>File name</span>
                    <strong>{file?.name}</strong>
                  </div>

                  <div className="fg-confirm-row">
                    <span>File size</span>
                    <strong>{file ? formatFileSize(file.size) : "0 B"}</strong>
                  </div>
                </div>

                <div className="fg-confirm-actions">
                  <button
                    type="button"
                    className="fg-import-button"
                    onClick={handleImportStatement}
                    disabled={status === "uploading"}
                  >
                    {status === "uploading" ? (
                      <>
                        <span
                          className="fg-button-spinner"
                          aria-hidden="true"
                        />
                        Uploading statement...
                      </>
                    ) : (
                      "Upload Statement"
                    )}
                  </button>

                  <button
                    type="button"
                    className="fg-cancel-button"
                    onClick={handleCancelAndStartOver}
                    disabled={status === "uploading"}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Recent Documents */}
        <section className="fg-recent-section">
          <div className="fg-recent-heading">
            <div>
              <span className="fg-step-label">YOUR WORKSPACE</span>
              <h2>Recent financial analyses</h2>
              <p>
                Continue from your previously created financial workspaces.
              </p>
            </div>

            <button
              type="button"
              className="fg-refresh-button"
              onClick={handleRefreshWorkspaces}
              disabled={workspaceStatus === "loading"}
              title="Refresh workspaces"
            >
              ↻ Refresh
            </button>
          </div>

          <div className="fg-recent-list">
            {workspaceStatus === "loading" && (
              <p className="fg-recent-note">
                Loading your recent documents...
              </p>
            )}

            {workspaceStatus === "signed-out" && (
              <p className="fg-recent-note">
                Sign in to view your saved financial workspaces.
              </p>
            )}

            {workspaceStatus === "empty" && (
              <p className="fg-recent-note">
                You haven't uploaded any statements yet. Your workspaces
                will appear here after your first successful upload.
              </p>
            )}

            {workspaceStatus === "error" && (
              <div className="fg-message fg-message-error" role="alert">
                <strong>Unable to load recent documents</strong>
                <span>{workspaceError}</span>

                <button
                  type="button"
                  className="fg-cancel-button"
                  onClick={handleRefreshWorkspaces}
                >
                  Try again
                </button>
              </div>
            )}

            {workspaceStatus === "loaded" &&
              workspaces.map((workspace) => (
                <article className="fg-analysis-card" key={workspace.id}>
                  <div className="fg-analysis-icon" aria-hidden="true">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                    >
                      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
                      <path d="M13 2v7h7M8 14h8M8 18h8" />
                    </svg>
                  </div>

                  <div className="fg-analysis-details">
                    <strong>{workspace.name}</strong>

                    <span>
                      {workspace.user_type === "business"
                        ? "Business"
                        : "Personal"}{" "}
                      • {formatWorkspaceDate(workspace.created_at)}
                    </span>
                  </div>

                  <span className="fg-demo-badge">
                    {workspace.document_type === "bank_statement"
                      ? "Bank statement"
                      : workspace.document_type}
                  </span>

                  <button
                    type="button"
                    className="fg-dashboard-button"
                    onClick={() => onSelectWorkspace && onSelectWorkspace(workspace.id, workspace)}
                    title="View transaction ledger for this workspace"
                  >
                    View Transactions
                    <span aria-hidden="true">→</span>
                  </button>
                </article>
              ))}
          </div>
        </section>
      </section>

      {/* Footer */}
      <footer className="fg-footer">
        <span>FinGenie</span>
        <span>Financial analysis, built together.</span>
      </footer>
    </main>
  );
}
