import fs from 'node:fs/promises';
import { createTestDatabase } from './database.mjs';

const db = await createTestDatabase();
try {
  const results = await db.exec(await fs.readFile(new URL('security_audit.sql', import.meta.url), 'utf8'));
  console.log(results.at(-1).rows[0].result);
} catch (error) {
  console.error('Security audit failed:', error.message, 'SQLSTATE:', error.code);
  process.exitCode = 1;
} finally {
  await db.close();
}
