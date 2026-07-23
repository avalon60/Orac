--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_location_summary_admin_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: admin summary projection of drop-box locations with job activity counts
-- orac-expected-columns: total_job_count, example_type

create or replace view orac_dropbox.drop_location_summary_admin_v as
select loc.drop_location_id,
       loc.location_code,
       loc.display_name,
       loc.path,
       loc.enabled_yn,
       case loc.enabled_yn
         when 'Y' then 'Enabled'
         else 'Disabled'
       end enabled_label,
       loc.target_scope_type,
       loc.target_scope_key,
       loc.processing_profile profile_code,
       loc.stability_seconds stable_seconds,
       loc.row_version,
       case loc.enabled_yn
         when 'Y' then 'N'
         else 'Y'
       end next_enabled_yn,
       case loc.enabled_yn
         when 'Y' then 'Disable'
         else 'Enable'
       end toggle_label,
       case
         when loc.enabled_yn = 'N'
          and loc.path like '/tmp/orac-dropbox-examples/%'
         then 'Example'
       end example_label,
       case
         when loc.enabled_yn = 'N'
          and loc.path like '/tmp/orac-dropbox-examples/%'
          and loc.target_scope_type = 'project'
         then 'Project Example'
         when loc.enabled_yn = 'N'
          and loc.path like '/tmp/orac-dropbox-examples/%'
          and loc.target_scope_type = 'plugin'
         then 'Plugin Example'
       end example_type,
       count(job.drop_job_id) job_count,
       count(job.drop_job_id) total_job_count,
       sum(
         case
           when job.detected_on >= systimestamp - interval '7' day then 1
           else 0
         end
       ) recent_job_count,
       max(coalesce(job.completed_on, job.stable_on, job.detected_on)) last_processed_on
  from orac_dropbox.drop_location loc
  left join orac_dropbox.drop_job job
    on job.drop_location_id = loc.drop_location_id
 group by loc.drop_location_id,
          loc.location_code,
          loc.display_name,
          loc.path,
          loc.enabled_yn,
          loc.target_scope_type,
          loc.target_scope_key,
          loc.processing_profile,
          loc.stability_seconds,
          loc.row_version;

--rollback drop view orac_dropbox.drop_location_summary_admin_v;
