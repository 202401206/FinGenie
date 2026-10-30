-- Run the entire script as postgres in Supabase SQL Editor or via the connector.
-- It creates disposable synthetic rows inside one transaction and rolls them back.
-- Storage rows here test RLS metadata only: no file bytes are uploaded.
begin;

select set_config('fingenie_test.user_a', gen_random_uuid()::text, true);
select set_config('fingenie_test.user_b', gen_random_uuid()::text, true);
select set_config('fingenie_test.workspace_a', gen_random_uuid()::text, true);
select set_config('fingenie_test.workspace_b', gen_random_uuid()::text, true);
select set_config('fingenie_test.document_a', gen_random_uuid()::text, true);
select set_config('fingenie_test.document_b', gen_random_uuid()::text, true);

insert into auth.users (id, aud, role)
values (current_setting('fingenie_test.user_a')::uuid, 'authenticated', 'authenticated'),
       (current_setting('fingenie_test.user_b')::uuid, 'authenticated', 'authenticated');

insert into public.workspaces (id, user_id, user_type, document_type, name)
values (
    current_setting('fingenie_test.workspace_a')::uuid,
    current_setting('fingenie_test.user_a')::uuid,
    'personal', 'bank_statement', 'Synthetic A'
), (
    current_setting('fingenie_test.workspace_b')::uuid,
    current_setting('fingenie_test.user_b')::uuid,
    'business', 'bank_statement', 'Synthetic B'
);

insert into public.documents (id, workspace_id, file_path, original_filename)
select current_setting('fingenie_test.document_' || suffix)::uuid,
       current_setting('fingenie_test.workspace_' || suffix)::uuid,
       current_setting('fingenie_test.user_' || suffix) || '/' ||
       current_setting('fingenie_test.workspace_' || suffix) || '/' ||
       current_setting('fingenie_test.document_' || suffix) || '/source.csv',
       'synthetic.csv'
from (values ('a'), ('b')) as owners(suffix);

insert into public.transactions (document_id, date, description, debit, credit, balance, source_row)
select current_setting('fingenie_test.document_' || suffix)::uuid,
       date '2026-01-01', 'Synthetic transaction', 0.10, 0.20, -0.30, 2
from (values ('a'), ('b')) as owners(suffix);

set local role authenticated;
select set_config('request.jwt.claim.sub', current_setting('fingenie_test.user_b'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.user_b'), 'role', 'authenticated'
)::text, true);
insert into storage.objects (bucket_id, name)
select 'financial-documents', file_path from public.documents;

select set_config('request.jwt.claim.sub', current_setting('fingenie_test.user_a'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.user_a'), 'role', 'authenticated'
)::text, true);
insert into storage.objects (bucket_id, name)
select 'financial-documents', file_path from public.documents;

do $$
declare
    affected integer;
    new_document uuid := gen_random_uuid();
