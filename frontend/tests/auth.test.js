import test from 'node:test';
import assert from 'node:assert';
import {
  validateEmail,
  validatePassword,
  validateSignUpForm,
  searchBanks,
  login,
  signUp,
  updateAccountType,
  updateBankSelection,
  completeOnboarding,
  logout
} from '../src/services/authService.js';

test('validateEmail validates RFC compliant email addresses', () => {
  assert.strictEqual(validateEmail('test@fingenie.app').valid, true);
  assert.strictEqual(validateEmail('user.name@bank.co.in').valid, true);
  assert.strictEqual(validateEmail('invalid-email').valid, false);
  assert.strictEqual(validateEmail('').valid, false);
});

test('validatePassword enforces length and complexity', () => {
  assert.strictEqual(validatePassword('Pass1234').valid, true);
  assert.strictEqual(validatePassword('short1').valid, false); // <8 chars
  assert.strictEqual(validatePassword('allcharacters').valid, false); // no number
  assert.strictEqual(validatePassword('12345678').valid, false); // no letter
});

test('validateSignUpForm catches mismatches and omissions', () => {
  const invalid = validateSignUpForm({
    fullName: '',
    email: 'bad',
    password: 'Password123',
    confirmPassword: 'MismatchPassword',
    termsAccepted: false
  });
  assert.strictEqual(invalid.valid, false);
  assert.ok(invalid.errors.fullName);
  assert.ok(invalid.errors.email);
  assert.ok(invalid.errors.confirmPassword);
  assert.ok(invalid.errors.terms);

  const valid = validateSignUpForm({
    fullName: 'Pooja Verma',
    email: 'pooja@example.com',
    password: 'SecretPassword123',
    confirmPassword: 'SecretPassword123',
    termsAccepted: true
  });
  assert.strictEqual(valid.valid, true);
});

test('searchBanks filters Indian banks by name or shortCode', () => {
  const sbiResults = searchBanks('sbi');
  assert.strictEqual(sbiResults.length, 1);
  assert.strictEqual(sbiResults[0].id, 'sbi');

  const bankResults = searchBanks('Bank');
  assert.ok(bankResults.length >= 5);

  const emptySearch = searchBanks('');
  assert.ok(emptySearch.length >= 8);
});

test('login authenticates known user and rejects bad passwords', async () => {
  const res = await login({ email: 'demo@fingenie.app', password: 'Password@123' });
  assert.strictEqual(res.user.email, 'demo@fingenie.app');
  assert.strictEqual(res.user.profile.bank_name, 'HDFC Bank');

  await assert.rejects(
    async () => await login({ email: 'demo@fingenie.app', password: 'WrongPassword' }),
    /Invalid email or password/
  );
});

test('multi-step onboarding progression functions end-to-end', async () => {
  const email = `newuser_${Date.now()}@fingenie.app`;
  
  // Step 1: Account registration
  const { user } = await signUp({
    fullName: 'Rahul Dravid',
    email,
    password: 'StrongPassword123',
    confirmPassword: 'StrongPassword123',
    termsAccepted: true
  });
  assert.strictEqual(user.profile.full_name, 'Rahul Dravid');
  assert.strictEqual(user.profile.onboarding_completed, false);

  // Step 2: Account type selection (Business)
  const p2 = await updateAccountType(user.id, 'business');
  assert.strictEqual(p2.account_type, 'business');

  // Step 3: Bank selection (ICICI Bank)
  const p3 = await updateBankSelection(user.id, { bankId: 'icici', bankName: 'ICICI Bank' });
  assert.strictEqual(p3.bank_id, 'icici');
  assert.strictEqual(p3.bank_name, 'ICICI Bank');

  // Step 4: Finish onboarding
  const p4 = await completeOnboarding(user.id);
  assert.strictEqual(p4.onboarding_completed, true);

  await logout();
});
