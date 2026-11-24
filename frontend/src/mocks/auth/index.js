/**
 * Synthetic development and test fixtures for Person 2 authentication.
 * Explicitly synthetic for local testing; never used as production fallback.
 */

export const MOCK_USER_A = {
  id: "00000000-0000-4000-a000-000000000001",
  email: "aditya.sharma@example.com",
  user_metadata: {
    full_name: "Aditya Sharma",
  },
  app_metadata: {
    provider: "email",
  },
  created_at: "2026-10-01T08:00:00.000Z",
};

export const MOCK_SESSION_A = {
  access_token: "mock-jwt-token-aditya-sharma-2026",
  token_type: "bearer",
  expires_in: 3600,
  refresh_token: "mock-refresh-token-aditya",
  user: MOCK_USER_A,
};

export const MOCK_USER_B = {
  id: "00000000-0000-4000-a000-000000000002",
  email: "priya.patel@example.com",
  user_metadata: {
    full_name: "Priya Patel",
  },
  app_metadata: {
    provider: "email",
  },
  created_at: "2026-10-05T08:00:00.000Z",
};

export const MOCK_SESSION_B = {
  access_token: "mock-jwt-token-priya-patel-2026",
  token_type: "bearer",
  expires_in: 3600,
  refresh_token: "mock-refresh-token-priya",
  user: MOCK_USER_B,
};

export const MOCK_AUTH_ERRORS = {
  invalidCredentials: {
    status: 400,
    message: "Invalid login credentials",
    code: "invalid_grant",
  },
  emailUnconfirmed: {
    status: 400,
    message: "Email not confirmed",
    code: "email_not_confirmed",
  },
  rateLimitExceeded: {
    status: 429,
    message: "Too many requests. Please wait a moment.",
    code: "over_request_rate_limit",
  },
};
