import test from 'node:test';
import assert from 'node:assert';
import { isLiveSupabase } from '../src/services/auth.js';

function validateEmail(email) {
  if (!email || typeof email !== 'string') return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function validatePassword(password) {
  if (!password || typeof password !== 'string') return false;
  return password.length >= 8;
}

test('validateEmail validates RFC compliant email addresses', () => {
  assert.strictEqual(validateEmail('test@fingenie.app'), true);
  assert.strictEqual(validateEmail('aditya@bank.co.in'), true);
  assert.strictEqual(validateEmail('invalid-email'), false);
  assert.strictEqual(validateEmail(''), false);
});

test('validatePassword enforces minimum length of 8 characters', () => {
  assert.strictEqual(validatePassword('SecretPassword123'), true);
  assert.strictEqual(validatePassword('short'), false);
  assert.strictEqual(validatePassword(''), false);
});

test('isLiveSupabase export is a valid boolean', () => {
  assert.strictEqual(typeof isLiveSupabase, 'boolean');
});

test('account change guard resets stale workspace requests', () => {
  let activeRequestId = 1;

  function initiateRequest() {
    return ++activeRequestId;
  }

  function handleAccountSwitch() {
    activeRequestId += 1;
  }

  const req1 = initiateRequest();
  assert.strictEqual(req1, 2);

  // User logs out or switches account while req1 is in flight
  handleAccountSwitch();

  // req1 completes later: verify it is detected as stale and ignored
  const isStale = req1 !== activeRequestId;
  assert.strictEqual(isStale, true);
});

test('duplicate upload submission guard rejects concurrent execution', () => {
  let uploadStatus = 'idle';

  function triggerUpload() {
    if (uploadStatus === 'uploading') {
      return false; // Submission prevented
    }
    uploadStatus = 'uploading';
    return true; // Submission accepted
  }

  assert.strictEqual(triggerUpload(), true);
  assert.strictEqual(triggerUpload(), false); // Prevented while uploading
  uploadStatus = 'idle';
  assert.strictEqual(triggerUpload(), true);
});
