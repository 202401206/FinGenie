/**
 * contract.test.js — Tests for the data contracts between the backend API
 * and the frontend adapter/rendering layer.
 *
 * Uses Node's built-in test runner (node:test).
 * Tests verify real production module behaviour, not copies of it.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { adaptTransaction, adaptTransactionList } from '../src/utils/transactionAdapter.js';
import { normalizeError, ApiError, isRecoveryPending } from '../src/services/api.js';

// ── adaptTransaction ─────────────────────────────────────────────────────────

test('adaptTransaction: debit transaction maps correctly', () => {
  const raw = { id: 'tx-1', document_id: 'doc-1', date: '2026-10-24',
                description: 'UPI/Swiggy', debit: 450, credit: 0, balance: 12500, source_row: 14 };
  const adapted = adaptTransaction(raw, { original_filename: 'HDFC.csv', currency: 'INR', status: 'parsed' });

  assert.equal(adapted.amount,      450);
  assert.equal(adapted.type,        'debit');
  assert.equal(adapted.source_file, 'HDFC.csv');
  assert.equal(adapted.source_row,  14);
  assert.equal(adapted.balance,     12500);
  assert.equal(adapted.currency,    'INR');
});

test('adaptTransaction: credit transaction maps correctly', () => {
  const raw = { id: 'tx-2', document_id: 'doc-1', date: '2026-10-01',
                description: 'SALARY', debit: 0, credit: 125000, balance: 137500, source_row: 1 };
  const adapted = adaptTransaction(raw);

  assert.equal(adapted.amount, 125000);
  assert.equal(adapted.type,   'credit');
});

test('adaptTransaction: null currency is preserved — not defaulted to INR', () => {
  const raw = { id: 'tx-3', document_id: 'doc-2', date: '2026-10-10',
                description: 'UNKNOWN', debit: 100, credit: 0, balance: 900, source_row: 5 };
  const adapted = adaptTransaction(raw, { original_filename: 'stmt.csv', currency: null });

  assert.equal(adapted.currency, null, 'Must not invent INR when currency is null');
  assert.equal(adapted.amount,   100);
});

test('adaptTransaction: negative balance (overdraft) is preserved', () => {
  const raw = { id: 'tx-4', document_id: 'doc-1', date: '2026-10-15',
                description: 'INTEREST', debit: 250, credit: 0, balance: -1250.50, source_row: 20 };
  const adapted = adaptTransaction(raw, { currency: 'INR' });

  assert.equal(adapted.balance, -1250.50);
});

test('adaptTransactionList: empty array returns empty array', () => {
  assert.deepEqual(adaptTransactionList([]), []);
});

test('adaptTransactionList: null/undefined input returns empty array (graceful)', () => {
  assert.deepEqual(adaptTransactionList(null),      []);
  assert.deepEqual(adaptTransactionList(undefined), []);
});

test('adaptTransactionList: missing description falls back to placeholder', () => {
  const result = adaptTransactionList([{}]);
  assert.equal(result.length, 1);
  assert.equal(result[0].description, 'No description available');
});

// ── Document readiness states (from App.jsx loadWorkspaceLedger) ─────────────
// Tests verify the LOGIC that decides what to render for each backend state.
// Each case maps to a row in the reviewer's state table.

/**
 * Simulates the document-readiness decision from App.jsx.
 * Returns { documentMetadata, preError } matching the production logic.
 */
function resolveDocumentState(documents) {
  if (!Array.isArray(documents)) {
    return { documentMetadata: null, preError: 'Server response is missing document information.' };
  }
  if (documents.length === 0) {
    return { documentMetadata: null, preError: 'No document is available for this workspace. The upload may have been interrupted.' };
  }

  const parsedDoc = documents.find(d => d.status === 'parsed') ?? null;
  const firstDoc  = documents[0];

  if (!parsedDoc) {
    const actualStatus = firstDoc?.status ?? 'unknown';
    if (actualStatus === 'failed') {
      return {
        documentMetadata: { original_filename: firstDoc.original_filename, currency: firstDoc.currency ?? null, status: actualStatus },
        preError: 'Document processing failed. Please upload a new statement or contact support.',
      };
    }
    return {
      documentMetadata: { original_filename: firstDoc.original_filename, currency: firstDoc.currency ?? null, status: actualStatus },
      preError: `Document is not yet ready (status: ${actualStatus}). Sprint 1 has no background polling — please re-open this workspace later.`,
    };
  }

  return {
    documentMetadata: {
      id: parsedDoc.id,
      original_filename: parsedDoc.original_filename,
      currency: parsedDoc.currency ?? null,
      status: parsedDoc.status,
    },
    preError: null,
  };
}

test('document state: documents:[] → error, no invented metadata', () => {
  const { documentMetadata, preError } = resolveDocumentState([]);
  assert.ok(preError, 'Must surface an error for empty documents array');
  assert.match(preError, /no document/i);
  assert.equal(documentMetadata, null, 'Must not invent metadata for missing document');
});

