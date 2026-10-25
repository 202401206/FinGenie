# Database - Backend team

Future focused database queries live in `repositories/`. Review
`docs/database-schema.md` before adding SQL or Supabase access. Initial tables, RLS
and private Storage policies are in `supabase/migrations/`. Repository methods and
atomic upload persistence are separate upcoming work. Use the verified caller's
access token and publishable key so RLS remains effective; do not share a mutable
user session or introduce a generic repository framework.
