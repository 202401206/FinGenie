-- Store one reported balance snapshot. File bytes stay in the Storage API.
create function public.finalize_balance_sheet(
    p_workspace_id uuid, p_document_id uuid, p_parsed_json jsonb
) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
    v_workspace public.workspaces%rowtype;
    v_document public.documents%rowtype;
    v_section jsonb;
    v_row jsonb;
    v_field text;
    v_section_name text;
    v_group text;
    v_prefix text;
    v_reporting_date date;
begin
    perform public.lock_source_upload(p_workspace_id);

    -- Match recovery's lock order: advisory lock, owned workspace, then document.
    select * into v_workspace from public.workspaces
    where id = p_workspace_id and user_id = auth.uid() for update;
    if not found then
        raise sqlstate 'PT404' using message = 'Workspace not found';
    end if;
    select * into v_document from public.documents
    where id = p_document_id and workspace_id = p_workspace_id for update;
    if not found then
        raise sqlstate 'PT404' using message = 'Workspace not found';
    end if;
    if v_workspace.user_type <> 'business'
        or v_workspace.document_type <> 'balance_sheet'
        or v_document.status <> 'uploaded' or v_document.parsed_json is not null
        or exists (select 1 from public.transactions where document_id = p_document_id)
        or exists (select 1 from public.upload_cancellations
            where user_id = auth.uid() and workspace_id = p_workspace_id)
    then
        raise sqlstate 'PT409' using message = 'Document cannot be finalized in its current state';
    end if;

    v_prefix := auth.uid()::text || '/' || p_workspace_id::text || '/' || p_document_id::text;
    if v_document.file_path not in (v_prefix || '/source.csv', v_prefix || '/source.xlsx')
        or not exists (select 1 from storage.objects
            where bucket_id = 'financial-documents' and name = v_document.file_path)
    then
        raise sqlstate 'PT409' using message = 'A registered canonical source is required';
    end if;

    -- Validate direct RPC calls too; Python validation is not an access boundary.
    if jsonb_typeof(p_parsed_json) is distinct from 'object'
        or not (p_parsed_json ?& array[
            'company', 'reporting_date', 'currency', 'unit_scale', 'assets',
            'liabilities', 'equity', 'unmapped', 'source_metadata'
        ])
        or jsonb_typeof(p_parsed_json->'company') not in ('string', 'null')
        or jsonb_typeof(p_parsed_json->'currency') not in ('string', 'null')
        or (p_parsed_json->>'currency' is not null
            and p_parsed_json->>'currency' not in ('INR', 'USD'))
        or jsonb_typeof(p_parsed_json->'unit_scale') not in ('number', 'null')
        or (p_parsed_json->>'unit_scale' is not null
            and (p_parsed_json->>'unit_scale')::numeric not in (1, 1000, 100000, 1000000, 10000000))
        or jsonb_typeof(p_parsed_json->'reporting_date') is distinct from 'string'
        or p_parsed_json->>'reporting_date' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        or jsonb_typeof(p_parsed_json->'unmapped') is distinct from 'array'
        or jsonb_typeof(p_parsed_json->'source_metadata') is distinct from 'object'
        or p_parsed_json->'source_metadata'->>'document_id' is distinct from p_document_id::text
        or not (p_parsed_json->'source_metadata' ? 'sheet_name')
        or jsonb_typeof(p_parsed_json->'source_metadata'->'sheet_name') not in ('string', 'null')
        or (p_parsed_json ? 'source_locations'
            and jsonb_typeof(p_parsed_json->'source_locations') is distinct from 'object')
    then
        raise sqlstate 'PT422' using message = 'Invalid parsed balance sheet';
    end if;
    v_reporting_date := (p_parsed_json->>'reporting_date')::date;
    if to_char(v_reporting_date, 'YYYY-MM-DD') <> p_parsed_json->>'reporting_date' then
        raise sqlstate 'PT422' using message = 'Invalid reporting date';
    end if;

    foreach v_section_name in array array['assets', 'liabilities'] loop
        v_section := p_parsed_json->v_section_name;
        if jsonb_typeof(v_section) is distinct from 'object'
            or not (v_section ?& array['current', 'non_current', 'total'])
            or jsonb_typeof(v_section->'current') is distinct from 'array'
            or jsonb_typeof(v_section->'non_current') is distinct from 'array'
            or jsonb_typeof(v_section->'total') not in ('number', 'null')
        then
            raise sqlstate 'PT422' using message = 'Invalid balance section';
        end if;
        foreach v_group in array array['current', 'non_current'] loop
            for v_row in select value from jsonb_array_elements(v_section->v_group) loop
                if jsonb_typeof(v_row) is distinct from 'object'
                    or not (v_row ?& array['canonical_field', 'raw_label', 'value', 'source_row'])
                    or jsonb_typeof(v_row->'canonical_field') not in ('string', 'null')
                    or jsonb_typeof(v_row->'raw_label') is distinct from 'string'
                    or jsonb_typeof(v_row->'value') not in ('number', 'null')
                    or jsonb_typeof(v_row->'source_row') is distinct from 'number'
                    or (v_row->>'source_row')::numeric <= 0
                    or trunc((v_row->>'source_row')::numeric) <> (v_row->>'source_row')::numeric
                    or (v_row->>'source_row')::numeric > 2147483647
                then
                    raise sqlstate 'PT422' using message = 'Invalid balance item';
                end if;
            end loop;
        end loop;
    end loop;
    v_section := p_parsed_json->'equity';
    if jsonb_typeof(v_section) is distinct from 'object'
        or not (v_section ?& array['share_capital', 'retained_earnings', 'total']) then
        raise sqlstate 'PT422' using message = 'Invalid equity section';
    end if;
    foreach v_field in array array['share_capital', 'retained_earnings', 'total'] loop
        if jsonb_typeof(v_section->v_field) not in ('number', 'null') then
            raise sqlstate 'PT422' using message = 'Invalid equity amount';
        end if;
    end loop;
    if exists (select 1 from jsonb_array_elements(p_parsed_json->'unmapped') item
        where jsonb_typeof(item) is distinct from 'object') then
        raise sqlstate 'PT422' using message = 'Invalid unmapped data';
    end if;

    -- Keep reported units and discrepancies intact. Analysis owns reconciliation.
    update public.documents set
        parsed_json = p_parsed_json, currency = p_parsed_json->>'currency',
        period_start = null, period_end = null, status = 'parsed'
    where id = p_document_id;
    return jsonb_build_object(
        'workspace_id', p_workspace_id, 'document_id', p_document_id,
        'status', 'parsed', 'transaction_count', 0
    );
exception when check_violation or not_null_violation or invalid_text_representation
    or datetime_field_overflow or numeric_value_out_of_range then
    raise sqlstate 'PT422' using message = 'Parsed values violate the save contract';
end;
$$;

revoke all on function public.finalize_balance_sheet(uuid, uuid, jsonb)
    from public, anon, authenticated;
grant execute on function public.finalize_balance_sheet(uuid, uuid, jsonb)
    to authenticated;
