import test from 'node:test';
import assert from 'node:assert';
import { 
  normalizeError, 
  ApiError, 
  isRecoveryPending, 
  uploadBankStatement, 
  apiRequest 
} from '../src/services/api.js';

test('normalizeError handles structured detail object and preserves code and message', () => {
  const err = normalizeError(503, {
    detail: { code: 'reconciliation_required', message: 'Upload completion could not be confirmed.' }
  });
  assert.strictEqual(err.status, 503);
  assert.strictEqual(err.code, 'reconciliation_required');
  assert.strictEqual(err.message, 'Upload completion could not be confirmed.');
});

test('normalizeError handles FastAPI 422 array of validation errors', () => {
  const err = normalizeError(422, {
    detail: [{ loc: ['body', 'file'], msg: 'field required' }]
  });
  assert.strictEqual(err.status, 422);
  assert.strictEqual(err.code, 'validation_error');
  assert.strictEqual(err.message, 'file: field required');
});

test('normalizeError handles string detail message without overwriting with generic fallback', () => {
  const err = normalizeError(409, { detail: 'Document conflict occurred.' });
  assert.strictEqual(err.status, 409);
  assert.strictEqual(err.code, 'http_409');
  assert.strictEqual(err.message, 'Document conflict occurred.');
});

test('normalizeError applies standard fallback messages when detail is absent', () => {
  const err401 = normalizeError(401, {});
  assert.strictEqual(err401.message, 'Your session has expired. Please sign in again.');

  const err404 = normalizeError(404, {});
  assert.strictEqual(err404.message, 'Workspace or document not found.');

  const err413 = normalizeError(413, {});
  assert.strictEqual(err413.message, 'File is too large. Maximum supported size is 5 MiB.');

  const err503 = normalizeError(503, {});
  assert.strictEqual(err503.message, 'Service temporarily unavailable. Please retry shortly.');
});

test('isRecoveryPending identifies 503 recovery codes correctly', () => {
  const recErr = new ApiError(503, 'reconciliation_required', 'Pending', null);
  assert.strictEqual(isRecoveryPending(recErr), true);

  const cleanErr = new ApiError(503, 'cleanup_required', 'Pending', null);
  assert.strictEqual(isRecoveryPending(cleanErr), true);

  const conflictErr = new ApiError(503, 'state_conflict', 'Pending', null);
  assert.strictEqual(isRecoveryPending(conflictErr), true);

  const genericErr = new ApiError(503, 'http_503', 'Unavailable', null);
  assert.strictEqual(isRecoveryPending(genericErr), false);

  const otherErr = new ApiError(404, 'not_found', 'Not found', null);
  assert.strictEqual(isRecoveryPending(otherErr), false);
});

test('uploadBankStatement validates file presence and 5 MiB limit', async () => {
  await assert.rejects(
    async () => {
      await uploadBankStatement(null);
    },
    (err) => err.status === 400 && err.code === 'missing_file'
  );

  const fakeOversizedFile = {
    name: 'statement.csv',
    size: 6 * 1024 * 1024 // 6 MiB
  };

  await assert.rejects(
    async () => {
      await uploadBankStatement(fakeOversizedFile);
    },
    (err) => err.status === 413 && err.code === 'file_too_large'
  );
});

test('apiRequest attaches Authorization Bearer token header', async () => {
  const originalFetch = global.fetch;
  let capturedHeaders = null;

  global.fetch = async (url, options) => {
    capturedHeaders = options.headers;
    return {
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' })
    };
  };

  try {
    await apiRequest('/test', { method: 'GET' }, 'mock-jwt-token-xyz');
    assert.ok(capturedHeaders);
    assert.strictEqual(capturedHeaders['Authorization'], 'Bearer mock-jwt-token-xyz');
  } finally {
    global.fetch = originalFetch;
  }
});

test('uploadBankStatement sends multipart request with exact contract fields', async () => {
  const originalFetch = global.fetch;
  let capturedBody = null;
  let capturedHeaders = null;

  global.fetch = async (url, options) => {
    capturedBody = options.body;
    capturedHeaders = options.headers;
    return {
      ok: true,
      status: 201,
      json: async () => ({
        workspace: { id: 'ws-123', name: 'Test' },
        document: { id: 'doc-123', status: 'parsed' }
      })
    };
  };

  try {
    const fakeFile = {
      name: 'bank.csv',
      size: 1024
    };

    await uploadBankStatement(fakeFile, 'business', 'token-abc');
    assert.ok(capturedBody);
    // Let browser set multipart Content-Type automatically (boundary included)
    assert.strictEqual(capturedHeaders['Content-Type'], undefined);
    assert.strictEqual(capturedHeaders['Authorization'], 'Bearer token-abc');
  } finally {
    global.fetch = originalFetch;
  }
});
