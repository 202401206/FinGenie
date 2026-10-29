import test from 'node:test';
import assert from 'node:assert';
import { formatCurrency, formatBalance, formatDate } from '../src/utils/formatters.js';

test('formatBalance explicitly distinguishes zero from missing values', () => {
  assert.strictEqual(formatBalance(0, 'INR'), '₹0.00');
  assert.strictEqual(formatBalance(null, 'INR'), '—');
  assert.strictEqual(formatBalance(undefined, 'INR'), '—');
  assert.strictEqual(formatBalance('', 'INR'), '—');
});

test('formatCurrency distinguishes missing amount from zero', () => {
  assert.strictEqual(formatCurrency(0, 'INR'), '₹0.00');
  assert.strictEqual(formatCurrency(null, 'INR'), '—');
  assert.strictEqual(formatCurrency(undefined, 'INR'), '—');
  assert.strictEqual(formatCurrency(125000, 'INR'), '₹1,25,000.00');
  assert.strictEqual(formatCurrency(15000000, 'INR'), '₹1,50,00,000.00');
});

test('formatCurrency supports foreign currencies without Lakh formatting', () => {
  assert.strictEqual(formatCurrency(5000, 'USD'), 'USD 5,000.00');
  assert.strictEqual(formatCurrency(1250000, 'EUR'), 'EUR 1,250,000.00');
});

test('formatDate prevents date shift bug across all timezones', () => {
  assert.strictEqual(formatDate('2026-10-24'), '24 Oct 2026');
  assert.strictEqual(formatDate('2026-01-01'), '01 Jan 2026');
  assert.strictEqual(formatDate('2026-12-31'), '31 Dec 2026');
  assert.strictEqual(formatDate(''), '—');
  assert.strictEqual(formatDate(null), '—');
});
