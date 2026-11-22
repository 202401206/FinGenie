import fs from 'node:fs/promises';
import { createTestDatabase } from './database.mjs';

const db = await createTestDatabase();
try {
  for (const name of ['ownership.sql', 'source_reservations.sql', 'parsed_documents.sql', 'upload_recovery.sql']) {
    const result = await db.exec(await fs.readFile(new URL(name, import.meta.url), 'utf8'));
    console.log(name, result.at(-1).rows[0].result);
  }
  const { rows: [counts] } = await db.query(`
    select (select count(*) from auth.users) as users,
           (select count(*) from public.workspaces) as workspaces,
           (select count(*) from public.documents) as documents,
           (select count(*) from public.transactions) as transactions,
           (select count(*) from storage.objects) as objects,
           (select count(*) from public.upload_cancellations) as cancellations;
  `);
  if (Object.values(counts).some(count => Number(count) !== 0)) {
    throw new Error('A SQL test left fixture rows behind.');
  }
  console.log('All migrations and four SQL suites passed. All fixture rows rolled back.');
} catch (error) {
  console.error('SQL verification failed:', error.message, 'SQLSTATE:', error.code);
  process.exitCode = 1;
} finally {
  await db.close();
}
