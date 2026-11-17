-- Reconcile balances without a fabricated bank transactions array.
-- Existing bank recovery and the shared failed-source release RPC stay unchanged.
create function public.begin_balance_sheet_recovery(
    p_workspace_id uuid,p_document_id uuid,p_file_extension text,p_expected_json jsonb
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
    v_workspace public.workspaces%rowtype;
    v_document public.documents%rowtype;
    v_path text;
    v_has_document boolean;
begin
    -- Includes the account deletion barrier and existing workspace lock order.
    perform public.lock_source_upload(p_workspace_id);
    if p_file_extension is null or p_file_extension not in ('csv','xlsx')
        or jsonb_typeof(p_expected_json) is distinct from 'object'
        or not (p_expected_json ?& array['company','reporting_date','currency','unit_scale',
            'assets','liabilities','equity','unmapped','source_metadata'])
        or jsonb_typeof(p_expected_json->'assets') is distinct from 'object'
        or jsonb_typeof(p_expected_json->'liabilities') is distinct from 'object'
        or jsonb_typeof(p_expected_json->'equity') is distinct from 'object'
        or jsonb_typeof(p_expected_json->'unmapped') is distinct from 'array'
        or jsonb_typeof(p_expected_json->'source_metadata') is distinct from 'object'
        or p_expected_json->'source_metadata'->>'document_id' is distinct from p_document_id::text
    then
        raise sqlstate 'PT422' using message='Invalid balance recovery context';
    end if;
    v_path:=auth.uid()::text || '/' || p_workspace_id::text || '/' || p_document_id::text || '/source.' || p_file_extension;
    if exists(select 1 from public.upload_cancellations where user_id=auth.uid()
        and workspace_id=p_workspace_id and document_id<>p_document_id) then
        return jsonb_build_object('state','conflict');
    end if;
    select * into v_workspace from public.workspaces
        where id=p_workspace_id and user_id=auth.uid() for update;
    if found and (v_workspace.user_type<>'business' or v_workspace.document_type<>'balance_sheet') then
        return jsonb_build_object('state','conflict');
    end if;
    select d.* into v_document from public.documents d join public.workspaces w on w.id=d.workspace_id
        where d.id=p_document_id and w.id=p_workspace_id and w.user_id=auth.uid() for update of d;
    v_has_document:=found;
    if v_has_document then
        if v_document.file_path<>v_path then
            return jsonb_build_object('state','conflict');
        end if;
        if v_document.status='parsed' then
            -- Compare every reported/current/prior-period field, not just totals.
            if v_document.parsed_json is distinct from p_expected_json
                or v_document.currency is distinct from p_expected_json->>'currency'
                or v_document.period_start is not null or v_document.period_end is not null
                or exists(select 1 from public.transactions where document_id=p_document_id)
                or exists(select 1 from public.upload_cancellations where user_id=auth.uid() and workspace_id=p_workspace_id)
                or not exists(select 1 from storage.objects where bucket_id='financial-documents' and name=v_path)
            then
                return jsonb_build_object('state','conflict');
            end if;
            return jsonb_build_object('state','completed','receipt',jsonb_build_object(
                'workspace_id',p_workspace_id,'document_id',p_document_id,
                'status','parsed','transaction_count',0));
        end if;
        if v_document.status not in ('uploaded','failed') or v_document.parsed_json is not null
            or exists(select 1 from public.transactions where document_id=p_document_id) then
            return jsonb_build_object('state','conflict');
        end if;
    elsif exists(select 1 from public.documents where workspace_id=p_workspace_id) then
        return jsonb_build_object('state','conflict');
    end if;
    -- Only an unfinished/absent owned attempt reaches cancellation and cleanup.
    insert into public.upload_cancellations(user_id,workspace_id,document_id)
        values(auth.uid(),p_workspace_id,p_document_id)
        on conflict(user_id,workspace_id) do nothing;
    if v_has_document then
        update public.documents set status='failed' where id=p_document_id;
        return jsonb_build_object('state','failed');
    end if;
    return jsonb_build_object('state','absent');
end;
$$;
revoke all on function public.begin_balance_sheet_recovery(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.begin_balance_sheet_recovery(uuid,uuid,text,jsonb) to authenticated;
