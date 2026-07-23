-- Author: Clive Bostock
-- Date: 19-Jul-2026
-- Purpose: Assert that every Drop Box job is counted in exactly one lifecycle bucket.
-- Usage: sql -name <apex-connection> @plugins/drop_box/db/acceptance/drop_box_lifecycle_rollup.sql

whenever sqlerror exit failure rollback
set serveroutput on size unlimited

declare
  l_location_count number;
  l_mismatch_count number;
begin
  with job_lifecycle as (
    select job.drop_location_id,
           job.drop_job_id,
           case
             when job.status_code in (
                    'skipped_duplicate',
                    'skipped_disallowed_type',
                    'skipped_too_large'
                  )
             then 'SKIPPED'
             when job.status_code in ('failed', 'quarantined')
             then 'FAILED_ATTENTION'
             when job.status_code in ('queued', 'processing')
             then 'AWAITING_HANDOFF'
             when job.knowledge_ingestion_request_id is null
               or core.ingestion_request_id is null
             then 'FAILED_ATTENTION'
             when core.searchable_yn = 'Y'
             then 'SEARCHABLE'
             when core.status_code in ('QUEUED', 'PROCESSING', 'RETRY_WAIT')
             then 'CORE_IN_PROGRESS'
             else 'FAILED_ATTENTION'
           end lifecycle_bucket
      from orac_dropbox.drop_job_admin_v job
      left join orac_code.knowledge_ingestion_requests_v core
        on core.ingestion_request_id = job.knowledge_ingestion_request_id
  ),
  job_rollup as (
    select loc.drop_location_id,
           count(distinct job.drop_job_id) total_job_count,
           count(distinct case
             when job.lifecycle_bucket = 'AWAITING_HANDOFF' then job.drop_job_id
           end) awaiting_handoff_count,
           count(distinct case
             when job.lifecycle_bucket = 'CORE_IN_PROGRESS' then job.drop_job_id
           end) core_in_progress_count,
           count(distinct case
             when job.lifecycle_bucket = 'SEARCHABLE' then job.drop_job_id
           end) searchable_count,
           count(distinct case
             when job.lifecycle_bucket = 'FAILED_ATTENTION' then job.drop_job_id
           end) failed_attention_count,
           count(distinct case
             when job.lifecycle_bucket = 'SKIPPED' then job.drop_job_id
           end) skipped_count
      from orac_dropbox.drop_location_summary_admin_v loc
      left join job_lifecycle job
        on job.drop_location_id = loc.drop_location_id
     group by loc.drop_location_id
  )
  select count(*),
         count(case
           when total_job_count <>
                awaiting_handoff_count
                + core_in_progress_count
                + searchable_count
                + failed_attention_count
                + skipped_count
           then 1
         end)
    into l_location_count,
         l_mismatch_count
    from job_rollup;

  if l_mismatch_count <> 0
  then
    raise_application_error(
      -20000,
      'Drop Box lifecycle bucket totals do not equal total job counts.'
    );
  end if;

  dbms_output.put_line(
    'DROP_BOX_LIFECYCLE_ROLLUP_OK locations=' || to_char(l_location_count)
  );
end;
/

exit
