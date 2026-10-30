-- Sprint 1 database foundation. No real users or financial data are seeded.
-- Version matches the hosted migration recorded by Supabase.
-- File bytes are managed through the Storage API, never by inserting object rows.

create table public.workspaces (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id),
    user_type text not null check (user_type in ('personal', 'business')),
    document_type text not null check (document_type in ('bank_statement', 'balance_sheet')),
    name text not null check (length(btrim(name)) > 0),
    created_at timestamptz not null default now(),
    constraint eligible_document_type check (
        user_type = 'business' or document_type = 'bank_statement'
    )
);

create table public.documents (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null unique references public.workspaces(id),
    file_path text not null unique,
    original_filename text not null check (length(btrim(original_filename)) > 0),
    currency text check (currency ~ '^[A-Z]{3}$'),
    period_start date,
    period_end date,
    status text not null default 'uploaded' check (status in ('uploaded', 'parsed', 'failed')),
    parsed_json jsonb,
    created_at timestamptz not null default now(),
    constraint valid_document_period check (
        period_start is null or period_end is null or period_start <= period_end
    ),
    constraint parsed_document_has_content check (
        status <> 'parsed' or (parsed_json is not null and jsonb_typeof(parsed_json) = 'object')
    ),
    constraint canonical_document_path check (
        array_length(string_to_array(file_path, '/'), 1) = 4
        and split_part(file_path, '/', 2) = workspace_id::text
        and split_part(file_path, '/', 3) = id::text
        and split_part(file_path, '/', 4) in ('source.csv', 'source.xlsx')
    )
);

create table public.transactions (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id),
    date date not null,
    description text not null,
    debit numeric not null check (debit >= 0 and debit < 'Infinity'::numeric),
    credit numeric not null check (credit >= 0 and credit < 'Infinity'::numeric),
    balance numeric not null check (
        balance > '-Infinity'::numeric and balance < 'Infinity'::numeric
    ),
    source_row integer not null check (source_row > 0)
);

-- The leading columns cover ownership/foreign-key lookups as well as pagination.
create index workspaces_owner_created_idx
    on public.workspaces (user_id, created_at desc, id desc);
create index transactions_document_row_idx
    on public.transactions (document_id, source_row, id);
create index transactions_document_date_idx
    on public.transactions (document_id, date);

alter table public.workspaces enable row level security;
alter table public.documents enable row level security;
alter table public.transactions enable row level security;

revoke all on public.workspaces, public.documents, public.transactions
    from public, anon, authenticated;
grant select, insert, update, delete on public.workspaces, public.documents, public.transactions
    to authenticated;
grant all on public.workspaces, public.documents, public.transactions to service_role;

create policy workspaces_select_own on public.workspaces
    for select to authenticated using (user_id = (select auth.uid()));
create policy workspaces_insert_own on public.workspaces
    for insert to authenticated with check (user_id = (select auth.uid()));
create policy workspaces_update_own on public.workspaces
    for update to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));
create policy workspaces_delete_own on public.workspaces
    for delete to authenticated using (user_id = (select auth.uid()));

create policy documents_select_own on public.documents
    for select to authenticated using (
        workspace_id in (select id from public.workspaces where user_id = (select auth.uid()))
    );
create policy documents_insert_own on public.documents
    for insert to authenticated with check (
        workspace_id in (select id from public.workspaces where user_id = (select auth.uid()))
        and split_part(file_path, '/', 1) = (select auth.uid())::text
    );
create policy documents_update_own on public.documents
    for update to authenticated using (
        workspace_id in (select id from public.workspaces where user_id = (select auth.uid()))
    ) with check (
        workspace_id in (select id from public.workspaces where user_id = (select auth.uid()))
        and split_part(file_path, '/', 1) = (select auth.uid())::text
    );
create policy documents_delete_own on public.documents
    for delete to authenticated using (
        workspace_id in (select id from public.workspaces where user_id = (select auth.uid()))
    );

create policy transactions_select_own on public.transactions
    for select to authenticated using (
        document_id in (
            select d.id from public.documents d
            join public.workspaces w on w.id = d.workspace_id
            where w.user_id = (select auth.uid())
        )
    );
create policy transactions_insert_own on public.transactions
    for insert to authenticated with check (
        document_id in (
            select d.id from public.documents d
            join public.workspaces w on w.id = d.workspace_id
            where w.user_id = (select auth.uid())
        )
    );
create policy transactions_update_own on public.transactions
    for update to authenticated using (
        document_id in (
            select d.id from public.documents d
            join public.workspaces w on w.id = d.workspace_id
            where w.user_id = (select auth.uid())
        )
    ) with check (
        document_id in (
            select d.id from public.documents d
            join public.workspaces w on w.id = d.workspace_id
            where w.user_id = (select auth.uid())
        )
    );
create policy transactions_delete_own on public.transactions
    for delete to authenticated using (
        document_id in (
            select d.id from public.documents d
            join public.workspaces w on w.id = d.workspace_id
            where w.user_id = (select auth.uid())
        )
    );

insert into storage.buckets (id, name, public, allowed_mime_types)
values (
    'financial-documents', 'financial-documents', false,
    array['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
);

-- Insert requires an owned workspace/document registered with this exact path.
create policy financial_documents_insert_own on storage.objects
    for insert to authenticated with check (
        bucket_id = 'financial-documents'
        and (storage.foldername(name))[1] = (select auth.uid())::text
        and name in (
            select d.file_path from public.documents d
            join public.workspaces w on w.id = d.workspace_id
            where w.user_id = (select auth.uid())
        )
    );

-- Owner-prefix reads/deletes also allow cleanup if metadata persistence failed.
-- No UPDATE policy: source documents cannot be overwritten/upserted.
create policy financial_documents_select_own on storage.objects
    for select to authenticated using (
        bucket_id = 'financial-documents'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );
create policy financial_documents_delete_own on storage.objects
    for delete to authenticated using (
        bucket_id = 'financial-documents'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );
