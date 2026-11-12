-- Save the parsed document, metadata and transaction rows together.
-- Storage bytes are separate; this function checks the registered source first.
create function public.finalize_bank_statement(
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

revoke all on function public.finalize_bank_statement(uuid, uuid, jsonb)
    from public, anon, authenticated;
grant execute on function public.finalize_bank_statement(uuid, uuid, jsonb)
    to authenticated;
