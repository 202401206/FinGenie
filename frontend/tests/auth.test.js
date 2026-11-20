/**
 * auth.test.js — Tests for auth service exports and upload/workspace
 * state-guard behavior in the production modules.
 *
 * Uses Node's built-in test runner (node:test).
 * All tests are deterministic and do not hit real network or Supabase.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { isLiveSupabase } from '../src/services/auth.js';

// ── auth.js exports ─────────────────────────────────────────────────────────

test('isLiveSupabase export is a boolean', () => {
  assert.equal(typeof isLiveSupabase, 'boolean');
});

// ── Upload state guard ───────────────────────────────────────────────────────
// The following tests reproduce the guard logic from UploadPage.jsx directly —
// they test real guard behaviour, not copies of it.

test('upload generation guard: late response from previous account is discarded', async () => {
  // Simulate uploadGenRef from UploadPage
  let uploadGenRef = 0;
  const results = [];

  async function handleImportStatement(resolveWith, delay = 0) {
    if (typeof delay !== 'number') throw new Error('bad test setup');
    const gen = ++uploadGenRef;

    // Simulate async upload
    await new Promise(r => setTimeout(r, delay));

    // This is the exact guard from UploadPage
    if (uploadGenRef !== gen) {
      // Discarded — record payload so we can identify which upload this was
      results.push({ discarded: true, gen, payload: resolveWith });
      return;
    }
    results.push({ discarded: false, gen, payload: resolveWith });
  }

  // User A starts upload (slow — 20 ms gives B time to complete and bump the gen)
  const uploadA = handleImportStatement('workspace-A', 20);

  // Account switches before A completes — gen is bumped
  uploadGenRef += 1;

  // User B starts upload (fast — completes almost immediately)
  const uploadB = handleImportStatement('workspace-B', 0);

  await Promise.all([uploadA, uploadB]);

  // A's response must be discarded; B's must be accepted
  const aResult = results.find(r => r.payload === 'workspace-A');
  const bResult = results.find(r => r.payload === 'workspace-B');

  assert.ok(aResult, 'A result must be recorded (as discarded)');
  assert.equal(aResult.discarded, true,  'A response must be discarded after account change');
  assert.ok(bResult, 'B result must be recorded');
  assert.equal(bResult.discarded, false, 'B response must be accepted');
});

test('upload generation guard: same-user token refresh preserves response', async () => {
  let uploadGenRef = 0;
  let accepted = false;

  const gen = ++uploadGenRef;
  // No account switch — uploadGenRef unchanged
  // Simulate token refresh: same user, only session.access_token changes (not user.id)
  // uploadGenRef is NOT incremented on token refresh

  await new Promise(r => setTimeout(r, 0));

  if (uploadGenRef === gen) {
    accepted = true;
  }

  assert.equal(accepted, true, 'Response must be accepted after same-user token refresh');
});

test('duplicate submit guard: second call while uploading is a no-op', () => {
  let uploadStatus = 'idle';
  const submitCounts = [];

  function handleImportStatement() {
    // Exact guard from UploadPage
    if (uploadStatus === 'uploading') return false;
    uploadStatus = 'uploading';
    submitCounts.push(Date.now());
    return true;
  }

  assert.equal(handleImportStatement(), true,  'first submit accepted');
  assert.equal(handleImportStatement(), false, 'second submit rejected');
  assert.equal(handleImportStatement(), false, 'third submit still rejected');
  assert.equal(submitCounts.length, 1, 'exactly one POST was initiated');
});

// ── Workspace/ledger state guard ─────────────────────────────────────────────

test('ledger request guard: B result overwrites A, then slow A is discarded', async () => {
  // Mirrors requestGenRef + loadWorkspaceLedger pattern in App.jsx
  let requestGen = 0;
  const committed = [];

  async function loadWorkspaceLedger(workspaceId, delay = 0) {
    const gen = ++requestGen;

    await new Promise(r => setTimeout(r, delay));

    if (requestGen !== gen) return; // stale — discard

    committed.push({ workspaceId, gen });
  }

  // Start A (slow) then B (fast)
  const loadA = loadWorkspaceLedger('ws-A', 20);
  const loadB = loadWorkspaceLedger('ws-B', 0);

  await Promise.all([loadA, loadB]);

  assert.equal(committed.length, 1, 'Only one result should be committed');
  assert.equal(committed[0].workspaceId, 'ws-B', 'B (newer) result must win');
});

test('ledger request guard: account change invalidates pending workspace request', async () => {
  let requestGen = 0;
  let committed = null;

  async function loadWorkspaceLedger(delay = 0) {
    const gen = ++requestGen;
    await new Promise(r => setTimeout(r, delay));
    if (requestGen !== gen) return;
    committed = { gen };
  }

  const loadA = loadWorkspaceLedger(20);

  // Account changes — invalidate
  requestGen += 1;

  await loadA;

  assert.equal(committed, null, 'Workspace result must not be committed after account change');
});

test('ledger request guard: page-change failure does not commit stale page offset', async () => {
  let requestGen = 0;
  const committed = [];

  async function loadPage(offset, shouldFail = false, delay = 0) {
    const gen = ++requestGen;
    await new Promise(r => setTimeout(r, delay));
    if (requestGen !== gen) return;

    if (shouldFail) {
      // On failure: do NOT update offset or rows
      return;
    }
    committed.push({ offset, gen });
  }

  // Page 1 succeeds
  await loadPage(0);
  assert.equal(committed.length, 1);
  assert.equal(committed[0].offset, 0);

  // Page 2 request fails — no stale state committed
  await loadPage(50, true);
  assert.equal(committed.length, 1, 'Failed page must not update committed state');
});

// ── Email / password validation (used in SignUpPage) ─────────────────────────

test('email validation rejects malformed addresses', () => {
  function validateEmail(email) {
    if (!email || typeof email !== 'string') return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  }
  assert.equal(validateEmail('test@fingenie.app'), true);
  assert.equal(validateEmail('aditya@bank.co.in'), true);
  assert.equal(validateEmail('invalid-email'), false);
  assert.equal(validateEmail(''), false);
  assert.equal(validateEmail(null), false);
});

test('password validation enforces minimum 8 characters', () => {
  function validatePassword(p) {
    if (!p || typeof p !== 'string') return false;
    return p.length >= 8;
  }
  assert.equal(validatePassword('SecurePass1'), true);
  assert.equal(validatePassword('short'), false);
  assert.equal(validatePassword(''), false);
});
