--liquibase formatted sql
create or replace force view orac_dropbox.drop_location_runtime_v as
select loc.drop_location_id,
       loc.location_code,
       loc.display_name,
       loc.path,
       loc.allowed_extensions,
       loc.ignore_patterns,
       loc.recursive_yn,
       loc.max_file_size_mb,
       loc.stability_seconds
  from orac_dropbox.drop_location loc
  join orac_dropbox.drop_processing_profile prf
    on prf.profile_code = loc.processing_profile
   and prf.active_yn = 'Y'
 where loc.enabled_yn = 'Y';
/
