import test from 'node:test';
import assert from 'node:assert';
import { formatINR, formatCompactINR, formatDate, parseINR } from '../src/utils/formatters.js';

test('formatINR correctly formats standard Indian amounts', () => {
  assert.strictEqual(formatINR(125000), '₹1,25,000.00');
  assert.strictEqual(formatINR(649), '₹649.00');
  assert.strictEqual(formatINR(0), '₹0.00');
});

test('formatINR correctly groups Lakhs and Crores', () => {
  assert.strictEqual(formatINR(15000000), '₹1,50,00,000.00');
  assert.strictEqual(formatINR(2500000), '₹25,00,000.00');
  assert.strictEqual(formatINR(100000), '₹1,00,000.00');
});

test('formatINR handles negative amounts and optional sign flags', () => {
  assert.strictEqual(formatINR(-4500), '-₹4,500.00');
  assert.strictEqual(formatINR(125000, { showSign: true }), '+₹1,25,000.00');
  assert.strictEqual(formatINR(125000, { includeDecimals: false }), '₹1,25,000');
});

test('formatCompactINR formats Lakhs, Crores, and Thousands compactly', () => {
  assert.strictEqual(formatCompactINR(125000), '₹1.25 L');
  assert.strictEqual(formatCompactINR(25000000), '₹2.50 Cr');
  assert.strictEqual(formatCompactINR(45000), '₹45.0 K');
  assert.strictEqual(formatCompactINR(500), '₹500');
});

test('formatDate converts ISO dates to Indian banking DD MMM YYYY format', () => {
  assert.strictEqual(formatDate('2026-10-24'), '24 Oct 2026');
  assert.strictEqual(formatDate('2026-01-05'), '05 Jan 2026');
  assert.strictEqual(formatDate(''), '—');
});

test('parseINR extracts float values from formatted INR strings', () => {
  assert.strictEqual(parseINR('₹1,25,000.50'), 125000.5);
  assert.strictEqual(parseINR('₹25,000'), 25000);
  assert.strictEqual(parseINR(''), 0);
});
