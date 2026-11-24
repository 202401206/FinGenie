/**
 * Validates that a requested post-login return path is a safe, strictly same-origin application URL.
 * Protects against:
 * - Backslash normalization attacks (e.g. "/\\external.example/phish")
 * - Protocol-relative URLs (e.g. "//evil.com")
 * - Absolute URLs with schemes (e.g. "https://...", "javascript:...")
 * - Control characters and user-info/credentials
 * - Canonicalization tricks like dot segments (e.g. "/documents/../login")
 * - Auth loop redirects (e.g. "/login", "/signup", "/auth/callback", etc.)
 */

const FALLBACK_PATH = "/documents";

const AUTH_LOOP_ROUTES = [
  "/login",
  "/signup",
  "/auth/callback",
  "/forgot-password",
  "/reset-password",
];

const SUPPORTED_APP_PREFIXES = [
  "/documents",
  "/upload",
  "/settings",
  "/workspaces",
];

export function sanitizeReturnPath(
  rawPath,
  baseOrigin = typeof window !== "undefined"
    ? window.location.origin
    : "https://fingenie.local",
) {
  if (!rawPath || typeof rawPath !== "string") {
    return FALLBACK_PATH;
  }

  // 1. Reject control characters (0-31, 127-159) anywhere in raw input
  for (let i = 0; i < rawPath.length; i += 1) {
    const code = rawPath.charCodeAt(i);
    if ((code >= 0 && code <= 31) || (code >= 127 && code <= 159)) {
      return FALLBACK_PATH;
    }
  }

  const trimmed = rawPath.trim();
  if (!trimmed) {
    return FALLBACK_PATH;
  }

  // 2. Explicitly reject backslashes anywhere in the candidate
  // Browsers normalize '\' into '/' which allows "/\evil.com" to resolve to "//evil.com"
  if (trimmed.includes("\\")) {
    return FALLBACK_PATH;
  }

  // 3. Must begin with a single forward slash and not protocol-relative "//"
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return FALLBACK_PATH;
  }

  // 4. Parse with browser URL API against the known application base origin
  let parsed;
  try {
    parsed = new URL(trimmed, baseOrigin);
  } catch {
    return FALLBACK_PATH;
  }

  // 5. Ensure the parsed origin strictly equals the application origin
  if (parsed.origin !== baseOrigin) {
    return FALLBACK_PATH;
  }

  // 6. Ensure no username or password credentials exist in the URL
  if (parsed.username || parsed.password) {
    return FALLBACK_PATH;
  }

  // 7. Canonicalize pathname (URL resolution already resolves '/..' and '/.')
  let normalizedPath = parsed.pathname;
  // Normalize trailing slash for comparison
  if (normalizedPath.length > 1 && normalizedPath.endsWith("/")) {
    normalizedPath = normalizedPath.slice(0, -1);
  }

  // 8. Block auth loop routes
  const lowerPath = normalizedPath.toLowerCase();
  for (const authRoute of AUTH_LOOP_ROUTES) {
    if (lowerPath === authRoute || lowerPath.startsWith(`${authRoute}/`)) {
      return FALLBACK_PATH;
    }
  }

  // 9. Root path '/' safely redirects to documents
  if (normalizedPath === "" || normalizedPath === "/") {
    return FALLBACK_PATH;
  }

  // 10. Verify that the destination path matches supported application areas
  const isSupported = SUPPORTED_APP_PREFIXES.some(
    (prefix) =>
      lowerPath === prefix ||
      lowerPath.startsWith(`${prefix}/`) ||
      lowerPath.startsWith(`${prefix}?`),
  );

  if (!isSupported) {
    return FALLBACK_PATH;
  }

  // Return the verified relative pathname with query and hash preserved
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}
