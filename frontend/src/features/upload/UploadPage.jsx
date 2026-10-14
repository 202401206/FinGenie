import { useRef, useState } from "react";
import { uploadBankStatement } from "./uploadService.js";
import "./UploadPage.css";

const ALLOWED_EXTENSIONS = [".csv", ".xlsx"];

function validateFile(file) {
  if (!file) {
    return "Please select a bank statement first.";
  }

  const fileName = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((extension) =>
    fileName.endsWith(extension),
  );

  if (!hasAllowedExtension) {
    return "Unsupported file type. Please choose a CSV or XLSX file.";
  }

  if (file.size === 0) {
    return "This file is empty. Please select another file.";
  }

  return "";
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadPage() {
  const fileInputRef = useRef(null);
  const [userType, setUserType] = useState("personal");
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] ?? null;

    setFile(selectedFile);
    setError("");
    setResult(null);
    setStatus("idle");
    event.target.value = "";
  }

  function handleUserTypeChange(type) {
    setUserType(type);
    setError("");
    setResult(null);
    setStatus("idle");
  }

  function handleRemoveFile() {
    setFile(null);
    setError("");
    setResult(null);
    setStatus("idle");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const validationError = validateFile(file);

    if (validationError) {
      setError(validationError);
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

      setResult(response);
      setStatus("success");
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Something went wrong. Please try again.",
      );
      setStatus("error");
    }
  }

  return (
    <main className="fg-page">
      <header className="fg-header">
        <a className="fg-brand" href="/" aria-label="FinGenie home">
          <span className="fg-brand-icon" aria-hidden="true">
            F
          </span>
          <span>FinGenie</span>
        </a>

        <span className="fg-header-label">Financial workspace</span>
      </header>

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
          Upload a bank statement to get started with your financial workspace.
          Your analysis and insights will follow as those features become
          available.
        </p>
      </section>

      <section className="fg-upload-card">
        <div className="fg-card-heading">
          <div>
            <span className="fg-step-label">STEP 01</span>
            <h2>Upload a bank statement</h2>
            <p>Choose your account type and select your file.</p>
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
          <fieldset className="fg-fieldset">
            <legend>Who is this statement for?</legend>

            <div className="fg-account-options">
              <button
                type="button"
                className={`fg-account-option ${
                  userType === "personal" ? "is-selected" : ""
                }`}
                aria-pressed={userType === "personal"}
                onClick={() => handleUserTypeChange("personal")}
                disabled={status === "uploading"}
              >
                <span className="fg-option-icon" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  >
                    <circle cx="12" cy="8" r="4" />
                    <path d="M4 21a8 8 0 0 1 16 0" />
                  </svg>
                </span>

                <span className="fg-option-copy">
                  <strong>Personal</strong>
                  <span>Your personal finances</span>
                </span>

                <span className="fg-radio" aria-hidden="true" />
              </button>

              <button
                type="button"
                className={`fg-account-option ${
                  userType === "business" ? "is-selected" : ""
                }`}
                aria-pressed={userType === "business"}
                onClick={() => handleUserTypeChange("business")}
                disabled={status === "uploading"}
              >
                <span className="fg-option-icon" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  >
                    <rect x="3" y="7" width="18" height="14" rx="2" />
                    <path d="M8 7V4h8v3M3 12h18M10 12v2h4v-2" />
                  </svg>
                </span>

                <span className="fg-option-copy">
                  <strong>Business</strong>
                  <span>Business bank finances</span>
                </span>

                <span className="fg-radio" aria-hidden="true" />
              </button>
            </div>
          </fieldset>

          <div className="fg-file-section">
            <label className="fg-section-label" htmlFor="bank-statement-file">
              Your bank statement
            </label>

            <input
              ref={fileInputRef}
              id="bank-statement-file"
              className="fg-file-input"
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              disabled={status === "uploading"}
              aria-describedby="file-format-help"
            />

            <div
              className={`fg-dropzone ${file ? "has-file" : ""} ${
                error ? "has-error" : ""
              }`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();

                if (status === "uploading") return;

                const droppedFile = event.dataTransfer.files?.[0] ?? null;
                const validationError = validateFile(droppedFile);

                if (validationError) {
                  setFile(droppedFile);
                  setError(validationError);
                  setResult(null);
                  setStatus("error");
                  return;
                }

                setFile(droppedFile);
                setError("");
                setResult(null);
                setStatus("idle");
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
              Supported formats: CSV and XLSX. PDF files are not supported.
            </p>
          </div>

          {error && (
            <div className="fg-message fg-message-error" role="alert">
              <strong>Unable to continue</strong>
              <span>{error}</span>
            </div>
          )}

          {status === "success" && result && (
            <div className="fg-message fg-message-success" role="status">
              <strong>
                {result.demo
                  ? "Upload flow tested successfully"
                  : "Statement uploaded successfully"}
              </strong>

              <span>
                {result.demo
                  ? "Demo mode is enabled. No file was sent to a server or stored."
                  : "Your workspace has been created."}
              </span>
            </div>
          )}

          <button
            type="submit"
            className="fg-submit-button"
            disabled={status === "uploading"}
          >
            {status === "uploading" ? (
              <>
                <span className="fg-spinner" aria-hidden="true" />
                Processing…
              </>
            ) : (
              <>
                Continue
                <span aria-hidden="true">→</span>
              </>
            )}
          </button>

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
            Only use sample or test statements while the upload is in demo mode.
          </p>
        </form>
      </section>

      <footer className="fg-footer">
        <span>FinGenie</span>
        <span>Financial analysis, built together.</span>
      </footer>
    </main>
  );
}
