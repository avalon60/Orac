--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_source_objects_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_source_objects_v as
select source_object_id,
       source_type,
       source_reference,
       parent_source_reference,
       target_scope_type,
       target_scope_key,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_source_objects;
--rollback drop view orac_api.knowledge_source_objects_v;
