/**
 * dashboard_views.test.js — Milestone 1 Tests
 * Tests for Person 3 Dashboard Views, Variants, Metric Cards, and Fixtures.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import bankAnalysisValid from '../src/mocks/dashboard/bankAnalysisValid.json' with { type: 'json' };
import balanceAnalysisValid from '../src/mocks/dashboard/balanceAnalysisValid.json' with { type: 'json' };
import unreliableAnalysis from '../src/mocks/dashboard/unreliableAnalysis.json' with { type: 'json' };
import insufficientDataAnalysis from '../src/mocks/dashboard/insufficientDataAnalysis.json' with { type: 'json' };
import { formatCurrency } from '../src/utils/formatters.js';

test('milestone 1: bank statement fixtures contain required metrics', () => {
  assert.equal(bankAnalysisValid.document_type, 'bank_statement');
  assert.equal(bankAnalysisValid.reliability, 'valid');

  const keys = bankAnalysisValid.metrics.map(m => m.key);
  assert.ok(keys.includes('total_credit'), 'must include total_credit');
  assert.ok(keys.includes('total_debit'), 'must include total_debit');
  assert.ok(keys.includes('net_cash_flow'), 'must include net_cash_flow');
});

test('milestone 1: balance sheet fixtures contain corporate liquidity metrics', () => {
  assert.equal(balanceAnalysisValid.document_type, 'balance_sheet');
  assert.equal(balanceAnalysisValid.reliability, 'valid');

  const keys = balanceAnalysisValid.metrics.map(m => m.key);
  assert.ok(keys.includes('working_capital'), 'must include working_capital');
  assert.ok(keys.includes('current_ratio'), 'must include current_ratio');
  assert.ok(keys.includes('balance_difference'), 'must include balance_difference');

  // Verify current_ratio unit is 'ratio' and not currency
  const ratioMetric = balanceAnalysisValid.metrics.find(m => m.key === 'current_ratio');
  assert.equal(ratioMetric.unit, 'ratio', 'ratios must have unit "ratio", not currency');
  assert.equal(typeof ratioMetric.value, 'number');
});

test('milestone 1: unreliable and insufficient data fixtures surface warnings', () => {
  assert.equal(unreliableAnalysis.reliability, 'unreliable');
  assert.ok(unreliableAnalysis.warnings.length > 0, 'unreliable fixtures must have warnings');

  assert.equal(insufficientDataAnalysis.reliability, 'insufficient_data');
  const unavailableMetric = insufficientDataAnalysis.metrics.find(m => m.status === 'unavailable');
  assert.ok(unavailableMetric, 'insufficient data must contain unavailable metric');
  assert.ok(unavailableMetric.reason, 'unavailable metric must have a reason string');
});

test('milestone 1: financial formatting preserves negative values and zero', () => {
  assert.equal(formatCurrency(0, 'INR'), '₹0.00', 'zero must not format as empty or missing');
  assert.equal(formatCurrency(-12500, 'INR'), '-₹12,500.00', 'negative cash flow must retain minus sign');
  assert.equal(formatCurrency(null, 'INR'), '—', 'null value must return dash');
});
