
import { useRef, useState } from "react";
import { uploadBankStatement } from "./uploadService.js";
import "./UploadPage.css";

const ALLOWED_EXTENSIONS = [".csv", ".xlsx"];

const BANK_GROUPS = [
  {
    label: "Public sector banks",
    banks: [
      "State Bank of India",
      "Bank of Baroda",
      "Punjab National Bank",
      "Canara Bank",
      "Union Bank of India",
      "Bank of India",
      "Indian Bank",
      "Central Bank of India",
      "Indian Overseas Bank",
      "UCO Bank",
      "Bank of Maharashtra",
      "Punjab & Sind Bank",
    ],
  },
  {
    label: "Private sector banks",
    banks: [
      "HDFC Bank",
      "ICICI Bank",
      "Axis Bank",
      "Kotak Mahindra Bank",
      "IndusInd Bank",
      "YES Bank",
      "IDFC FIRST Bank",
      "Federal Bank",
      "RBL Bank",
      "Bandhan Bank",
      "South Indian Bank",
      "Jammu & Kashmir Bank",
      "Karnataka Bank",
      "City Union Bank",
      "Karur Vysya Bank",
      "Tamilnad Mercantile Bank",
      "DCB Bank",
      "CSB Bank",
    ],
  },
  {
    label: "Small finance banks",
    banks: [
      "AU Small Finance Bank",
      "Equitas Small Finance Bank",
      "Ujjivan Small Finance Bank",
      "Jana Small Finance Bank",
      "Suryoday Small Finance Bank",
      "ESAF Small Finance Bank",
    ],
  },
];

const RECENT_ANALYSES = [
  {
    id: "demo-analysis-1",
    title: "Monthly spending review",
    bankName: "Sample Bank",
    period: "Demo example",
  },
  {
    id: "demo-analysis-2",
    title: "Financial overview",
    bankName: "Sample Bank",
    period: "Demo example",
  },
];

