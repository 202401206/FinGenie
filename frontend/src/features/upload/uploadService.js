import {
  uploadBankStatement as uploadStatementRequest,
  getWorkspaces as getWorkspacesRequest,
} from "../../services/api.js";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MiB

/**
 * Validate and upload a bank statement.
 *
 * Uses the shared API client for:
 * - Backend URL
 * - Supabase access token
 * - Multipart request
 * - Backend error handling
 */
export async function uploadBankStatement({ userType, file }) {
  if (!["personal", "business"].includes(userType)) {
    throw new Error("Please select Personal or Business account type.");
  }

  if (!file) {
    throw new Error("Please select a bank statement first.");
  }

  const fileName = file.name.toLowerCase();

  if (!fileName.endsWith(".csv") && !fileName.endsWith(".xlsx")) {
    throw new Error("Only CSV and XLSX files are supported.");
  }

  if (file.size === 0) {
    throw new Error("The selected file is empty.");
  }

  if (file.size > MAX_FILE_SIZE) {
    throw new Error("File size exceeds the 5 MiB limit.");
  }

  // The shared API client handles the actual authenticated upload.
  return uploadStatementRequest(file, userType);
}

/**
 * Fetch the current user's recent workspaces.
 *
 * Backend supports limit 1-100 and offset >= 0.
 */
export async function getWorkspaces({ limit = 50, offset = 0 } = {}) {
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    throw new Error("Workspace limit must be between 1 and 100.");
  }

  if (!Number.isInteger(offset) || offset < 0) {
    throw new Error("Workspace offset cannot be negative.");
  }

  return getWorkspacesRequest(limit, offset);
}
