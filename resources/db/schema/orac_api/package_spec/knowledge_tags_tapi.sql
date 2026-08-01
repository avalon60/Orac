--liquibase formatted sql

--changeset clive:create_package_spec_orac_api_knowledge_tags_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
create or replace package orac_api.knowledge_tags_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.knowledge_tags_v%rowtype
  );

  procedure upd(
    p_knowledge_tag_id in     orac_api.knowledge_tags_v.knowledge_tag_id%type,
    p_row              in out orac_api.knowledge_tags_v%rowtype
  );
end knowledge_tags_tapi;
/
--rollback drop package orac_api.knowledge_tags_tapi;
