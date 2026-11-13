// Stdio bridge for Python component tests. It opens no port and uses no credentials.
import readline from 'node:readline';
import { createTestDatabase } from './database.mjs';

const db = await createTestDatabase();
console.log(JSON.stringify({ ready: true }));
try {
  for await (const line of readline.createInterface({ input: process.stdin })) {
    try {
      const command = JSON.parse(line);
      await db.exec('begin');
      if (command.user_id) {
        await db.exec('set local role authenticated');
        await db.query("select set_config('request.jwt.claim.sub', $1, true)", [command.user_id]);
      }
      const result = await db.query(command.sql, command.params ?? []);
      await db.exec('commit');
      console.log(JSON.stringify({ rows: result.rows }));
    } catch (error) {
      await db.exec('rollback');
      console.log(JSON.stringify({ error: error.code, message: error.message }));
    }
  }
} finally {
  await db.close();
}
