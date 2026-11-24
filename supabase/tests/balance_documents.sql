-- Synthetic balance finalization checks. Apply all migrations first.
begin;
select set_config('fingenie_test.balance_owner', gen_random_uuid()::text, true);
select set_config('fingenie_test.balance_other', gen_random_uuid()::text, true);
select set_config('fingenie_test.balance_workspace', gen_random_uuid()::text, true);
select set_config('fingenie_test.balance_document', gen_random_uuid()::text, true);
insert into auth.users (id, aud, role) values
    (current_setting('fingenie_test.balance_owner')::uuid, 'authenticated', 'authenticated'),
    (current_setting('fingenie_test.balance_other')::uuid, 'authenticated', 'authenticated');

create function pg_temp.balance_snapshot(document_id uuid) returns jsonb language sql as $$
    select jsonb_build_object(
        'company', null, 'reporting_date', '2026-03-31', 'currency', 'USD', 'unit_scale', 1000,
        'assets', jsonb_build_object('current', jsonb_build_array(jsonb_build_object(
            'canonical_field', 'cash', 'raw_label', 'Synthetic cash',
            'value', 12345678901234567890.1234567890123456789::numeric, 'source_row', 6
        )), 'non_current', '[]'::jsonb, 'total', 300),
        'liabilities', jsonb_build_object('current', '[]'::jsonb, 'non_current', '[]'::jsonb, 'total', 120),
        'equity', jsonb_build_object('share_capital', 150, 'retained_earnings', -0.1234567890123456789::numeric, 'total', 179),
        'unmapped', '[{"raw_label":"Unclassified","source_row":20}]'::jsonb,
        'source_metadata', jsonb_build_object('document_id', document_id, 'sheet_name', null),
        'source_locations', '{"assets.total":{"source_row":10}}'::jsonb,
        'prior_period', '{"reporting_date":"2025-03-31","total":12345678901234567890.1234567890123456789}'::jsonb
    );
$$;

-- A later database failure must undo the attempted status/metadata update.
create function pg_temp.fail_balance_update() returns trigger language plpgsql as $$
begin
    if current_setting('fingenie_test.fail_balance_update', true) = 'yes' then
        raise check_violation using message = 'Synthetic failure after balance update';
    end if;
    return new;
end;
$$;
create trigger test_balance_update after update on public.documents
for each row execute function pg_temp.fail_balance_update();

set local role authenticated;
select set_config('request.jwt.claim.sub', current_setting('fingenie_test.balance_owner'), true);
do $$
declare
    v_workspace_id uuid := current_setting('fingenie_test.balance_workspace')::uuid;
    v_document_id uuid := current_setting('fingenie_test.balance_document')::uuid;
    snapshot jsonb := pg_temp.balance_snapshot(v_document_id);
    bad jsonb;
    result jsonb;
    extra_workspace uuid;
    extra_document uuid;
