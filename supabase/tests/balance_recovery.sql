-- Direct RPC checks with synthetic records only. Real file deletion uses Storage.
begin;
select set_config('fingenie_test.br_owner',gen_random_uuid()::text,true);
select set_config('fingenie_test.br_other',gen_random_uuid()::text,true);
select set_config('fingenie_test.br_workspace',gen_random_uuid()::text,true);
select set_config('fingenie_test.br_document',gen_random_uuid()::text,true);
insert into auth.users(id) values(current_setting('fingenie_test.br_owner')::uuid),
    (current_setting('fingenie_test.br_other')::uuid);

create function pg_temp.recover_balance_snapshot(document_id uuid) returns jsonb
language sql as $$
    select jsonb_build_object('company',null,'reporting_date','2026-03-31','currency',null,'unit_scale',null,
        'assets','{"current":[],"non_current":[],"total":12345678901234567890.1234567890123456789}'::jsonb,
        'liabilities','{"current":[],"non_current":[],"total":null}'::jsonb,
        'equity','{"share_capital":null,"retained_earnings":-0.1234567890123456789,"total":0}'::jsonb,
        'unmapped','[]'::jsonb,'source_metadata',jsonb_build_object('document_id',document_id,'sheet_name',null),
        'source_locations','{}'::jsonb,'prior_period','{"total":42.1234567890123456789}'::jsonb);
$$;
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('fingenie_test.br_owner'),true);
do $$
declare
    v_workspace uuid:=current_setting('fingenie_test.br_workspace')::uuid;
    v_document uuid:=current_setting('fingenie_test.br_document')::uuid;
    v_expected jsonb:=pg_temp.recover_balance_snapshot(v_document);
    v_result jsonb;
    v_pending_workspace uuid:=gen_random_uuid();
    v_pending_document uuid:=gen_random_uuid();
    v_pending_json jsonb:=pg_temp.recover_balance_snapshot(v_pending_document);
    v_path text;
