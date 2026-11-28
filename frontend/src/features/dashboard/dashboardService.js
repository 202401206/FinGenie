/**
 * Dashboard API Service
 * Handles data fetching for workspace financial analysis from FastAPI backend.
 * All paths relative to VITE_API_BASE_URL (default http://localhost:8000/api).
 */
import { apiRequest } from '../../services/api.js';

/**
 * Fetches deterministic financial analysis for a workspace.
 * Endpoint: GET /workspaces/{id}/analysis
 *
 * @param {string} workspaceId - UUID of the workspace
 * @param {AbortSignal} [signal] - Optional AbortSignal for cancellation
 * @returns {Promise<Object>} Analysis envelope: { workspace_id, document_type, currency, reliability, metrics, warnings }
 */
export async function getWorkspaceAnalysis(workspaceId, signal = null) {
  if (!workspaceId) {
    throw new Error('workspaceId is required to fetch workspace analysis.');
  }

  const options = {
    method: 'GET'
  };

  if (signal) {
    options.signal = signal;
  }

  return apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/analysis`, options);
}

/**
 * Validates whether an analysis payload matches the expected contract.
 *
 * @param {Object} data - API response payload
 * @returns {boolean} True if payload satisfies the contract
 */
export function isValidAnalysisPayload(data) {
  if (!data || typeof data !== 'object') return false;
  if (!data.workspace_id || typeof data.workspace_id !== 'string') return false;
  if (!data.document_type || !['bank_statement', 'balance_sheet'].includes(data.document_type)) return false;
  if (!Array.isArray(data.metrics)) return false;
  if (!['valid', 'unreliable', 'insufficient_data'].includes(data.reliability)) return false;
  return true;
}
