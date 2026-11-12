-- Keep only IDs for a cancelled attempt so a queued request cannot recreate it.
create table public.upload_cancellations (
    user_id uuid not null references auth.users(id),
    workspace_id uuid not null,
    document_id uuid not null,
    created_at timestamptz not null default now(),
    primary key (user_id, workspace_id)
);
alter table public.upload_cancellations enable row level security;
revoke all on public.upload_cancellations from public, anon, authenticated;
grant select, insert on public.upload_cancellations to authenticated;
grant all on public.upload_cancellations to service_role;
create policy cancellations_select_own on public.upload_cancellations
    for select to authenticated using (user_id = (select auth.uid()));
create policy cancellations_insert_own on public.upload_cancellations
    for insert to authenticated with check (user_id = (select auth.uid()));

create function public.lock_source_upload(p_workspace_id uuid) returns void
language plpgsql security invoker set search_path = '' as $$
begin
    if auth.uid() is null then
        raise exception using errcode = '42501', message = 'Authentication required';
    end if;
    -- All cooperating writes for this owner's workspace use the same lock order.
    perform pg_advisory_xact_lock(hashtextextended(
        'fingenie.source:' || auth.uid()::text || ':' || p_workspace_id::text, 0
    ));
end;
$$;
revoke all on function public.lock_source_upload(uuid) from public, anon, authenticated;
grant execute on function public.lock_source_upload(uuid) to authenticated;

create function public.can_insert_source_object(p_name text) returns boolean
language plpgsql security invoker set search_path = '' as $$
declare
    v_parts text[] := string_to_array(p_name, '/');
    v_workspace_id uuid;
    v_document_id uuid;
begin
    if auth.uid() is null or array_length(v_parts, 1) is distinct from 4
        or v_parts[1] <> auth.uid()::text
        or v_parts[4] not in ('source.csv', 'source.xlsx')
    then
        return false;
    end if;
    begin
        v_workspace_id := v_parts[2]::uuid;
        v_document_id := v_parts[3]::uuid;
    exception when invalid_text_representation then
        return false;
    end;
    perform public.lock_source_upload(v_workspace_id);
    if exists (select 1 from public.upload_cancellations
        where user_id = auth.uid() and workspace_id = v_workspace_id)
    then
        return false;
    end if;
    return exists (
        select 1 from public.documents d join public.workspaces w on w.id = d.workspace_id
        where d.id = v_document_id and w.id = v_workspace_id and w.user_id = auth.uid()
            and d.file_path = p_name and d.status = 'uploaded' and d.parsed_json is null
    );
end;
$$;
revoke all on function public.can_insert_source_object(text) from public, anon, authenticated;
grant execute on function public.can_insert_source_object(text) to authenticated;

drop policy financial_documents_insert_own on storage.objects;
create policy financial_documents_insert_own on storage.objects
    for insert to authenticated with check (
        bucket_id = 'financial-documents' and public.can_insert_source_object(name)
    );

create function public.begin_upload_recovery(
    p_workspace_id uuid, p_document_id uuid, p_file_extension text, p_expected_json jsonb
) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
    v_document public.documents%rowtype;
    v_count integer;
    v_path text;
    v_has_document boolean;
