--liquibase formatted sql

--changeset clive:create_view_orac_code_doc_class_lov_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: active document-classification list of values for new assignments

create or replace force view orac_code.doc_class_lov_v as
select doc_class_code return_value
     , display_value
     , description
     , display_sequence
     , icon
     , color
  from orac_code.doc_class_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';

--rollback drop view orac_code.doc_class_lov_v;
