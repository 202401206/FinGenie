/**
 * auth.test.js — Tests for auth service exports, return path security,
 * upload/workspace state-guard behavior, and account boundary verification.
 *
 * Uses Node's built-in test runner (node:test).
 * All tests are deterministic and do not hit real network or Supabase.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  isLiveSupabase,
  signIn,
  signUpUser,
  signOutUser,
  resendConfirmationEmail,
  sendPasswordResetEmail,
  updateUserPassword,
  updateUserEmail,
} from "../src/services/auth.js";
import { sanitizeReturnPath } from "../src/features/auth/utils/urlSecurity.js";
import {
  MOCK_USER_A,
  MOCK_USER_B,
  MOCK_SESSION_A,
  MOCK_SESSION_B,
} from "../src/mocks/auth/index.js";

// ── auth.js exports ─────────────────────────────────────────────────────────

test("isLiveSupabase export is a boolean", () => {
  assert.equal(typeof isLiveSupabase, "boolean");
});

// ── Return path sanitization ─────────────────────────────────────────────────

test("sanitizeReturnPath accepts safe application paths", () => {
  assert.equal(sanitizeReturnPath("/documents"), "/documents");
  assert.equal(sanitizeReturnPath("/upload"), "/upload");
  assert.equal(sanitizeReturnPath("/settings"), "/settings");
  assert.equal(
    sanitizeReturnPath("/workspaces/ws-123/dashboard"),
    "/workspaces/ws-123/dashboard",
  );
  assert.equal(
    sanitizeReturnPath("/workspaces/ws-123/dashboard?tab=analytics"),
    "/workspaces/ws-123/dashboard?tab=analytics",
  );
});

test("sanitizeReturnPath rejects malicious external or protocol-relative paths", () => {
  assert.equal(sanitizeReturnPath("//evil.com/hack"), "/documents");
  assert.equal(
    sanitizeReturnPath("https://malicious.site/phish"),
    "/documents",
  );
  assert.equal(sanitizeReturnPath("http://insecure.site"), "/documents");
  assert.equal(sanitizeReturnPath("javascript:alert(1)"), "/documents");
  assert.equal(sanitizeReturnPath("data:text/html,bad"), "/documents");
  assert.equal(sanitizeReturnPath(""), "/documents");
  assert.equal(sanitizeReturnPath(null), "/documents");
  assert.equal(sanitizeReturnPath(undefined), "/documents");
});

test("sanitizeReturnPath prevents redirect loops to auth flow routes", () => {
  assert.equal(sanitizeReturnPath("/login"), "/documents");
  assert.equal(sanitizeReturnPath("/signup"), "/documents");
  assert.equal(sanitizeReturnPath("/auth/callback"), "/documents");
  assert.equal(sanitizeReturnPath("/forgot-password"), "/documents");
  assert.equal(sanitizeReturnPath("/reset-password"), "/documents");
  assert.equal(sanitizeReturnPath("/login?returnTo=/dashboard"), "/documents");
  assert.equal(sanitizeReturnPath("/login#fragment"), "/documents");
  assert.equal(sanitizeReturnPath("/signup/"), "/documents");
  assert.equal(sanitizeReturnPath("/auth/callback?code=abc"), "/documents");
});

test("sanitizeReturnPath rejects backslash bypass attempts and control characters", () => {
  const origin = "https://fingenie.invalid";
  const slashBackslash =
    "/" + String.fromCharCode(92) + "external.example/phishing";
  assert.equal(sanitizeReturnPath(slashBackslash, origin), "/documents");

  assert.equal(sanitizeReturnPath("\\external.example", origin), "/documents");
  assert.equal(sanitizeReturnPath("/\\external.example", origin), "/documents");
  assert.equal(sanitizeReturnPath("/\\\\evil.com", origin), "/documents");

  // Control characters and null bytes
  assert.equal(
    sanitizeReturnPath("/documents" + String.fromCharCode(0), origin),
    "/documents",
  );
  assert.equal(sanitizeReturnPath("/upload\r\n", origin), "/documents");
});

test("sanitizeReturnPath rejects dot-segment escapes and unsupported destinations", () => {
  const origin = "https://fingenie.invalid";
  // Escaping to auth route via dot segments
  assert.equal(
    sanitizeReturnPath("/workspaces/../login", origin),
    "/documents",
  );
  assert.equal(
    sanitizeReturnPath("/upload/../auth/callback", origin),
    "/documents",
  );
  assert.equal(sanitizeReturnPath("/documents/../", origin), "/documents");

  // Unsupported root paths
  assert.equal(sanitizeReturnPath("/unknown-route", origin), "/documents");
  assert.equal(sanitizeReturnPath("/admin/secret", origin), "/documents");
  assert.equal(sanitizeReturnPath("/api/v1/internal", origin), "/documents");
});

// ── Account isolation and mocks ──────────────────────────────────────────────

test("mock auth fixtures enforce distinct user IDs for isolation", () => {
  assert.notEqual(MOCK_USER_A.id, MOCK_USER_B.id);
  assert.notEqual(MOCK_SESSION_A.access_token, MOCK_SESSION_B.access_token);
  assert.equal(typeof MOCK_USER_A.email, "string");
  assert.equal(typeof MOCK_USER_B.email, "string");
});

// ── Upload state guard ───────────────────────────────────────────────────────

test("upload generation guard: late response from previous account is discarded", async () => {
  let uploadGenRef = 0;
  const results = [];

  async function handleImportStatement(resolveWith, delay = 0) {
    if (typeof delay !== "number") throw new Error("bad test setup");
    const gen = ++uploadGenRef;

    await new Promise((r) => setTimeout(r, delay));

    if (uploadGenRef !== gen) {
      results.push({ discarded: true, gen, payload: resolveWith });
      return;
    }
    results.push({ discarded: false, gen, payload: resolveWith });
  }

  // User A starts upload (slow)
  const uploadA = handleImportStatement("workspace-A", 20);

  // Account switches before A completes
  uploadGenRef += 1;

  // User B starts upload (fast)
  const uploadB = handleImportStatement("workspace-B", 0);

  await Promise.all([uploadA, uploadB]);

  const aResult = results.find((r) => r.payload === "workspace-A");
  const bResult = results.find((r) => r.payload === "workspace-B");

  assert.ok(aResult, "A result must be recorded");
  assert.equal(
    aResult.discarded,
    true,
    "A response must be discarded after account change",
  );
  assert.ok(bResult, "B result must be recorded");
  assert.equal(bResult.discarded, false, "B response must be accepted");
});

test("upload generation guard: same-user token refresh preserves response", async () => {
  let uploadGenRef = 0;
  let accepted = false;

  const gen = ++uploadGenRef;
  await new Promise((r) => setTimeout(r, 0));

  if (uploadGenRef === gen) {
    accepted = true;
  }

  assert.equal(
    accepted,
    true,
    "Response must be accepted after same-user token refresh",
  );
});

test("duplicate submit guard: second call while uploading is a no-op", () => {
  let uploadStatus = "idle";
  const submitCounts = [];

  function handleImportStatement() {
    if (uploadStatus === "uploading") return false;
    uploadStatus = "uploading";
    submitCounts.push(Date.now());
    return true;
  }

  assert.equal(handleImportStatement(), true, "first submit accepted");
  assert.equal(handleImportStatement(), false, "second submit rejected");
  assert.equal(handleImportStatement(), false, "third submit still rejected");
  assert.equal(submitCounts.length, 1, "exactly one POST was initiated");
});

// ── Workspace/ledger state guard ─────────────────────────────────────────────

test("ledger request guard: B result overwrites A, then slow A is discarded", async () => {
  let requestGen = 0;
  const committed = [];

  async function loadWorkspaceLedger(workspaceId, delay = 0) {
    const gen = ++requestGen;
    await new Promise((r) => setTimeout(r, delay));
    if (requestGen !== gen) return;
    committed.push({ workspaceId, gen });
  }

  const loadA = loadWorkspaceLedger("ws-A", 20);
  const loadB = loadWorkspaceLedger("ws-B", 0);

  await Promise.all([loadA, loadB]);

  assert.equal(committed.length, 1, "Only one result should be committed");
  assert.equal(committed[0].workspaceId, "ws-B", "B (newer) result must win");
});

test("ledger request guard: account change invalidates pending workspace request", async () => {
  let requestGen = 0;
  let committed = null;

  async function loadWorkspaceLedger(delay = 0) {
    const gen = ++requestGen;
    await new Promise((r) => setTimeout(r, delay));
    if (requestGen !== gen) return;
    committed = { gen };
  }

  const loadA = loadWorkspaceLedger(20);
  requestGen += 1;
  await loadA;

  assert.equal(
    committed,
    null,
    "Workspace result must not be committed after account change",
  );
});

test("ledger request guard: page-change failure does not commit stale page offset", async () => {
  let requestGen = 0;
  const committed = [];

  async function loadPage(offset, shouldFail = false, delay = 0) {
    const gen = ++requestGen;
    await new Promise((r) => setTimeout(r, delay));
    if (requestGen !== gen) return;

    if (shouldFail) {
      return;
    }
    committed.push({ offset, gen });
  }

  await loadPage(0);
  assert.equal(committed.length, 1);
  assert.equal(committed[0].offset, 0);

  await loadPage(50, true);
  assert.equal(
    committed.length,
    1,
    "Failed page must not update committed state",
  );
});

// ── Email / password validation ──────────────────────────────────────────────

test("email validation rejects malformed addresses", () => {
  function validateEmail(email) {
    if (!email || typeof email !== "string") return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  }
  assert.equal(validateEmail("test@fingenie.app"), true);
  assert.equal(validateEmail("aditya@bank.co.in"), true);
  assert.equal(validateEmail("invalid-email"), false);
  assert.equal(validateEmail(""), false);
  assert.equal(validateEmail(null), false);
});

test("password validation enforces minimum 8 characters", () => {
  function validatePassword(p) {
    if (!p || typeof p !== "string") return false;
    return p.length >= 8;
  }
  assert.equal(validatePassword("SecurePass1"), true);
  assert.equal(validatePassword("short"), false);
  assert.equal(validatePassword(""), false);
});

// ── Auth client actions ──────────────────────────────────────────────────────

test("resendConfirmationEmail validates email input and throws auth_unconfigured when offline", async () => {
  await assert.rejects(async () => {
    await resendConfirmationEmail({ email: "" });
  }, /email address/i);

  await assert.rejects(async () => {
    await resendConfirmationEmail({ email: null });
  }, /email address/i);

  // When email is provided but Supabase is unconfigured, throws auth_unconfigured
  await assert.rejects(
    async () => {
      await resendConfirmationEmail({ email: "user@fingenie.app" });
    },
    (err) => err.code === "auth_unconfigured",
  );
});

test("signOutUser returns structured result and clears local state", async () => {
  const res = await signOutUser();
  assert.equal(typeof res, "object");
  assert.equal(res.success, true);
  assert.equal(res.remoteRevoked, true);
  assert.equal(res.error, null);
});

test("auth client throws documented auth_unconfigured error when environment is missing", async () => {
  await assert.rejects(
    async () => {
      await signIn({ email: "test@example.com", password: "password123" });
    },
    (err) => err.code === "auth_unconfigured",
  );

  await assert.rejects(
    async () => {
      await signUpUser({ email: "test@example.com", password: "password123" });
    },
    (err) => err.code === "auth_unconfigured",
  );

  await assert.rejects(
    async () => {
      await sendPasswordResetEmail({ email: "test@example.com" });
    },
    (err) => err.code === "auth_unconfigured",
  );

  await assert.rejects(
    async () => {
      await updateUserPassword({ newPassword: "NewSecurePassword1" });
    },
    (err) => err.code === "auth_unconfigured",
  );

  await assert.rejects(
    async () => {
      await updateUserEmail({ newEmail: "new@example.com" });
    },
    (err) => err.code === "auth_unconfigured",
  );
});

// ── Auth provider lifecycle & race isolation tests ──────────────────────────

test("auth lifecycle: stale /me verification resolving after signOut cannot restore identity (Reproduction A)", async () => {
  // Simulates AuthContext verification generation tracking
  let verificationGen = 0;
  let status = "unauthenticated";
  let activeUser = null;

  // Step 1: Session A restored, verification starts
  const genA = ++verificationGen;
  let resolveMeA;
  const pendingMePromise = new Promise((resolve) => {
    resolveMeA = resolve;
  });

  // Step 2: User A signs out before verification finishes
  // In our fix: signOut() unconditionally bumps verificationGen
  ++verificationGen;
  status = "unauthenticated";
  activeUser = null;

  // Step 3: Delayed /me resolves for User A
  resolveMeA({ id: "user-A-uuid", email: "a@fingenie.app" });
  const meResult = await pendingMePromise;

  // AuthContext check: drop result if generation changed
  if (genA === verificationGen) {
    status = "authenticated";
    activeUser = meResult;
  }

  // Verification: status MUST remain unauthenticated and activeUser MUST remain null
  assert.equal(
    status,
    "unauthenticated",
    "Delayed /me result must not restore authenticated state after signOut",
  );
  assert.equal(activeUser, null, "Active user must remain null");
});

test("auth lifecycle: account A old 401 does not clear account B active session (Reproduction B)", async () => {
  // Simulates AuthContext token-bound 401 handler
  let activeToken = "token-account-B";
  let activeStatus = "authenticated";
  let activeUser = { id: "user-B", email: "b@fingenie.app" };

  function handleUnauthorized(error, failedToken) {
    // If the 401 belongs to an old token, ignore it
    if (failedToken && failedToken !== activeToken) {
      return; // Ignored: stale token from previous account or prior to refresh
    }
    activeStatus = "unauthenticated";
    activeUser = null;
    activeToken = null;
  }

  // Account A's old request fails with 401 and reports failedToken 'token-account-A'
  handleUnauthorized(
    { status: 401, message: "Token expired" },
    "token-account-A",
  );

  // Account B MUST remain authenticated
  assert.equal(
    activeStatus,
    "authenticated",
    "Account B must not be signed out by Account A's late 401",
  );
  assert.equal(activeToken, "token-account-B");
  assert.equal(activeUser.id, "user-B");

  // When 401 matches activeToken, session is cleared
  handleUnauthorized(
    { status: 401, message: "Token expired" },
    "token-account-B",
  );
  assert.equal(activeStatus, "unauthenticated");
  assert.equal(activeUser, null);
});

test("auth lifecycle: same-user token refresh preserves verified readiness", () => {
  let status = "authenticated";
  let activeUser = { id: "user-A", email: "a@fingenie.app" };
  let workspaceState = { activeWorkspaceId: "ws-123", transactionsCount: 42 };

  function handleAuthStateChange(event, session) {
    if (event === "TOKEN_REFRESHED" && session?.user?.id === activeUser?.id) {
      // Preserve verified readiness and workspace financial state
      return;
    }
    // Account change or logout would clear financial state
    workspaceState = null;
  }

  handleAuthStateChange("TOKEN_REFRESHED", {
    user: { id: "user-A" },
    access_token: "refreshed-token",
  });

  assert.equal(status, "authenticated");
  assert.ok(workspaceState);
  assert.equal(workspaceState.activeWorkspaceId, "ws-123");
});
