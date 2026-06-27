--liquibase formatted sql
create or replace force view orac_dropbox.drop_location_runtime_v as
select drop_location_id,
       location_code,
       display_name,
       path,
       allowed_extensions,
       ignore_patterns,
       recursive_yn,
       max_file_size_mb,
       stability_seconds
  from orac_dropbox.drop_location
 where enabled_yn = 'Y';
/
