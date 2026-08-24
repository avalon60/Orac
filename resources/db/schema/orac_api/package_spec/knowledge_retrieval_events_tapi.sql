--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Defines insert-only retrieval audit access.

--changeset clive:create_package_spec_orac_api_knowledge_retrieval_events_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.knowledge_retrieval_events_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.knowledge_retrieval_events_v%rowtype
  );
end knowledge_retrieval_events_tapi;
/
--rollback drop package orac_api.knowledge_retrieval_events_tapi;
