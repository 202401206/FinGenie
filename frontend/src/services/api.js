/**
 * FinGenie Shared Authenticated API Transport
 * Single shared API service for all frontend requests to FastAPI backend.
 * Provides bearer token attachment, error normalization, AbortSignal support,
 * Retry-After parsing, and auth failure signalling without circular dependencies.
 */
import { getAccessToken } from "./supabase.js";

const getBaseUrl = () => {
  if (
    typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL
  ) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return "http://localhost:8000/api";
};

/**
 * Normalized API Error holding structured domain and operational details.
 */
export class ApiError extends Error {
  constructor(
    status,
    code,
    message,
    rawDetail = null,
    attemptId = null,
    operationId = null,
    retryAfterSeconds = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.rawDetail = rawDetail;
    this.attemptId = attemptId;
    this.operationId = operationId;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export const RECOVERY_PENDING_CODES = [
  "reconciliation_required",
  "cleanup_required",
  "state_conflict",
];

/**
 * Checks if a given error corresponds to a 503 recovery-pending upload state.
 */
export function isRecoveryPending(error) {
  if (!error) return false;
  return error.status === 503 && RECOVERY_PENDING_CODES.includes(error.code);
}

/**
 * Checks if an error was caused by request cancellation via AbortSignal.
 */
export function isAbortError(error) {
  if (!error) return false;
  return error.name === "AbortError" || error.code === "aborted";
}

/**
 * Parses HTTP Retry-After header into integer seconds.
 * Supports delta-seconds or HTTP-date formats.
 */
export function parseRetryAfter(headerValue) {
  if (!headerValue || typeof headerValue !== "string") return null;

  const trimmed = headerValue.trim();
  const numeric = parseInt(trimmed, 10);
  if (!Number.isNaN(numeric) && String(numeric) === trimmed) {
    return Math.max(0, numeric);
  }

  // Attempt parsing as HTTP date
  const parsedDate = Date.parse(trimmed);
  if (!Number.isNaN(parsedDate)) {
    const diffSeconds = Math.round((parsedDate - Date.now()) / 1000);
    return Math.max(0, diffSeconds);
  }

  return null;
}

/**
 * Signal handler for authentication failures (e.g. 401 session expiry)
 * Allows AuthProvider to subscribe without circular imports.
 */
let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === "function" ? handler : null;
}

/**
 * Normalizes FastAPI string, object, and array error shapes.
 * Preserves backend detail message, domain codes, attempt/operation IDs, and Retry-After.
 */
export function normalizeError(status, data, retryAfter = null) {
  let code = `http_${status}`;
  let message = "";
  let attemptId = null;
  let operationId = null;

  if (data?.detail) {
    if (typeof data.detail === "string") {
      message = data.detail;
    } else if (Array.isArray(data.detail)) {
      // FastAPI 422 field validation error array
      message = data.detail
        .map((d) => `${d.loc?.slice(-1)[0] || "field"}: ${d.msg}`)
        .join(", ");
      code = "validation_error";
    } else if (typeof data.detail === "object") {
      code = data.detail.code || code;
      message = data.detail.message || message;
      attemptId = data.detail.attempt_id || null;
      operationId = data.detail.operation_id || null;
    }
  }

  // Fallbacks only when no specific message was extracted from detail
  if (!message) {
    if (status === 401)
      message = "Your session has expired. Please sign in again.";
    else if (status === 404) message = "Workspace or document not found.";
    else if (status === 409)
      message = "Unsupported document type or workspace state conflict.";
    else if (status === 413)
      message = "File is too large. Maximum supported size is 5 MiB.";
    else if (status === 415)
      message =
        "Unsupported file format. Please upload a valid .csv or .xlsx file.";
    else if (status === 422)
      message = "Document layout or processing validation failed.";
    else if (status === 429)
      message = "Too many requests. Please slow down and try again shortly.";
    else if (status === 503)
      message = "Service temporarily unavailable. Please retry shortly.";
    else message = "An unexpected error occurred. Please try again.";
  }

  return new ApiError(
    status,
    code,
    message,
    data?.detail,
    attemptId,
    operationId,
    retryAfter,
  );
}

/**
 * Core authenticated fetch wrapper.
 * Paths are relative to VITE_API_BASE_URL (e.g. /workspaces, /me).
 * Attaches Authorization: Bearer token for protected requests.
 * Supports explicit auth: false for public endpoints.
 */
export async function apiRequest(endpoint, options = {}, explicitToken = null) {
  const baseUrl = getBaseUrl();
  const targetUrl =
    endpoint.startsWith("http://") || endpoint.startsWith("https://")
      ? endpoint
      : `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  // Extract auth flag; default to true (protected) unless explicitly false
  const requiresAuth = options.auth !== false;

  // Clone options and strip custom 'auth' property before passing to window.fetch
  const fetchOptions = { ...options };
  delete fetchOptions.auth;

  // Build headers (preserving Headers instance or plain object)
  const headers = {};
  if (options.headers) {
    if (typeof options.headers.forEach === "function") {
      options.headers.forEach((value, key) => {
        headers[key] = value;
      });
    } else {
      Object.assign(headers, options.headers);
    }
  }

  // Attach bearer token if request requires authentication
  if (requiresAuth) {
    const token = explicitToken || (await getAccessToken());
    if (!token) {
      throw new ApiError(
        401,
        "unauthorized",
        "Authentication required. Please sign in.",
        null,
      );
    }
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Never overwrite or set multipart Content-Type when sending FormData
  if (fetchOptions.body instanceof FormData) {
    delete headers["Content-Type"];
  }

  fetchOptions.headers = headers;

  let response;
  try {
    response = await fetch(targetUrl, fetchOptions);
  } catch (fetchErr) {
    if (fetchErr.name === "AbortError") {
      throw new ApiError(0, "aborted", "Request was cancelled.", null);
    }
    throw new ApiError(
      0,
      "network_error",
      "Network connection interrupted. Unable to reach the server.",
      null,
    );
  }

  // Handle non-2xx responses
  if (!response.ok) {
    const retryAfter = parseRetryAfter(response.headers?.get("Retry-After"));
    const errorData = await response.json().catch(() => ({}));
    const error = normalizeError(response.status, errorData, retryAfter);

    // Notify auth provider on 401 on protected requests (except /me to prevent loops)
    if (response.status === 401 && endpoint !== "/me" && unauthorizedHandler) {
      unauthorizedHandler(error);
    }

    throw error;
  }

  // 204 No Content
  if (response.status === 204) return null;

  return response.json();
}

/**
 * 1. Health check (liveness, no auth required)
 */
export async function checkHealth() {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/health`);
  return res.json();
}

