import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.join(__dirname, 'frontend');

const testProcess = spawn(process.execPath, ['run-tests.js'], {
  cwd: frontendDir,
  stdio: 'inherit'
});

testProcess.on('close', (code) => {
  process.exit(code);
});
