--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_location_admin_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: admin projection of drop-box location configuration

create or replace view orac_dropbox.drop_location_admin_v as
select drop_location_id,
       location_code,
       display_name,
       path,
       enabled_yn,
       target_scope_type,
       target_scope_key,
       processing_profile,
       processing_instruction,
       allowed_extensions,
       ignore_patterns,
       recursive_yn,
       move_processed_yn,
       processed_path,
       failed_path,
       max_file_size_mb,
       stability_seconds,
       created_on,
       created_by,
       updated_on,
       updated_by,
       row_version
  from orac_dropbox.drop_location;

--rollback drop view orac_dropbox.drop_location_admin_v;
