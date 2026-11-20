-- Durable context is owned financial data, never a token or public API payload.
create table public.upload_attempts (
    id uuid primary key,
    user_id uuid not null references auth.users(id),
    workspace_id uuid not null,
    document_id uuid not null,
    upload_generation bigint not null check (upload_generation >= 0),
    user_type text not null check (user_type in ('personal','business')),
    document_type text not null check (document_type in ('bank_statement','balance_sheet')),
    kind text not null check (kind in ('csv','xlsx')),
    name text not null check (length(name) between 1 and 255),
    original_filename text not null check (length(original_filename) between 1 and 255),
    expected_json jsonb not null check (jsonb_typeof(expected_json) = 'object'),
    status text not null default 'pending'
        check (status in ('pending','completed','cleaned','needs_review')),
    last_error_code text,
    receipt jsonb,
    revision bigint not null default 0 check (revision >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id,workspace_id),
    unique(user_id,document_id),
    check (user_type = 'business' or document_type = 'bank_statement'),
    check ((status = 'completed') = (receipt is not null)),
    check (last_error_code is null or last_error_code in (
        'auth_required','reconciliation_required','cleanup_required','state_conflict')),
    check ((status = 'needs_review') = (last_error_code is not distinct from 'state_conflict')),
    check (status not in ('completed','cleaned') or last_error_code is null)
);
create index upload_attempts_owner_page on public.upload_attempts(user_id,created_at desc,id desc);
alter table public.upload_attempts enable row level security;
revoke all on public.upload_attempts from public,anon,authenticated;
grant select,insert on public.upload_attempts to authenticated;
grant update(status,last_error_code,receipt,revision,updated_at),delete
    on public.upload_attempts to authenticated;
grant all on public.upload_attempts to service_role;
create policy attempts_select on public.upload_attempts for select to authenticated
    using (user_id = (select auth.uid()));
create policy attempts_insert on public.upload_attempts for insert to authenticated
    with check (user_id = (select auth.uid()));
create policy attempts_update on public.upload_attempts for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
-- Deletion of recovery evidence is allowed only by the confirmed account cleanup.
create policy attempts_delete on public.upload_attempts for delete to authenticated
    using (user_id = (select auth.uid()) and exists (
        select 1 from public.data_deletion_jobs where user_id=auth.uid() and status='pending'
    ) and not exists(select 1 from public.workspaces where user_id=auth.uid())
      and not exists(select 1 from storage.objects where bucket_id='financial-documents'
        and starts_with(name,auth.uid()::text || '/')));

create function public.upload_attempt_summary(p_row public.upload_attempts) returns jsonb
language sql security invoker set search_path='' as $$
    select jsonb_build_object('attempt_id',p_row.id,'workspace_id',p_row.workspace_id,
        'document_id',p_row.document_id,'document_type',p_row.document_type,
        'status',p_row.status,'last_error_code',p_row.last_error_code,
        'receipt',p_row.receipt,'created_at',p_row.created_at,'updated_at',p_row.updated_at);
$$;
create function public.upload_attempt_context(p_row public.upload_attempts) returns jsonb
language sql security invoker set search_path='' as $$
    select jsonb_build_object('user_id',p_row.user_id,'workspace_id',p_row.workspace_id,
        'document_id',p_row.document_id,'upload_generation',p_row.upload_generation,
        'user_type',p_row.user_type,'document_type',p_row.document_type,'kind',p_row.kind,
        'name',p_row.name,'original_filename',p_row.original_filename);
$$;

-- Run the existing reconciliation under the same account/source locks.
create function public.reconcile_journal_attempt(p_row public.upload_attempts) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare v_decision jsonb;
begin
    if p_row.user_id is distinct from auth.uid() then
        raise sqlstate 'PT404' using message='Upload attempt not found';
    end if;
    perform public.lock_source_upload(p_row.workspace_id);
    if p_row.status='needs_review' or p_row.upload_generation is distinct from
        coalesce((select generation from public.financial_data_state where user_id=auth.uid()),0) then
        return jsonb_build_object('state','conflict');
    end if;
    if p_row.status='cleaned' then
        if exists(select 1 from public.workspaces where id=p_row.workspace_id)
            or exists(select 1 from public.documents where id=p_row.document_id)
            or exists(select 1 from storage.objects where bucket_id='financial-documents'
                and name=auth.uid()::text || '/' || p_row.workspace_id::text || '/' || p_row.document_id::text || '/source.' || p_row.kind)
            or not exists(select 1 from public.upload_cancellations where user_id=auth.uid()
                and workspace_id=p_row.workspace_id and document_id=p_row.document_id) then
            return jsonb_build_object('state','conflict');
        end if;
        return jsonb_build_object('state','absent');
    end if;
    -- A formerly completed record must never trigger destructive reconciliation.
    -- Raising inside this block rolls back any cancellation the old RPC attempted.
    begin
        if p_row.document_type='bank_statement' then
            v_decision := public.begin_upload_recovery(p_row.workspace_id,p_row.document_id,p_row.kind,p_row.expected_json);
        else
            v_decision := public.begin_balance_sheet_recovery(p_row.workspace_id,p_row.document_id,p_row.kind,p_row.expected_json);
        end if;
        if p_row.status='completed' and v_decision->>'state' <> 'completed' then
            raise no_data_found;
        end if;
        return v_decision;
    exception when no_data_found then
        return jsonb_build_object('state','conflict');
    end;
