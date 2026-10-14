const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api"
).replace(/\/$/, "");

/** Request a relative API path, e.g. apiRequest("/health"). */
export async function apiRequest(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, options);

  if (!response.ok) {
    throw new Error(`API request failed (${response.status}).`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
