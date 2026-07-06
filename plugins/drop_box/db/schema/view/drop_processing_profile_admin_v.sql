--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_processing_profile_admin_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: admin projection of all drop-box processing profiles

create or replace view orac_dropbox.drop_processing_profile_admin_v as
select profile_code,
       display_name,
       description,
       default_instruction,
       active_yn,
       system_yn,
       sort_order,
       created_at,
       updated_at
  from orac_dropbox.drop_processing_profile;

--rollback drop view orac_dropbox.drop_processing_profile_admin_v;
