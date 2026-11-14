/**
 * FinGenie Shared API Client (PR #10 / Sprint 1 Contract)
 * Single shared API service for all frontend requests to FastAPI backend.
 */
import { getAccessToken } from './supabase.js';

const getBaseUrl = () => {
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return 'http://localhost:8000/api';
};

export class ApiError extends Error {
  constructor(status, code, message, rawDetail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.rawDetail = rawDetail;
  }
}

/**
 * Normalizes FastAPI string, object, and array error shapes
 */
export function normalizeError(status, data) {
  let code = `http_${status}`;
  let message = 'An unexpected error occurred. Please try again.';

  if (data?.detail) {
    if (typeof data.detail === 'string') {
      message = data.detail;
    } else if (Array.isArray(data.detail)) {
      // FastAPI 422 field validation error array
      message = data.detail.map(d => `${d.loc?.slice(-1)[0] || 'field'}: ${d.msg}`).join(', ');
      code = 'validation_error';
    } else if (typeof data.detail === 'object') {
      code = data.detail.code || code;
      message = data.detail.message || message;
    }
  }

  // Fallbacks for standard HTTP codes per Sprint 1 specification
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  if (status === 404) message = 'Workspace or document not found.';
  if (status === 409) message = 'Unsupported document type or workspace state conflict.';
  if (status === 413) message = 'File is too large. Maximum supported size is 5 MiB.';
  if (status === 415) message = 'Unsupported file format. Please upload a valid .csv or .xlsx file.';
  if (status === 422 && code !== 'validation_error') message = 'Document layout or processing validation failed.';
  if (status === 503) message = 'Service temporarily unavailable. Please retry shortly.';

  return new ApiError(status, code, message, data?.detail);
}

/**
 * Core authenticated fetch wrapper
 * Can receive token directly or fetch automatically from Supabase session
 */
export async function apiRequest(endpoint, options = {}, explicitToken = null) {
  const baseUrl = getBaseUrl();
  const token = explicitToken || (await getAccessToken());

  const headers = {
    ...(options.headers || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${baseUrl}${endpoint}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw normalizeError(response.status, errorData);
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
  return apiRequest('/me', { method: 'GET' }, token);
}

/**
 * 3. Upload Bank Statement (POST /upload)
 * Multipart upload with exact fields: user_type, document_type, file
 */
export async function uploadBankStatement(file, userType = 'personal', token = null) {
  const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MiB (5,242,880 bytes)
  if (!file) {
    throw new ApiError(400, 'missing_file', 'Please select a file to upload.', null);
  }
  if (file.size > MAX_FILE_SIZE) {
    throw new ApiError(413, 'file_too_large', 'File exceeds the 5 MiB size limit.', null);
  }

  const form = new FormData();
  form.append('user_type', userType);
  form.append('document_type', 'bank_statement');
  form.append('file', file);

  // Let browser automatically generate multipart Content-Type with boundary
  return apiRequest('/upload', {
    method: 'POST',
    body: form
  }, token);
}

/**
 * 4. List Workspaces (GET /workspaces?limit=50&offset=0)
 */
export async function getWorkspaces(limit = 50, offset = 0, token = null) {
  return apiRequest(`/workspaces?limit=${limit}&offset=${offset}`, { method: 'GET' }, token);
}

/**
 * 5. Get Workspace Detail & Documents (GET /workspaces/{id})
 */
export async function getWorkspaceDetail(workspaceId, token = null) {
  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}`, { method: 'GET' }, token);
}

/**
 * 6. Get Paginated Transactions (GET /workspaces/{id}/transactions?limit=50&offset=0)
 */
export async function getWorkspaceTransactions(workspaceId, limit = 50, offset = 0, token = null) {
  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/transactions?limit=${limit}&offset=${offset}`, { method: 'GET' }, token);
}