/**
 * 2. Get current user session verification (/me)
 */
export async function getMe(token = null) {
  return apiRequest("/me", { method: "GET" }, token);
}

/**
 * 3. Upload Bank Statement (POST /upload)
 */
export async function uploadBankStatement(
  file,
  userType = "personal",
  token = null,
) {
  const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MiB (5,242,880 bytes)
  if (!file) {
    throw new ApiError(
      400,
      "missing_file",
      "Please select a file to upload.",
      null,
    );
  }
  if (file.size > MAX_FILE_SIZE) {
    throw new ApiError(
      413,
      "file_too_large",
      "File exceeds the 5 MiB size limit.",
      null,
    );
  }

  const form = new FormData();
  form.append("user_type", userType);
  form.append("document_type", "bank_statement");
  form.append("file", file);

  return apiRequest(
    "/upload",
    {
      method: "POST",
      body: form,
    },
    token,
  );
}

/**
 * 4. List Workspaces (GET /workspaces?limit=50&offset=0)
 */
export async function getWorkspaces(limit = 50, offset = 0, token = null) {
  return apiRequest(
    `/workspaces?limit=${limit}&offset=${offset}`,
    { method: "GET" },
    token,
  );
}

/**
 * 5. Get Workspace Detail & Documents (GET /workspaces/{id})
 */
export async function getWorkspaceDetail(workspaceId, token = null) {
  return apiRequest(
    `/workspaces/${encodeURIComponent(workspaceId)}`,
    { method: "GET" },
    token,
  );
}

/**
 * 6. Get Paginated Transactions (GET /workspaces/{id}/transactions?limit=50&offset=0)
 */
export async function getWorkspaceTransactions(
  workspaceId,
  limit = 50,
  offset = 0,
  token = null,
) {
  return apiRequest(
    `/workspaces/${encodeURIComponent(workspaceId)}/transactions?limit=${limit}&offset=${offset}`,
    { method: "GET" },
    token,
  );
}
