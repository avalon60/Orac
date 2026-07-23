--liquibase formatted sql

--changeset clive:create_package_spec_orac_api_rag_usage_privileges_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: controlled table API for historical RAG usage privileges
create or replace package orac_api.rag_usage_privileges_tapi
authid definer
as
  procedure ins(p_row in out orac_api.rag_usage_privileges_v%rowtype);
  procedure upd(
    p_rag_usage_privilege_id in orac_api.rag_usage_privileges_v.rag_usage_privilege_id%type,
    p_row                    in out orac_api.rag_usage_privileges_v%rowtype,
    p_row_version            in orac_api.rag_usage_privileges_v.row_version%type
  );
end rag_usage_privileges_tapi;
/
--rollback drop package orac_api.rag_usage_privileges_tapi;
