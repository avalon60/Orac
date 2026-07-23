--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_rag_usage_privilege_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: administrative lifecycle API for RAG usage privileges
create or replace package orac_code.rag_usage_privilege_api
authid definer
as
  function grant_scope_usage(
    p_username          in varchar2,
    p_scope_type        in varchar2,
    p_scope_key         in varchar2,
    p_effective_on      in timestamp with time zone default systimestamp,
    p_expires_on        in timestamp with time zone default null,
    p_granted_by        in varchar2 default null,
    p_grant_reason_code in varchar2 default 'ADMIN_GRANT'
  ) return varchar2;

  function revoke_scope_usage(
    p_username           in varchar2,
    p_scope_type         in varchar2,
    p_scope_key          in varchar2,
    p_revoked_by         in varchar2 default null,
    p_revoke_reason_code in varchar2 default 'ADMIN_REVOKE'
  ) return varchar2;
end rag_usage_privilege_api;
/
--rollback drop package orac_code.rag_usage_privilege_api;
