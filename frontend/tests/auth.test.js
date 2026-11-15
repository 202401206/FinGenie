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

function checkIsLiveSupabase(url, publishableKey, anonKey) {
  const key = publishableKey || anonKey;
  return Boolean(
    url && 
    key && 
    !url.includes('YOUR_PROJECT_REF') && 
    !url.includes('your-project-ref')
  );
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

test('checkIsLiveSupabase correctly recognizes VITE_SUPABASE_PUBLISHABLE_KEY', () => {
  const url = 'https://btkiojssgksyfulrlzjs.supabase.co';
  const pubKey = 'sb_publishable_CAGjDTxrNINr9eOIVel-hg_bJmDm9f1';
  
  // Enabled via publishable key
  assert.strictEqual(checkIsLiveSupabase(url, pubKey, null), true);
  
  // Enabled via fallback anon key
  assert.strictEqual(checkIsLiveSupabase(url, null, 'anon-key-123'), true);
  
  // Disabled if unconfigured placeholder
  assert.strictEqual(checkIsLiveSupabase('https://YOUR_PROJECT_REF.supabase.co', pubKey, null), false);
  assert.strictEqual(checkIsLiveSupabase('', '', null), false);
});
