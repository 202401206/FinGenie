-- Run as postgres after migrations. Synthetic fixtures only; always roll back.
-- This checks real SQL transaction/RLS semantics, not actual Storage file bytes.
begin;

select set_config('fingenie_test.source_owner', gen_random_uuid()::text, true);
select set_config('fingenie_test.source_other', gen_random_uuid()::text, true);
select set_config('fingenie_test.source_workspace', gen_random_uuid()::text, true);
select set_config('fingenie_test.source_document', gen_random_uuid()::text, true);

insert into auth.users (id, aud, role)
values (current_setting('fingenie_test.source_owner')::uuid, 'authenticated', 'authenticated'),
       (current_setting('fingenie_test.source_other')::uuid, 'authenticated', 'authenticated');

set local role authenticated;
select set_config('request.jwt.claim.sub', current_setting('fingenie_test.source_owner'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.source_owner'), 'role', 'authenticated'
)::text, true);

do $$
declare
    receipt jsonb;
    attempted_workspace uuid := gen_random_uuid();
begin
    receipt := public.reserve_source_upload(
        current_setting('fingenie_test.source_workspace')::uuid,
        current_setting('fingenie_test.source_document')::uuid,
        'personal', 'bank_statement', 'Synthetic source', 'synthetic.csv', 'csv'
    );
    if receipt->'document'->>'status' <> 'uploaded'
        or receipt->'document'->>'file_path' <>
            current_setting('fingenie_test.source_owner') || '/' ||
            current_setting('fingenie_test.source_workspace') || '/' ||
            current_setting('fingenie_test.source_document') || '/source.csv'
    then
        raise exception 'Reservation did not derive the canonical owned path';
    end if;

    -- The document insert fails after workspace insertion. Both must roll back.
    begin
        perform public.reserve_source_upload(
            attempted_workspace, gen_random_uuid(), 'personal', 'bank_statement',
            'Must roll back', '   ', 'csv'
        );
        raise exception 'Blank filename was accepted';
    exception when check_violation then null;
    end;
    if exists (select 1 from public.workspaces where id = attempted_workspace) then
        raise exception 'Failed reservation left a workspace behind';
    end if;

    begin
        perform public.reserve_source_upload(
            gen_random_uuid(), gen_random_uuid(), 'personal', 'balance_sheet',
            'Invalid combination', 'synthetic.xlsx', 'xlsx'
        );
        raise exception 'Personal balance sheet was accepted';
    exception when check_violation then null;
    end;

    begin
        perform public.reserve_source_upload(
            gen_random_uuid(), gen_random_uuid(), 'personal', 'bank_statement',
            'Invalid extension', 'synthetic.pdf', 'pdf'
        );
        raise exception 'Unsupported extension was accepted';
    exception when invalid_parameter_value then null;
    end;

    begin
        perform public.reserve_source_upload(
            current_setting('fingenie_test.source_workspace')::uuid,
            current_setting('fingenie_test.source_document')::uuid,
            'personal', 'bank_statement', 'Overwrite attempt', 'other.csv', 'csv'
        );
        raise exception 'Reservation overwrote existing IDs';
    exception when unique_violation then null;
    end;
end;
$$;

-- A second user cannot see the reservation or claim an existing parent ID.
select set_config('request.jwt.claim.sub', current_setting('fingenie_test.source_other'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.source_other'), 'role', 'authenticated'
)::text, true);
do $$
begin
    if exists (select 1 from public.workspaces
        where id = current_setting('fingenie_test.source_workspace')::uuid)
        or exists (select 1 from public.documents
        where id = current_setting('fingenie_test.source_document')::uuid)
    then
        raise exception 'Cross-user reservation visibility was allowed';
    end if;
    begin
        perform public.reserve_source_upload(
            current_setting('fingenie_test.source_workspace')::uuid, gen_random_uuid(),
            'personal', 'bank_statement', 'Foreign parent', 'synthetic.csv', 'csv'
        );
        raise exception 'Another user claimed the reservation';
    exception when unique_violation then null;
    end;
end;
$$;

-- Authenticated role without a subject is also rejected inside the function.
select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
do $$
begin
    begin
        perform public.reserve_source_upload(
            gen_random_uuid(), gen_random_uuid(), 'personal', 'bank_statement',
            'No identity', 'synthetic.csv', 'csv'
        );
        raise exception 'Missing identity was accepted';
    exception when insufficient_privilege then null;
    end;
end;
$$;

set local role anon;
do $$
begin
    if has_function_privilege(
        current_user,
        'public.reserve_source_upload(uuid,uuid,text,text,text,text,text)', 'EXECUTE'
    ) then
        raise exception 'Anonymous role can execute reservation';
    end if;
end;
$$;

reset role;
rollback;
select 'Source reservation ownership and rollback checks passed' as result;
