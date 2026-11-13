import test from 'node:test';
import assert from 'node:assert';
import { adaptTransaction, adaptTransactionList } from '../src/utils/transactionAdapter.js';

test('adaptTransaction correctly parses backend debit and credit structure', () => {
  const backendFixture = {
    id: 'tx-001',
    document_id: 'doc-42',
    date: '2026-10-24',
    description: 'UPI/Swiggy Order 492',
    debit: 450.00,
    credit: 0,
    balance: 12500.00,
    source_row: 14
  };

  const adapted = adaptTransaction(backendFixture, { filename: 'HDFC_Statement.csv', currency: 'INR' });
  
  assert.strictEqual(adapted.amount, 450.00);
  assert.strictEqual(adapted.type, 'debit');
  assert.strictEqual(adapted.source_file, 'HDFC_Statement.csv');
  assert.strictEqual(adapted.source_row, 14);
  assert.strictEqual(adapted.balance, 12500.00);
});

test('adaptTransaction handles salary credit with zero debit', () => {
  const salaryFixture = {
    id: 'tx-002',
    document_id: 'doc-42',
    date: '2026-10-01',
    description: 'OCTOBER SALARY CREDIT',
    debit: 0,
    credit: 125000.00,
    balance: 137500.00,
    source_row: 1
  };

  const adapted = adaptTransaction(salaryFixture);
  assert.strictEqual(adapted.amount, 125000.00);
  assert.strictEqual(adapted.type, 'credit');
});

test('adaptTransactionList handles empty or corrupt fixtures gracefully', () => {
  assert.deepStrictEqual(adaptTransactionList(null), []);
  assert.deepStrictEqual(adaptTransactionList([]), []);
  const result = adaptTransactionList([{}]);
  assert.strictEqual(result.length, 1);
  assert.strictEqual(result[0].description, 'No description available');
});

test('Sprint 1 pagination bounds calculation', () => {
  const limit = 50;
  
  // Page 1: offset 0, total 120
  let offset = 0;
  let total = 120;
  let canGoNext = offset + limit < total;
  let canGoPrev = offset > 0;
  assert.strictEqual(canGoNext, true);
  assert.strictEqual(canGoPrev, false);

  // Page 2: offset 50
  offset = offset + limit;
  canGoNext = offset + limit < total;
  canGoPrev = offset > 0;
  assert.strictEqual(canGoNext, true);
  assert.strictEqual(canGoPrev, true);

  // Page 3: offset 100
  offset = offset + limit;
  canGoNext = offset + limit < total; // 100 + 50 < 120 is false
  canGoPrev = offset > 0;
  assert.strictEqual(canGoNext, false);
  assert.strictEqual(canGoPrev, true);

  // Previous page boundary
  const prevOffset = Math.max(0, offset - limit);
  assert.strictEqual(prevOffset, 50);
});
