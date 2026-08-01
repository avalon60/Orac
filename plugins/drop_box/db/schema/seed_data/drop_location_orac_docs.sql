--liquibase formatted sql
-- Author: clive
-- Date: 26-Jul-2026
-- Description: Seeds the canonical Orac documentation drop location.

--changeset clive:seed_orac_dropbox_drop_location_orac_docs context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:RAG_USAGE_SCOPE_ELIGIBLE select orac_plugin.knowledge_scope_validation_api.scope_status('PROJECT', 'ORAC_CORE') from dual;
-- __author__: clive
-- __date__: 2026-07-26
-- __description__: seed the enabled recursive Markdown adapter for the canonical Orac documentation project

merge into orac_dropbox.drop_location dst
using (
  select 'ORAC_DOCS' location_code,
         'Orac Docs' display_name,
         '$' || '{ORAC_HOME}/docs' path,
         'project' target_scope_type,
         'ORAC_CORE' target_scope_key,
         'raw_reference' processing_profile,
         '*.tmp,*.part,*.partial,*.crdownload,.~*,~$*,.DS_Store,pending_work/**,backlog/**' ignore_patterns
    from dual
) src
on (dst.location_code = src.location_code)
when matched then
  update set
    dst.display_name             = src.display_name,
    dst.path                     = src.path,
    dst.enabled_yn               = 'Y',
    dst.target_scope_type        = src.target_scope_type,
    dst.target_scope_key         = src.target_scope_key,
    dst.processing_profile       = src.processing_profile,
    dst.processing_instruction   = null,
    dst.allowed_extensions       = 'md',
    dst.ignore_patterns          = src.ignore_patterns,
    dst.recursive_yn             = 'Y',
    dst.move_processed_yn        = 'N',
    dst.processed_path           = null,
    dst.failed_path              = null,
    dst.max_file_size_mb         = 10,
    dst.stability_seconds        = 10,
    dst.classification_tags_json = to_clob('["raw_reference"]')
when not matched then
  insert (
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
    classification_tags_json
  ) values (
    src.location_code,
    src.display_name,
    src.path,
    'Y',
    src.target_scope_type,
    src.target_scope_key,
    src.processing_profile,
    null,
    'md',
    src.ignore_patterns,
    'Y',
    'N',
    null,
    null,
    10,
    10,
    to_clob('["raw_reference"]')
  );

update orac_dropbox.drop_job job
   set effective_scope_type = 'project',
       effective_scope_key  = 'ORAC_CORE'
 where job.drop_location_id = (
         select location.drop_location_id
           from orac_dropbox.drop_location location
          where location.location_code = 'ORAC_DOCS'
       )
   and job.knowledge_ingestion_request_id is null
   and job.status_code in (
         'queued',
         'processing',
         'deferred_prerequisite',
         'conversion_retry_wait'
       )
   and job.effective_scope_type = 'plugin'
   and job.effective_scope_key = 'drop_box';

--rollback select 1 from dual;
