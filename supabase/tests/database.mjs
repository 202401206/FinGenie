// Test-only Supabase scaffolding. Hosted Supabase owns these schemas in production.
import fs from 'node:fs/promises';
import { PGlite } from '@electric-sql/pglite';

export async function createTestDatabase() {
  const db = new PGlite();
  try {
    await db.exec(`
      create role anon;
      create role authenticated;
      create role service_role bypassrls;
      create schema auth;
      create schema storage;
      create table auth.users (id uuid primary key, aud text, role text);
      create function auth.uid() returns uuid language sql stable as $$
        select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
      $$;
      create table storage.buckets (
        id text primary key, name text, public boolean, allowed_mime_types text[]
      );
      create table storage.objects (
        id uuid primary key default gen_random_uuid(),
        bucket_id text references storage.buckets(id), name text,
        unique (bucket_id, name)
      );
      alter table storage.objects enable row level security;
      create function storage.foldername(name text) returns text[] language sql as $$
        select (string_to_array(name, '/'))[1:array_length(string_to_array(name, '/'), 1) - 1];
      $$;
      grant usage on schema public, auth, storage to anon, authenticated, service_role;
      grant select, insert, update, delete on storage.objects to authenticated;
      grant select on storage.objects to anon;
    `);
    const directory = new URL('../migrations/', import.meta.url);
    const migrations = (await fs.readdir(directory)).filter(name => name.endsWith('.sql')).sort();
    for (const name of migrations) {
      await db.exec(await fs.readFile(new URL(name, directory), 'utf8'));
    }
    return db;
  } catch (error) {
    await db.close();
    throw error;
  }
}
