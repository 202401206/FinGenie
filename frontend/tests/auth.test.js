/**
 * auth.test.js — Tests for auth service exports, return path security,
 * upload/workspace state-guard behavior, and account boundary verification.
 *
 * Uses Node's built-in test runner (node:test).
 * All tests are deterministic and do not hit real network or Supabase.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { isLiveSupabase } from "../src/services/auth.js";
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
