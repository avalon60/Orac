--liquibase formatted sql

--changeset clive:create_knowledge_tag_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_tag_lov_v as
select return_value,
       display_value,
       description,
       display_sequence sort_order
  from orac_code.doc_class_lov_v;
--rollback drop view orac_code.knowledge_tag_lov_v;