begin
    perform public.reserve_source_upload(v_workspace,v_document,'business','balance_sheet','Recovery fixture','synthetic.csv','csv');
    insert into storage.objects(bucket_id,name) select 'financial-documents',file_path from public.documents where id=v_document;
    perform public.finalize_balance_sheet(v_workspace,v_document,v_expected);
    v_result:=public.begin_balance_sheet_recovery(v_workspace,v_document,'csv',v_expected);
    if v_result <> jsonb_build_object('state','completed','receipt',jsonb_build_object(
        'workspace_id',v_workspace,'document_id',v_document,'status','parsed','transaction_count',0))
        or exists(select 1 from public.upload_cancellations where user_id=auth.uid() and workspace_id=v_workspace)
    then raise exception 'Completed balance was not preserved with a zero-row receipt'; end if;
    if public.begin_balance_sheet_recovery(v_workspace,v_document,'csv',v_expected) <> v_result then
        raise exception 'Repeated completed recovery differs';
    end if;
    update public.documents set parsed_json=jsonb_set(parsed_json,'{prior_period,total}','0') where id=v_document;
    if public.begin_balance_sheet_recovery(v_workspace,v_document,'csv',v_expected)->>'state'<>'conflict' then
        raise exception 'Changed prior period was not a conflict';
    end if;
    update public.documents set parsed_json=v_expected where id=v_document;
    insert into public.transactions(document_id,date,description,debit,credit,balance,source_row)
        values(v_document,'2026-01-01','Unexpected row',0,1,1,1);
    if public.begin_balance_sheet_recovery(v_workspace,v_document,'csv',v_expected)->>'state'<>'conflict' then
        raise exception 'Balance with bank rows was accepted';
    end if;
    delete from public.transactions where document_id=v_document;
    begin
        perform public.begin_balance_sheet_recovery(v_workspace,v_document,'csv','{}'::jsonb);
        raise exception 'Invalid recovery context was accepted';
    exception when sqlstate 'PT422' then null;
    end;

    perform public.reserve_source_upload(v_pending_workspace,v_pending_document,'business','balance_sheet','Unfinished','pending.xlsx','xlsx');
    select file_path into v_path from public.documents where id=v_pending_document;
    insert into storage.objects(bucket_id,name) values('financial-documents',v_path);
    if public.begin_balance_sheet_recovery(v_pending_workspace,v_pending_document,'xlsx',v_pending_json)->>'state'<>'failed' then
        raise exception 'Unfinished balance was not marked failed';
    end if;
    begin
        perform public.finalize_balance_sheet(v_pending_workspace,v_pending_document,v_pending_json);
        raise exception 'Late balance save overwrote failed state';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        perform public.release_failed_upload(v_pending_workspace,v_pending_document,'xlsx');
        raise exception 'Metadata released while source was registered';
    exception when sqlstate 'PT409' then null;
    end;
    delete from storage.objects where bucket_id='financial-documents' and name=v_path;
    perform public.release_failed_upload(v_pending_workspace,v_pending_document,'xlsx');
    if public.begin_balance_sheet_recovery(v_pending_workspace,v_pending_document,'xlsx',v_pending_json)->>'state'<>'absent' then
        raise exception 'Repeated cleaned recovery did not keep original IDs absent';
    end if;
    perform public.release_failed_upload(v_pending_workspace,v_pending_document,'xlsx');
    begin
        perform public.reserve_source_upload(v_pending_workspace,v_pending_document,'business','balance_sheet','Late reservation','pending.xlsx','xlsx');
        raise exception 'Cancelled balance attempt was recreated';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        insert into storage.objects(bucket_id,name) values('financial-documents',v_path);
        raise exception 'Late source insertion was allowed';
    exception when insufficient_privilege then null;
    end;

    v_pending_workspace:=gen_random_uuid(); v_pending_document:=gen_random_uuid();
    perform public.reserve_source_upload(v_pending_workspace,v_pending_document,'personal','bank_statement','Wrong type','bank.csv','csv');
    if public.begin_balance_sheet_recovery(v_pending_workspace,v_pending_document,'csv',pg_temp.recover_balance_snapshot(v_pending_document))->>'state'<>'conflict'
        or not exists(select 1 from public.documents where id=v_pending_document and status='uploaded') then
        raise exception 'Balance recovery changed a bank document';
    end if;
    delete from storage.objects where name=(select file_path from public.documents where id=v_document);
    if public.begin_balance_sheet_recovery(v_workspace,v_document,'csv',v_expected)->>'state'<>'conflict'
        or not exists(select 1 from public.documents where id=v_document and status='parsed' and parsed_json=v_expected) then
        raise exception 'Missing source caused a completed balance to be discarded';
    end if;
end;
$$;
select set_config('request.jwt.claim.sub',current_setting('fingenie_test.br_other'),true);
do $$
declare
    v_workspace uuid:=current_setting('fingenie_test.br_workspace')::uuid;
    v_document uuid:=current_setting('fingenie_test.br_document')::uuid;
begin
    if exists(select 1 from public.documents where id=v_document) then
        raise exception 'Foreign balance was visible';
    end if;
    -- A foreign UUID is absent in this caller's namespace; no foreign path is used.
    if public.begin_balance_sheet_recovery(v_workspace,v_document,'csv',pg_temp.recover_balance_snapshot(v_document))->>'state'<>'absent' then
        raise exception 'Foreign state leaked';
    end if;
    perform public.release_failed_upload(v_workspace,v_document,'csv');
end;
$$;
reset role;
do $$
begin
    if not exists(select 1 from public.documents where id=current_setting('fingenie_test.br_document')::uuid and status='parsed') then
        raise exception 'Foreign caller changed the owner balance';
    end if;
    if has_function_privilege('anon','public.begin_balance_sheet_recovery(uuid,uuid,text,jsonb)','execute')
        or exists(select 1 from pg_proc where oid='public.begin_balance_sheet_recovery(uuid,uuid,text,jsonb)'::regprocedure
            and (prosecdef or not ('search_path=""'=any(proconfig)))) then
        raise exception 'Unsafe balance recovery privileges';
    end if;
end;
$$;
rollback;
select 'Balance recovery preserves completed/conflicting data and safely cleans original attempts' as result;
