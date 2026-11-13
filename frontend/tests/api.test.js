import test from 'node:test';
import assert from 'node:assert';

function normalizeError(status, data) {
  let code = `http_${status}`;
  let message = 'An unexpected error occurred. Please try again.';

  if (data?.detail) {
    if (typeof data.detail === 'string') {
      message = data.detail;
    } else if (Array.isArray(data.detail)) {
      message = data.detail.map(d => `${d.loc?.slice(-1)[0] || 'field'}: ${d.msg}`).join(', ');
      code = 'validation_error';
    } else if (typeof data.detail === 'object') {
      code = data.detail.code || code;
      message = data.detail.message || message;
    }
  }

  if (status === 401) message = 'Your session has expired. Please sign in again.';
  if (status === 404) message = 'Workspace or document not found.';
  if (status === 413) message = 'File is too large. Maximum supported size is 5 MiB.';
  if (status === 415) message = 'Unsupported file format. Please upload a valid .csv or .xlsx file.';
  if (status === 503) message = 'Service temporarily unavailable. Please retry shortly.';

  return { status, code, message };
}

test('normalizeError handles structured detail object per handoff spec', () => {
  const err = normalizeError(404, {
    detail: { code: 'workspace_not_found', message: 'Workspace not found.' }
  });
  assert.strictEqual(err.status, 404);
  assert.strictEqual(err.code, 'workspace_not_found');
  assert.strictEqual(err.message, 'Workspace or document not found.');
});

test('normalizeError handles FastAPI 422 array of validation errors', () => {
  const err = normalizeError(422, {
    detail: [{ loc: ['body', 'file'], msg: 'field required' }]
  });
  assert.strictEqual(err.status, 422);
  assert.strictEqual(err.code, 'validation_error');
  assert.strictEqual(err.message, 'file: field required');
});

test('normalizeError handles string detail message', () => {
  const err = normalizeError(409, { detail: 'Document conflict occurred.' });
  assert.strictEqual(err.status, 409);
  assert.strictEqual(err.message, 'Document conflict occurred.');
});