end;
$$;

create function public.guard_upload_attempt() returns trigger
language plpgsql security invoker set search_path='' as $$
declare v_decision jsonb;
begin
    perform public.lock_source_upload(new.workspace_id);
    if new.user_id is distinct from auth.uid() then
        raise exception using errcode='42501',message='Upload attempt owner mismatch';
    end if;
    if tg_op='INSERT' then
        if new.status <> 'pending' or new.last_error_code is not null or new.receipt is not null
            or new.revision <> 0 or new.upload_generation is distinct from coalesce(
                (select generation from public.financial_data_state where user_id=auth.uid()),0)
            or exists(select 1 from public.upload_cancellations where user_id=auth.uid() and workspace_id=new.workspace_id)
            or exists(select 1 from public.workspaces where id=new.workspace_id)
            or exists(select 1 from public.documents where id=new.document_id) then
            raise sqlstate 'PT409' using message='Upload journal must precede source writes';
        end if;
        if octet_length(new.expected_json::text) > 16777216
            or new.expected_json->'source_metadata'->>'document_id' is distinct from new.document_id::text
            or (new.document_type='bank_statement' and jsonb_typeof(new.expected_json->'transactions') is distinct from 'array')
            or (new.document_type='balance_sheet' and not (new.expected_json ?& array['assets','liabilities','equity','reporting_date']))
            or new.original_filename ~ '[/\\[:cntrl:]]'
            or lower(right(new.original_filename,length(new.kind)+1)) <> '.' || new.kind
            or btrim(new.name)='' or new.name ~ '[[:cntrl:]]' then
            raise sqlstate 'PT422' using message='Invalid upload journal context';
        end if;
        new.created_at := now();
    else
        if (to_jsonb(new)-array['status','last_error_code','receipt','revision','updated_at'])
            is distinct from (to_jsonb(old)-array['status','last_error_code','receipt','revision','updated_at'])
            or new.revision <> old.revision+1
            or (old.status='needs_review' and new.status <> 'needs_review')
            or (old.status in ('completed','cleaned') and new.status not in (old.status,'needs_review')) then
            raise sqlstate 'PT409' using message='Upload journal context or transition conflicts';
        end if;
        if new.status='completed' then
            v_decision := public.reconcile_journal_attempt(old);
            if v_decision->>'state' <> 'completed' then
                raise sqlstate 'PT409' using message='Saved upload has not been verified';
            end if;
            new.receipt := v_decision->'receipt';
        elsif new.status='cleaned' then
            if exists(select 1 from public.workspaces where id=new.workspace_id)
                or exists(select 1 from public.documents where id=new.document_id)
                or exists(select 1 from storage.objects where bucket_id='financial-documents'
                    and name=auth.uid()::text || '/' || new.workspace_id::text || '/' || new.document_id::text || '/source.' || new.kind)
                or not exists(select 1 from public.upload_cancellations where user_id=auth.uid()
                    and workspace_id=new.workspace_id and document_id=new.document_id) then
                raise sqlstate 'PT409' using message='Upload cleanup has not been verified';
            end if;
            new.receipt := null;
        else
            new.receipt := null;
        end if;
    end if;
    new.updated_at := now();
    return new;
end;
$$;
create trigger guard_upload_attempt before insert or update on public.upload_attempts
    for each row execute function public.guard_upload_attempt();

