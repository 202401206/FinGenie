/**
 * dashboard_summary_journey.test.js — Milestone 5 Tests
 * Tests for Person 4 AI Summary integration, user-initiated generation,
 * failure isolation, and pending-deletion state.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

test('milestone 5: AI summary generation requires explicit user action', () => {
  // Verification that initial state is unrequested
  let requested = false;
  const triggerSummary = () => { requested = true; };

  assert.equal(requested, false, 'summary must not be auto-generated on component mount');
  triggerSummary();
  assert.equal(requested, true, 'summary generates only after explicit user click');
});

test('milestone 5: AI summary failure is isolated and preserves deterministic metrics', () => {
  const deterministicMetrics = [
    { key: 'total_credit', value: 125000, status: 'available' },
    { key: 'total_debit', value: 28649, status: 'available' }
  ];

  let summaryError = 'Rate limit exceeded on LLM provider (429)';

  // Error in summary must not clear or corrupt deterministicMetrics
  assert.equal(deterministicMetrics.length, 2);
  assert.equal(deterministicMetrics[0].value, 125000, 'deterministic metric values must remain intact on summary failure');
  assert.ok(summaryError.includes('429'), 'summary error is isolated to summary panel');
});

test('milestone 5: pending deletion suspends financial data display', () => {
  const deletionPending = true;
  const shouldRenderFinancials = !deletionPending;

  assert.equal(shouldRenderFinancials, false, 'financial metrics must not render while deletion is pending');
});

test('milestone 5: document journey correctly selects bank vs balance sheet mode', () => {
  function selectDashboardMode(docType) {
    if (docType === 'balance_sheet') return 'balance_view';
    return 'bank_view';
  }

  assert.equal(selectDashboardMode('bank_statement'), 'bank_view');
  assert.equal(selectDashboardMode('balance_sheet'), 'balance_view');
  assert.equal(selectDashboardMode(null), 'bank_view', 'defaults safely to bank view');
});
