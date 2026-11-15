import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../hooks/useAuth.js";
import {
  uploadBankStatement,
  getWorkspaces,
} from "./uploadService.js";
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

export default function UploadPage() {
  const fileInputRef = useRef(null);

  // Get the real Supabase session from the shared authentication context.
  const {
    session,
    loading: authLoading,
  } = useAuth();

  const [userType, setUserType] = useState("");
  const [file, setFile] = useState(null);

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

      if (isNetworkError) {
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
          Upload a bank statement to create or update your financial analysis.
          Your transactions and insights will be available in your dashboard
          when those features are ready.
        </p>
      </section>

      {/* Upload card */}
      <section className="fg-upload-card">
        <div className="fg-card-heading">
          <div>
            <span className="fg-step-label">GET STARTED</span>
            <h2>Upload a bank statement</h2>
            <p>
              Select your account type and choose the statement you want
              to analyze.
            </p>
          </div>

          <div className="fg-document-icon" aria-hidden="true">
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
        </div>

        <form onSubmit={handleSubmit} noValidate>
          {/* Account type selection */}
          <div className="fg-bank-section">
            <label className="fg-section-label" htmlFor="user-type">
              Select your account type
            </label>

            <select
              id="user-type"
              className="fg-bank-select"
              value={userType}
              onChange={handleUserTypeChange}
              disabled={status === "uploading" || status === "success"}
              required
            >
              <option value="">Choose account type</option>
              <option value="personal">Personal</option>
              <option value="business">Business</option>
            </select>

            <p className="fg-format-help">
              Choose whether this statement belongs to your personal
              or business finances.
            </p>
          </div>

          {/* File selection */}
          <div className="fg-file-section">
            <label
              className="fg-section-label"
              htmlFor="bank-statement-file"
            >
              Your bank statement
            </label>

            <input
              ref={fileInputRef}
              id="bank-statement-file"
              className="fg-file-input"
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              disabled={status === "uploading" || status === "success"}
              aria-describedby="file-format-help"
            />

            <div
              className={`fg-dropzone ${file ? "has-file" : ""} ${
                error ? "has-error" : ""
              }`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();

                if (status === "uploading" || status === "success") {
                  return;
                }

                const droppedFile =
                  event.dataTransfer.files?.[0] ?? null;

                const validationError = validateFile(droppedFile);

                if (validationError) {
                  setFile(droppedFile);
                  setError(validationError);
                  setResult(null);
                  setStatus("error");
                  return;
                }

                setFile(droppedFile);
                resetMessages();
              }}
            >
              {file ? (
                <div className="fg-selected-file">
                  <span className="fg-file-icon" aria-hidden="true">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.7"
                    >
                      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
                      <path d="M13 2v7h7" />
                    </svg>
                  </span>

                  <span className="fg-file-details">
                    <strong title={file.name}>{file.name}</strong>
                    <span>{formatFileSize(file.size)}</span>
                  </span>

                  <button
                    type="button"
                    className="fg-remove-file"
                    onClick={handleRemoveFile}
                    aria-label="Remove selected file"
                    disabled={status === "uploading"}
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="fg-dropzone-content">
                  <span className="fg-upload-icon" aria-hidden="true">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.7"
                    >
                      <path d="M12 16V4m-5 5 5-5 5 5" />
                      <path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
                    </svg>
                  </span>

                  <strong>Choose a file to upload</strong>

                  <span className="fg-dropzone-secondary">
                    or drag and drop it here
                  </span>

                  <button
                    type="button"
                    className="fg-browse-button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={status === "uploading"}
                  >
                    Browse files
                  </button>
                </div>
              )}
            </div>

            <p id="file-format-help" className="fg-format-help">
              Supported formats: CSV and XLSX. Maximum size: 5 MiB.
              PDF files are not supported.
            </p>
          </div>

          {/* Error messages */}
          {error && (
            <div className="fg-message fg-message-error" role="alert">
              <strong>
                {status === "uncertain"
                  ? "Upload status could not be confirmed"
                  : "Unable to continue"}
              </strong>

              <span>{error}</span>

              {status === "uncertain" && (
                <button
                  type="button"
                  className="fg-cancel-button"
                  onClick={handleRefreshWorkspaces}
                >
                  Refresh Recent Documents
                </button>
              )}
            </div>
          )}

          {/* Successful upload */}
          {status === "success" && result && (
            <div className="fg-message fg-message-success" role="status">
              <strong>Statement uploaded successfully!</strong>

              <span>
                {result.workspace?.name
                  ? `Your workspace "${result.workspace.name}" has been created.`
                  : "Your statement has been saved successfully."}
              </span>

              {result.document?.status && (
                <span>
                  Processing status: {result.document.status}
                </span>
              )}

              <button
                type="button"
                className="fg-cancel-button"
                onClick={handleCancelAndStartOver}
              >
                Upload another statement
              </button>
            </div>
          )}

          {/* Import confirmation */}
          {(status === "ready" || status === "uploading") && (
            <section className="fg-import-panel">
              <div className="fg-import-heading">
                <span className="fg-step-label">CONFIRM UPLOAD</span>

                <h3>Ready to import your statement?</h3>

                <p>
                  Your selected statement will be uploaded and saved
                  to your financial workspace.
                </p>
              </div>

              <div className="fg-import-actions">
                <button
                  type="button"
                  className="fg-import-button"
                  onClick={handleImportStatement}
                  disabled={status === "uploading"}
                >
                  {status === "uploading" ? (
                    <>
                      <span className="fg-spinner" aria-hidden="true" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      Import Statement
                      <span aria-hidden="true">→</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  className="fg-cancel-button"
                  onClick={handleCancelAndStartOver}
                  disabled={status === "uploading"}
                >
                  Cancel and upload a new document
                </button>
              </div>
            </section>
          )}

          {/* Continue button */}
          {(status === "idle" || status === "error") && (
            <button type="submit" className="fg-submit-button">
              Continue
              <span aria-hidden="true">→</span>
            </button>
          )}

          <p className="fg-privacy-note">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              aria-hidden="true"
            >
              <rect x="4" y="10" width="16" height="11" rx="2" />
              <path d="M8 10V7a4 4 0 1 1 8 0v3" />
            </svg>
            Your selected statement will be sent to FinGenie for processing.
          </p>
        </form>
      </section>

      {/* Recent Documents */}
      {/* Workspace navigation will be connected with the Dashboard teammate later. */}
      <section className="fg-recent-section">
        <div className="fg-recent-heading">
          <div>
            <span className="fg-step-label">YOUR WORKSPACE</span>
            <h2>Recent financial analyses</h2>
            <p>
              Continue from your previously created financial analyses.
            </p>
          </div>
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
                    · {formatWorkspaceDate(workspace.created_at)}
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
                  disabled
                  title="Dashboard navigation will be connected later"
                >
                  Open dashboard
                  <span aria-hidden="true">→</span>
                </button>
              </article>
            ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="fg-footer">
        <span>FinGenie</span>
        <span>Financial analysis, built together.</span>
      </footer>
    </main>
  );
}