create function public.create_upload_attempt(p_attempt_id uuid,p_context jsonb,p_expected_json jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare v_row public.upload_attempts%rowtype;
begin
    perform public.lock_source_upload((p_context->>'workspace_id')::uuid);
    if p_context->>'user_id' is distinct from auth.uid()::text or p_attempt_id is null
        or jsonb_typeof(p_context) is distinct from 'object'
        or not (p_context ?& array['user_id','workspace_id','document_id','upload_generation',
            'user_type','document_type','kind','name','original_filename'])
        or exists(select 1 from jsonb_object_keys(p_context) k where k not in
            ('user_id','workspace_id','document_id','upload_generation','user_type','document_type','kind','name','original_filename')) then
        raise sqlstate 'PT422' using message='Invalid upload journal context';
    end if;
    select * into v_row from public.upload_attempts where id=p_attempt_id and user_id=auth.uid() for update;
    if found then
        if v_row.status <> 'pending' or public.upload_attempt_context(v_row) is distinct from p_context
            or v_row.expected_json is distinct from p_expected_json then
            raise sqlstate 'PT409' using message='Upload journal already exists with different state';
        end if;
        return public.upload_attempt_summary(v_row);
    end if;
    insert into public.upload_attempts(id,user_id,workspace_id,document_id,upload_generation,
        user_type,document_type,kind,name,original_filename,expected_json)
    values(p_attempt_id,auth.uid(),(p_context->>'workspace_id')::uuid,(p_context->>'document_id')::uuid,
        (p_context->>'upload_generation')::bigint,p_context->>'user_type',p_context->>'document_type',
        p_context->>'kind',p_context->>'name',p_context->>'original_filename',p_expected_json)
    returning * into v_row;
    return public.upload_attempt_summary(v_row);
exception when unique_violation then
    raise sqlstate 'PT409' using message='Upload journal identity conflicts';
end;
$$;

create function public.begin_journal_recovery(p_attempt_id uuid,p_revision bigint) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare v_row public.upload_attempts%rowtype;
begin
    perform public.lock_financial_data();
    select * into v_row from public.upload_attempts where id=p_attempt_id and user_id=auth.uid() for update;
    if not found then raise sqlstate 'PT404' using message='Upload attempt not found'; end if;
    if v_row.revision is distinct from p_revision then
        raise sqlstate 'PT409' using message='Upload attempt changed; read it again';
    end if;
    return public.reconcile_journal_attempt(v_row);
end;
$$;

create function public.list_upload_attempts(p_limit integer default 50,p_offset integer default 0) returns jsonb
language plpgsql security invoker set search_path='' as $$
begin
    perform public.lock_financial_data();
    if p_limit is null or p_offset is null or p_limit < 1 or p_limit > 100 or p_offset < 0 then
        raise sqlstate 'PT422' using message='Invalid upload attempt pagination';
    end if;
    return jsonb_build_object('limit',p_limit,'offset',p_offset,
        'total',(select count(*) from public.upload_attempts where user_id=auth.uid()),
        'items',coalesce((select jsonb_agg(public.upload_attempt_summary(page.entry)
            order by (page.entry).created_at desc,(page.entry).id desc) from (
            select a as entry from public.upload_attempts a where user_id=auth.uid()
            order by created_at desc,id desc limit p_limit offset p_offset
        ) page),'[]'::jsonb));
end;
$$;

create function public.settle_upload_attempt(p_attempt_id uuid,p_revision bigint,p_status text,p_error_code text default null) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare v_row public.upload_attempts%rowtype;
begin
    perform public.lock_financial_data();
    select * into v_row from public.upload_attempts where id=p_attempt_id and user_id=auth.uid() for update;
    if not found then raise sqlstate 'PT404' using message='Upload attempt not found'; end if;
    if v_row.revision is distinct from p_revision then
        raise sqlstate 'PT409' using message='Upload attempt changed; read it again';
    end if;
    update public.upload_attempts set status=p_status,last_error_code=p_error_code,
        revision=revision+1 where id=p_attempt_id returning * into v_row;
    return public.upload_attempt_summary(v_row);
end;
$$;

-- Include journal-only attempts in deletion cancellation and data erasure.
create function public.cancel_journal_on_data_deletion() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
    perform public.lock_financial_data();
    insert into public.upload_cancellations(user_id,workspace_id,document_id)
        select user_id,workspace_id,document_id from public.upload_attempts where user_id=auth.uid()
        on conflict(user_id,workspace_id) do nothing;
    return new;
end;
$$;
create trigger cancel_journal_on_data_deletion after insert on public.data_deletion_jobs
    for each row execute function public.cancel_journal_on_data_deletion();
create function public.purge_journal_on_data_deletion() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
    if new.status='completed' and old.status='pending' then
        perform public.lock_financial_data();
        if exists(select 1 from public.workspaces where user_id=auth.uid())
            or exists(select 1 from storage.objects where bucket_id='financial-documents'
                and starts_with(name,auth.uid()::text || '/'))
            or exists(select 1 from public.data_deletion_sources where user_id=auth.uid() and job_id=new.id and not removed) then
            raise sqlstate 'PT409' using message='Financial deletion has not been verified';
        end if;
        delete from public.upload_attempts where user_id=auth.uid();
    end if;
    return new;
end;
$$;
-- Runs before the existing evidence guard and completion write.
create trigger aa_purge_upload_journal before update on public.data_deletion_jobs
    for each row execute function public.purge_journal_on_data_deletion();

-- A completed deletion key must also reject newly journaled financial data.
create function public.guard_journal_deletion_replay() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
    perform public.lock_financial_data();
    if new.status='completed' and exists(select 1 from public.upload_attempts where user_id=auth.uid()) then
        raise sqlstate 'PT410' using message='New upload context exists; confirm a new deletion';
    end if;
    return new;
end;
$$;
create trigger guard_journal_deletion_replay before update on public.data_deletion_jobs
    for each row execute function public.guard_journal_deletion_replay();

create or replace function public.begin_financial_data_deletion(p_operation_id uuid default null) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare v_job public.data_deletion_jobs%rowtype;
begin
    perform public.lock_financial_data();
    if p_operation_id is not null then
        select * into v_job from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id;
        if found then
            if v_job.status='completed' and (
                exists(select 1 from public.workspaces where user_id=auth.uid()) or
                exists(select 1 from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')) or
                exists(select 1 from public.upload_attempts where user_id=auth.uid())) then
                raise sqlstate 'PT410' using message='New data exists; confirm a new deletion';
            end if;
            return jsonb_build_object('id',v_job.id,'status',v_job.status);
        end if;
    end if;
    select * into v_job from public.data_deletion_jobs where user_id=auth.uid() and status='pending';
    if found then
        if p_operation_id is not null and p_operation_id <> v_job.id then
            raise sqlstate 'PT409' using message='Another deletion is in progress';
        end if;
        return jsonb_build_object('id',v_job.id,'status',v_job.status);
    end if;
    insert into public.data_deletion_jobs(user_id,id) values(auth.uid(),coalesce(p_operation_id,gen_random_uuid())) returning * into v_job;
    return jsonb_build_object('id',v_job.id,'status',v_job.status);
end;
$$;
create or replace function public.finish_financial_data_deletion(p_operation_id uuid) returns jsonb
language plpgsql security invoker set search_path='' as $$
begin
    perform public.lock_financial_data();
    if not exists(select 1 from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id) then
        raise sqlstate 'PT404' using message='Deletion not found';
    end if;
    if exists(select 1 from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id and status='completed') then
        if exists(select 1 from public.workspaces where user_id=auth.uid()) or
            exists(select 1 from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')) or
            exists(select 1 from public.upload_attempts where user_id=auth.uid()) then
            raise sqlstate 'PT410' using message='New data exists; confirm a new deletion';
        end if;
        return jsonb_build_object('status','deleted');
    end if;
    if exists(select 1 from public.data_deletion_sources where user_id=auth.uid() and job_id=p_operation_id and not removed)
        or exists(select 1 from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')) then
        raise sqlstate 'PT409' using message='Financial source removal is incomplete';
    end if;
    delete from public.transactions where document_id in (select d.id from public.documents d join public.workspaces w on w.id=d.workspace_id where w.user_id=auth.uid());
    delete from public.documents where workspace_id in (select id from public.workspaces where user_id=auth.uid());
    delete from public.workspaces where user_id=auth.uid();
    -- The completion trigger purges owned journal payloads in this transaction.
    update public.data_deletion_jobs set status='completed',completed_at=coalesce(completed_at,now()) where user_id=auth.uid() and id=p_operation_id;
    delete from public.data_deletion_sources where user_id=auth.uid() and job_id=p_operation_id;
    return jsonb_build_object('status','deleted');
end;
$$;

revoke all on function public.upload_attempt_summary(public.upload_attempts),
    public.upload_attempt_context(public.upload_attempts),public.reconcile_journal_attempt(public.upload_attempts),
    public.guard_upload_attempt(),public.create_upload_attempt(uuid,jsonb,jsonb),
    public.begin_journal_recovery(uuid,bigint),public.settle_upload_attempt(uuid,bigint,text,text),
    public.list_upload_attempts(integer,integer),
    public.cancel_journal_on_data_deletion(),public.purge_journal_on_data_deletion(),
    public.guard_journal_deletion_replay() from public,anon,authenticated;
grant execute on function public.upload_attempt_summary(public.upload_attempts),
    public.upload_attempt_context(public.upload_attempts),public.reconcile_journal_attempt(public.upload_attempts),
    public.guard_upload_attempt(),public.create_upload_attempt(uuid,jsonb,jsonb),
    public.begin_journal_recovery(uuid,bigint),public.settle_upload_attempt(uuid,bigint,text,text),
    public.list_upload_attempts(integer,integer),
    public.cancel_journal_on_data_deletion(),public.purge_journal_on_data_deletion(),
    public.guard_journal_deletion_replay() to authenticated;
