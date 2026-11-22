-- Synthetic role/transaction checks. Run after all migrations, then roll back.
begin;
select set_config('fingenie_test.final_owner', gen_random_uuid()::text, true);
select set_config('fingenie_test.final_other', gen_random_uuid()::text, true);
select set_config('fingenie_test.final_workspace', gen_random_uuid()::text, true);
select set_config('fingenie_test.final_document', gen_random_uuid()::text, true);

insert into auth.users (id, aud, role) values
    (current_setting('fingenie_test.final_owner')::uuid, 'authenticated', 'authenticated'),
    (current_setting('fingenie_test.final_other')::uuid, 'authenticated', 'authenticated');

create function pg_temp.test_statement(document_id uuid) returns jsonb
language sql as $$
    select jsonb_build_object(
        'bank', 'Synthetic Bank', 'account_holder', null, 'account_type', null,
        'currency', 'INR', 'period_start', '2026-01-01', 'period_end', '2026-01-31',
        'opening_balance', null, 'closing_balance', -0.1234567890123456789::numeric,
        'transactions', jsonb_build_array(
            jsonb_build_object('date', '2026-01-05', 'description', 'Synthetic payment',
                'debit', 123456789012345.6789::numeric, 'credit', 0,
                'balance', -0.1234567890123456789::numeric, 'source_row', 6),
            jsonb_build_object('date', '2026-01-05', 'description', 'Synthetic payment',
                'debit', 123456789012345.6789::numeric, 'credit', 0,
                'balance', -0.1234567890123456789::numeric, 'source_row', 7)
        ),
        'unmapped', jsonb_build_array(jsonb_build_object('source_row', 10, 'raw_value', 'Keep me')),
        'source_metadata', jsonb_build_object('document_id', document_id, 'sheet_name', null),
        'extra_note', 'Preserve this field'
    );
$$;

set local role authenticated;
select set_config('request.jwt.claim.sub', current_setting('fingenie_test.final_owner'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.final_owner'), 'role', 'authenticated'
)::text, true);

do $$
declare
    v_workspace_id uuid := current_setting('fingenie_test.final_workspace')::uuid;
    v_document_id uuid := current_setting('fingenie_test.final_document')::uuid;
    statement jsonb := pg_temp.test_statement(v_document_id);
    result jsonb;
    extra_workspace uuid := gen_random_uuid();
    extra_document uuid := gen_random_uuid();
    bad_statement jsonb;
