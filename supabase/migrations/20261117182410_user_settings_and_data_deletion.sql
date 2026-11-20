-- Owner-scoped settings and durable, manually resumed financial-data deletion.
create table public.user_preferences (
    user_id uuid primary key references auth.users(id),
    default_currency text not null default 'INR'
        check (default_currency in ('INR','USD','EUR','GBP','AED','AUD','CAD','JPY')),
    theme text not null default 'light' check (theme in ('light','dark'))
);
create table public.financial_data_state (
    user_id uuid primary key references auth.users(id),
    generation bigint not null check (generation >= 0)
);
create table public.data_deletion_jobs (
    user_id uuid not null references auth.users(id),
    id uuid not null,
    status text not null default 'pending' check (status in ('pending','completed')),
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    primary key (user_id,id),
    check ((status = 'completed') = (completed_at is not null))
);
create unique index one_pending_data_deletion on public.data_deletion_jobs(user_id)
    where status = 'pending';
create table public.data_deletion_sources (
    user_id uuid not null,
    job_id uuid not null,
    path text not null check (split_part(path,'/',1) = user_id::text),
    removed boolean not null default false,
    primary key (user_id,job_id,path),
    foreign key (user_id,job_id) references public.data_deletion_jobs(user_id,id)
);

alter table public.user_preferences enable row level security;
alter table public.financial_data_state enable row level security;
alter table public.data_deletion_jobs enable row level security;
alter table public.data_deletion_sources enable row level security;
revoke all on public.user_preferences,public.financial_data_state,
    public.data_deletion_jobs,public.data_deletion_sources from public,anon,authenticated;
grant select,insert on public.user_preferences,public.financial_data_state,
    public.data_deletion_jobs,public.data_deletion_sources to authenticated;
grant update(default_currency,theme) on public.user_preferences to authenticated;
grant update(generation) on public.financial_data_state to authenticated;
grant update(status,completed_at) on public.data_deletion_jobs to authenticated;
grant update(removed),delete on public.data_deletion_sources to authenticated;
grant all on public.user_preferences,public.financial_data_state,
    public.data_deletion_jobs,public.data_deletion_sources to service_role;

create policy preferences_select on public.user_preferences for select to authenticated
    using (user_id = (select auth.uid()));
create policy preferences_insert on public.user_preferences for insert to authenticated
    with check (user_id = (select auth.uid()));
create policy preferences_update on public.user_preferences for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy data_state_select on public.financial_data_state for select to authenticated
    using (user_id = (select auth.uid()));
create policy data_state_insert on public.financial_data_state for insert to authenticated
    with check (user_id = (select auth.uid()));
create policy data_state_update on public.financial_data_state for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy deletion_jobs_select on public.data_deletion_jobs for select to authenticated
    using (user_id = (select auth.uid()));
create policy deletion_jobs_insert on public.data_deletion_jobs for insert to authenticated
    with check (user_id = (select auth.uid()) and status = 'pending');
create policy deletion_jobs_update on public.data_deletion_jobs for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy deletion_sources_select on public.data_deletion_sources for select to authenticated
    using (user_id = (select auth.uid()));
create policy deletion_sources_insert on public.data_deletion_sources for insert to authenticated
    with check (user_id = (select auth.uid()) and not removed and exists (
        select 1 from public.data_deletion_jobs j where j.user_id = auth.uid()
            and j.id = job_id and j.status = 'pending'));
create policy deletion_sources_update on public.data_deletion_sources for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy deletion_sources_delete on public.data_deletion_sources for delete to authenticated
    using (user_id = (select auth.uid()) and removed);

create function public.lock_financial_data() returns void
language plpgsql security invoker set search_path = '' as $$
begin
    if auth.uid() is null then
        raise exception using errcode = '42501', message = 'Authentication required';
    end if;
    perform pg_advisory_xact_lock(hashtextextended('fingenie.owner:' || auth.uid()::text,0));
end;
$$;

-- Every existing cooperating source writer already calls this helper.
create or replace function public.lock_source_upload(p_workspace_id uuid) returns void
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if exists (select 1 from public.data_deletion_jobs where user_id = auth.uid() and status = 'pending') then
        raise sqlstate 'PT409' using message = 'Financial data deletion is in progress';
    end if;
    perform pg_advisory_xact_lock(hashtextextended(
        'fingenie.source:' || auth.uid()::text || ':' || p_workspace_id::text,0));
