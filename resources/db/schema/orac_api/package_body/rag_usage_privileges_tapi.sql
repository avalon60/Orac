--liquibase formatted sql

--changeset clive:create_package_body_orac_api_rag_usage_privileges_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: controlled table API body for historical RAG usage privileges
create or replace package body orac_api.rag_usage_privileges_tapi
as
  procedure ins(p_row in out orac_api.rag_usage_privileges_v%rowtype)
  is
  begin
    insert into orac_api.rag_usage_privileges_v
      (
        user_id, knowledge_scope_id, privilege_code, active_yn,
        effective_on, expires_on, granted_on, granted_by, grant_reason_code,
        revoked_on, revoked_by, revoke_reason_code
      )
    values
      (
        p_row.user_id, p_row.knowledge_scope_id, p_row.privilege_code, p_row.active_yn,
        p_row.effective_on, p_row.expires_on, p_row.granted_on, p_row.granted_by,
        p_row.grant_reason_code, p_row.revoked_on, p_row.revoked_by,
        p_row.revoke_reason_code
      )
    returning rag_usage_privilege_id, row_version
         into p_row.rag_usage_privilege_id, p_row.row_version;
  end ins;

  procedure upd(
    p_rag_usage_privilege_id in orac_api.rag_usage_privileges_v.rag_usage_privilege_id%type,
    p_row                    in out orac_api.rag_usage_privileges_v%rowtype,
    p_row_version            in orac_api.rag_usage_privileges_v.row_version%type
  )
  is
  begin
    update orac_api.rag_usage_privileges_v
       set active_yn = p_row.active_yn,
           revoked_on = p_row.revoked_on,
           revoked_by = p_row.revoked_by,
           revoke_reason_code = p_row.revoke_reason_code
     where rag_usage_privilege_id = p_rag_usage_privilege_id
       and row_version = p_row_version
    returning row_version into p_row.row_version;

    if sql%rowcount = 0
    then
      raise no_data_found;
    end if;
  end upd;
end rag_usage_privileges_tapi;
/
--rollback drop package body orac_api.rag_usage_privileges_tapi;