begin
    perform public.reserve_source_upload(v_workspace_id, v_document_id,
        'personal', 'bank_statement', 'Synthetic save', 'synthetic.csv', 'csv');

    begin
        perform public.finalize_bank_statement(v_workspace_id, v_document_id, statement);
        raise exception 'Missing Storage source was accepted';
    exception when sqlstate 'PT409' then null;
    end;
    -- This fixture registers Storage metadata only, not real file bytes.
    insert into storage.objects (bucket_id, name)
    select 'financial-documents', file_path from public.documents where id = v_document_id;

    -- The first row and document update happen before the second row fails.
    bad_statement := jsonb_set(statement, '{transactions,1,debit}', '-1'::jsonb);
    begin
        perform public.finalize_bank_statement(v_workspace_id, v_document_id, bad_statement);
        raise exception 'Negative debit was accepted';
    exception when sqlstate 'PT422' then null;
    end;
    if exists (select 1 from public.transactions t where t.document_id = v_document_id)
        or not exists (select 1 from public.documents d where d.id = v_document_id
            and d.status = 'uploaded' and d.parsed_json is null and d.currency is null)
    then
        raise exception 'Failed save left partial rows or changed metadata';
    end if;

    bad_statement := jsonb_set(statement, '{transactions,1,source_row}', '2.5'::jsonb);
    begin
        perform public.finalize_bank_statement(v_workspace_id, v_document_id, bad_statement);
        raise exception 'Fractional source row was accepted';
    exception when sqlstate 'PT422' then null;
    end;
    bad_statement := jsonb_set(statement, '{source_metadata,document_id}', to_jsonb(gen_random_uuid()::text));
    begin
        perform public.finalize_bank_statement(v_workspace_id, v_document_id, bad_statement);
        raise exception 'Mismatched source document was accepted';
    exception when sqlstate 'PT422' then null;
    end;

    result := public.finalize_bank_statement(v_workspace_id, v_document_id, statement);
    if result->>'status' <> 'parsed' or (result->>'transaction_count')::int <> 2 then
        raise exception 'Bad finalization receipt';
    end if;
    if (select count(*) from public.transactions t where t.document_id = v_document_id) <> 2
        or not exists (select 1 from public.transactions t where t.document_id = v_document_id
            and t.debit = 123456789012345.6789 and t.balance = -0.1234567890123456789)
        or not exists (select 1 from public.documents d where d.id = v_document_id
            and d.parsed_json = statement and d.currency = 'INR'
            and d.period_start = date '2026-01-01')
    then
        raise exception 'Saved document, exact amounts or legitimate duplicate rows differ';
    end if;
    begin
        perform public.finalize_bank_statement(v_workspace_id, v_document_id, statement);
        raise exception 'Repeated finalization was accepted';
    exception when sqlstate 'PT409' then null;
    end;
    if (select count(*) from public.transactions t where t.document_id = v_document_id) <> 2 then
        raise exception 'Repeated save duplicated transaction rows';
    end if;

    perform public.reserve_source_upload(extra_workspace, extra_document,
        'business', 'bank_statement', 'Unknown metadata', 'synthetic.xlsx', 'xlsx');
    insert into storage.objects (bucket_id, name)
    select 'financial-documents', file_path from public.documents where id = extra_document;
    bad_statement := pg_temp.test_statement(extra_document) ||
        '{"currency":null,"period_start":null,"period_end":null}'::jsonb;
    perform public.finalize_bank_statement(extra_workspace, extra_document, bad_statement);
    if not exists (select 1 from public.documents d where d.id = extra_document
        and d.currency is null and d.period_start is null and d.period_end is null)
    then
        raise exception 'Unknown metadata was replaced with defaults';
    end if;

    extra_workspace := gen_random_uuid();
    extra_document := gen_random_uuid();
    perform public.reserve_source_upload(extra_workspace, extra_document,
        'personal', 'bank_statement', 'Existing rows', 'synthetic.csv', 'csv');
    insert into storage.objects (bucket_id, name)
    select 'financial-documents', file_path from public.documents where id = extra_document;
    insert into public.transactions (document_id, date, description, debit, credit, balance, source_row)
    values (extra_document, date '2026-01-01', 'Existing row', 0, 1, 1, 1);
    begin
        perform public.finalize_bank_statement(extra_workspace, extra_document, pg_temp.test_statement(extra_document));
        raise exception 'Existing transaction rows were overwritten';
    exception when sqlstate 'PT409' then null;
    end;
    delete from public.transactions t where t.document_id = extra_document;
    update public.documents set status = 'failed' where id = extra_document;
    begin
        perform public.finalize_bank_statement(extra_workspace, extra_document, pg_temp.test_statement(extra_document));
        raise exception 'A failed document was finalized';
    exception when sqlstate 'PT409' then null;
    end;
end;
$$;

select set_config('request.jwt.claim.sub', current_setting('fingenie_test.final_other'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.final_other'), 'role', 'authenticated'
)::text, true);
do $$
begin
    begin
        perform public.finalize_bank_statement(
            current_setting('fingenie_test.final_workspace')::uuid,
            current_setting('fingenie_test.final_document')::uuid,
            pg_temp.test_statement(current_setting('fingenie_test.final_document')::uuid)
        );
        raise exception 'Another user finalized this document';
    exception when sqlstate 'PT404' then null;
    end;
    begin
        perform public.finalize_bank_statement(gen_random_uuid(), gen_random_uuid(), '{}'::jsonb);
        raise exception 'Missing workspace was accepted';
    exception when sqlstate 'PT404' then null;
    end;
end;
$$;

select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
do $$
begin
    begin
        perform public.finalize_bank_statement(gen_random_uuid(), gen_random_uuid(), '{}'::jsonb);
        raise exception 'Identity-less role was accepted';
    exception when insufficient_privilege then null;
    end;
end;
$$;

set local role anon;
do $$
begin
    if has_function_privilege(current_user, 'public.finalize_bank_statement(uuid,uuid,jsonb)', 'EXECUTE') then
        raise exception 'Anonymous role can finalize documents';
    end if;
end;
$$;
reset role;
rollback;
select 'Parsed document atomicity, ownership and exact money checks passed' as result;