begin
    perform public.lock_source_upload(p_workspace_id);
    if p_file_extension is null or p_file_extension not in ('csv', 'xlsx')
        or jsonb_typeof(p_expected_json) is distinct from 'object'
        or jsonb_typeof(p_expected_json->'transactions') is distinct from 'array'
        or p_expected_json->'source_metadata'->>'document_id' is distinct from p_document_id::text
    then
        raise sqlstate 'PT422' using message = 'Invalid recovery context';
    end if;
    v_path := auth.uid()::text || '/' || p_workspace_id::text || '/' || p_document_id::text || '/source.' || p_file_extension;

    if exists (select 1 from public.upload_cancellations where user_id = auth.uid()
        and workspace_id = p_workspace_id and document_id <> p_document_id)
    then
        return jsonb_build_object('state', 'conflict');
    end if;

    perform 1 from public.workspaces where id = p_workspace_id and user_id = auth.uid() for update;
    select d.* into v_document from public.documents d join public.workspaces w on w.id = d.workspace_id
    where d.id = p_document_id and w.id = p_workspace_id and w.user_id = auth.uid() for update of d;
    v_has_document := found;

    if v_has_document then
        if v_document.file_path <> v_path then
            return jsonb_build_object('state', 'conflict');
        end if;
        select count(*) into v_count from public.transactions where document_id = p_document_id;
        if v_document.status = 'parsed' then
            -- Compare the complete JSON, metadata and transaction multiset.
            if v_document.parsed_json is distinct from p_expected_json
                or v_document.currency is distinct from p_expected_json->>'currency'
                or v_document.period_start is distinct from (p_expected_json->>'period_start')::date
                or v_document.period_end is distinct from (p_expected_json->>'period_end')::date
                or v_count <> jsonb_array_length(p_expected_json->'transactions')
                or exists (select 1 from public.upload_cancellations
                    where user_id = auth.uid() and workspace_id = p_workspace_id)
                or not exists (select 1 from storage.objects where bucket_id = 'financial-documents' and name = v_path)
                or exists (
                    select t.date, t.description, t.debit, t.credit, t.balance, t.source_row
                    from public.transactions t where t.document_id = p_document_id
                    except all
                    select x.date, x.description, x.debit, x.credit, x.balance, x.source_row
                    from jsonb_to_recordset(p_expected_json->'transactions') as x(
                        date date, description text, debit numeric, credit numeric,
                        balance numeric, source_row integer
                    )
                )
            then
                return jsonb_build_object('state', 'conflict');
            end if;
            return jsonb_build_object('state', 'completed', 'receipt', jsonb_build_object(
                'workspace_id', p_workspace_id, 'document_id', p_document_id,
                'status', 'parsed', 'transaction_count', v_count
            ));
        end if;
        if v_document.status not in ('uploaded', 'failed') or v_document.parsed_json is not null or v_count <> 0 then
            return jsonb_build_object('state', 'conflict');
        end if;
    elsif exists (select 1 from public.documents where workspace_id = p_workspace_id) then
        return jsonb_build_object('state', 'conflict');
    end if;

    insert into public.upload_cancellations (user_id, workspace_id, document_id)
    values (auth.uid(), p_workspace_id, p_document_id)
    on conflict (user_id, workspace_id) do nothing;
    if v_has_document then
        update public.documents set status = 'failed' where id = p_document_id;
        return jsonb_build_object('state', 'failed');
    end if;
    return jsonb_build_object('state', 'absent');
exception when invalid_text_representation or datetime_field_overflow or numeric_value_out_of_range then
    raise sqlstate 'PT422' using message = 'Invalid recovery values';
end;
$$;
revoke all on function public.begin_upload_recovery(uuid, uuid, text, jsonb) from public, anon, authenticated;
grant execute on function public.begin_upload_recovery(uuid, uuid, text, jsonb) to authenticated;

create function public.release_failed_upload(p_workspace_id uuid, p_document_id uuid, p_file_extension text)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
    v_document public.documents%rowtype;
    v_path text;