begin
    perform public.reserve_source_upload(v_workspace_id, v_document_id,
        'business', 'balance_sheet', 'Synthetic balance', 'synthetic.csv', 'csv');
    begin
        perform public.finalize_balance_sheet(v_workspace_id, v_document_id, snapshot);
        raise exception 'Missing source was accepted';
    exception when sqlstate 'PT409' then null;
    end;
    insert into storage.objects (bucket_id, name)
        select 'financial-documents', file_path from public.documents where id = v_document_id;

    foreach bad in array array[
        null::jsonb, '[]'::jsonb, '{}'::jsonb,
        snapshot - 'currency',
        snapshot - 'reporting_date',
        jsonb_set(snapshot, '{source_metadata,document_id}', to_jsonb(gen_random_uuid()::text)),
        jsonb_set(snapshot, '{source_metadata}', '{"document_id":null}'::jsonb),
        jsonb_set(snapshot, '{company}', 'true'::jsonb),
        jsonb_set(snapshot, '{currency}', '"EUR"'::jsonb),
        jsonb_set(snapshot, '{unit_scale}', 'true'::jsonb),
        jsonb_set(snapshot, '{unit_scale}', '2'::jsonb),
        jsonb_set(snapshot, '{reporting_date}', '"2026-02-30"'::jsonb),
        jsonb_set(snapshot, '{assets,current}', '{}'::jsonb),
        jsonb_set(snapshot, '{assets,current,0,value}', 'true'::jsonb),
        jsonb_set(snapshot, '{assets,current,0,value}', '"NaN"'::jsonb),
        jsonb_set(snapshot, '{assets,current,0,source_row}', '2.5'::jsonb),
        jsonb_set(snapshot, '{assets,current,0,source_row}', '0'::jsonb),
        jsonb_set(snapshot, '{assets,current,0,source_row}', 'true'::jsonb),
        jsonb_set(snapshot, '{assets,total}', '"Infinity"'::jsonb),
        jsonb_set(snapshot, '{equity,retained_earnings}', 'false'::jsonb),
        jsonb_set(snapshot, '{unmapped}', '["not an object"]'::jsonb),
        jsonb_set(snapshot, '{source_locations}', '[]'::jsonb)
    ] loop
        begin
            perform public.finalize_balance_sheet(v_workspace_id, v_document_id, bad);
            raise exception 'Invalid snapshot was accepted: %', bad;
        exception when sqlstate 'PT422' then null;
        end;
        if not exists (select 1 from public.documents where id = v_document_id
            and status = 'uploaded' and parsed_json is null and currency is null)
        then raise exception 'Invalid snapshot changed document state'; end if;
    end loop;

    perform set_config('fingenie_test.fail_balance_update', 'yes', true);
    begin
        perform public.finalize_balance_sheet(v_workspace_id, v_document_id, snapshot);
        raise exception 'Late update failure did not abort';
    exception when sqlstate 'PT422' then null;
    end;
    perform set_config('fingenie_test.fail_balance_update', 'no', true);
    if not exists (select 1 from public.documents where id = v_document_id
        and status = 'uploaded' and parsed_json is null and currency is null)
    then raise exception 'Late failure left partial metadata'; end if;

    result := public.finalize_balance_sheet(v_workspace_id, v_document_id, snapshot);
    if result is distinct from jsonb_build_object('workspace_id', v_workspace_id,
        'document_id', v_document_id, 'status', 'parsed', 'transaction_count', 0)
        or not exists (select 1 from public.documents where id = v_document_id
            and status = 'parsed' and currency = 'USD' and parsed_json = snapshot
            and period_start is null and period_end is null)
        or exists (select 1 from public.transactions where document_id = v_document_id)
    then raise exception 'Balance snapshot or zero-row receipt differs'; end if;
    begin
        perform public.finalize_balance_sheet(v_workspace_id, v_document_id, snapshot);
        raise exception 'Repeated save was accepted';
    exception when sqlstate 'PT409' then null;
    end;

    -- Missing metadata and legitimate negative/unbalanced values are preserved.
    extra_workspace := gen_random_uuid(); extra_document := gen_random_uuid();
    perform public.reserve_source_upload(extra_workspace, extra_document,
        'business', 'balance_sheet', 'Unknown units', 'synthetic.xlsx', 'xlsx');
    insert into storage.objects (bucket_id, name)
        select 'financial-documents', file_path from public.documents where id = extra_document;
    bad := pg_temp.balance_snapshot(extra_document) || '{"currency":null,"unit_scale":null}'::jsonb;
    bad := jsonb_set(bad, '{assets,total}', 'null'::jsonb);
    perform public.finalize_balance_sheet(extra_workspace, extra_document, bad);
    if not exists (select 1 from public.documents where id = extra_document
        and parsed_json = bad and currency is null and period_start is null and period_end is null)
    then raise exception 'Unknown metadata was replaced'; end if;

    extra_workspace := gen_random_uuid(); extra_document := gen_random_uuid();
    perform public.reserve_source_upload(extra_workspace, extra_document,
        'personal', 'bank_statement', 'Wrong type', 'synthetic.csv', 'csv');
    begin
        perform public.finalize_balance_sheet(extra_workspace, extra_document, pg_temp.balance_snapshot(extra_document));
        raise exception 'Bank workspace was accepted';
    exception when sqlstate 'PT409' then null;
    end;

    extra_workspace := gen_random_uuid(); extra_document := gen_random_uuid();
    perform public.reserve_source_upload(extra_workspace, extra_document,
        'business', 'balance_sheet', 'Invalid state', 'synthetic.csv', 'csv');
    insert into storage.objects (bucket_id, name)
        select 'financial-documents', file_path from public.documents where id = extra_document;
    insert into public.transactions(document_id, date, description, debit, credit, balance, source_row)
        values (extra_document, date '2026-01-01', 'Unexpected bank row', 0, 1, 1, 1);
    begin
        perform public.finalize_balance_sheet(extra_workspace, extra_document, pg_temp.balance_snapshot(extra_document));
        raise exception 'Existing bank rows were accepted';
    exception when sqlstate 'PT409' then null;
    end;
    delete from public.transactions where transactions.document_id = extra_document;
    update public.documents set status = 'failed' where id = extra_document;
    begin
        perform public.finalize_balance_sheet(extra_workspace, extra_document, pg_temp.balance_snapshot(extra_document));
        raise exception 'Failed status was accepted';
    exception when sqlstate 'PT409' then null;
    end;
    update public.documents set status = 'uploaded' where id = extra_document;
    insert into public.upload_cancellations(user_id, workspace_id, document_id)
        values (auth.uid(), extra_workspace, extra_document);
    begin
        perform public.finalize_balance_sheet(extra_workspace, extra_document, pg_temp.balance_snapshot(extra_document));
        raise exception 'Cancelled attempt was finalized';
    exception when sqlstate 'PT409' then null;
    end;
end;
$$;

select set_config('request.jwt.claim.sub', current_setting('fingenie_test.balance_other'), true);
do $$
begin
    begin
        perform public.finalize_balance_sheet(
            current_setting('fingenie_test.balance_workspace')::uuid,
            current_setting('fingenie_test.balance_document')::uuid, '{}'::jsonb);
        raise exception 'Foreign workspace was accepted';
    exception when sqlstate 'PT404' then null;
    end;
    begin
        perform public.finalize_balance_sheet(gen_random_uuid(), gen_random_uuid(), '{}'::jsonb);
        raise exception 'Missing workspace was accepted';
    exception when sqlstate 'PT404' then null;
    end;
end;
$$;
select set_config('request.jwt.claim.sub', '', true);
do $$
begin
    begin
        perform public.finalize_balance_sheet(gen_random_uuid(), gen_random_uuid(), '{}'::jsonb);
        raise exception 'Identity-less caller was accepted';
    exception when insufficient_privilege then null;
    end;
end;
$$;
set local role anon;
do $$
begin
    if has_function_privilege(current_user, 'public.finalize_balance_sheet(uuid,uuid,jsonb)', 'EXECUTE') then
        raise exception 'Anonymous execution is allowed';
    end if;
end;
$$;
reset role;
do $$
begin
    if exists (select 1 from pg_proc where oid = 'public.finalize_balance_sheet(uuid,uuid,jsonb)'::regprocedure
        and (prosecdef or not ('search_path=""' = any(proconfig)))) then
        raise exception 'Function privileges or search_path changed';
    end if;
end;
$$;
rollback;
select 'Balance snapshot atomicity, ownership and exact values passed' as result;
