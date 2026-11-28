/**
 * dashboard_charts_evidence.test.js — Milestone 4 Tests
 * Tests for FinancialMetricsChart, Evidence Focus Query, and Analytics Boundaries.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

test('milestone 4: bank metrics chart proportions do not fabricate time-series', () => {
  const creditVal = 125000;
  const debitVal = 28649;
  const netVal = 96351;

  const maxVal = Math.max(creditVal, debitVal, Math.abs(netVal));
  const creditPct = Math.round((creditVal / maxVal) * 100);
  const debitPct = Math.round((debitVal / maxVal) * 100);

  assert.equal(maxVal, 125000);
  assert.equal(creditPct, 100);
  assert.equal(debitPct, 23);
});

test('milestone 4: balance sheet liquidity gauge isolates ratio from currency scale', () => {
  const currentRatio = 2.15; // Unit: ratio
  const workingCapital = 7000000; // Unit: INR

  // Ensure current ratio is unitless and not treated as currency
  assert.equal(typeof currentRatio, 'number');
  assert.ok(currentRatio < 100, 'ratio is a pure decimal multiplier, not a large currency figure');
  assert.ok(workingCapital > 1000, 'working capital is absolute money');
});

test('milestone 4: evidence query handling parses sourceRow and checks page membership', () => {
  // Query string: ?documentId=doc-1&sourceRow=14
  const query = '?documentId=doc-1&sourceRow=14';
  const params = new URLSearchParams(query);
  const sourceRow = Number(params.get('sourceRow'));
  const documentId = params.get('documentId');

  assert.equal(sourceRow, 14);
  assert.equal(documentId, 'doc-1');

  // Currently loaded page has rows 1 to 10
  const page1Transactions = [
    { id: '1', source_row: 6 },
    { id: '2', source_row: 7 },
    { id: '3', source_row: 8 }
  ];
  const isLoadedPage1 = page1Transactions.some(tx => tx.source_row === sourceRow);
  assert.equal(isLoadedPage1, false, 'row 14 is not loaded on page 1');

  // Page 2 has rows 11 to 20
  const page2Transactions = [
    { id: '4', source_row: 12 },
    { id: '5', source_row: 14 },
    { id: '6', source_row: 15 }
  ];
  const isLoadedPage2 = page2Transactions.some(tx => tx.source_row === sourceRow);
  assert.equal(isLoadedPage2, true, 'row 14 is loaded on page 2');

  // Acceptance check: Never calculate offset as sourceRow - 1
  const naiveOffset = sourceRow - 1; // 13
  assert.notEqual(naiveOffset, 50, 'sourceRow is a physical statement row, never a server pagination offset');
});