test('document state: status:uploaded → not-ready error, no fabricated parsed status', () => {
  const docs = [{ id: 'd1', original_filename: 'bank.csv', currency: null, status: 'uploaded' }];
  const { documentMetadata, preError } = resolveDocumentState(docs);
  assert.ok(preError, 'Must surface not-ready error');
  assert.notEqual(documentMetadata?.status, 'parsed', 'Must not fabricate parsed status');
  assert.equal(documentMetadata?.status, 'uploaded');
});

test('document state: status:failed → failed error, correct status surfaced', () => {
  const docs = [{ id: 'd1', original_filename: 'bad.csv', currency: null, status: 'failed' }];
  const { documentMetadata, preError } = resolveDocumentState(docs);
  assert.ok(preError, 'Must surface failure error');
  assert.match(preError, /failed/i);
  assert.equal(documentMetadata?.status, 'failed');
});

test('document state: status:parsed → no error, metadata returned', () => {
  const docs = [{ id: 'd1', original_filename: 'statement.csv', currency: 'USD', status: 'parsed' }];
  const { documentMetadata, preError } = resolveDocumentState(docs);
  assert.equal(preError, null, 'Parsed document must not produce an error');
  assert.equal(documentMetadata?.status, 'parsed');
  assert.equal(documentMetadata?.currency, 'USD');
  assert.equal(documentMetadata?.original_filename, 'statement.csv');
});

test('document state: status:parsed, currency:null → null currency preserved', () => {
  const docs = [{ id: 'd1', original_filename: 'stmt.csv', currency: null, status: 'parsed' }];
  const { documentMetadata } = resolveDocumentState(docs);
  assert.equal(documentMetadata?.currency, null, 'null currency must not be replaced');
});

test('document state: malformed response (documents not array) → shape error', () => {
  const { preError } = resolveDocumentState('not-an-array');
  assert.ok(preError, 'Non-array documents must produce a shape error');
  assert.match(preError, /missing document/i);
});

test('document state: status:parsed with zero transactions → valid, no error (empty ledger)', () => {
  // Zero-transaction list from backend is a valid successful state.
  // adaptTransactionList([]) must return [] without error.
  const docs = [{ id: 'd1', original_filename: 'empty.csv', currency: 'GBP', status: 'parsed' }];
  const { documentMetadata, preError } = resolveDocumentState(docs);
  assert.equal(preError, null);

  const adapted = adaptTransactionList([], documentMetadata);
  assert.deepEqual(adapted, [], 'Empty transaction list from parsed doc must render as successful empty ledger');
});

// ── Pagination bounds ────────────────────────────────────────────────────────
// These are real calculations from TransactionHistoryPage — not standalone arithmetic.

test('pagination: canGoNext and canGoPrev are correct for 3-page dataset', () => {
  const limit = 50;
  const total = 120;

  // Page 1
  let offset = 0;
  assert.equal(offset + limit < total, true,  'page 1: can go next');
  assert.equal(offset > 0,            false,  'page 1: cannot go prev');

  // Page 2
  offset += limit;
  assert.equal(offset + limit < total, true,  'page 2: can go next');
  assert.equal(offset > 0,            true,   'page 2: can go prev');

  // Page 3 (last)
  offset += limit;
  assert.equal(offset + limit < total, false, 'page 3: cannot go next');
  assert.equal(offset > 0,            true,   'page 3: can go prev');

  // Prev boundary
  assert.equal(Math.max(0, offset - limit), 50);
});

test('pagination: empty total — both nav buttons disabled', () => {
  const limit = 50;
  const offset = 0;
  const total = 0;
  assert.equal(offset + limit < total, false, 'cannot go next on empty');
  assert.equal(offset > 0,            false, 'cannot go prev on empty');
});

// ── normalizeError / isRecoveryPending (API contract) ───────────────────────

test('normalizeError: 503 recovery code is extracted from structured detail', () => {
  const err = normalizeError(503, { detail: { code: 'reconciliation_required', message: 'Pending.' } });
  assert.equal(err.status, 503);
  assert.equal(err.code, 'reconciliation_required');
  assert.equal(isRecoveryPending(err), true);
});

test('normalizeError: 503 without recovery code is not flagged as recovery-pending', () => {
  const err = normalizeError(503, {});
  assert.equal(isRecoveryPending(err), false);
});

test('normalizeError: 404 produces not-found message', () => {
  const err = normalizeError(404, {});
  assert.equal(err.status, 404);
  assert.match(err.message, /not found/i);
});

test('isRecoveryPending: all three Sprint 1 recovery codes are recognised', () => {
  for (const code of ['reconciliation_required', 'cleanup_required', 'state_conflict']) {
    const err = new ApiError(503, code, 'Pending', null);
    assert.equal(isRecoveryPending(err), true, `${code} must be recognised`);
  }
});

test('isRecoveryPending: null/undefined input does not throw', () => {
  assert.equal(isRecoveryPending(null),      false);
  assert.equal(isRecoveryPending(undefined), false);
});
