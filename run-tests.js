import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const testDir = fs.existsSync(path.join(__dirname, 'frontend', 'tests')) 
  ? path.join(__dirname, 'frontend') 
  : __dirname;

const testFiles = [
  path.join(testDir, 'tests', 'formatters.test.js'),
  path.join(testDir, 'tests', 'auth.test.js'),
  path.join(testDir, 'tests', 'transactions.test.js')
];

const testProcess = spawn(process.execPath, ['--test', ...testFiles], {
  cwd: testDir,
  stdio: 'inherit'
});

testProcess.on('close', (code) => {
  process.exit(code);
});
