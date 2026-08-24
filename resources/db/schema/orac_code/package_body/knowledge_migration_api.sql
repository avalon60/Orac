--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-13
-- Description: Implements bounded and resumable legacy knowledge migration.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_package_body_orac_code_knowledge_migration_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.knowledge_migration_api
as
  c_max_page_size constant pls_integer := 1000;

  function bounded_limit(
    p_limit in number
  ) return pls_integer
  is
  begin
    if p_limit is null or p_limit < 1 or p_limit > c_max_page_size
    then
      raise_application_error(-20530, 'Migration page size must be between 1 and 1000.');
    end if;
    return trunc(p_limit);
  end bounded_limit;

  procedure add_event(
    p_document_version_id in number,
    p_event_type          in varchar2,
    p_event_message       in varchar2
  )
  is
  begin
    insert into orac_api.knowledge_ingestion_events_v (
      ingestion_request_id,
      event_type,
      event_message
    )
    select ingestion_request_id,
           p_event_type,
           to_clob(p_event_message)
      from orac_api.knowledge_ingestion_requests_v
     where document_version_id = p_document_version_id;
  end add_event;

  procedure open_backfill_candidates(
    p_candidates          out sys_refcursor,
    p_after_extraction_id in number default null,
    p_limit               in number default 100
  )
  is
    l_limit pls_integer := bounded_limit(p_limit);
  begin
    open p_candidates for
      select ext.extraction_id,
             ext.document_version_id,
             ext.extractor_code,
             ext.extractor_version,
             ext.output_mime_type,
             ext.text_sha256,
             ext.extracted_text,
             (
               select count(*)
                 from orac_api.knowledge_artefacts_v art
                where art.extraction_id = ext.extraction_id
             ) artefact_count,
             (
               select max(artset.complete_yn)
                 from orac_code.knowledge_artefact_sets_v artset
                where artset.extraction_id = ext.extraction_id
             ) artefact_set_complete_yn,
             (
               select max(art.artefact_id)
                 from orac_api.knowledge_artefacts_v art
                where art.extraction_id = ext.extraction_id
                  and art.artefact_role_code = 'PRIMARY'
             ) primary_artefact_id,
             (
               select max(art.content_sha256)
                 from orac_api.knowledge_artefacts_v art
                where art.extraction_id = ext.extraction_id
                  and art.artefact_role_code = 'PRIMARY'
             ) primary_content_sha256,
             (
               select max(art.storage_key)
                 from orac_api.knowledge_artefacts_v art
                where art.extraction_id = ext.extraction_id
                  and art.artefact_role_code = 'PRIMARY'
             ) primary_storage_key,
             (
               select max(art.byte_size)
                 from orac_api.knowledge_artefacts_v art
                where art.extraction_id = ext.extraction_id
                  and art.artefact_role_code = 'PRIMARY'
             ) primary_byte_size,
             (
               select count(*)
                 from orac_api.knowledge_chunk_sets_v chs
                where chs.extraction_id = ext.extraction_id
                  and chs.source_artefact_id is null
             ) legacy_chunk_set_count,
             (
               select count(*)
                 from orac_api.knowledge_chunk_sets_v chs
                where chs.extraction_id = ext.extraction_id
                  and chs.source_artefact_id is not null
             ) artefact_chunk_set_count
        from orac_api.knowledge_extractions_v ext
       where ext.extraction_id > nvl(p_after_extraction_id, 0)
       order by ext.extraction_id
       fetch first l_limit rows only;
  end open_backfill_candidates;

  procedure open_raw_locator_candidates(
    p_candidates                out sys_refcursor,
    p_after_document_version_id in number default null,
    p_limit                     in number default 100
  )
  is
    l_limit pls_integer := bounded_limit(p_limit);
  begin
    open p_candidates for
      select document_version_id,
             content_sha256,
             content_uri,
             byte_size
        from orac_api.knowledge_document_versions_v
       where document_version_id > nvl(p_after_document_version_id, 0)
       order by document_version_id
       fetch first l_limit rows only;
  end open_raw_locator_candidates;

  function backfill_extraction(
    p_extraction_id   in number,
    p_output_set_json in clob
  ) return clob
  is
    l_document_version_id number;
    l_existing_count      number;
    l_primary_artefact_id number;
    l_mismatched_count    number;
    l_chunk_set_count     number;
    l_relinked_count      number;
    l_output_set          clob;
    l_result              clob;
    l_outcome             varchar2(20);
  begin
    select document_version_id
      into l_document_version_id
      from orac_api.knowledge_extractions_v
     where extraction_id = p_extraction_id
       for update;

    select count(*)
      into l_existing_count
      from orac_api.knowledge_artefacts_v
     where extraction_id = p_extraction_id;

    l_output_set := orac_code.knowledge_artefact_api.register_output_set(
      p_extraction_id   => p_extraction_id,
      p_output_set_json => p_output_set_json
    );

    select artefact_id
      into l_primary_artefact_id
      from orac_api.knowledge_artefacts_v
     where extraction_id = p_extraction_id
       and artefact_role_code = 'PRIMARY';

    select count(*),
           sum(
             case
               when source_artefact_id is not null
                and source_artefact_id <> l_primary_artefact_id
               then 1
               else 0
             end
           )
      into l_chunk_set_count, l_mismatched_count
      from orac_api.knowledge_chunk_sets_v
     where extraction_id = p_extraction_id;

    if l_chunk_set_count = 0 or l_mismatched_count > 0
    then
      raise_application_error(
        -20531,
        'Backfill requires existing chunk sets with consistent legacy lineage.'
      );
    end if;

    update orac_api.knowledge_chunk_sets_v
       set source_artefact_id = l_primary_artefact_id
     where extraction_id = p_extraction_id
       and source_artefact_id is null;
    l_relinked_count := sql%rowcount;

    l_outcome := case when l_existing_count = 0 then 'BACKFILLED' else 'REUSED' end;
    if l_existing_count = 0 or l_relinked_count > 0
    then
      add_event(
        p_document_version_id => l_document_version_id,
        p_event_type          => 'artefact_backfilled',
        p_event_message       => 'Legacy extraction registered as one managed PRIMARY artefact.'
      );
    end if;

    select json_object(
             'schema_version' value 1,
             'outcome' value l_outcome,
             'extraction_id' value p_extraction_id,
             'artefact_id' value l_primary_artefact_id,
             'relinked_chunk_set_count' value l_relinked_count
             returning clob
           )
      into l_result
      from dual;
    return l_result;
  exception
    when no_data_found then
      raise_application_error(-20532, 'Backfill extraction or PRIMARY artefact does not exist.');
  end backfill_extraction;

  function migrate_raw_locator(
    p_document_version_id in number,
    p_expected_locator    in varchar2,
    p_expected_sha256     in varchar2
  ) return clob
  is
    l_content_uri    varchar2(1000);
    l_content_sha256 varchar2(64);
    l_legacy_uri     varchar2(1000);
    l_logical_uri    varchar2(71);
    l_outcome        varchar2(20);
    l_result         clob;
  begin
    select content_uri, content_sha256
      into l_content_uri, l_content_sha256
      from orac_api.knowledge_document_versions_v
     where document_version_id = p_document_version_id
       for update;

    if p_expected_sha256 <> l_content_sha256
       or p_expected_locator <> l_content_uri
    then
      raise_application_error(-20533, 'Raw locator changed after preflight verification.');
    end if;
    l_legacy_uri := 'sha256/' || substr(l_content_sha256, 1, 2) || '/'
                    || substr(l_content_sha256, 3, 2) || '/' || l_content_sha256;
    l_logical_uri := 'sha256:' || l_content_sha256;

    if l_content_uri = l_logical_uri
    then
      l_outcome := 'REUSED';
    elsif l_content_uri = l_legacy_uri
    then
      update orac_api.knowledge_document_versions_v
         set content_uri = l_logical_uri
       where document_version_id = p_document_version_id;
      l_outcome := 'MIGRATED';
      add_event(
        p_document_version_id => p_document_version_id,
        p_event_type          => 'raw_locator_migrated',
        p_event_message       => 'Verified legacy raw locator migrated to its logical storage key.'
      );
    else
      raise_application_error(-20534, 'Raw locator is not an approved legacy shard locator.');
    end if;

    select json_object(
             'schema_version' value 1,
             'outcome' value l_outcome,
             'document_version_id' value p_document_version_id,
             'storage_key' value l_logical_uri
             returning clob
           )
      into l_result
      from dual;
    return l_result;
  exception
    when no_data_found then
      raise_application_error(-20535, 'Knowledge document version does not exist.');
  end migrate_raw_locator;
end knowledge_migration_api;
/
--rollback drop package body orac_code.knowledge_migration_api;
