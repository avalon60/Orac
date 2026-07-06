--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_processing_profile_runtime_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: active processing profile definitions for future ingestion workers

create or replace view orac_dropbox.drop_processing_profile_runtime_v as
select profile_code,
       display_name,
       description,
       default_instruction,
       sort_order
  from orac_dropbox.drop_processing_profile
 where active_yn = 'Y';

--rollback drop view orac_dropbox.drop_processing_profile_runtime_v;
