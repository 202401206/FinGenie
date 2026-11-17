import test from 'node:test';
import assert from 'node:assert';
import { 
  formatCurrency, 
  formatBalance, 
  formatDate, 
  formatCurrencyLabel 
} from '../src/utils/formatters.js';

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

test('formatCurrency handles null currency without inventing INR or prepending null', () => {
  assert.strictEqual(formatCurrency(1250.50, null), '1,250.50');
  assert.strictEqual(formatCurrency(0, null), '0.00');
  assert.strictEqual(formatCurrency(null, null), '—');
  assert.notStrictEqual(formatCurrency(100, null), '₹100.00');
  assert.ok(!formatCurrency(100, null).includes('null'));
});

test('formatCurrency handles negative balances correctly across currencies', () => {
  assert.strictEqual(formatCurrency(-500, 'INR'), '-₹500.00');
  assert.strictEqual(formatCurrency(-1250.75, 'USD'), '-USD 1,250.75');
  assert.strictEqual(formatCurrency(-42.50, null), '-42.50');
});

test('formatCurrency supports foreign currencies without Lakh formatting', () => {
  assert.strictEqual(formatCurrency(5000, 'USD'), 'USD 5,000.00');
  assert.strictEqual(formatCurrency(1250000, 'EUR'), 'EUR 1,250,000.00');
});

test('formatCurrencyLabel returns Currency unavailable for missing or empty currency', () => {
  assert.strictEqual(formatCurrencyLabel(null), 'Currency unavailable');
  assert.strictEqual(formatCurrencyLabel(undefined), 'Currency unavailable');
  assert.strictEqual(formatCurrencyLabel(''), 'Currency unavailable');
  assert.strictEqual(formatCurrencyLabel('INR'), 'INR');
  assert.strictEqual(formatCurrencyLabel('USD'), 'USD');
});

test('formatDate prevents date shift bug across all timezones', () => {
  assert.strictEqual(formatDate('2026-10-24'), '24 Oct 2026');
  assert.strictEqual(formatDate('2026-01-01'), '01 Jan 2026');
  assert.strictEqual(formatDate('2026-12-31'), '31 Dec 2026');
  assert.strictEqual(formatDate(''), '—');
  assert.strictEqual(formatDate(null), '—');
});
