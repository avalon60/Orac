--liquibase formatted sql

--changeset clive:create_knowledge_tag_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_tag_lov_v as
select tag_code return_value,
       display_name display_value,
       description,
       sort_order
  from orac_api.knowledge_tags_v
 where active_yn = 'Y'
 order by sort_order, tag_code;
--rollback drop view orac_code.knowledge_tag_lov_v;
