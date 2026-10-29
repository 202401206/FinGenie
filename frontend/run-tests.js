import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const testFiles = [
  'tests/contract.test.js',
  'tests/formatters.test.js',
  'tests/auth.test.js'
];

const testProcess = spawn(process.execPath, ['--test', ...testFiles], {
  cwd: __dirname,
  stdio: 'inherit'
});

testProcess.on('close', (code) => {
  process.exit(code);
});
