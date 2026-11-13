-- Recovery uses synthetic metadata only. All fixtures are rolled back.
begin;
select set_config('fingenie_test.recovery_owner', gen_random_uuid()::text, true);
select set_config('fingenie_test.recovery_other', gen_random_uuid()::text, true);
select set_config('fingenie_test.recovery_workspace', gen_random_uuid()::text, true);
select set_config('fingenie_test.recovery_document', gen_random_uuid()::text, true);
insert into auth.users (id, aud, role) values
    (current_setting('fingenie_test.recovery_owner')::uuid, 'authenticated', 'authenticated'),
    (current_setting('fingenie_test.recovery_other')::uuid, 'authenticated', 'authenticated');

create function pg_temp.recovery_statement(p_document uuid) returns jsonb language sql as $$
    select jsonb_build_object(
        'bank', null, 'account_holder', null, 'account_type', null, 'currency', 'INR',
        'period_start', null, 'period_end', null, 'opening_balance', null, 'closing_balance', 1,
        'transactions', jsonb_build_array(jsonb_build_object(
            'date', '2026-01-01', 'description', 'Synthetic amount',
            'debit', 0, 'credit', 123456789012345.6789::numeric,
            'balance', 1, 'source_row', 2)),
        'unmapped', '[]'::jsonb,
        'source_metadata', jsonb_build_object('document_id', p_document, 'sheet_name', null),
        'source_locations', '{}'::jsonb
    );
$$;
set local role authenticated;
select set_config('request.jwt.claim.sub', current_setting('fingenie_test.recovery_owner'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.recovery_owner'), 'role', 'authenticated'
)::text, true);

do $$
declare
    v_ws uuid := current_setting('fingenie_test.recovery_workspace')::uuid;
    v_doc uuid := current_setting('fingenie_test.recovery_document')::uuid;
    v_statement jsonb := pg_temp.recovery_statement(v_doc);
    v_result jsonb;
    v_path text;
    v_done_ws uuid := gen_random_uuid();
    v_done_doc uuid := gen_random_uuid();
    v_absent_ws uuid := gen_random_uuid();
    v_absent_doc uuid := gen_random_uuid();
