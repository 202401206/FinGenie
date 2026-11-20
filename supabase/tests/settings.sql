-- Synthetic settings and deletion policy checks. File operations here stand in
-- for Storage API calls; production code must never delete storage rows by SQL.
begin;
select set_config('fingenie_test.settings_owner',gen_random_uuid()::text,true);
select set_config('fingenie_test.settings_other',gen_random_uuid()::text,true);
insert into auth.users(id) values(current_setting('fingenie_test.settings_owner')::uuid),
    (current_setting('fingenie_test.settings_other')::uuid);
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('fingenie_test.settings_owner'),true);
do $$
declare
    v_workspace uuid:=gen_random_uuid(); v_document uuid:=gen_random_uuid();
    v_job uuid:=gen_random_uuid(); v_path text; v_result jsonb; v_bad jsonb;
begin
    if public.patch_user_preferences('{}') <> '{"default_currency":"INR","theme":"light"}'::jsonb then
        raise exception 'Preference defaults differ';
    end if;
    perform public.patch_user_preferences('{"default_currency":"USD"}');
    if public.patch_user_preferences('{"theme":"dark"}') <> '{"default_currency":"USD","theme":"dark"}'::jsonb then
        raise exception 'Partial update lost another preference';
    end if;
    foreach v_bad in array array['[]'::jsonb,'{"theme":null}'::jsonb,'{"user_id":"foreign"}'::jsonb,
        '{"theme":"system"}'::jsonb,'{"default_currency":"XXX"}'::jsonb,'{"theme":false}'::jsonb] loop
        begin
            perform public.patch_user_preferences(v_bad);
            raise exception 'Invalid preference was accepted';
        exception when sqlstate 'PT422' then null;
        end;
    end loop;
    begin
        insert into public.user_preferences(user_id) values(current_setting('fingenie_test.settings_other')::uuid);
        raise exception 'Foreign preference insert succeeded';
    exception when insufficient_privilege then null;
    end;
    perform public.reserve_source_upload(v_workspace,v_document,'business','balance_sheet','Synthetic settings','settings.csv','csv');
    select file_path into v_path from public.documents where id=v_document;
    insert into storage.objects(bucket_id,name) values('financial-documents',v_path);
    v_result:=public.begin_financial_data_deletion(v_job);
    if v_result->>'status' <> 'pending' or (public.get_financial_data_deletion_sources(v_job))->'sources' <> jsonb_build_array(v_path) then
        raise exception 'Durable deletion manifest differs';
    end if;
    if public.begin_financial_data_deletion(v_job) <> v_result then
        raise exception 'Retry did not retain the original operation';
    end if;
    begin
        perform public.get_upload_generation();
        raise exception 'Upload was admitted while deletion is pending';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        perform public.finish_financial_data_deletion(v_job);
        raise exception 'Completed while source was accessible';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        update public.data_deletion_jobs set status='completed',completed_at=now() where user_id=auth.uid() and id=v_job;
        raise exception 'Forged completion accepted';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        perform public.confirm_financial_data_sources_removed(v_job,array[v_path]);
        raise exception 'False source removal accepted';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        perform public.confirm_financial_data_sources_removed(v_job,array['unknown']);
        raise exception 'Unknown source accepted';
    exception when sqlstate 'PT422' then null;
    end;
    delete from storage.objects where bucket_id='financial-documents' and name=v_path;
    perform public.confirm_financial_data_sources_removed(v_job,array[v_path]);
    if public.finish_financial_data_deletion(v_job) <> '{"status":"deleted"}'::jsonb then
        raise exception 'Deletion receipt differs';
    end if;
    if exists(select 1 from public.workspaces where user_id=auth.uid())
        or not exists(select 1 from public.user_preferences where user_id=auth.uid() and theme='dark' and default_currency='USD') then
        raise exception 'Financial deletion lost preferences or retained workspaces';
    end if;
    perform public.finish_financial_data_deletion(v_job);
    begin
        perform public.reserve_source_upload(gen_random_uuid(),gen_random_uuid(),'personal','bank_statement','Late','late.csv','csv');
        raise exception 'A generation-zero upload survived deletion';
    exception when sqlstate 'PT409' then null;
    end;
    begin
        update public.financial_data_state set generation=0 where user_id=auth.uid();
        raise exception 'Upload generation was reset';
    exception when sqlstate 'PT409' then null;
    end;
    perform public.reserve_source_upload_at_generation(gen_random_uuid(),gen_random_uuid(),
        'personal','bank_statement','New upload','new.csv','csv',1);
    begin
        perform public.begin_financial_data_deletion(v_job);
        raise exception 'Old deletion key reused against newly uploaded data';
    exception when sqlstate 'PT410' then null;
    end;
    begin
        perform public.finish_financial_data_deletion(v_job);
        raise exception 'Old completed operation erased new data';
    exception when sqlstate 'PT410' then null;
    end;
    perform set_config('fingenie_test.settings_job',v_job::text,true);
end;
$$;
select set_config('request.jwt.claim.sub',current_setting('fingenie_test.settings_other'),true);
do $$
begin
    if exists(select 1 from public.user_preferences) or exists(select 1 from public.data_deletion_jobs)
        or exists(select 1 from public.financial_data_state) then
        raise exception 'Foreign settings/deletion state leaked';
    end if;
    begin
        perform public.get_financial_data_deletion_sources(current_setting('fingenie_test.settings_job')::uuid);
        raise exception 'Foreign deletion manifest leaked';
    exception when sqlstate 'PT404' then null;
    end;
end;
$$;
set local role anon;
do $$
begin
    if has_function_privilege(current_user,'public.patch_user_preferences(jsonb)','execute')
        or has_function_privilege(current_user,'public.begin_financial_data_deletion(uuid)','execute') then
        raise exception 'Anonymous settings/deletion RPC execution allowed';
    end if;
end;
$$;
reset role;
do $$
begin
    if (select count(*) from auth.users where id in(current_setting('fingenie_test.settings_owner')::uuid,
        current_setting('fingenie_test.settings_other')::uuid)) <> 2 then
        raise exception 'Auth identities were deleted';
    end if;
    if exists(select 1 from pg_proc where pronamespace='public'::regnamespace and proname in(
        'patch_user_preferences','begin_financial_data_deletion','finish_financial_data_deletion','get_upload_generation')
        and (prosecdef or not ('search_path=""'=any(proconfig)))) then
        raise exception 'Unsafe function privileges/search path';
    end if;
end;
$$;
rollback;
select 'Preferences, deletion retries, generation guards and ownership passed' as result;