end;
$$;

create function public.get_upload_generation() returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if exists (select 1 from public.data_deletion_jobs where user_id = auth.uid() and status = 'pending') then
        raise sqlstate 'PT409' using message = 'Financial data deletion is in progress';
    end if;
    return jsonb_build_object('generation',coalesce((select generation from public.financial_data_state
        where user_id = auth.uid()),0));
end;
$$;

create function public.reserve_source_upload_at_generation(
    p_workspace_id uuid,p_document_id uuid,p_user_type text,p_document_type text,
    p_name text,p_original_filename text,p_file_extension text,p_generation bigint
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
    v_workspace public.workspaces%rowtype;
    v_document public.documents%rowtype;
begin
    perform public.lock_source_upload(p_workspace_id);
    if p_generation is distinct from coalesce((select generation from public.financial_data_state
        where user_id = auth.uid()),0) or exists (select 1 from public.upload_cancellations
        where user_id = auth.uid() and workspace_id = p_workspace_id) then
        raise sqlstate 'PT409' using message = 'Upload was invalidated by data deletion or cancellation';
    end if;
    if p_file_extension is null or p_file_extension not in ('csv','xlsx') then
        raise exception using errcode = '22023', message = 'Unsupported source extension';
    end if;
    insert into public.workspaces(id,user_id,user_type,document_type,name)
        values(p_workspace_id,auth.uid(),p_user_type,p_document_type,p_name) returning * into v_workspace;
    insert into public.documents(id,workspace_id,file_path,original_filename)
        values(p_document_id,p_workspace_id,auth.uid()::text || '/' || p_workspace_id::text || '/'
            || p_document_id::text || '/source.' || p_file_extension,p_original_filename)
        returning * into v_document;
    return jsonb_build_object('workspace',jsonb_build_object('id',v_workspace.id,
        'name',v_workspace.name,'user_type',v_workspace.user_type,'document_type',v_workspace.document_type,
        'created_at',v_workspace.created_at),'document',jsonb_build_object('id',v_document.id,
        'file_path',v_document.file_path,'status',v_document.status));
end;
$$;

-- Legacy generation-zero calls still work until the owner's first deletion.
create or replace function public.reserve_source_upload(
    p_workspace_id uuid,p_document_id uuid,p_user_type text,p_document_type text,
    p_name text,p_original_filename text,p_file_extension text
) returns jsonb language sql security invoker set search_path = '' as $$
    select public.reserve_source_upload_at_generation(p_workspace_id,p_document_id,p_user_type,
        p_document_type,p_name,p_original_filename,p_file_extension,0);
$$;

create function public.patch_user_preferences(p_patch jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare v_preferences public.user_preferences%rowtype;
begin
    if auth.uid() is null then
        raise exception using errcode = '42501', message = 'Authentication required';
    end if;
    if jsonb_typeof(p_patch) is distinct from 'object' then
        raise sqlstate 'PT422' using message = 'Invalid preferences';
    end if;
    if exists (select 1 from jsonb_object_keys(p_patch) k where k not in ('default_currency','theme'))
        or (p_patch ? 'default_currency' and (jsonb_typeof(p_patch->'default_currency') is distinct from 'string'
            or p_patch->>'default_currency' not in ('INR','USD','EUR','GBP','AED','AUD','CAD','JPY')))
        or (p_patch ? 'theme' and (jsonb_typeof(p_patch->'theme') is distinct from 'string'
            or p_patch->>'theme' not in ('light','dark'))) then
        raise sqlstate 'PT422' using message = 'Invalid preferences';
    end if;
    insert into public.user_preferences(user_id,default_currency,theme)
        values(auth.uid(),coalesce(p_patch->>'default_currency','INR'),coalesce(p_patch->>'theme','light'))
    on conflict(user_id) do update set
        default_currency = case when p_patch ? 'default_currency' then excluded.default_currency else user_preferences.default_currency end,
        theme = case when p_patch ? 'theme' then excluded.theme else user_preferences.theme end
    returning * into v_preferences;
    return jsonb_build_object('default_currency',v_preferences.default_currency,'theme',v_preferences.theme);
end;
$$;

create function public.begin_financial_data_deletion(p_operation_id uuid default null) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare v_job public.data_deletion_jobs%rowtype;
begin
    perform public.lock_financial_data();
    if p_operation_id is not null then
        select * into v_job from public.data_deletion_jobs where user_id = auth.uid() and id = p_operation_id;
        if found then
            if v_job.status = 'completed' and (
                exists(select 1 from public.workspaces where user_id = auth.uid()) or
                exists(select 1 from storage.objects where bucket_id = 'financial-documents'
                    and starts_with(name,auth.uid()::text || '/'))) then
                raise sqlstate 'PT410' using message = 'New data exists; confirm a new deletion';
            end if;
            return jsonb_build_object('id',v_job.id,'status',v_job.status);
        end if;
    end if;
    select * into v_job from public.data_deletion_jobs where user_id = auth.uid() and status = 'pending';
    if found then
        if p_operation_id is not null and p_operation_id <> v_job.id then
            raise sqlstate 'PT409' using message = 'Another deletion is in progress';
        end if;
        return jsonb_build_object('id',v_job.id,'status',v_job.status);
    end if;
    insert into public.data_deletion_jobs(user_id,id)
        values(auth.uid(),coalesce(p_operation_id,gen_random_uuid())) returning * into v_job;
    return jsonb_build_object('id',v_job.id,'status',v_job.status);
end;
$$;

-- Initialize evidence for direct owner table inserts too, not only RPC callers.
create function public.initialize_financial_data_deletion() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if tg_when = 'BEFORE' then return new; end if;
    insert into public.financial_data_state(user_id,generation) values(auth.uid(),1)
        on conflict(user_id) do update set generation = financial_data_state.generation + 1;
    -- Cancellation IDs remain after deletion so old finalization/recovery cannot resurrect data.
    insert into public.upload_cancellations(user_id,workspace_id,document_id)
        select auth.uid(),w.id,d.id from public.workspaces w join public.documents d on d.workspace_id=w.id
        where w.user_id=auth.uid() on conflict(user_id,workspace_id) do nothing;
    insert into public.data_deletion_sources(user_id,job_id,path)
        select auth.uid(),new.id,paths.path from (
            select d.file_path as path from public.documents d join public.workspaces w on w.id=d.workspace_id where w.user_id=auth.uid()
            union select name from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')
        ) paths;
    return new;
end;
$$;
create trigger lock_data_deletion_insert before insert on public.data_deletion_jobs
    for each row execute function public.initialize_financial_data_deletion();
create trigger initialize_data_deletion_insert after insert on public.data_deletion_jobs
    for each row execute function public.initialize_financial_data_deletion();

create function public.get_financial_data_deletion_sources(p_operation_id uuid,p_limit integer default 100) returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if not exists(select 1 from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id) then
        raise sqlstate 'PT404' using message='Deletion not found';
    end if;
    if p_limit is null or p_limit < 1 or p_limit > 100 then
        raise sqlstate 'PT422' using message='Invalid deletion batch limit';
    end if;
    return jsonb_build_object('id',p_operation_id,'sources',coalesce((select jsonb_agg(path) from (
        select path from public.data_deletion_sources where user_id=auth.uid() and job_id=p_operation_id and not removed
        order by path limit p_limit) batch),'[]'::jsonb));
end;
$$;

create function public.confirm_financial_data_sources_removed(p_operation_id uuid,p_paths text[]) returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if not exists(select 1 from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id and status='pending') then
        raise sqlstate 'PT409' using message='Deletion is not pending';
    end if;
    if p_paths is null or cardinality(p_paths) > 100 or exists(select 1 from unnest(p_paths) as requested(path)
        where requested.path is null or not exists(select 1 from public.data_deletion_sources s
            where s.user_id=auth.uid() and s.job_id=p_operation_id and s.path=requested.path)) then
        raise sqlstate 'PT422' using message='Invalid deletion sources';
    end if;
    if exists(select 1 from storage.objects where bucket_id='financial-documents' and name=any(p_paths)) then
        raise sqlstate 'PT409' using message='Source removal has not been confirmed';
    end if;
    update public.data_deletion_sources set removed=true where user_id=auth.uid() and job_id=p_operation_id and path=any(p_paths);
    return jsonb_build_object('confirmed',true);
end;
$$;

create function public.finish_financial_data_deletion(p_operation_id uuid) returns jsonb
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if not exists(select 1 from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id) then
        raise sqlstate 'PT404' using message='Deletion not found';
    end if;
    if exists(select 1 from public.data_deletion_jobs where user_id=auth.uid() and id=p_operation_id and status='completed') then
        if exists(select 1 from public.workspaces where user_id=auth.uid()) or
            exists(select 1 from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')) then
            raise sqlstate 'PT410' using message='New data exists; confirm a new deletion';
        end if;
        return jsonb_build_object('status','deleted');
    end if;
    if exists(select 1 from public.data_deletion_sources where user_id=auth.uid() and job_id=p_operation_id and not removed)
        or exists(select 1 from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')) then
        raise sqlstate 'PT409' using message='Financial source removal is incomplete';
    end if;
    delete from public.transactions where document_id in (select d.id from public.documents d
        join public.workspaces w on w.id=d.workspace_id where w.user_id=auth.uid());
    delete from public.documents where workspace_id in (select id from public.workspaces where user_id=auth.uid());
    delete from public.workspaces where user_id=auth.uid();
    update public.data_deletion_jobs set status='completed',completed_at=coalesce(completed_at,now())
        where user_id=auth.uid() and id=p_operation_id;
    delete from public.data_deletion_sources where user_id=auth.uid() and job_id=p_operation_id;
    return jsonb_build_object('status','deleted');
end;
$$;

-- Protect durable evidence even when an owner calls the table API directly.
create function public.guard_deletion_evidence() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
    perform public.lock_financial_data();
    if tg_table_name='financial_data_state' then
        if new.generation <= old.generation then
            raise sqlstate 'PT409' using message='Upload generation cannot be reset';
        end if;
    elsif tg_table_name='data_deletion_sources' then
        if (old.removed and not new.removed) or (new.removed and exists(select 1 from storage.objects
            where bucket_id='financial-documents' and name=new.path)) then
            raise sqlstate 'PT409' using message='Source removal is not verified';
        end if;
    elsif (old.status='completed' and new.status <> old.status) or (new.status='completed' and (
        exists(select 1 from public.workspaces where user_id=auth.uid()) or
        exists(select 1 from storage.objects where bucket_id='financial-documents' and starts_with(name,auth.uid()::text || '/')))) then
        raise sqlstate 'PT409' using message='Deletion completion is not verified';
    end if;
    return new;
end;
$$;
create trigger guard_upload_generation before update on public.financial_data_state
    for each row execute function public.guard_deletion_evidence();
create trigger guard_deletion_job before update on public.data_deletion_jobs
    for each row execute function public.guard_deletion_evidence();
create trigger guard_deletion_source before update on public.data_deletion_sources
    for each row execute function public.guard_deletion_evidence();

revoke all on function public.lock_financial_data(),public.get_upload_generation(),
    public.reserve_source_upload_at_generation(uuid,uuid,text,text,text,text,text,bigint),
    public.patch_user_preferences(jsonb),public.begin_financial_data_deletion(uuid),
    public.get_financial_data_deletion_sources(uuid,integer),
    public.confirm_financial_data_sources_removed(uuid,text[]),public.finish_financial_data_deletion(uuid),
    public.guard_deletion_evidence(),public.initialize_financial_data_deletion() from public,anon,authenticated;
grant execute on function public.lock_financial_data(),public.get_upload_generation(),
    public.reserve_source_upload_at_generation(uuid,uuid,text,text,text,text,text,bigint),
    public.patch_user_preferences(jsonb),public.begin_financial_data_deletion(uuid),
    public.get_financial_data_deletion_sources(uuid,integer),
    public.confirm_financial_data_sources_removed(uuid,text[]),public.finish_financial_data_deletion(uuid),
    public.guard_deletion_evidence(),public.initialize_financial_data_deletion() to authenticated;