function getDefaultBankSelection() {
  try {
    const savedSettings = JSON.parse(
      localStorage.getItem("fingenie-settings") || "{}",
    );

    const savedBank = savedSettings.bankName?.trim() || "";
    const allBanks = BANK_GROUPS.flatMap((group) => group.banks);

    if (allBanks.includes(savedBank)) {
      return {
        bankSelection: savedBank,
        otherBankName: "",
      };
    }

    if (savedBank) {
      return {
        bankSelection: "other",
        otherBankName: savedBank,
      };
    }
  } catch {
    // Use an empty selection if saved preferences cannot be read.
  }

  return {
    bankSelection: "",
    otherBankName: "",
  };
}

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

  const [bankState, setBankState] = useState(getDefaultBankSelection);

  const { bankSelection, otherBankName } = bankState;

  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [workflowMessage, setWorkflowMessage] = useState("");

  const bankName =
    bankSelection === "other" ? otherBankName.trim() : bankSelection.trim();

  function resetMessages() {
    setError("");
    setResult(null);
    setWorkflowMessage("");
    setStatus("idle");
  }

  function handleBankSelectionChange(event) {
    setBankState((current) => ({
      ...current,
      bankSelection: event.target.value,
      otherBankName:
        event.target.value === "other" ? current.otherBankName : "",
    }));

    resetMessages();
  }

  function handleOtherBankChange(event) {
    setBankState((current) => ({
      ...current,
      otherBankName: event.target.value,
    }));

    resetMessages();
  }

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] ?? null;

    setFile(selectedFile);
    resetMessages();

    event.target.value = "";
  }

  function handleRemoveFile() {
    setFile(null);
    resetMessages();

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!bankName) {
      setError("Please select your bank.");
      setStatus("error");
      return;
    }

    if (!file) {
      setError("Please select a bank statement first.");
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
    setWorkflowMessage("");
    setStatus("uploading");

    try {
      const response = await uploadBankStatement({
        bankName,
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

  function handleImportStatement() {
    setWorkflowMessage(
      `Demo mode: "${file?.name}" is selected for import into your financial workspace. Actual importing and combining data will be connected when the backend API is ready.`,
    );
  }

  function handleCancelAndStartOver() {
    setFile(null);
    resetMessages();

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
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
          Upload a bank statement to create or update your financial analysis.
          Your transactions and insights will be available in your dashboard
          when those features are ready.
        </p>
      </section>

      <section className="fg-upload-card">
        <div className="fg-card-heading">
          <div>
            <span className="fg-step-label">GET STARTED</span>
            <h2>Upload a bank statement</h2>
            <p>Select your bank and choose the statement you want to analyze.</p>
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
          <div className="fg-bank-section">
            <label className="fg-section-label" htmlFor="bank-name">
              Select your bank
            </label>

            <select
              id="bank-name"
              className="fg-bank-select"
              value={bankSelection}
              onChange={handleBankSelectionChange}
              disabled={status === "uploading" || status === "success"}
            >
              <option value="">Choose your bank</option>

              {BANK_GROUPS.map((group) => (
                <optgroup key={group.label} label={group.label}>
                  {group.banks.map((bank) => (
                    <option key={bank} value={bank}>
                      {bank}
                    </option>
                  ))}
                </optgroup>
              ))}

              <option value="other">Other bank / Not listed</option>
            </select>

            {bankSelection === "other" && (
              <input
                className="fg-bank-input"
                type="text"
                value={otherBankName}
                onChange={handleOtherBankChange}
                placeholder="Enter your bank name"
                aria-label="Other bank name"
                disabled={status === "uploading" || status === "success"}
              />
            )}

            <p className="fg-format-help">
              Select the bank from which this statement was issued.
            </p>
          </div>

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

                if (status === "uploading" || status === "success") return;

                const droppedFile = event.dataTransfer.files?.[0] ?? null;
                const validationError = validateFile(droppedFile);

                if (validationError) {
                  setFile(droppedFile);
                  setError(validationError);
                  setResult(null);
                  setWorkflowMessage("");
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
            <>
              <div className="fg-message fg-message-success" role="status">
                <strong>
                  {result.demo
                    ? "Upload flow tested successfully"
                    : "Statement uploaded successfully"}
                </strong>

                <span>
                  {result.demo
                    ? "Demo mode is enabled. No file was sent to a server or stored."
                    : "Your statement was uploaded successfully."}
                </span>
              </div>

              <section className="fg-import-panel">
                <div className="fg-import-heading">
                  <span className="fg-step-label">NEXT STEP</span>
                  <h3>What would you like to do next?</h3>
                  <p>
                    Import this statement into your financial workspace or
                    cancel and choose another document.
                  </p>
                </div>

                <div className="fg-import-actions">
                  <button
                    type="button"
                    className="fg-import-button"
                    onClick={handleImportStatement}
                  >
                    Import statement
                    <span aria-hidden="true">→</span>
                  </button>

                  <button
                    type="button"
                    className="fg-cancel-button"
                    onClick={handleCancelAndStartOver}
                  >
                    Cancel and upload a new document
                  </button>
                </div>

                {workflowMessage && (
                  <div className="fg-workflow-message" role="status">
                    {workflowMessage}
                  </div>
                )}
              </section>
            </>
          )}

          {status !== "success" && (
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
            Only use sample or test statements while upload is in demo mode.
          </p>
        </form>
      </section>

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
          {RECENT_ANALYSES.map((analysis) => (
            <article className="fg-analysis-card" key={analysis.id}>
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
                <strong>{analysis.title}</strong>
                <span>
                  {analysis.bankName} · {analysis.period}
                </span>
              </div>

              <span className="fg-demo-badge">Demo</span>

              <button
                type="button"
                className="fg-dashboard-button"
                disabled
                title="Dashboard will be available later"
              >
                Open dashboard
                <span aria-hidden="true">→</span>
              </button>
            </article>
          ))}
        </div>

        <p className="fg-recent-note">
          These are sample entries for preview only. Your actual analyses will
          appear here after the backend integration is ready.
        </p>
      </section>

      <footer className="fg-footer">
        <span>FinGenie</span>
        <span>Financial analysis, built together.</span>
      </footer>
    </main>
  );
}