begin
    if (select count(*) from public.workspaces) <> 1
        or (select count(*) from public.documents) <> 1
        or (select count(*) from public.transactions) <> 1
        or (select count(*) from storage.objects where bucket_id = 'financial-documents') <> 1
    then
        raise exception 'Owner isolation failed for tables or Storage';
    end if;
    if not exists (select 1 from public.transactions where debit = 0.10 and balance = -0.30) then
        raise exception 'Exact decimals or negative balances were not preserved';
    end if;

    update public.workspaces set name = 'Updated synthetic A';
    get diagnostics affected = row_count;
    if affected <> 1 then raise exception 'Owner update failed'; end if;

    update public.workspaces set name = 'Must not update'
        where id = current_setting('fingenie_test.workspace_b')::uuid;
    get diagnostics affected = row_count;
    if affected <> 0 then raise exception 'Foreign update was allowed'; end if;
    delete from public.transactions
        where document_id = current_setting('fingenie_test.document_b')::uuid;
    get diagnostics affected = row_count;
    if affected <> 0 then raise exception 'Foreign delete was allowed'; end if;

    begin
        insert into public.workspaces (user_id, user_type, document_type, name)
        values (current_setting('fingenie_test.user_b')::uuid, 'personal', 'bank_statement', 'Forged');
        raise exception 'Forged workspace owner was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        update public.workspaces set user_id = current_setting('fingenie_test.user_b')::uuid;
        raise exception 'Workspace ownership transfer was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        insert into public.transactions (document_id, date, description, debit, credit, balance, source_row)
        values (current_setting('fingenie_test.document_b')::uuid, current_date, 'Forged', 0, 1, 1, 3);
        raise exception 'Foreign transaction insert was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        update public.transactions set document_id = current_setting('fingenie_test.document_b')::uuid;
        raise exception 'Transaction reparenting was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        update public.documents set
            workspace_id = current_setting('fingenie_test.workspace_b')::uuid,
            file_path = current_setting('fingenie_test.user_a') || '/' ||
                current_setting('fingenie_test.workspace_b') || '/' || id::text || '/source.csv';
        raise exception 'Document reparenting was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        update public.documents set file_path = current_setting('fingenie_test.user_b') || '/' ||
            workspace_id::text || '/' || id::text || '/source.csv';
        raise exception 'Foreign Storage prefix was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        insert into storage.objects (bucket_id, name)
        values ('financial-documents', current_setting('fingenie_test.user_b') || '/forged/source.csv');
        raise exception 'Foreign Storage insert was allowed';
    exception when insufficient_privilege then null;
    end;
    begin
        insert into storage.objects (bucket_id, name)
        values ('financial-documents', current_setting('fingenie_test.user_a') || '/unregistered/source.csv');
        raise exception 'Storage insert without owned metadata was allowed';
    exception when insufficient_privilege then null;
    end;
    update storage.objects set name = name || '.changed'
        where bucket_id = 'financial-documents';
    get diagnostics affected = row_count;
    if affected <> 0 then raise exception 'Source overwrite was allowed'; end if;

    begin
        insert into public.documents (id, workspace_id, file_path, original_filename)
        values (new_document, current_setting('fingenie_test.workspace_a')::uuid,
            current_setting('fingenie_test.user_a') || '/' ||
            current_setting('fingenie_test.workspace_a') || '/' || new_document::text || '/source.xlsx',
            'second.xlsx');
        raise exception 'Second document per workspace was allowed';
    exception when unique_violation then null;
    end;
    begin
        insert into public.workspaces (user_id, user_type, document_type, name)
        values (current_setting('fingenie_test.user_a')::uuid, 'personal', 'balance_sheet', 'Invalid');
        raise exception 'Personal balance sheet was allowed';
    exception when check_violation then null;
    end;
    begin
        update public.transactions set debit = -1;
        raise exception 'Negative debit was allowed';
    exception when check_violation then null;
    end;
    begin
        update public.transactions set credit = 'NaN'::numeric;
        raise exception 'Non-finite money was allowed';
    exception when check_violation then null;
    end;
    begin
        update public.transactions set source_row = 0;
        raise exception 'Invalid source row was allowed';
    exception when check_violation then null;
    end;
    begin
        update public.documents set status = 'parsed';
        raise exception 'Parsed status without content was allowed';
    exception when check_violation then null;
    end;
end;
$$;

-- Anonymous clients have neither table grants nor object access.
set local role anon;
select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claims', '{}', true);
do $$
begin
    begin
        perform id from public.workspaces;
        raise exception 'Anonymous table read was allowed';
    exception when insufficient_privilege then null;
    end;
    if exists (select 1 from storage.objects where bucket_id = 'financial-documents') then
        raise exception 'Anonymous Storage read was allowed';
    end if;
end;
$$;

-- Merely using the authenticated DB role without a user identity grants no rows.
set local role authenticated;
do $$
begin
    if exists (select 1 from public.workspaces)
        or exists (select 1 from public.documents)
        or exists (select 1 from public.transactions)
    then
        raise exception 'Missing identity exposed private rows';
    end if;
end;
$$;

rollback;
select 'Ownership, storage policies and financial constraints passed; test rows rolled back.' as result;