begin
    perform public.lock_source_upload(p_workspace_id);
    if p_file_extension is null or p_file_extension not in ('csv', 'xlsx') then
        raise sqlstate 'PT422' using message = 'Unsupported source extension';
    end if;
    v_path := auth.uid()::text || '/' || p_workspace_id::text || '/' || p_document_id::text || '/source.' || p_file_extension;
    if not exists (select 1 from public.upload_cancellations where user_id = auth.uid()
        and workspace_id = p_workspace_id and document_id = p_document_id)
        or exists (select 1 from storage.objects where bucket_id = 'financial-documents' and name = v_path)
    then
        raise sqlstate 'PT409' using message = 'Source cleanup has not been confirmed';
    end if;
    perform 1 from public.workspaces where id = p_workspace_id and user_id = auth.uid() for update;
    select d.* into v_document from public.documents d join public.workspaces w on w.id = d.workspace_id
    where d.id = p_document_id and w.id = p_workspace_id and w.user_id = auth.uid() for update of d;
    if found then
        if v_document.status <> 'failed' or v_document.parsed_json is not null
            or v_document.file_path <> v_path
            or exists (select 1 from public.transactions where document_id = p_document_id)
        then
            raise sqlstate 'PT409' using message = 'Document is not safe to release';
        end if;
        delete from public.documents where id = p_document_id;
    end if;
    if exists (select 1 from public.documents where workspace_id = p_workspace_id) then
        raise sqlstate 'PT409' using message = 'Workspace still contains a document';
    end if;
    delete from public.workspaces where id = p_workspace_id and user_id = auth.uid();
    return jsonb_build_object('released', true);
