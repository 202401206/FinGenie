import { apiRequest } from "../../services/api.js";

// Keep demo mode enabled until the upload API and authentication are ready.
const USE_MOCK_UPLOAD = true;

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function uploadBankStatement({ userType, file, accessToken }) {
  if (!file) {
    throw new Error("Please select a file.");
  }

  if (!["personal", "business"].includes(userType)) {
    throw new Error("Please select a valid account type.");
  }

  if (USE_MOCK_UPLOAD) {
    // Simulate network latency without sending or storing the selected file.
    await delay(800);

    return {
      demo: true,
      workspace: {
        id: "demo-workspace",
        name: "Demo bank statement",
        user_type: userType,
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

  formData.append("user_type", userType);
  formData.append("document_type", "bank_statement");
  formData.append("file", file);

  // Do not manually set Content-Type; the browser supplies the multipart boundary.
  return apiRequest("/upload", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    body: formData,
  });
}
