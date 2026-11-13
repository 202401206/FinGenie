import test from 'node:test';
import assert from 'node:assert';

function validateEmail(email) {
  if (!email || typeof email !== 'string') return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function validatePassword(password) {
  if (!password || typeof password !== 'string') return false;
  return password.length >= 8;
}

test('validateEmail validates RFC compliant email addresses', () => {
  assert.strictEqual(validateEmail('test@fingenie.app'), true);
  assert.strictEqual(validateEmail('aditya@bank.co.in'), true);
  assert.strictEqual(validateEmail('invalid-email'), false);
  assert.strictEqual(validateEmail(''), false);
});

test('validatePassword enforces minimum length', () => {
  assert.strictEqual(validatePassword('SecretPassword123'), true);
  assert.strictEqual(validatePassword('short'), false);
  assert.strictEqual(validatePassword(''), false);
});
