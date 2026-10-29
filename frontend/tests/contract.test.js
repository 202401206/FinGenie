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
    credit: null,
    balance: 12500.00,
    source_row: 14,
    category: null,
    payment_method: null
  };

  const adapted = adaptTransaction(backendFixture, { filename: 'HDFC_Statement.csv', currency: 'INR' });
  
  assert.strictEqual(adapted.amount, 450.00);
  assert.strictEqual(adapted.type, 'debit');
  assert.strictEqual(adapted.category, 'Unknown');
  assert.strictEqual(adapted.payment_method, 'Unknown');
  assert.strictEqual(adapted.source_file, 'HDFC_Statement.csv');
  assert.strictEqual(adapted.source_row, 14);
  assert.strictEqual(adapted.balance, 12500.00);
});

test('adaptTransaction handles salary credit with null debit', () => {
  const salaryFixture = {
    id: 'tx-002',
    document_id: 'doc-42',
    date: '2026-10-01',
    description: 'OCTOBER SALARY CREDIT',
    debit: null,
    credit: 125000.00,
    balance: 137500.00,
    source_row: 1
  };

  const adapted = adaptTransaction(salaryFixture);
  assert.strictEqual(adapted.amount, 125000.00);
  assert.strictEqual(adapted.type, 'credit');
  assert.strictEqual(adapted.category, 'Unknown');
});

test('adaptTransactionList handles empty or corrupt fixtures gracefully', () => {
  assert.deepStrictEqual(adaptTransactionList(null), []);
  assert.deepStrictEqual(adaptTransactionList([]), []);
  const result = adaptTransactionList([{}]);
  assert.strictEqual(result.length, 1);
  assert.strictEqual(result[0].description, 'No description available');
  assert.strictEqual(result[0].category, 'Unknown');
});
