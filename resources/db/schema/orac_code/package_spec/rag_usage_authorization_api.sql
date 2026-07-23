--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_rag_usage_authorization_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: least-privilege runtime RAG usage decision API
create or replace package orac_code.rag_usage_authorization_api
authid definer
as
  function authorization_result(
    p_username   in varchar2,
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2;
end rag_usage_authorization_api;
/
--rollback drop package orac_code.rag_usage_authorization_api;