end;
$$;
revoke all on function public.release_failed_upload(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.release_failed_upload(uuid, uuid, text) to authenticated;


-- Preserve the published interface while coordinating writes with recovery.
create or replace function public.reserve_source_upload(
    p_workspace_id uuid,
    p_document_id uuid,
    p_user_type text,
    p_document_type text,
    p_name text,
    p_original_filename text,
    p_file_extension text
) returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_owner uuid := auth.uid();
    v_workspace public.workspaces%rowtype;
    v_document public.documents%rowtype;
begin
    if v_owner is null then
        raise exception using errcode = '42501', message = 'Authentication required';
    end if;
    perform public.lock_source_upload(p_workspace_id);
    if exists (select 1 from public.upload_cancellations
        where user_id = auth.uid() and workspace_id = p_workspace_id) then
        raise sqlstate 'PT409' using message = 'This upload attempt was cancelled';
    end if;
    if p_file_extension is null or p_file_extension not in ('csv', 'xlsx') then
        raise exception using errcode = '22023', message = 'Unsupported source extension';
    end if;

    insert into public.workspaces (id, user_id, user_type, document_type, name)
    values (p_workspace_id, v_owner, p_user_type, p_document_type, p_name)
    returning * into v_workspace;

    insert into public.documents (id, workspace_id, file_path, original_filename)
    values (
        p_document_id,
        p_workspace_id,
        v_owner::text || '/' || p_workspace_id::text || '/' ||
            p_document_id::text || '/source.' || p_file_extension,
        p_original_filename
    )
    returning * into v_document;

    return jsonb_build_object(
        'workspace', jsonb_build_object(
            'id', v_workspace.id,
            'name', v_workspace.name,
            'user_type', v_workspace.user_type,
            'document_type', v_workspace.document_type,
            'created_at', v_workspace.created_at
        ),
        'document', jsonb_build_object(
            'id', v_document.id,
            'file_path', v_document.file_path,
            'status', v_document.status
        )
    );
end;
$$;


-- Preserve the published interface while coordinating writes with recovery.
create or replace function public.finalize_bank_statement(
    p_workspace_id uuid,
    p_document_id uuid,
    p_parsed_json jsonb
) returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_document public.documents%rowtype;
    v_document_type text;
    v_row jsonb;
    v_field text;
    v_count integer;
begin
    if auth.uid() is null then
        raise exception using errcode = '42501', message = 'Authentication required';
    end if;
    perform public.lock_source_upload(p_workspace_id);
    if exists (select 1 from public.upload_cancellations
        where user_id = auth.uid() and workspace_id = p_workspace_id) then
        raise sqlstate 'PT409' using message = 'This upload attempt was cancelled';
    end if;

    -- Lock this document so two saves cannot both append its transactions.
    select d.* into v_document
    from public.documents d
    join public.workspaces w on w.id = d.workspace_id
    where d.id = p_document_id and w.id = p_workspace_id and w.user_id = auth.uid()
    for update of d;

    if not found then
        raise sqlstate 'PT404' using message = 'Workspace not found';
    end if;
    select document_type into v_document_type
    from public.workspaces where id = p_workspace_id;
    if v_document_type <> 'bank_statement'
        or v_document.status <> 'uploaded'
        or v_document.parsed_json is not null
        or exists (select 1 from public.transactions where document_id = p_document_id)
    then
        raise sqlstate 'PT409' using message = 'Document cannot be finalized in its current state';
    end if;
    if not exists (
        select 1 from storage.objects
        where bucket_id = 'financial-documents' and name = v_document.file_path
    ) then
        raise sqlstate 'PT409' using message = 'A registered source file is required';
    end if;

    if jsonb_typeof(p_parsed_json) is distinct from 'object'
        or not (p_parsed_json ?& array[
            'bank', 'account_holder', 'account_type', 'currency',
            'period_start', 'period_end', 'opening_balance', 'closing_balance',
            'transactions', 'unmapped', 'source_metadata'
        ])
        or jsonb_typeof(p_parsed_json->'transactions') is distinct from 'array'
        or jsonb_typeof(p_parsed_json->'unmapped') is distinct from 'array'
        or jsonb_typeof(p_parsed_json->'source_metadata') is distinct from 'object'
        or p_parsed_json->'source_metadata'->>'document_id' is distinct from p_document_id::text
    then
        raise sqlstate 'PT422' using message = 'Invalid parsed bank statement';
    end if;

    foreach v_field in array array['bank', 'account_holder', 'account_type', 'currency', 'period_start', 'period_end']
    loop
        if jsonb_typeof(p_parsed_json->v_field) not in ('string', 'null') then
            raise sqlstate 'PT422' using message = 'Invalid statement metadata';
        end if;
    end loop;
    foreach v_field in array array['opening_balance', 'closing_balance']
    loop
        if jsonb_typeof(p_parsed_json->v_field) not in ('number', 'null') then
            raise sqlstate 'PT422' using message = 'Invalid statement balance';
        end if;
    end loop;
    foreach v_field in array array['period_start', 'period_end']
    loop
        if p_parsed_json->>v_field is not null
            and p_parsed_json->>v_field !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        then
            raise sqlstate 'PT422' using message = 'Dates must use YYYY-MM-DD';
        end if;
    end loop;

    update public.documents
    set currency = p_parsed_json->>'currency',
        period_start = (p_parsed_json->>'period_start')::date,
        period_end = (p_parsed_json->>'period_end')::date,
        parsed_json = p_parsed_json,
        status = 'parsed'
    where id = p_document_id;

    for v_row in select value from jsonb_array_elements(p_parsed_json->'transactions')
    loop
        if jsonb_typeof(v_row) is distinct from 'object'
            or jsonb_typeof(v_row->'date') is distinct from 'string'
            or (v_row->>'date') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            or jsonb_typeof(v_row->'description') is distinct from 'string'
            or jsonb_typeof(v_row->'debit') is distinct from 'number'
            or jsonb_typeof(v_row->'credit') is distinct from 'number'
            or jsonb_typeof(v_row->'balance') is distinct from 'number'
            or jsonb_typeof(v_row->'source_row') is distinct from 'number'
        then
            raise sqlstate 'PT422' using message = 'Invalid transaction fields';
        end if;

        insert into public.transactions (document_id, date, description, debit, credit, balance, source_row)
        values (
            p_document_id, (v_row->>'date')::date, v_row->>'description',
            (v_row->>'debit')::numeric, (v_row->>'credit')::numeric,
            (v_row->>'balance')::numeric, (v_row->>'source_row')::integer
        );
    end loop;
    v_count := jsonb_array_length(p_parsed_json->'transactions');

    return jsonb_build_object(
        'workspace_id', p_workspace_id, 'document_id', p_document_id,
        'status', 'parsed', 'transaction_count', v_count
    );
exception
    -- A bad later row must undo the metadata update and earlier inserted rows.
    when check_violation or not_null_violation or invalid_text_representation
        or datetime_field_overflow or numeric_value_out_of_range then
        raise sqlstate 'PT422' using message = 'Parsed values violate the save contract';
end;
$$;
