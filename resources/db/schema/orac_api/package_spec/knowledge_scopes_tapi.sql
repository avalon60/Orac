--liquibase formatted sql

--changeset clive:create_package_spec_orac_api_knowledge_scopes_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: controlled insert API for canonical knowledge scopes
create or replace package orac_api.knowledge_scopes_tapi
authid definer
as
  procedure ins(p_row in out orac_api.knowledge_scopes_v%rowtype);
end knowledge_scopes_tapi;
/
--rollback drop package orac_api.knowledge_scopes_tapi;
