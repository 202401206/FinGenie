/**
 * Validates that a requested post-login return path is a safe, relative application URL.
 * Rejects protocol-relative URLs (//evil.com), absolute URLs (https://...),
 * and authentication callback/loop routes.
 */
export function sanitizeReturnPath(rawPath) {
  if (!rawPath || typeof rawPath !== "string") return "/documents";

  const trimmed = rawPath.trim();

  // Must begin with single forward slash; must not be protocol-relative (//)
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return "/documents";
  }

  // Must not contain scheme or protocol
  if (trimmed.includes("://")) {
    return "/documents";
  }

  // Prevent redirect loops back to auth flows
  const lower = trimmed.toLowerCase();
  const authRoutes = [
    "/login",
    "/signup",
    "/auth/callback",
    "/forgot-password",
    "/reset-password",
  ];
  for (const route of authRoutes) {
    if (
      lower === route ||
      lower.startsWith(`${route}?`) ||
      lower.startsWith(`${route}/`)
    ) {
      return "/documents";
    }
  }

  return trimmed;
}
