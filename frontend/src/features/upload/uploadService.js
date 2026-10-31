
import { apiRequest } from "../../services/api.js";

// Keep demo mode enabled until the upload API and authentication are ready.
const USE_MOCK_UPLOAD = true;

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function uploadBankStatement({
  bankName,
  file,
  accessToken,
}) {
  if (!file) {
    throw new Error("Please select a file.");
  }

  if (!bankName?.trim()) {
    throw new Error("Please enter the bank name.");
  }

  const fileName = file.name.toLowerCase();

  if (!fileName.endsWith(".csv") && !fileName.endsWith(".xlsx")) {
    throw new Error("Only CSV and XLSX files are supported.");
  }

  if (file.size === 0) {
    throw new Error("The selected file is empty.");
  }

  if (USE_MOCK_UPLOAD) {
    // Simulate network latency without sending or storing the selected file.
    await delay(800);

    return {
      demo: true,
      workspace: {
        id: "demo-workspace",
        name: `${bankName.trim()} statement`,
        bank_name: bankName.trim(),
        document_type: "bank_statement",
        created_at: new Date().toISOString(),
      },
      document: {
        id: "demo-document",
        status: "mocked",
      },
    };
  }

  if (!accessToken) {
    throw new Error("Sign in before uploading your bank statement.");
  }

  const formData = new FormData();

  formData.append("bank_name", bankName.trim());
  formData.append("document_type", "bank_statement");
  formData.append("file", file);

  // Do not manually set Content-Type.
  // The browser supplies the multipart boundary.
  return apiRequest("/upload", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    body: formData,
  });
}