begin
    perform public.reserve_source_upload(v_ws, v_doc, 'personal', 'bank_statement',
        'Recovery fixture', 'synthetic.csv', 'csv');
    select file_path into v_path from public.documents where id = v_doc;
    insert into storage.objects (bucket_id, name) values ('financial-documents', v_path);
    v_result := public.begin_upload_recovery(v_ws, v_doc, 'csv', v_statement);
    if v_result->>'state' <> 'failed'
        or not exists (select 1 from public.documents where id = v_doc and status = 'failed')
    then raise exception 'Pending attempt was not claimed as failed'; end if;

    begin
        perform public.release_failed_upload(v_ws, v_doc, 'csv');
        raise exception 'Metadata released while source still exists';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        perform public.finalize_bank_statement(v_ws, v_doc, v_statement);
        raise exception 'Late finalization ignored cancellation';
    exception when sqlstate 'PT409' then null;
    end;
    -- SQL metadata deletion is test-only; application cleanup uses Storage API.
    delete from storage.objects where bucket_id = 'financial-documents' and name = v_path;
    begin
        insert into storage.objects (bucket_id, name) values ('financial-documents', v_path);
        raise exception 'Late upload was allowed for failed attempt';
    exception when insufficient_privilege then null;
    end;
    perform public.release_failed_upload(v_ws, v_doc, 'csv');
    if exists (select 1 from public.workspaces where id = v_ws)
        or exists (select 1 from public.documents where id = v_doc)
        or not exists (select 1 from public.upload_cancellations where workspace_id = v_ws)
    then raise exception 'Cleanup did not release metadata and retain cancellation'; end if;
    begin
        perform public.reserve_source_upload(v_ws, v_doc, 'personal', 'bank_statement',
            'Late reservation', 'synthetic.csv', 'csv');
        raise exception 'Queued reservation recreated cancelled attempt';
    exception when sqlstate 'PT409' then null;
    end;
    perform public.begin_upload_recovery(v_ws, v_doc, 'csv', v_statement);
    perform public.release_failed_upload(v_ws, v_doc, 'csv');

    -- Also cancel an attempt whose reservation never became visible.
    v_result := public.begin_upload_recovery(v_absent_ws, v_absent_doc, 'csv', pg_temp.recovery_statement(v_absent_doc));
    if v_result->>'state' <> 'absent' then raise exception 'Missing reservation not recognized'; end if;
    begin
        perform public.reserve_source_upload(v_absent_ws, v_absent_doc, 'personal', 'bank_statement',
            'Late absent reservation', 'synthetic.csv', 'csv');
        raise exception 'Missing attempt was not fenced against late arrival';
    exception when sqlstate 'PT409' then null;
    end;

    perform public.reserve_source_upload(v_done_ws, v_done_doc, 'business', 'bank_statement',
        'Saved fixture', 'synthetic.xlsx', 'xlsx');
    insert into storage.objects (bucket_id, name)
    select 'financial-documents', file_path from public.documents where id = v_done_doc;
    perform public.finalize_bank_statement(v_done_ws, v_done_doc, pg_temp.recovery_statement(v_done_doc));
    v_result := public.begin_upload_recovery(v_done_ws, v_done_doc, 'xlsx', pg_temp.recovery_statement(v_done_doc));
    if v_result->>'state' <> 'completed' or (v_result->'receipt'->>'transaction_count')::int <> 1 then
        raise exception 'Successful save was not reconciled';
    end if;
    if exists (select 1 from public.upload_cancellations where workspace_id = v_done_ws) then
        raise exception 'Successful save was cancelled';
    end if;
    begin
        perform public.release_failed_upload(v_done_ws, v_done_doc, 'xlsx');
        raise exception 'Successful save was released';
    exception when sqlstate 'PT409' then null;
    end;
    update public.transactions set credit = 1 where document_id = v_done_doc;
    v_result := public.begin_upload_recovery(v_done_ws, v_done_doc, 'xlsx', pg_temp.recovery_statement(v_done_doc));
    if v_result->>'state' <> 'conflict' then raise exception 'Changed rows were reported as matching success'; end if;
    if exists (select 1 from public.upload_cancellations where workspace_id = v_done_ws) then
        raise exception 'Conflicting saved data was cancelled';
    end if;

    begin
        delete from public.upload_cancellations where workspace_id = v_ws;
        raise exception 'Cancellation can be removed by an ordinary client';
    exception when insufficient_privilege then null;
    end;
end;
$$;

select set_config('request.jwt.claim.sub', current_setting('fingenie_test.recovery_other'), true);
select set_config('request.jwt.claims', json_build_object(
    'sub', current_setting('fingenie_test.recovery_other'), 'role', 'authenticated'
)::text, true);
do $$
begin
    if exists (select 1 from public.upload_cancellations
        where user_id = current_setting('fingenie_test.recovery_owner')::uuid) then
        raise exception 'Cross-user cancellation visibility';
    end if;
    begin
        insert into public.upload_cancellations (user_id, workspace_id, document_id)
        values (current_setting('fingenie_test.recovery_owner')::uuid, gen_random_uuid(), gen_random_uuid());
        raise exception 'Forged cancellation owner was accepted';
    exception when insufficient_privilege then null;
    end;
end;
$$;
select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claims', '{}', true);
do $$
begin
    begin
        perform public.begin_upload_recovery(gen_random_uuid(), gen_random_uuid(), 'csv', '{}'::jsonb);
        raise exception 'Missing identity was accepted';
    exception when insufficient_privilege then null;
    end;
end;
$$;
set local role anon;
do $$
begin
    if has_function_privilege(current_user, 'public.begin_upload_recovery(uuid,uuid,text,jsonb)', 'EXECUTE')
        or has_function_privilege(current_user, 'public.release_failed_upload(uuid,uuid,text)', 'EXECUTE')
    then raise exception 'Anonymous recovery execution allowed'; end if;
end;
$$;
reset role;
rollback;
select 'Recovery, cancellation, late-write and saved-data protection checks passed' as result;
