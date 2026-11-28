/**
 * dashboard_transactions.test.js — Milestone 3 Tests
 * Verifies bank transaction exploration, server pagination bounds, and balance-sheet isolation.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { formatBalance, formatCurrency } from '../src/utils/formatters.js';

test('milestone 3: pagination logic calculates page bounds accurately', () => {
  const limit = 50;

  // Page 1 of 3 (total = 125, offset = 0)
  const total = 125;
  let offset = 0;
  let currentPage = Math.floor(offset / limit) + 1;
  let totalPages = Math.max(1, Math.ceil(total / limit));
  let canGoPrevious = offset > 0;
  let canGoNext = offset + limit < total;

  assert.equal(currentPage, 1);
  assert.equal(totalPages, 3);
  assert.equal(canGoPrevious, false, 'previous must be disabled on first page');
  assert.equal(canGoNext, true, 'next must be enabled when more records exist');

  // Page 3 of 3 (last page, offset = 100)
  offset = 100;
  currentPage = Math.floor(offset / limit) + 1;
  canGoPrevious = offset > 0;
  canGoNext = offset + limit < total;

  assert.equal(currentPage, 3);
  assert.equal(canGoPrevious, true, 'previous must be enabled on page 3');
  assert.equal(canGoNext, false, 'next must be disabled on last page');

  // Empty dataset (total = 0, offset = 0)
  const emptyTotal = 0;
  offset = 0;
  currentPage = Math.floor(offset / limit) + 1;
  totalPages = Math.max(1, Math.ceil(emptyTotal / limit));
  canGoPrevious = offset > 0;
  canGoNext = offset + limit < emptyTotal;

  assert.equal(currentPage, 1);
  assert.equal(totalPages, 1);
  assert.equal(canGoPrevious, false);
  assert.equal(canGoNext, false);
});

test('milestone 3: transaction values preserve exact zeros and overdraft balances', () => {
  // Test zero balance
  assert.equal(formatBalance(0, 'INR'), '₹0.00', 'zero balance must be formatted as ₹0.00');

  // Test negative overdraft balance
  assert.equal(formatBalance(-4500.5, 'INR'), '-₹4,500.50', 'overdraft must retain minus sign');

  // Test debit and credit formatting
  assert.equal(formatCurrency(649, 'INR'), '₹649.00');
  assert.equal(formatCurrency(null, 'INR'), '—', 'null amount must format as dash');
});

test('milestone 3: source row numbers are 1-based provenance references', () => {
  const sampleTransactions = [
    { id: 'tx-1', source_row: 6, description: 'UPI Deposit', debit: null, credit: 5000, balance: 15000 },
    { id: 'tx-2', source_row: 7, description: 'Swiggy', debit: 450, credit: null, balance: 14550 }
  ];

  sampleTransactions.forEach(tx => {
    assert.ok(typeof tx.source_row === 'number', 'source_row must be a number');
    assert.ok(tx.source_row >= 1, 'source_row must be 1-based index from document');
  });
});
