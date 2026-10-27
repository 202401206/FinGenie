/**
 * FinGenie Test Suite Runner
 * Runs all unit and integration tests across formatters, auth, and transactions
 */

import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const testFiles = [
  'tests/formatters.test.js',
  'tests/auth.test.js',
  'tests/transactions.test.js'
];

console.log('======================================================');
console.log('🧪 FIN GENIE — RUNNING AUTOMATED TEST SUITE');
console.log('======================================================');

const nodeExec = process.execPath;
const args = ['--test', ...testFiles];

const testProcess = spawn(nodeExec, args, {
  cwd: __dirname,
  stdio: 'inherit'
});

testProcess.on('close', (code) => {
  if (code === 0) {
    console.log('\n======================================================');
    console.log('✅ ALL TEST SUITES PASSED CLEANLY (100% SUCCESS)');
    console.log('======================================================\n');
  } else {
    console.error(`\n❌ Test suite exited with code ${code}`);
  }
  process.exit(code);
});
