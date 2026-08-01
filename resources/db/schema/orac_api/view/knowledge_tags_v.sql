--liquibase formatted sql

--changeset clive:create_orac_api_knowledge_tags_views context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_tags_v as
select knowledge_tag_id, tag_code, display_name, description, active_yn,
       system_yn, sort_order, created_by, created_on, updated_by, updated_on,
       row_version
  from orac_core.knowledge_tags;

--rollback drop view orac_api.knowledge_tags_v;
