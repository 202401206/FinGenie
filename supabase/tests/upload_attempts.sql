-- Disposable ownership and journal-evidence tests. No real file bytes or users.
begin;
select set_config('journal.a',gen_random_uuid()::text,true);
select set_config('journal.b',gen_random_uuid()::text,true);
select set_config('journal.id',gen_random_uuid()::text,true);
select set_config('journal.workspace',gen_random_uuid()::text,true);
select set_config('journal.document',gen_random_uuid()::text,true);
insert into auth.users(id) values(current_setting('journal.a')::uuid),(current_setting('journal.b')::uuid);
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('journal.a'),true);
select set_config('request.jwt.claims',json_build_object('sub',current_setting('journal.a'),'role','authenticated')::text,true);
select set_config('journal.context',jsonb_build_object(
    'user_id',current_setting('journal.a'),'workspace_id',current_setting('journal.workspace'),
    'document_id',current_setting('journal.document'),'upload_generation',0,
    'user_type','business','document_type','balance_sheet','kind','csv',
    'name','Synthetic balance','original_filename','synthetic.csv')::text,true);
select set_config('journal.expected',jsonb_build_object(
    'company',null,'reporting_date','2026-03-31','currency',null,'unit_scale',null,
    'assets',jsonb_build_object('current','[]'::jsonb,'non_current','[]'::jsonb,'total',12345678901234567890.1234567890123456789),
    'liabilities',jsonb_build_object('current','[]'::jsonb,'non_current','[]'::jsonb,'total',null),
    'equity',jsonb_build_object('share_capital',null,'retained_earnings',-0.1234567890123456789,'total',null),
    'unmapped','[]'::jsonb,'source_locations','{}'::jsonb,
    'source_metadata',jsonb_build_object('document_id',current_setting('journal.document'),'sheet_name',null))::text,true);
select public.create_upload_attempt(current_setting('journal.id')::uuid,current_setting('journal.context')::jsonb,current_setting('journal.expected')::jsonb);
-- Same pending context is idempotent, without creating source rows.
select public.create_upload_attempt(current_setting('journal.id')::uuid,current_setting('journal.context')::jsonb,current_setting('journal.expected')::jsonb);
do $$
declare affected int;
begin
    if (select count(*) from public.upload_attempts) <> 1
        or exists(select 1 from public.workspaces) then raise exception 'Journal ordering/idempotency failed'; end if;
    if (select expected_json#>>'{assets,total}' from public.upload_attempts) <> '12345678901234567890.1234567890123456789' then
        raise exception 'Journal rounded exact Decimal values';
    end if;
    begin
        update public.upload_attempts set expected_json='{}';
        raise exception 'Immutable financial context was writable';
    exception when insufficient_privilege then null; end;
    delete from public.upload_attempts;
    get diagnostics affected=row_count;
    if affected <> 0 then raise exception 'Pending evidence could be deleted'; end if;
    begin
        update public.upload_attempts set status='completed',revision=revision+1;
        raise exception 'Unverified completion was allowed';
    exception when sqlstate 'PT409' then null; end;
    begin
        update public.upload_attempts set status='cleaned',revision=revision+1;
        raise exception 'Unverified cleanup was allowed';
    exception when sqlstate 'PT409' then null; end;
    if exists(select 1 from public.upload_cancellations) then raise exception 'Failed verification left cancellation behind'; end if;
end;
$$;
select public.settle_upload_attempt(current_setting('journal.id')::uuid,0,'pending','cleanup_required');
do $$
begin
    begin
        perform public.settle_upload_attempt(current_setting('journal.id')::uuid,0,'pending',null);
        raise exception 'Stale revision overwrote newer state';
    exception when sqlstate 'PT409' then null; end;
end;
$$;
select set_config('request.jwt.claim.sub',current_setting('journal.b'),true);
select set_config('request.jwt.claims',json_build_object('sub',current_setting('journal.b'),'role','authenticated')::text,true);
do $$
declare affected int;
begin
    if exists(select 1 from public.upload_attempts) then raise exception 'Foreign journal was exposed'; end if;
    update public.upload_attempts set revision=revision+1;
    get diagnostics affected=row_count;
    if affected <> 0 then raise exception 'Foreign journal was changed'; end if;
    begin
        perform public.begin_journal_recovery(current_setting('journal.id')::uuid,1);
        raise exception 'Foreign journal could be recovered';
    exception when sqlstate 'PT404' then null; end;
    begin
        perform public.begin_journal_recovery(gen_random_uuid(),1);
        raise exception 'Missing journal did not return not-found';
    exception when sqlstate 'PT404' then null; end;
end;
$$;
set local role anon;
do $$
begin
    begin perform 1 from public.upload_attempts;
        raise exception 'Anonymous journal read allowed';
    exception when insufficient_privilege then null; end;
    if has_function_privilege('anon','public.create_upload_attempt(uuid,jsonb,jsonb)','execute')
        or has_function_privilege('anon','public.begin_journal_recovery(uuid,bigint)','execute')
        or has_function_privilege('anon','public.list_upload_attempts(integer,integer)','execute')
        or has_function_privilege('anon','public.settle_upload_attempt(uuid,bigint,text,text)','execute') then
        raise exception 'Anonymous journal function execution allowed';
    end if;
end;
$$;
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('journal.a'),true);
select set_config('request.jwt.claims',json_build_object('sub',current_setting('journal.a'),'role','authenticated')::text,true);
select public.settle_upload_attempt(current_setting('journal.id')::uuid,1,'needs_review','state_conflict');
do $$
begin
    begin
        perform public.settle_upload_attempt(current_setting('journal.id')::uuid,2,'pending',null);
        raise exception 'Conflicting evidence was silently reset';
    exception when sqlstate 'PT409' then null; end;
    if (public.begin_journal_recovery(current_setting('journal.id')::uuid,2))->>'state' <> 'conflict' then
        raise exception 'Needs-review state was not preserved';
    end if;
end;
$$;
select set_config('journal.deletion',(public.begin_financial_data_deletion(gen_random_uuid()))->>'id',true);
select public.finish_financial_data_deletion(current_setting('journal.deletion')::uuid);
do $$
begin
    if exists(select 1 from public.upload_attempts) then raise exception 'Deletion retained journal financial context'; end if;
    if not exists(select 1 from public.upload_cancellations where workspace_id=current_setting('journal.workspace')::uuid) then
        raise exception 'Journal-only cancellation evidence was lost';
    end if;
    begin
        perform public.create_upload_attempt(current_setting('journal.id')::uuid,current_setting('journal.context')::jsonb,current_setting('journal.expected')::jsonb);
        raise exception 'Deleted upload context returned';
    exception when sqlstate 'PT409' then null; end;
end;
$$;
reset role;
do $$
begin
    if exists(select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='public' and p.proname in ('create_upload_attempt','list_upload_attempts','begin_journal_recovery','settle_upload_attempt','guard_upload_attempt')
        and (p.prosecdef or not ('search_path=""'=any(p.proconfig)))) then
        raise exception 'Journal function lost invoker/search-path protections';
    end if;
end;
$$;
rollback;
select 'Durable journal ownership, precision, evidence, revisions and deletion passed' as result;
