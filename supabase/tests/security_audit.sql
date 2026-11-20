-- Catalog audit complements behavioral owner/foreign tests in the main suites.
-- Run against a disposable database after all FinGenie migrations.
begin;
do $$
declare
    item record;
    privilege_name text;
    policy_command text;
begin
    for item in select c.oid,c.relname,c.relrowsecurity from pg_class c
        join pg_namespace n on n.oid=c.relnamespace
        where n.nspname='public' and c.relkind in ('r','p')
    loop
        if not item.relrowsecurity then
            raise exception 'RLS missing on public.%',item.relname;
        end if;
        foreach privilege_name in array array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] loop
            if (case when privilege_name in ('SELECT','INSERT','UPDATE')
                then has_any_column_privilege('anon',item.oid,privilege_name)
                else has_table_privilege('anon',item.oid,privilege_name) end) then
                raise exception 'Unexpected anonymous % on public.%',privilege_name,item.relname;
            end if;
        end loop;
        foreach privilege_name in array array['TRUNCATE','REFERENCES','TRIGGER'] loop
            if has_table_privilege('authenticated',item.oid,privilege_name) then
                raise exception 'Unexpected authenticated % on public.%',privilege_name,item.relname;
            end if;
        end loop;
        -- A granted operation must have a corresponding policy. Behavioral tests
        -- separately exercise the owner predicate; policy text is not proof of it.
        foreach policy_command in array array['r','a','w','d'] loop
            privilege_name := case policy_command when 'r' then 'SELECT' when 'a' then 'INSERT'
                when 'w' then 'UPDATE' else 'DELETE' end;
            if (case when policy_command='d' then has_table_privilege('authenticated',item.oid,privilege_name)
                    else has_any_column_privilege('authenticated',item.oid,privilege_name) end)
                and not exists(select 1 from pg_policy p where p.polrelid=item.oid
                    and p.polcmd in (policy_command::"char",'*'::"char")
                    and ((select oid from pg_roles where rolname='authenticated')=any(p.polroles)
                        or 0=any(p.polroles))) then
                raise exception 'Granted % lacks a policy on public.%',privilege_name,item.relname;
            end if;
        end loop;
    end loop;

    for item in select p.oid,p.proname,p.prosecdef,p.proconfig from pg_proc p
        join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'
    loop
        if item.prosecdef or not coalesce('search_path=""'=any(item.proconfig),false) then
            raise exception 'Unsafe invoker/search_path configuration: %',item.proname;
        end if;
        if has_function_privilege('anon',item.oid,'EXECUTE') then
            raise exception 'Anonymous function execution allowed: %',item.proname;
        end if;
    end loop;

    if exists(select 1 from pg_views where schemaname='public') then
        raise exception 'A public view requires an explicit security-invoker audit';
    end if;
    if exists(select 1 from storage.buckets where id='financial-documents' and public) then
        raise exception 'Financial source bucket is public';
    end if;
    if exists(select 1 from pg_policy where polrelid='storage.objects'::regclass
        and polcmd in ('w','*')) then
        raise exception 'Financial source overwrite requires an explicit policy review';
    end if;
    if has_column_privilege('authenticated','public.upload_attempts','expected_json','UPDATE')
        or has_column_privilege('authenticated','public.upload_attempts','workspace_id','UPDATE')
        or has_column_privilege('authenticated','public.upload_attempts','document_id','UPDATE')
        or has_column_privilege('authenticated','public.upload_attempts','upload_generation','UPDATE') then
        raise exception 'Immutable journal context can be updated';
    end if;
    if has_table_privilege('authenticated','public.upload_cancellations','DELETE')
        or has_table_privilege('authenticated','public.upload_cancellations','UPDATE') then
        raise exception 'Cancellation evidence can be rewritten';
    end if;
end;
$$;
rollback;
select 'Catalog audit passed: RLS, policies, grants, invoker functions and private sources' as result;
