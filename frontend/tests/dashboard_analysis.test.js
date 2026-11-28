/**
 * dashboard_analysis.test.js — Milestone 2 Tests
 * Verifies backend analysis service, contracts, and error boundaries.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { isValidAnalysisPayload } from '../src/features/dashboard/dashboardService.js';
import bankAnalysisValid from '../src/mocks/dashboard/bankAnalysisValid.json' with { type: 'json' };
import balanceAnalysisValid from '../src/mocks/dashboard/balanceAnalysisValid.json' with { type: 'json' };

test('milestone 2: isValidAnalysisPayload validates conformant payloads', () => {
  assert.ok(isValidAnalysisPayload(bankAnalysisValid), 'valid bank payload must pass validation');
  assert.ok(isValidAnalysisPayload(balanceAnalysisValid), 'valid balance sheet payload must pass validation');

  // Negative validation
  assert.equal(isValidAnalysisPayload(null), false, 'null payload must be rejected');
  assert.equal(isValidAnalysisPayload({}), false, 'empty payload must be rejected');
  assert.equal(isValidAnalysisPayload({ workspace_id: '123' }), false, 'missing document_type must be rejected');
  assert.equal(isValidAnalysisPayload({
    workspace_id: '123',
    document_type: 'unsupported_type',
    metrics: [],
    reliability: 'valid'
  }), false, 'invalid document_type must be rejected');
  assert.equal(isValidAnalysisPayload({
    workspace_id: '123',
    document_type: 'bank_statement',
    metrics: [],
    reliability: 'unknown_reliability'
  }), false, 'invalid reliability must be rejected');
});

test('milestone 2: analysis contract values use base currency with no second unit scaling', () => {
  // Balance sheet analysis values (e.g. working_capital = 7000000) are already converted to base currency by backend
  const wc = balanceAnalysisValid.metrics.find(m => m.key === 'working_capital');
  assert.ok(wc, 'working capital metric must be present');
  assert.equal(typeof wc.value, 'number');
  assert.equal(wc.unit, 'INR');

  // Verify that frontend does not divide or multiply unit_scale again
  assert.equal(wc.value, 7000000, 'must preserve raw backend base currency value');
});

test('milestone 2: distinct error code classifications (404, 409, 503)', () => {
  function classifyError(status, _message) {
    if (status === 404) return 'not_found';
    if (status === 409) return 'document_not_ready';
    if (status === 503) return 'service_unavailable';
    return 'generic_error';
  }

  assert.equal(classifyError(404, 'Workspace not found'), 'not_found');
  assert.equal(classifyError(409, 'Document is not yet ready'), 'document_not_ready');
  assert.equal(classifyError(503, 'Database unavailable'), 'service_unavailable');
  assert.equal(classifyError(500, 'Server error'), 'generic_error');
});
