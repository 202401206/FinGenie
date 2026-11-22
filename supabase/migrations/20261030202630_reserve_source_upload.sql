-- Reserve metadata before the private Storage insert policy can accept a file.
-- A function call is one PostgreSQL transaction: neither parent nor child can
-- survive a failed reservation. File bytes are a separate Storage API operation.
create function public.reserve_source_upload(
    p_workspace_id uuid,
    p_document_id uuid,
    p_user_type text,
    p_document_type text,
    p_name text,
    p_original_filename text,
    p_file_extension text
) returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
    v_owner uuid := auth.uid();
    v_workspace public.workspaces%rowtype;
    v_document public.documents%rowtype;
begin
    if v_owner is null then
        raise exception using errcode = '42501', message = 'Authentication required';
    end if;
    if p_file_extension is null or p_file_extension not in ('csv', 'xlsx') then
        raise exception using errcode = '22023', message = 'Unsupported source extension';
    end if;

    insert into public.workspaces (id, user_id, user_type, document_type, name)
    values (p_workspace_id, v_owner, p_user_type, p_document_type, p_name)
    returning * into v_workspace;

    insert into public.documents (id, workspace_id, file_path, original_filename)
    values (
        p_document_id,
        p_workspace_id,
        v_owner::text || '/' || p_workspace_id::text || '/' ||
            p_document_id::text || '/source.' || p_file_extension,
        p_original_filename
    )
    returning * into v_document;

    return jsonb_build_object(
        'workspace', jsonb_build_object(
            'id', v_workspace.id,
            'name', v_workspace.name,
            'user_type', v_workspace.user_type,
            'document_type', v_workspace.document_type,
            'created_at', v_workspace.created_at
        ),
        'document', jsonb_build_object(
            'id', v_document.id,
            'file_path', v_document.file_path,
            'status', v_document.status
        )
    );
end;
$$;

-- Postgres normally grants function EXECUTE to PUBLIC. Narrow this explicitly.
revoke all on function public.reserve_source_upload(uuid, uuid, text, text, text, text, text)
    from public, anon, authenticated;
grant execute on function public.reserve_source_upload(uuid, uuid, text, text, text, text, text)
    to authenticated;
